# Viewing, Downloading, and Hosting Docs

Once a variant reaches `ready`, you can open it through docsfy, download it as a `tar.gz`, or publish the generated static site somewhere else.

In docsfy, a "variant" is one generated docs build for a specific project, branch, provider, and model.

## Open Docs

Use an explicit variant URL when you want one exact build:

- `/docs/<project>/<branch>/<provider>/<model>/`
- `/docs/<project>/<branch>/<provider>/<model>/index.html`

Use the latest route when you want "whatever is newest and ready" for a project:

- `/docs/<project>/`
- `/docs/<project>/index.html`

The repository exercises both URL shapes directly:

```127:149:tests/test_integration.py
# Check docs are served via variant-specific route
response = await client.get("/docs/test-repo/main/claude/opus/index.html")
assert response.status_code == 200
assert "test-repo" in response.text

response = await client.get("/docs/test-repo/main/claude/opus/introduction.html")
assert response.status_code == 200
assert "Welcome!" in response.text

# Check docs are served via latest-variant route
response = await client.get("/docs/test-repo/index.html")
assert response.status_code == 200
assert "test-repo" in response.text

# Download via variant-specific route
response = await client.get("/api/projects/test-repo/main/claude/opus/download")
assert response.status_code == 200
assert response.headers["content-type"] == "application/gzip"

# Download via latest-variant route
response = await client.get("/api/projects/test-repo/download")
assert response.status_code == 200
assert response.headers["content-type"] == "application/gzip"
```

If you open docs from the dashboard, the app builds an explicit variant URL and includes `?owner=` when it needs to disambiguate the owner:

```366:367:frontend/src/components/shared/VariantDetail.tsx
const docsUrl = `/docs/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/?owner=${encodeURIComponent(project.owner)}`
const downloadUrl = `/api/projects/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/download?owner=${encodeURIComponent(project.owner)}`
```

If you're an admin or working with shared docs, keep that `?owner=` query string when the UI gives it to you. It helps docsfy resolve the correct variant when the same project name exists under multiple owners.

Any generated file under the docs base URL is available the same way. That includes page files like `introduction.html`, text outputs like `llms.txt`, and support files under `assets/`.

> **Tip:** Use the latest route for a bookmark like "current docs", and the explicit route for review links, release docs, or anything else that must stay pinned to one build.

> **Warning:** The latest route follows the newest `ready` variant. If you regenerate docs with a different branch, provider, or model, the same latest URL can point to a different build.

> **Note:** `/docs/*` requires authentication. Browser requests for HTML are redirected to `/login` when you are not signed in. API-style requests return `401`, and users without access receive `404`.

> **Note:** The branch is part of the URL path. docsfy accepts names like `main`, `dev`, or `release-1.x`, but not names with `/` such as `release/1.x`.

## Download Tarballs

docsfy exposes two download endpoints:

- `/api/projects/<project>/<branch>/<provider>/<model>/download` for one exact variant
- `/api/projects/<project>/download` for the latest ready variant

Downloads only work for `ready` variants. The response is a gzip-compressed tar archive.

The archive filename is:

- explicit variant: `<project>-<branch>-<provider>-<model>-docs.tar.gz`
- latest route: `<project>-docs.tar.gz`

A real test-plan example downloads a variant archive, extracts it, and inspects the generated files:

```78:84:test-plans/e2e-08-cross-model-updates.md
curl -s -L -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/for-testing-only/main/$BASELINE_PROVIDER/$BASELINE_MODEL/download" \
  -o "$CROSS_PROVIDER_ROOT/baseline.tar.gz"
mkdir -p "$CROSS_PROVIDER_ROOT/baseline"
tar -xzf "$CROSS_PROVIDER_ROOT/baseline.tar.gz" --strip-components=1 -C "$CROSS_PROVIDER_ROOT/baseline"
ls "$CROSS_PROVIDER_ROOT/baseline"
```

