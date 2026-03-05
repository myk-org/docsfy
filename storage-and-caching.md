# Storage and Caching

docsfy uses a two-tier persistence strategy: a SQLite database for project metadata and the local filesystem for generated content. This separation keeps structured queries fast while allowing large markdown and HTML files to live on disk where they can be served directly.

## SQLite Database

### Location

The database file is stored at `{DATA_DIR}/docsfy.db`, where `DATA_DIR` defaults to `/data` and is configurable via environment variable:

```python
# src/docsfy/storage.py
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
```

In Docker deployments, this path lives inside the mounted volume:

```yaml
# docker-compose.yaml
volumes:
  - ./data:/data
```

### Schema

docsfy uses a single `projects` table, created automatically on application startup via `init_db()`:

```sql
CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'generating',
    last_commit_sha TEXT,
    last_generated TEXT,
    page_count INTEGER DEFAULT 0,
    error_message TEXT,
    plan_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

| Column | Type | Description |
|--------|------|-------------|
| `name` | `TEXT PRIMARY KEY` | Project identifier, derived from the repository name |
| `repo_url` | `TEXT NOT NULL` | Git clone URL or local path used as source |
| `status` | `TEXT NOT NULL` | Current state: `generating`, `ready`, or `error` |
| `last_commit_sha` | `TEXT` | Git SHA at which documentation was last generated |
| `last_generated` | `TEXT` | Timestamp of last successful generation |
| `page_count` | `INTEGER` | Number of documentation pages produced |
| `error_message` | `TEXT` | Error details when `status = 'error'` |
| `plan_json` | `TEXT` | Serialized JSON of the documentation plan |
| `created_at` | `TIMESTAMP` | Record creation time |
| `updated_at` | `TIMESTAMP` | Last modification time |

### Status Lifecycle

The `status` column is validated against a fixed set of allowed values:

```python
VALID_STATUSES = frozenset({"generating", "ready", "error"})
```

A project progresses through these states during generation:

```
generating  ──►  ready
     │
     └──────►  error
