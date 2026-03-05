# Generating Documentation

Docsfy generates documentation through an asynchronous API-driven pipeline. You submit a generation request pointing at a Git repository, and docsfy clones the code, plans a documentation structure using AI, then generates each page concurrently — caching results and tracking commits so subsequent runs only regenerate what's changed.

## Submitting a Generation Request

Documentation generation starts with a `POST` request to the `/api/generate` endpoint. The server validates the request, creates a background task, and immediately returns an HTTP `202 Accepted` response.

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/repo.git",
    "ai_provider": "claude",
    "ai_model": "claude-opus-4-6[1m]",
    "ai_cli_timeout": 60,
    "force": false
  }'
```

**Response** (HTTP 202):

```json
{
  "project": "repo",
  "status": "generating"
}
```

The project name is derived automatically from the repository URL or path (see [Project Naming](#project-naming) below). Generation runs in the background — poll the project status endpoint to track progress:

```bash
curl http://localhost:8000/api/projects/repo
```

### Request Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo_url` | `string` | One of `repo_url` / `repo_path` | — | Git repository URL (HTTPS or SSH) |
| `repo_path` | `string` | One of `repo_url` / `repo_path` | — | Absolute path to a local git repository |
| `ai_provider` | `string` | No | `"claude"` | AI provider: `"claude"`, `"gemini"`, or `"cursor"` |
| `ai_model` | `string` | No | `"claude-opus-4-6[1m]"` | Model identifier for the AI provider |
| `ai_cli_timeout` | `integer` | No | `60` | Timeout in seconds per AI CLI call (must be > 0) |
| `force` | `boolean` | No | `false` | Force full regeneration, ignoring all caches |

> **Note:** The `ai_provider`, `ai_model`, and `ai_cli_timeout` fields override the server-wide defaults set via environment variables or `.env` file. When omitted, the server settings apply.

### Concurrent Generation Guard

Docsfy prevents duplicate generation for the same project. If a generation is already in progress, a second request for the same project returns HTTP `409 Conflict`:

```json
{
  "detail": "Project 'repo' is already being generated"
}
```

The guard uses an in-memory set that tracks active project names:

```python
# main.py
_generating: set[str] = set()

if project_name in _generating:
    raise HTTPException(
        status_code=409,
        detail=f"Project '{project_name}' is already being generated",
    )
```

The project name is released from the set in a `finally` block, ensuring cleanup even if generation fails.

## Repository Sources: `repo_url` vs `repo_path`

Every request must specify exactly one repository source. Providing both or neither raises a validation error.

### Using `repo_url` (Remote Repository)

Use `repo_url` for public or authenticated remote repositories. Docsfy performs a shallow clone into a temporary directory, generates documentation, then automatically cleans up the clone.

```bash
# HTTPS
curl -X POST http://localhost:8000/api/generate \
  -d '{"repo_url": "https://github.com/org/repo.git"}'

# SSH
curl -X POST http://localhost:8000/api/generate \
  -d '{"repo_url": "git@github.com:org/repo.git"}'
```

**How it works internally:**

1. The URL is validated against accepted patterns (HTTPS and SSH):
   ```python
   https_pattern = r"^https?://[\w.\-]+/[\w.\-]+/[\w.\-]+(\.git)?$"
   ssh_pattern = r"^git@[\w.\-]+:[\w.\-]+/[\w.\-]+(\.git)?$"
   ```

2. A shallow clone is performed with `--depth 1` to minimize transfer size:
   ```python
   subprocess.run(
       ["git", "clone", "--depth", "1", "--", repo_url, str(repo_path)],
       capture_output=True,
       text=True,
       timeout=300,
   )
   ```

3. The HEAD commit SHA is captured via `git rev-parse HEAD`.

4. Documentation is generated from the cloned directory.

5. The temporary directory is cleaned up automatically.

> **Tip:** SSH URLs use your system's configured SSH keys. Make sure the docsfy process has access to the appropriate credentials for private repositories.

### Using `repo_path` (Local Repository)

Use `repo_path` for repositories already present on the filesystem. This skips the clone step entirely, making it faster and suitable for large repositories or local development workflows.

```bash
curl -X POST http://localhost:8000/api/generate \
  -d '{"repo_path": "/home/user/projects/my-app"}'
```

**Validation requirements:**

- The path must exist on the filesystem
- The path must contain a `.git` directory (be a valid git repository)

```python
path = Path(v)
if not path.exists():
    msg = f"Repository path does not exist: '{v}'"
    raise ValueError(msg)
if not (path / ".git").exists():
    msg = f"Not a git repository (no .git directory): '{v}'"
    raise ValueError(msg)
```

> **Warning:** Docsfy reads directly from the given path. If you modify the repository while generation is running, results may be inconsistent. Commit or stash changes before generating.

### Validation Errors

