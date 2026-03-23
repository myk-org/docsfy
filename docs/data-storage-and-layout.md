# Data Storage and Layout

docsfy stores persistent server-side data in a single base directory controlled by `DATA_DIR`. By default, that directory is `/data`, so the two most important things on disk are `/data/docsfy.db` and `/data/projects/`. If those paths do not exist yet, docsfy creates them automatically at startup.

```13:17:.env.example
# Data directory for database and generated docs
DATA_DIR=/data

# Cookie security (set to false for local HTTP development)
SECURE_COOKIES=true
```

> **Note:** In the included Docker setup, `./data` on the host is bind-mounted to `/data` in the container, so generated docs and the SQLite database survive container restarts.

| Location | What it stores |
| --- | --- |
| `/data/docsfy.db` | SQLite data for projects, users, sharing rules, and browser sessions |
| `/data/projects/<owner>/<project>/<branch>/<provider>/<model>/` | One generated docs variant |
| `.../site/` | The rendered docs site that docsfy serves under `/docs/...` |
| `.../cache/pages/` | Per-page markdown cache used for incremental generation |
| `~/.config/docsfy/config.toml` | Local CLI profiles and saved credentials |

## SQLite database

docsfy uses SQLite, not a separate database server. The database is created automatically at startup, and the most important table is `projects`, where each row represents one variant identified by project name, branch, AI provider, AI model, and owner.

```63:80:src/docsfy/storage.py
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT NOT NULL,
                branch TEXT NOT NULL DEFAULT 'main',
                ai_provider TEXT NOT NULL DEFAULT '',
                ai_model TEXT NOT NULL DEFAULT '',
                owner TEXT NOT NULL DEFAULT '',
                repo_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'generating',
                current_stage TEXT,
                last_commit_sha TEXT,
                last_generated TEXT,
                page_count INTEGER DEFAULT 0,
                error_message TEXT,
                plan_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (name, branch, ai_provider, ai_model, owner)
            )
```

The rest of the database is straightforward:

- `projects` stores the source repository URL, generation status, current stage, last commit SHA, page count, error text, timestamps, and the serialized documentation plan in `plan_json`.
- `users` stores DB-backed users, their roles, and hashed API keys.
- `project_access` stores sharing rules by project name and owner. Sharing is project-wide for that owner; it does not split access by branch, provider, or model.
- `sessions` stores hashed browser session tokens and their expiration times. Browser sessions last 8 hours by default.

A few storage details are worth knowing:

- Raw user API keys are not stored in SQLite. The database stores `api_key_hash`.
- Browser session tokens are also hashed before being written to the `sessions` table.
- The admin credential comes from the `ADMIN_KEY` environment variable, not from the database.

> **Note:** Startup also runs migrations automatically. If the server restarts while a docs job is still `generating`, docsfy changes that row to `error` so stale jobs do not look permanently in progress.

## Variant directories under `/data/projects`

Each generated variant gets its own directory. The path is shaped by five values:

- owner
- project name
- branch
- AI provider
- AI model

A test in the codebase shows the exact layout that docsfy expects:

```848:854:tests/test_storage.py
result = get_project_dir(
    "my-repo", ai_provider="claude", ai_model="opus", owner="user", branch="main"
)
assert result == PROJECTS_DIR / "user" / "my-repo" / "main" / "claude" / "opus"
```

In a default deployment, that variant lives at:

`/data/projects/user/my-repo/main/claude/opus/`

At that variant root, docsfy stores:

- `plan.json`, a pretty-printed copy of the last generated plan
- `site/`, the rendered documentation site
- `cache/pages/`, the markdown cache for individual pages

docsfy also stores the same plan in SQLite as `projects.plan_json`, so the database record and the on-disk artifact directory stay aligned.

> **Note:** If you ever see `_default` in place of an owner name, that is docsfy’s on-disk fallback for an empty owner value. In normal authenticated generation flows, the owner is the logged-in username, so `_default` is mostly relevant when inspecting older or special-case data.

### What `site/` contains

The `site/` directory is the part docsfy actually serves and downloads. It contains the rendered HTML, markdown copies of each page, static assets, search data, and the generated `llms.txt` files.

```464:551:src/docsfy/renderer.py
def render_site(plan: dict[str, Any], pages: dict[str, str], output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Prevent GitHub Pages from running Jekyll
    (output_dir / ".nojekyll").touch()

    # ... static asset copy and navigation setup omitted ...

    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    (output_dir / f"{slug}.html").write_text(page_html, encoding="utf-8")
    (output_dir / f"{slug}.md").write_text(md_content, encoding="utf-8")
    (output_dir / "search-index.json").write_text(
        json.dumps(search_index), encoding="utf-8"
    )
    (output_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")
    (output_dir / "llms-full.txt").write_text(llms_full_txt, encoding="utf-8")
```