```

- **`generating`** — Set when a generation request is accepted. Updated incrementally as pages are produced (`page_count` increases).
- **`ready`** — Set once all pages are generated and the HTML site is rendered.
- **`error`** — Set if any unrecoverable failure occurs. The `error_message` column captures the details.

### Database Operations

All database access is asynchronous via `aiosqlite`. Every query uses parameterized placeholders to prevent SQL injection:

```python
# src/docsfy/storage.py
async def save_project(name: str, repo_url: str, status: str = "generating") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO projects (name, repo_url, status, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(name) DO UPDATE SET
               repo_url = excluded.repo_url,
               status = excluded.status,
               error_message = NULL,
               updated_at = CURRENT_TIMESTAMP""",
            (name, repo_url, status),
        )
        await db.commit()
```

The `save_project` function uses `INSERT ... ON CONFLICT` (upsert) so that re-generating an existing project updates the record rather than failing.

The `update_project_status` function builds its `SET` clause dynamically, but only from hardcoded column names — never from user input:

```python
fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
values: list[str | int | None] = [status]
if last_commit_sha is not None:
    fields.append("last_commit_sha = ?")
    values.append(last_commit_sha)
# ... additional optional fields
```

> **Note:** The `plan_json` column is updated early in the generation pipeline so that API consumers can inspect the documentation structure while pages are still being generated.

## Filesystem Layout

Each project gets its own directory tree under `/data/projects/`. The three-level structure separates the documentation plan, cached intermediate files, and the final rendered site:

```
/data/
├── docsfy.db                          # SQLite database
└── projects/
    └── {project-name}/
        ├── plan.json                  # Documentation structure
        ├── cache/
        │   └── pages/
        │       ├── introduction.md    # Cached AI-generated markdown
        │       ├── quickstart.md
        │       ├── configuration.md
        │       └── *.md
        └── site/                      # Final rendered output
            ├── index.html             # Landing page
            ├── introduction.html      # Rendered content pages
            ├── introduction.md        # Raw markdown copies
            ├── quickstart.html
            ├── quickstart.md
            ├── assets/
            │   ├── style.css
            │   ├── search.js
            │   ├── theme.js
            │   ├── copy.js
            │   ├── callouts.js
            │   ├── codelabels.js
            │   ├── scrollspy.js
            │   └── github.js
            ├── search-index.json      # Client-side search data
            ├── llms.txt               # AI-readable page index
            └── llms-full.txt          # All pages concatenated
```

### Path Helper Functions

Three functions in `storage.py` provide consistent access to each level of the tree. All three validate the project name before constructing a path:

```python
# src/docsfy/storage.py
def get_project_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name)

def get_project_site_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "site"

def get_project_cache_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "cache" / "pages"
```

### plan.json

The documentation plan is a JSON file written to the project root after generation completes. It captures the project's structure, navigation hierarchy, and metadata:

```json
{
  "project_name": "my-library",
  "tagline": "A fast data processing library",
  "repo_url": "https://github.com/org/my-library",
  "navigation": [
    {
      "group": "Getting Started",
      "pages": [
        {
          "slug": "introduction",
          "title": "Introduction",
          "description": "Overview of the library"
        },
        {
          "slug": "quickstart",
          "title": "Quick Start",
          "description": "Get started fast"
        }
      ]
    }
  ]
}
```

This file is also stored in the database's `plan_json` column for fast API access without filesystem reads.

### site/ Directory

The renderer (`renderer.py`) produces the final HTML site by cleaning the output directory and rebuilding it from scratch:

```python
# src/docsfy/renderer.py
def render_site(plan: dict[str, Any], pages: dict[str, str], output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
```

Each page slug produces two files: `{slug}.html` (rendered HTML) and `{slug}.md` (raw markdown). The site also includes:

- **`search-index.json`** — An array of objects with `slug`, `title`, and `content` (truncated to 2000 characters) for client-side search.
- **`llms.txt`** — An index of all pages in a format optimized for LLM consumption.
- **`llms-full.txt`** — The complete concatenated markdown of every page.

## Page-Level Caching Strategy

docsfy caches each documentation page individually as a markdown file under `cache/pages/`. This allows the system to skip expensive AI generation calls for pages that have already been produced.

### Cache Lookup

When generating a page, the system first checks whether a cached version exists:

```python
# src/docsfy/generator.py
cache_file = cache_dir / f"{slug}.md"
if use_cache and cache_file.exists():
    return cache_file.read_text(encoding="utf-8")
```

If `use_cache` is `True` and the file exists, the cached content is returned immediately — no AI call is made.

### Cache Write

After a page is generated by the AI, it is always written to the cache directory:

```python
# src/docsfy/generator.py
output = _strip_ai_preamble(output)
cache_dir.mkdir(parents=True, exist_ok=True)
cache_file.write_text(output, encoding="utf-8")
```

> **Note:** The `_strip_ai_preamble()` function removes any AI "thinking" or planning text that appears before the first markdown heading, ensuring clean content in the cache.

### Progress Tracking

After each page is written to cache, the current count of cached `.md` files is reported back to the database so API consumers can track generation progress:

```python
# src/docsfy/generator.py
existing_pages = len(list(cache_dir.glob("*.md")))
await update_project_status(
    project_name, status="generating", page_count=existing_pages
)
```

### Concurrent Generation

Pages are generated concurrently with a configurable concurrency limit. Each page independently checks its own cache, so a mix of cached and uncached pages is handled efficiently:

```python
# src/docsfy/generator.py
MAX_CONCURRENT_PAGES = 5

results = await run_parallel_with_limit(
    coroutines, max_concurrency=MAX_CONCURRENT_PAGES
)
```

Failed pages receive placeholder content rather than blocking the entire generation:

```python
pages[page_info["slug"]] = (
    f"# {page_info['title']}\n\n*Documentation generation failed.*"
)
```

### Cache Invalidation

Cache invalidation happens through two mechanisms:

**1. Commit SHA comparison** — On non-forced generation, the system compares the repository's current commit SHA against the stored `last_commit_sha`. If they match and the project status is `ready`, generation is skipped entirely:

```python
# src/docsfy/main.py
existing = await get_project(project_name)
if (
    existing
    and existing.get("last_commit_sha") == commit_sha
    and existing.get("status") == "ready"
):
    await update_project_status(project_name, status="ready")
    return
```

**2. Force regeneration** — When `force=True` is passed in the API request, the entire cache directory is deleted and page count is reset to zero:

```python
# src/docsfy/main.py
if force:
    cache_dir = get_project_cache_dir(project_name)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    await update_project_status(project_name, status="generating", page_count=0)
```

> **Tip:** Use `"force": true` in the generate request when you've made changes to AI prompts or want to regenerate documentation even if the repository hasn't changed:
> ```bash
> curl -X POST http://localhost:8000/api/generate \
>   -H "Content-Type: application/json" \
>   -d '{"repo_url": "https://github.com/org/repo", "force": true}'
> ```

### Deletion Cleanup

When a project is deleted via the API, both the database record and the entire project directory (including cache and site) are removed:

```python
# src/docsfy/main.py
deleted = await delete_project(name)
project_dir = get_project_dir(name)
if project_dir.exists():
    shutil.rmtree(project_dir)
```

## Path Traversal Security

docsfy employs a defense-in-depth strategy with four layers of validation to prevent path traversal attacks.

### Layer 1: Project Name Validation (Storage)

All filesystem path construction passes through `_validate_name()`, which enforces a strict allowlist regex:

```python
# src/docsfy/storage.py
def _validate_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        msg = f"Invalid project name: '{name}'"
        raise ValueError(msg)
    return name
```

This pattern ensures:
- The name starts with an alphanumeric character (no leading `.` or `-`)
- Only alphanumeric characters, dots, underscores, and hyphens are allowed
- No slashes, spaces, or `..` sequences can appear

### Layer 2: API Endpoint Validation

A duplicate validation at the HTTP layer catches invalid names early and returns a proper `400 Bad Request` response:

```python
# src/docsfy/main.py
def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise HTTPException(status_code=400, detail=f"Invalid project name: '{name}'")
    return name
```

This is applied to every endpoint that accepts a project name parameter: `GET /api/projects/{name}`, `DELETE /api/projects/{name}`, `GET /api/projects/{name}/download`, and `GET /docs/{project}/{path}`.

### Layer 3: Page Slug Validation

Page slugs — used to construct cache file paths — are validated at both the individual page and batch levels:

```python
# src/docsfy/generator.py
if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
    msg = f"Invalid page slug: '{slug}'"
    raise ValueError(msg)
```

In `generate_all_pages()`, invalid slugs are logged and silently skipped rather than causing the entire generation to fail:

```python
if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
    logger.warning(f"[{_label}] Skipping path-unsafe slug: '{slug}'")
    continue
```

The renderer applies the same check when writing output files:

```python
# src/docsfy/renderer.py
for slug, content in pages.items():
    if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
        logger.warning(f"Skipping invalid slug: {slug}")
```

### Layer 4: Resolved Path Verification

The file-serving endpoint applies a final structural check using Python's `Path.resolve()` and `relative_to()`. This catches any traversal attempt that might bypass string-level validation:

```python
# src/docsfy/main.py
@app.get("/docs/{project}/{path:path}")
async def serve_docs(project: str, path: str = "index.html") -> FileResponse:
    project = _validate_project_name(project)
    site_dir = get_project_site_dir(project)
    file_path = site_dir / path
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
```

This resolves symlinks and `..` components in the actual filesystem, then verifies that the resulting absolute path is still within the expected `site/` directory. If not, the request is rejected with `403 Access denied`.

> **Warning:** The `resolve()` + `relative_to()` check is the most critical security boundary. It operates on the real filesystem path after symlink resolution, making it resistant to encoding tricks and double-dot sequences that might slip through regex-based validation.

### Defense Summary

| Layer | Location | Mechanism | Response |
|-------|----------|-----------|----------|
| 1 | `storage._validate_name()` | Alphanumeric regex | `ValueError` |
| 2 | `main._validate_project_name()` | Same regex at HTTP boundary | `400 Bad Request` |
| 3 | `generator.generate_page()` | Slash/dot checks on slugs | `ValueError` or skip |
| 4 | `main.serve_docs()` | `Path.resolve().relative_to()` | `403 Access Denied` |

### SQL Injection Prevention

All database queries use parameterized placeholders (`?`), and the dynamic field construction in `update_project_status` uses only hardcoded column names:

```python
# src/docsfy/storage.py
await db.execute("SELECT * FROM projects WHERE name = ?", (name,))
```

> **Note:** The `update_project_status` function constructs a dynamic `SET` clause, but the field names in the `fields` list are always string literals (`"status = ?"`, `"last_commit_sha = ?"`, etc.) — never derived from user input.

## Configuration Reference

Storage-related settings are managed through environment variables, loaded via Pydantic Settings:

```python
# src/docsfy/config.py
class Settings(BaseSettings):
    data_dir: str = "/data"
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `/data` | Root directory for the SQLite database and all project files |

In Docker deployments, mount a host volume to persist data across container restarts:

```yaml
# docker-compose.yaml
services:
  docsfy:
    volumes:
      - ./data:/data
```

> **Warning:** If `DATA_DIR` is not backed by a persistent volume, all project data — database, cached pages, and rendered sites — will be lost when the container is removed.