Providing both fields or neither returns HTTP `422`:

```python
# Neither provided
"Either 'repo_url' or 'repo_path' must be provided"

# Both provided
"Provide either 'repo_url' or 'repo_path', not both"
```

### Project Naming

The project name is derived automatically from the source:

- **From `repo_url`:** The last path segment, with `.git` stripped if present. `https://github.com/org/my-app.git` becomes `my-app`.
- **From `repo_path`:** The resolved directory name. `/home/user/projects/my-app` becomes `my-app`.

```python
@property
def project_name(self) -> str:
    if self.repo_url:
        name = self.repo_url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name
    if self.repo_path:
        return Path(self.repo_path).resolve().name
    return "unknown"
```

## Force Regeneration

By default, docsfy skips generation if the repository hasn't changed (see [Incremental Updates](#incremental-updates-via-commit-sha-tracking)). Set `force: true` to bypass all caching and regenerate every page from scratch.

```bash
curl -X POST http://localhost:8000/api/generate \
  -d '{
    "repo_url": "https://github.com/org/repo.git",
    "force": true
  }'
```

### What `force: true` Does

1. **Deletes the entire page cache** for the project:
   ```python
   if force:
       cache_dir = get_project_cache_dir(project_name)
       if cache_dir.exists():
           shutil.rmtree(cache_dir)
           logger.info(f"[{project_name}] Cleared cache (force=True)")
   ```

2. **Resets the page count** to `0` so API consumers see a fresh progress counter.

3. **Re-runs the AI planner** to regenerate the documentation structure, even if the commit SHA hasn't changed.

4. **Regenerates all pages** — with the cache cleared, every page is built from a new AI call.

### What `force: false` (Default) Does

1. Compares the current commit SHA against the stored `last_commit_sha`.
2. If the SHA matches and the project status is `"ready"`, generation is skipped entirely:
   ```python
   existing = await get_project(project_name)
   if (
       existing
       and existing.get("last_commit_sha") == commit_sha
       and existing.get("status") == "ready"
   ):
       logger.info(f"[{project_name}] Project is up to date at {commit_sha[:8]}")
       return
   ```

### When to Use Force Regeneration

- After changing AI provider or model (the cached pages were generated with different settings)
- When you want a complete refresh of all documentation content
- If a previous generation partially failed and left stale cache entries
- After upgrading docsfy itself (prompt or rendering improvements)

> **Tip:** Force regeneration makes a fresh AI call for every page. For large projects with many pages, this can be time-consuming and costly. Use it selectively.

## Incremental Updates via Commit SHA Tracking

Docsfy tracks the Git commit SHA of each generated project to enable efficient incremental updates. When the repository hasn't changed, generation is skipped entirely. When new commits are present, docsfy re-plans the documentation structure but reuses cached pages where possible.

### How Commit SHAs Are Tracked

The `projects` table in the SQLite database stores the `last_commit_sha` for each project:

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

### The Update Flow

The incremental update logic operates at two levels:

**1. Commit-level check — Skip unchanged repositories**

Before any AI calls are made, docsfy compares the current HEAD SHA against the stored value. If the project is already `"ready"` and the SHA matches, generation returns immediately with no work done.

**2. Page-level caching — Reuse unchanged pages**

When the commit SHA has changed (new commits exist), docsfy re-runs the AI planner to determine the documentation structure. However, individual pages that still exist in the cache are reused rather than regenerated:

```python
cache_file = cache_dir / f"{slug}.md"
if use_cache and cache_file.exists():
    logger.debug(f"[{_label}] Using cached page: {slug}")
    return cache_file.read_text(encoding="utf-8")
```

This means:
- If the planner produces the same page slugs as before, those cached pages are served from disk.
- If the planner adds new pages, only those new pages trigger AI calls.
- If the planner removes pages, those cached files simply aren't used.

**3. SHA stored on completion**

After all pages are generated and the site is rendered, the new commit SHA is persisted:

```python
await update_project_status(
    project_name,
    status="ready",
    last_commit_sha=commit_sha,
    page_count=page_count,
    plan_json=json.dumps(plan),
)
```

### Practical Example

Consider a project that was generated at commit `a1b2c3d4`:

```bash
# First run: full generation (planner + all pages)
curl -X POST http://localhost:8000/api/generate \
  -d '{"repo_url": "https://github.com/org/repo.git"}'
# → Generates 8 pages, stores SHA a1b2c3d4

# Second run, no new commits: skipped entirely
curl -X POST http://localhost:8000/api/generate \
  -d '{"repo_url": "https://github.com/org/repo.git"}'
# → "Project is up to date at a1b2c3d4", returns immediately

# Third run, after new commits (SHA now e5f6g7h8):
curl -X POST http://localhost:8000/api/generate \
  -d '{"repo_url": "https://github.com/org/repo.git"}'
# → Re-runs planner, reuses cached pages, only generates new/changed pages
```

