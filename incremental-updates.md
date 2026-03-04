# Incremental Updates

docsfy tracks repository state between generation runs so that subsequent requests skip unchanged content. Instead of regenerating an entire documentation site from scratch, docsfy compares commit SHAs, detects structural changes in the documentation plan, and selectively regenerates only the pages affected by new commits. This reduces both generation time and AI token usage.

## How It Works

Incremental updates operate through a layered comparison strategy. Each layer acts as a gate — if no changes are detected, docsfy skips all downstream work.

```
Generate request received
│
├── Fetch current repo HEAD SHA
├── Query SQLite for stored SHA
│
├── SHAs match?
│   └── YES → Serve cached site (zero work)
│
└── NO → Clone repo
    ├── Run AI Planner → produce new plan.json
    ├── Compare new plan.json against cached plan.json
    │
    ├── Plan structure changed?
    │   └── YES → Regenerate ALL pages
    │
    └── NO → Identify changed files between commits
        ├── For each page in plan.json:
        │   ├── Depends on changed files? → Regenerate
        │   └── No dependency? → Reuse cached markdown
        └── Render HTML from all pages
```

There are three distinct levels of optimization:

1. **SHA comparison** — the cheapest check. If the repository HEAD hasn't changed since the last generation, docsfy serves the existing static site immediately with no AI calls.

2. **Plan stability detection** — if the repository changed but the documentation structure (pages, sections, navigation) remains the same, docsfy only regenerates pages that reference modified source files.

3. **Full regeneration** — when the documentation plan itself changes (new pages added, pages removed, navigation restructured), docsfy regenerates all content to ensure consistency.

## Commit SHA Tracking

docsfy stores the last successfully generated commit SHA for each project in its SQLite database at `/data/docsfy.db`.

The projects table tracks:

| Field | Type | Purpose |
|-------|------|---------|
| `project_name` | `TEXT` | Unique project identifier |
| `repo_url` | `TEXT` | Repository URL |
| `status` | `TEXT` | `generating` / `ready` / `error` |
| `last_commit_sha` | `TEXT` | HEAD SHA at last successful generation |
| `last_generated` | `DATETIME` | Timestamp of last generation |
| `generation_history` | `TEXT` | Logs and history |

When a `POST /api/generate` request arrives for a repository that has already been generated, docsfy fetches the current HEAD SHA from the remote repository and compares it against `last_commit_sha` in the database:

```python
# Pseudocode for the SHA comparison gate
stored_sha = db.get_last_commit_sha(project_name)
current_sha = git.ls_remote(repo_url, "HEAD")

if stored_sha == current_sha:
    # No changes — serve cached site
    return cached_site_response(project_name)

# Repository has new commits — proceed with incremental update
```

> **Note:** The initial clone uses `git clone --depth 1` for speed, fetching only the latest commit. This is sufficient because docsfy relies on the AI to analyze the current state of the repository, not the full commit history.

## Cached Artifacts

docsfy maintains a layered cache on the filesystem that enables selective regeneration:

```
/data/projects/{project-name}/
├── plan.json              # Documentation structure from AI Planner
├── cache/
│   └── pages/
│       ├── overview.md        # Cached AI-generated markdown
│       ├── getting-started.md
│       ├── api-reference.md
│       └── ...
└── site/                  # Final rendered HTML
    ├── index.html
    ├── overview.html
    ├── getting-started.html
    ├── assets/
    │   ├── style.css
    │   ├── search.js
    │   ├── theme-toggle.js
    │   └── highlight.js
    └── search-index.json
```

Each layer serves a specific role in incremental updates:

- **`plan.json`** — the previous documentation plan. Compared against the newly generated plan to detect structural changes.
- **`cache/pages/*.md`** — individual markdown files produced by the AI Content Generator. Pages that are unaffected by repository changes are served directly from this cache, avoiding redundant AI calls.
- **`site/`** — the final HTML output. Always regenerated from markdown and `plan.json` during the HTML Renderer stage (Stage 4), since rendering is fast and deterministic.

## The Incremental Update Pipeline

When docsfy detects a new commit SHA, it re-runs the generation pipeline with incremental logic injected into Stages 2 and 3.

### Stage 1: Clone Repository

The repository is shallow-cloned to a temporary directory, identical to a fresh generation:

```bash
git clone --depth 1 <repo_url> <temp_dir>
```

The temporary directory is deleted after generation completes.

### Stage 2: AI Planner (Change Detection)

The AI Planner runs against the newly cloned repository to produce a fresh `plan.json`. This new plan is then compared against the cached `plan.json` from the previous generation.

```python
old_plan = load_json(f"/data/projects/{project_name}/plan.json")
new_plan = run_ai_planner(cloned_repo_path)

if old_plan == new_plan:
    # Structure unchanged — selective regeneration possible
    affected_pages = identify_affected_pages(old_commit_sha, new_commit_sha)
else:
    # Structure changed — must regenerate everything
    affected_pages = all_pages_in(new_plan)
    save_json(f"/data/projects/{project_name}/plan.json", new_plan)
```