A few practical consequences follow from this:

- Variant downloads package the `site/` directory, not the cache or `plan.json`.
- Each page exists twice inside `site/`: as rendered HTML and as a `.md` source copy.
- `search-index.json`, `llms.txt`, and `llms-full.txt` are generated outputs, not hand-maintained files.

> **Warning:** Do not treat `site/` as a hand-edited working directory. docsfy deletes and recreates it on each render, so manual changes there will be overwritten the next time that variant is generated.

## Cache locations and behavior

docsfy’s persistent cache lives inside the variant directory, not in a separate global cache. Each page is cached as markdown under `cache/pages/`, using the page slug as the filename.

```270:323:src/docsfy/generator.py
    # Validate slug to prevent path traversal
    if is_unsafe_slug(slug):
        msg = f"Invalid page slug: '{slug}'"
        raise ValueError(msg)

    cache_file = cache_dir / f"{slug}.md"
    if use_cache and cache_file.exists():
        logger.debug(f"[{_label}] Using cached page: {slug}")
        return cache_file.read_text(encoding="utf-8")

    # ... generation omitted ...

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(output, encoding="utf-8")
    logger.info(f"[{_label}] Generated page: {slug} ({len(output)} chars)")
```

In practice, the cache behaves like this:

- A cached page lives at `.../cache/pages/<slug>.md`.
- A normal incremental update deletes only the page cache files that need regeneration and reuses the rest.
- A full regeneration clears the target variant’s page cache before rebuilding.
- If you generate a new provider/model variant from the same branch and commit, docsfy can reuse copied artifacts from the existing ready variant. That can include cached pages and, on same-commit replacements, the rendered `site/` as well.
- `force=true` tells docsfy to regenerate the target variant from scratch instead of relying on that artifact reuse.

> **Tip:** If you are debugging stale content, inspect the exact variant directory you generated. There is no single shared cache directory for the whole server.

## How branch, provider, and model shape the path

Branch, provider, and model are not just labels in the UI. They are part of the database key and the directory layout, which is why different variants can exist side by side.

Branch names are validated before generation:

```28:47:src/docsfy/models.py
    branch: str = Field(
        default=DEFAULT_BRANCH, description="Git branch to generate docs from"
    )

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        if "/" in v:
            msg = (
                f"Invalid branch name: '{v}'. Branch names cannot contain slashes "
                "— use hyphens instead (e.g., release-1.x)."
            )
            raise ValueError(msg)
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", v):
            msg = f"Invalid branch name: '{v}'"
            raise ValueError(msg)
        if ".." in v:
            msg = f"Invalid branch name: '{v}'"
            raise ValueError(msg)
        return v
```

That gives you predictable, separate paths such as:

- `/data/projects/alice/my-repo/main/claude/opus/`
- `/data/projects/alice/my-repo/v2.0/claude/opus/`
- `/data/projects/alice/my-repo/main/gemini/gemini-2.5-pro/`

Branch defaults to `main`, so if you omit it, docsfy uses `main` in both the database and the path. Provider and model are also required to build the on-disk path, and docsfy rejects unsafe path segments such as values containing `/`, `\`, `..`, or leading dots.

> **Warning:** Use branch names like `release-1.x`, not `release/1.x`. A slash is rejected by validation and would also break the directory layout.

## What is not stored under `/data`

Not every working file becomes persistent server data.

- When you generate from a remote `repo_url`, docsfy does a shallow temporary clone and discards it after the run finishes.
- When you generate from a local `repo_path`, docsfy uses that repository in place. It does not copy the repo into `DATA_DIR` automatically.
- If the server runs in Docker and you want to use `repo_path`, that path must exist inside the container. With the included compose file, the easiest option is to place or bind-mount the repository somewhere under the host `./data` directory so it appears under `/data/...` in the container.

The `docsfy` CLI also stores its own local configuration outside the server data directory. Connection profiles live at `~/.config/docsfy/config.toml`, and the CLI creates that file with owner-only permissions because it contains saved credentials.

> **Tip:** For local development, both `data/` and `.dev/data/` are git-ignored. For backups, the simplest rule is to preserve the whole `DATA_DIR`, and if you use the CLI on other machines, back up `~/.config/docsfy/config.toml` there as well.
