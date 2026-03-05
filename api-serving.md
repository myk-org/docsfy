# Serving and Download Endpoints

docsfy exposes three read-only GET endpoints for consuming generated documentation: a static file server for browsing docs in the browser, a download endpoint for exporting an entire project as a compressed archive, and a health check for infrastructure probes.

## Health Check

```
GET /health
```

A minimal liveness probe that confirms the docsfy server is running and accepting requests. It has no dependencies on the database or filesystem.

### Response

**Status:** `200 OK`
**Content-Type:** `application/json`

```json
{
  "status": "ok"
}
```

### Usage

```bash
curl http://localhost:8000/health
```

The handler is intentionally simple — it returns a fixed JSON response with no external checks:

```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

### Docker and Orchestration

Both the `Dockerfile` and `docker-compose.yaml` use this endpoint for container health monitoring.

**Dockerfile:**

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

**docker-compose.yaml:**

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

> **Tip:** When deploying to Kubernetes, point your `livenessProbe` at `GET /health` on port `8000`. Since this endpoint has no side effects and no dependencies, it is also suitable as a `readinessProbe`.

---

## Serving Static Documentation

```
GET /docs/{project}/{path}
```

Serves the rendered HTML, CSS, JavaScript, and other static files for a project's generated documentation site. This is the primary endpoint users visit in a browser to read documentation.

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | Yes | Project name. Must match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$` |
| `path` | string | No | File path relative to the project's site directory. Defaults to `index.html` |

The `path` parameter is a greedy path (`{path:path}` in FastAPI), so it can include subdirectories like `assets/style.css`.

### Response

**Status:** `200 OK`
**Content-Type:** Automatically detected from file extension (e.g., `text/html`, `text/css`, `application/javascript`)

Returns a `FileResponse` that streams the requested file.

### Error Responses

| Status | Condition | Detail |
|--------|-----------|--------|
| `400 Bad Request` | Project name fails validation | `"Invalid project name: '{name}'"` |
| `403 Forbidden` | Path traversal attempt detected | `"Access denied"` |
| `404 Not Found` | File does not exist or is a directory | `"File not found"` |

### Examples

```bash
# Serve the landing page (index.html)
curl http://localhost:8000/docs/my-project/

# Serve a specific documentation page
curl http://localhost:8000/docs/my-project/getting-started.html

# Serve a static asset
curl http://localhost:8000/docs/my-project/assets/style.css

# Retrieve the raw markdown source for a page
curl http://localhost:8000/docs/my-project/overview.md

# Access the search index
curl http://localhost:8000/docs/my-project/search-index.json

# Fetch LLM-friendly documentation
curl http://localhost:8000/docs/my-project/llms.txt
curl http://localhost:8000/docs/my-project/llms-full.txt
```

### File Structure

Each generated project site lives under `{DATA_DIR}/projects/{name}/site/` and contains:

| File / Directory | Description |
|-----------------|-------------|
| `index.html` | Landing page with project overview and navigation |
| `{slug}.html` | Rendered HTML for each documentation page |
| `{slug}.md` | Raw markdown source for each page |
| `assets/` | Static CSS and JavaScript files |
| `search-index.json` | Client-side search index (JSON array) |
| `llms.txt` | LLM-friendly page index with links |
| `llms-full.txt` | Complete documentation concatenated for LLM consumption |

### Security

The handler applies two layers of protection against path traversal attacks:

```python
@app.get("/docs/{project}/{path:path}")
async def serve_docs(project: str, path: str = "index.html") -> FileResponse:
    project = _validate_project_name(project)
    if not path or path == "/":
        path = "index.html"
    site_dir = get_project_site_dir(project)
    file_path = site_dir / path
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
```

1. **Project name validation** — The `_validate_project_name()` function rejects names that don't match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$`, preventing directory traversal through the project parameter.

2. **Resolved path containment** — After constructing the full file path, the handler calls `resolve()` on both the file path and the site directory, then verifies the file is contained within the site directory using `relative_to()`. Any attempt to escape (e.g., `../../etc/passwd`) results in a `403`.

> **Warning:** The endpoint only serves regular files. Requesting a directory path (without a trailing filename) that doesn't map to an actual file will return `404`, not a directory listing.

---

## Archive Download

```
GET /api/projects/{name}/download
```