> **Tip:** The AI Planner always runs during an incremental update, even if only a single file changed. This ensures docsfy detects cases where a small code change warrants a new documentation page or a restructured navigation hierarchy.

### Stage 3: AI Content Generator (Selective Regeneration)

This is where the primary savings occur. Only pages in the `affected_pages` set are sent to the AI for regeneration. All other pages are served from the markdown cache:

```python
for page in plan["pages"]:
    if page in affected_pages:
        # Run AI CLI to regenerate this page
        markdown = await run_ai_generator(cloned_repo_path, page)
        save_to_cache(f"/data/projects/{project_name}/cache/pages/{page}.md", markdown)
    else:
        # Reuse existing cached markdown
        markdown = load_from_cache(f"/data/projects/{project_name}/cache/pages/{page}.md")
```

Pages are generated concurrently using async execution with semaphore-limited concurrency, so even when multiple pages need regeneration, they run in parallel:

```python
# Concurrent generation with bounded parallelism
async with asyncio.Semaphore(max_concurrent):
    results = await asyncio.gather(*[
        generate_page(page) for page in affected_pages
    ])
```

### Stage 4: HTML Renderer

The HTML Renderer always runs in full. It converts all markdown pages (both cached and freshly generated) into the final static HTML site using Jinja2 templates. Since this stage is purely deterministic and fast (no AI calls), there is no need for selective rendering.

## AI Usage Savings

The incremental update system dramatically reduces AI token consumption on subsequent runs:

| Scenario | AI Planner Calls | AI Content Generator Calls | Savings |
|----------|-----------------|---------------------------|---------|
| No changes (SHA match) | 0 | 0 | 100% |
| Code changes, plan unchanged, 2 of 10 pages affected | 1 | 2 | ~80% |
| Code changes, plan structure changed | 1 | All pages | 0% (full regen) |
| First generation | 1 | All pages | N/A (baseline) |

> **Note:** The AI Planner call is relatively inexpensive compared to content generation calls. The Content Generator is where the bulk of AI usage occurs, since each page requires the AI to explore and analyze relevant portions of the codebase.

## API Behavior

Incremental updates are triggered automatically. When you submit a `POST /api/generate` request for a repository that has already been generated, docsfy performs the SHA comparison and runs the incremental pipeline if changes are detected:

```bash
# First generation — full pipeline
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repo"}'

# Subsequent call — incremental update (automatic)
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repo"}'
```

You can inspect the current commit SHA and generation status for any project:

```bash
# Check project details including last commit SHA
curl http://localhost:8000/api/projects/repo
```

The response includes `last_commit_sha` and `last_generated` fields, allowing you to verify which commit the current documentation reflects.

To force a full regeneration, delete the project and regenerate:

```bash
# Delete cached project (clears all state)
curl -X DELETE http://localhost:8000/api/projects/repo

# Regenerate from scratch
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repo"}'
```

> **Warning:** Deleting a project removes all cached artifacts including `plan.json`, cached markdown, and the rendered site. The next generation will run the full pipeline with no incremental benefits.

## Storage Configuration

All state required for incremental updates is stored under the `/data` volume:

```yaml
# docker-compose.yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data    # Persists SQLite DB and project caches
```

The `./data` volume must be persisted between container restarts. Without it, docsfy loses its SQLite database and cached artifacts, forcing a full regeneration for every project on the next request.

The storage layout:

```
/data/
├── docsfy.db                          # SQLite: commit SHAs, project metadata
└── projects/
    ├── my-project/
    │   ├── plan.json                  # Cached documentation plan
    │   ├── cache/pages/*.md           # Cached AI-generated markdown
    │   └── site/                      # Rendered HTML
    └── another-project/
        ├── plan.json
        ├── cache/pages/*.md
        └── site/
```

## Edge Cases

**Repository force-pushed or rebased:** Since docsfy compares HEAD SHAs, a force-push that changes the HEAD SHA triggers an incremental update even if the content is effectively the same. The AI Planner will detect that the plan is unchanged, and only affected pages (if any) will be regenerated.

**Repository deleted and recreated:** If the remote repository is deleted and recreated with a new initial commit, the SHA will differ and docsfy will run an incremental update. If the plan structure differs significantly, a full regeneration occurs.

**Multiple concurrent requests for the same project:** The project `status` field (`generating` / `ready` / `error`) prevents duplicate generation runs. While a project is in the `generating` state, subsequent requests will not trigger a new pipeline.

**AI Planner produces a different plan for identical code:** Since AI outputs are non-deterministic, the AI Planner may produce a slightly different `plan.json` even when no code changed. This would trigger a full regeneration. Plan comparison should account for semantically equivalent structures to minimize false positives.