### Cache Storage Layout

Cached pages are stored as individual markdown files on disk:

```
/data/projects/{project_name}/
├── cache/
│   └── pages/
│       ├── introduction.md
│       ├── quickstart.md
│       ├── configuration.md
│       └── api-reference.md
├── site/           # Rendered HTML output
│   ├── index.html
│   ├── introduction.html
│   ├── introduction.md
│   ├── llms.txt
│   ├── llms-full.txt
│   └── ...
└── plan.json       # Documentation structure
```

## Concurrent Page Generation

Docsfy generates multiple documentation pages in parallel to reduce total generation time. A semaphore limits concurrency to prevent overwhelming the AI provider.

### Concurrency Limit

The maximum number of concurrent page generation tasks is defined as a constant:

```python
# generator.py
MAX_CONCURRENT_PAGES = 5
```

This means up to 5 pages are generated simultaneously, with additional pages queued until a slot becomes available.

### How It Works

The `generate_all_pages` function collects all pages from the documentation plan, creates an async coroutine for each one, and executes them with bounded concurrency:

```python
async def generate_all_pages(
    repo_path: Path,
    plan: dict[str, Any],
    cache_dir: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    use_cache: bool = False,
    project_name: str = "",
) -> dict[str, str]:
    all_pages: list[dict[str, str]] = []
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            slug = page.get("slug", "")
            if not slug:
                continue
            all_pages.append({
                "slug": slug,
                "title": page.get("title", slug),
                "description": page.get("description", ""),
            })

    coroutines = [
        generate_page(
            repo_path=repo_path,
            slug=p["slug"],
            title=p["title"],
            description=p["description"],
            cache_dir=cache_dir,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=ai_cli_timeout,
            use_cache=use_cache,
            project_name=project_name,
        )
        for p in all_pages
    ]

    results = await run_parallel_with_limit(
        coroutines, max_concurrency=MAX_CONCURRENT_PAGES
    )
```

The `run_parallel_with_limit` function (from `ai_cli_runner`) uses an asyncio semaphore to cap concurrent execution at `MAX_CONCURRENT_PAGES`.

### Error Isolation

Individual page failures do not stop the generation of other pages. Failed pages receive placeholder content, and the remaining pages continue generating:

```python
for page_info, result in zip(all_pages, results):
    if isinstance(result, Exception):
        logger.warning(
            f"[{_label}] Page generation failed for '{page_info['slug']}': {result}"
        )
        pages[page_info["slug"]] = (
            f"# {page_info['title']}\n\n*Documentation generation failed.*"
        )
    else:
        pages[page_info["slug"]] = result
```

This ensures that a single page timing out or encountering an error doesn't prevent the rest of the documentation from being generated.

### Real-Time Progress Tracking

As each page completes, docsfy updates the `page_count` in the database. API consumers can poll the project status endpoint to monitor generation progress in real time:

```python
# After each page is generated and cached:
existing_pages = len(list(cache_dir.glob("*.md")))
await update_project_status(
    project_name, status="generating", page_count=existing_pages
)
```

Poll for progress:

```bash
# Check generation progress
curl http://localhost:8000/api/projects/repo

# Response during generation:
{
  "name": "repo",
  "status": "generating",
  "page_count": 3,
  ...
}

# Response when complete:
{
  "name": "repo",
  "status": "ready",
  "page_count": 8,
  "last_commit_sha": "a1b2c3d4...",
  "last_generated": "2026-03-05 14:30:00"
}
```

## The Generation Pipeline

Putting it all together, here is the full sequence of operations when you submit a generation request:

1. **Request validation** — Pydantic validates the URL/path format, mutual exclusivity, and field constraints.
2. **Concurrent guard** — Checks if this project is already being generated (HTTP 409 if so).
3. **AI CLI check** — Verifies the configured AI provider and model are available.
4. **Repository access** — Clones via `git clone --depth 1` (for `repo_url`) or reads directly (for `repo_path`).
5. **Commit SHA comparison** — Skips generation if the project is up to date (unless `force: true`).
6. **Cache cleanup** — If `force: true`, deletes all cached pages and resets the page count.
7. **AI planner** — A single AI call analyzes the repository and produces a documentation plan (JSON structure with navigation groups and pages).
8. **Concurrent page generation** — Up to 5 pages generated in parallel, with per-page caching and real-time progress updates.
9. **Site rendering** — Markdown pages are converted to HTML with navigation, search index, and `llms.txt` files.
10. **Status update** — The project is marked `"ready"` with the current commit SHA and page count stored in the database.

> **Note:** If any step fails, the project status is set to `"error"` with a descriptive `error_message`. The concurrent guard is always released in the `finally` block, so a failed generation does not permanently block the project.