Downloads the entire generated documentation site for a project as a gzip-compressed tar archive. Useful for offline access, CI/CD artifact collection, or hosting documentation on a separate static file server.

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Project name. Must match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$` |

### Response

**Status:** `200 OK`
**Content-Type:** `application/gzip`
**Content-Disposition:** `attachment; filename={name}-docs.tar.gz`

The response is a `StreamingResponse` that streams the tar.gz archive in 8 KB chunks. The archive root directory is named after the project.

### Error Responses

| Status | Condition | Detail |
|--------|-----------|--------|
| `400 Bad Request` | Project name fails validation | `"Invalid project name: '{name}'"` |
| `400 Bad Request` | Project is not in `ready` status | `"Project '{name}' is not ready (status: {status})"` |
| `404 Not Found` | Project does not exist in the database | `"Project '{name}' not found"` |
| `404 Not Found` | Site directory missing on disk | `"Site directory not found for '{name}'"` |

> **Note:** Only projects with status `"ready"` can be downloaded. Projects still in `"generating"` or `"error"` status will return a `400` error. Check a project's status via `GET /api/projects/{name}` before attempting a download.

### Examples

```bash
# Download as tar.gz
curl -OJ http://localhost:8000/api/projects/my-project/download

# Download with wget
wget http://localhost:8000/api/projects/my-project/download -O my-project-docs.tar.gz

# Extract the archive
tar -xzf my-project-docs.tar.gz

# View extracted contents
ls my-project/
# index.html  introduction.html  assets/  search-index.json  llms.txt  ...
```

### Implementation Details

The archive is built on-the-fly into a temporary file, then streamed to the client with automatic cleanup:

```python
@app.get("/api/projects/{name}/download")
async def download_project(name: str) -> StreamingResponse:
    name = _validate_project_name(name)
    project = await get_project(name)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    if project["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Project '{name}' is not ready (status: {project['status']})",
        )
    site_dir = get_project_site_dir(name)
    if not site_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Site directory not found for '{name}'"
        )
    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tar_path = Path(tmp.name)
    tmp.close()
    with tarfile.open(tar_path, mode="w:gz") as tar:
        tar.add(str(site_dir), arcname=name)

    async def _stream_and_cleanup() -> AsyncIterator[bytes]:
        try:
            with open(tar_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        finally:
            tar_path.unlink(missing_ok=True)

    return StreamingResponse(
        _stream_and_cleanup(),
        media_type="application/gzip",
        headers={"Content-Disposition": f"attachment; filename={name}-docs.tar.gz"},
    )
```

Key behaviors:

- **Temporary file lifecycle** — The tar.gz is written to a temporary file, streamed to the client in 8 KB chunks, then deleted in the generator's `finally` block regardless of success or failure.
- **Archive structure** — The `arcname=name` argument ensures the archive extracts into a directory named after the project rather than including the full server-side filesystem path.
- **Memory efficiency** — The streaming approach avoids loading the entire archive into memory, making it safe for large documentation sites.

### Archive Contents

The downloaded archive mirrors the site directory structure:

```
my-project/
├── index.html
├── introduction.html
├── introduction.md
├── getting-started.html
├── getting-started.md
├── assets/
│   ├── style.css
│   ├── theme.js
│   ├── search.js
│   ├── copy.js
│   ├── callouts.js
│   ├── codelabels.js
│   ├── scrollspy.js
│   └── github.js
├── search-index.json
├── llms.txt
└── llms-full.txt
```

---

## Project Name Validation

All three endpoints that accept a project name parameter (`/docs/{project}/...` and `/api/projects/{name}/download`) share the same validation logic:

```python
def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise HTTPException(status_code=400, detail=f"Invalid project name: '{name}'")
    return name
```

**Rules:**
- Must start with an alphanumeric character (`a-z`, `A-Z`, `0-9`)
- May contain letters, digits, dots (`.`), underscores (`_`), and hyphens (`-`)
- Cannot contain slashes, spaces, or other special characters

**Valid names:** `myproject`, `my-project`, `my_project.v2`, `React2024`

**Invalid names:** `-project`, `my project`, `../etc`, `.hidden`

---

## Data Directory Configuration

The site files served by these endpoints are stored on disk under the configurable `DATA_DIR`:

```python
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"
```

Each project's rendered site lives at `{PROJECTS_DIR}/{name}/site/`. The default data directory is `/data`, which can be overridden with the `DATA_DIR` environment variable.

When running with Docker Compose, this directory is typically mounted as a volume:

```yaml
volumes:
  - ./data:/data
```

---

## Quick Reference

| Endpoint | Method | Response Type | Auth | Description |
|----------|--------|--------------|------|-------------|
| `/health` | GET | JSON | None | Liveness probe |
| `/docs/{project}/{path}` | GET | File (HTML/CSS/JS/etc.) | None | Serve documentation files |
| `/api/projects/{name}/download` | GET | Streaming tar.gz | None | Download full site archive |