The archive contains a top-level directory. If you want the files placed directly into an existing target directory, extract it with `tar --strip-components=1` as shown above.

If you prefer the CLI, set up a server profile with `docsfy config init` or create `~/.config/docsfy/config.toml` like this:

```7:25:config.toml.example
[default]
server = "dev"

[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<your-dev-key>"

[servers.prod]
url = "https://docsfy.example.com"
username = "admin"
password = "<your-prod-key>"

[servers.staging]
url = "https://staging.docsfy.example.com"
username = "deployer"
password = "<your-staging-key>"
```

Then use:

- `docsfy download my-repo` to save the latest ready archive in your current directory
- `docsfy download my-repo --branch main --provider cursor --model gpt-5` to save one explicit variant
- `docsfy download my-repo --branch main --provider cursor --model gpt-5 --output ./docs` to download and extract in one step
- `docsfy download ... --owner <username>` when you are an admin targeting another owner's variant

> **Note:** For explicit CLI downloads, `--branch`, `--provider`, and `--model` are all-or-nothing. If you specify one, you must specify all three.

## Host The Static Site

docsfy also writes the rendered site to disk. The path is `${DATA_DIR}/projects/<owner>/<project>/<branch>/<provider>/<model>/site`.

By default `DATA_DIR` is `/data`. In the provided Compose setup, that directory is persisted from the host:

```1:22:docker-compose.yaml
services:
  docsfy:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
      # Uncomment for development (DEV_MODE=true)
      # - "5173:5173"
    volumes:
      - ./data:/data
      # Uncomment for development (hot reload)
      # - ./frontend:/app/frontend
    env_file:
      - .env
```

With that setup, a typical host-side path looks like `./data/projects/<owner>/<project>/<branch>/<provider>/<model>/site`.

The renderer writes a self-contained static site. Here is the relevant output from the actual render step:

```471:551:src/docsfy/renderer.py
# Prevent GitHub Pages from running Jekyll
(output_dir / ".nojekyll").touch()

# ... static files are copied into assets/

index_html = render_index(
    project_name, tagline, filtered_navigation, repo_url=repo_url
)
(output_dir / "index.html").write_text(index_html, encoding="utf-8")

# ... one HTML page and one Markdown page per slug

(output_dir / f"{slug}.html").write_text(page_html, encoding="utf-8")
(output_dir / f"{slug}.md").write_text(md_content, encoding="utf-8")

search_index = _build_search_index(valid_pages, plan)
(output_dir / "search-index.json").write_text(
    json.dumps(search_index), encoding="utf-8"
)

(output_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")
(output_dir / "llms-full.txt").write_text(llms_full_txt, encoding="utf-8")
```

In practice, keep these files together when you publish:

- `index.html`
- every generated page `.html` file
- `assets/`
- `search-index.json`
- `.nojekyll`
- `llms.txt` and `llms-full.txt`
- any generated page `.md` files if you want the Markdown copies too

You can publish the `site/` directory with any static host or web server. There is no built-in publish workflow in this repository, so publishing is simply a matter of copying or syncing that directory to your hosting platform.

Because the output is plain static HTML, CSS, and JavaScript, you can host it without the docsfy backend once generation is finished. Start at `index.html` and serve the directory as-is.

> **Tip:** GitHub Pages is a good fit for the published output because docsfy writes `.nojekyll` automatically.

> **Warning:** When you publish the `site/` directory outside docsfy, docsfy’s authentication and ownership checks no longer protect it. If the docs should stay private, enforce access control at your static host or CDN.

## Quick Reference

- Use `/docs/<project>/` for a moving "latest ready docs" link.
- Use `/docs/<project>/<branch>/<provider>/<model>/` for a stable, exact variant.
- Use `/api/projects/.../download` or `docsfy download ...` when you need an archive to inspect, diff, or publish elsewhere.
- Use the `site/` directory when you want to host the docs as a standalone static website.
