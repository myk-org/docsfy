# Serving and Downloading

Once docsfy generates documentation for a project, the resulting site is immediately available for browsing through the built-in HTTP endpoint and for downloading as a portable archive.

## Serving Documentation

### The `/docs` Endpoint

Every generated project is served at `/docs/{project}/{path}` through the FastAPI application. The endpoint is defined in `src/docsfy/main.py`:

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

### Browsing a Project

Once generation completes and a project's status is `ready`, you can access its documentation in a browser:

```
http://localhost:8000/docs/{project}/
```

The landing page at `index.html` is served by default when no path or `/` is requested. From there, navigate to any page or asset within the site:

```bash
# Project landing page (serves index.html)
http://localhost:8000/docs/my-project/

# Explicit index.html
http://localhost:8000/docs/my-project/index.html

# A specific documentation page
http://localhost:8000/docs/my-project/getting-started.html

# Static assets (CSS, JavaScript)
http://localhost:8000/docs/my-project/assets/style.css
http://localhost:8000/docs/my-project/assets/search.js

# Raw markdown source for any page
http://localhost:8000/docs/my-project/getting-started.md

# AI-consumable files
http://localhost:8000/docs/my-project/llms.txt
http://localhost:8000/docs/my-project/llms-full.txt

# Client-side search index
http://localhost:8000/docs/my-project/search-index.json
```

### Project Name Validation

Project names are validated against a strict pattern to prevent path traversal attacks:

```python
def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise HTTPException(status_code=400, detail=f"Invalid project name: '{name}'")
    return name
```

Valid project names must:
- Start with an alphanumeric character
- Contain only letters, digits, dots (`.`), underscores (`_`), and hyphens (`-`)

Examples: `my-project`, `app_v2`, `MyLibrary`, `widget.js`

The project name is derived automatically from the repository URL or local path when you trigger generation. For a URL like `https://github.com/org/my-project.git`, the project name becomes `my-project`.

### Path Traversal Protection

The endpoint resolves both the requested file path and the site directory to absolute paths, then verifies the file resides within the allowed directory:

```python
file_path.resolve().relative_to(site_dir.resolve())
```

If the resolved path escapes the site directory (e.g., via `../../etc/passwd`), a `403 Access denied` response is returned. Only regular files are served — directory listings are not supported.

### HTTP Responses

| Status Code | Condition |
|---|---|
| `200` | File found and returned |
| `400` | Invalid project name |
| `403` | Path traversal attempt detected |
| `404` | File does not exist or is a directory |

## Downloading as an Archive

### The Download Endpoint

Complete documentation sites can be downloaded as gzip-compressed tar archives via the API:

```
GET /api/projects/{name}/download
```

The endpoint implementation in `src/docsfy/main.py`:

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

### Downloading with `curl`

```bash
curl -O -J http://localhost:8000/api/projects/my-project/download
```

Or specify an output filename directly:

```bash
curl http://localhost:8000/api/projects/my-project/download -o my-project-docs.tar.gz
```

### Extracting the Archive

```bash
tar -xzf my-project-docs.tar.gz
```

This creates a directory named after the project containing the complete documentation site. You can open `index.html` directly in a browser to view the documentation offline:

```bash
open my-project/index.html        # macOS
xdg-open my-project/index.html    # Linux
```

### Preconditions

The download endpoint enforces two checks before creating the archive:

1. **Project must exist** in the database — returns `404` otherwise
2. **Project status must be `ready`** — returns `400` if the project is still `generating` or in an `error` state

> **Note:** You cannot download documentation while generation is in progress. Poll the project status endpoint (`GET /api/projects/{name}`) and wait for `"status": "ready"` before requesting a download.

### Streaming Behavior

The archive is created as a temporary file, then streamed to the client in 8 KB chunks. The temporary file is automatically cleaned up after the response completes, even if the client disconnects mid-transfer. The response includes:

- `Content-Type: application/gzip`
- `Content-Disposition: attachment; filename={name}-docs.tar.gz`

### HTTP Responses

| Status Code | Condition |
|---|---|
| `200` | Archive streamed successfully |
| `400` | Project exists but is not in `ready` status |
| `404` | Project not found, or site directory missing |

## Filesystem Layout

### Data Directory Structure

All generated output is stored under the data directory, which defaults to `/data` and can be configured via the `DATA_DIR` environment variable. The paths are defined in `src/docsfy/storage.py`:

```python
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"
```

Each project has three path helpers:

```python
def get_project_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name)

def get_project_site_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "site"

def get_project_cache_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "cache" / "pages"
```

### Complete Directory Tree

```
$DATA_DIR/                          # Default: /data
├── docsfy.db                       # SQLite database (project metadata)
└── projects/
    └── {project-name}/
        ├── plan.json               # Documentation structure plan (JSON)
        ├── site/                   # Generated site (served at /docs/{project}/)
        │   ├── index.html          # Landing page with project overview
        │   ├── {slug}.html         # Rendered HTML page for each doc page
        │   ├── {slug}.md           # Raw markdown source for each doc page
        │   ├── assets/             # Static assets
        │   │   ├── style.css       # Stylesheet (responsive, dark/light themes)
        │   │   ├── search.js       # Client-side full-text search
        │   │   ├── theme.js        # Dark/light theme toggle + persistence
        │   │   ├── copy.js         # Code block copy-to-clipboard
        │   │   ├── callouts.js     # Callout box rendering
        │   │   ├── scrollspy.js    # Active section highlighting in TOC
        │   │   ├── codelabels.js   # Language labels on code blocks
        │   │   └── github.js       # GitHub repository link integration
        │   ├── search-index.json   # Search index for client-side search
        │   ├── llms.txt            # Page index for AI/LLM consumers
        │   └── llms-full.txt       # Full concatenated content for AI/LLMs
        └── cache/
            └── pages/
                └── {slug}.md       # Cached generated page content
```

### File Descriptions

#### `site/index.html`

The landing page for the documentation site. Contains a hero section with the project name and tagline, a card grid linking to documentation groups and pages, a navigation sidebar, and interactive search (triggered with `Cmd+K` / `Ctrl+K`).

#### `site/{slug}.html`

Each documentation page rendered as a standalone HTML file with:
- Left sidebar navigation with all sections
- Main content area with rendered markdown
- Right-side table of contents (auto-generated from headings)
- Previous/next page navigation links
- Top bar with search, theme toggle, and GitHub link

#### `site/{slug}.md`

The raw markdown source for each page, written alongside its HTML counterpart. These files are referenced by `llms.txt` and can be served directly via the `/docs` endpoint.

#### `site/search-index.json`

A JSON array used by `search.js` for client-side full-text search. Each entry contains the page slug, title, and the first 2,000 characters of content:

```json
[
  {
    "slug": "introduction",
    "title": "Introduction",
    "content": "# Introduction\n\nWelcome to..."
  }
]
```

The index is built by `_build_search_index()` in `src/docsfy/renderer.py`:

```python
def _build_search_index(
    pages: dict[str, str], plan: dict[str, Any]
) -> list[dict[str, str]]:
    index: list[dict[str, str]] = []
    title_map: dict[str, str] = {}
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            title_map[page.get("slug", "")] = page.get("title", "")
    for slug, content in pages.items():
        index.append(
            {
                "slug": slug,
                "title": title_map.get(slug, slug),
                "content": content[:2000],
            }
        )
    return index
```

#### `site/llms.txt`

An index file designed for AI and LLM consumers. Lists all pages with relative links to their markdown sources:

```markdown
# My Project

> A brief description of the project

## Getting Started

- [Introduction](introduction.md): Overview of the project
- [Installation](installation.md): How to install

## API Reference

- [Endpoints](endpoints.md): Available API endpoints
```

#### `site/llms-full.txt`

The complete documentation concatenated into a single file, with page boundaries marked by `---` separators and `Source:` headers:

```markdown
# My Project

> A brief description of the project

---

Source: introduction.md

# Introduction

Welcome to...

---

Source: installation.md

# Installation

To install...

---
```

> **Tip:** The `llms.txt` and `llms-full.txt` files follow emerging conventions for making documentation accessible to AI tools. Use `llms.txt` as a table of contents and `llms-full.txt` when you need the complete documentation in a single context.

#### `cache/pages/{slug}.md`

Cached markdown content from previous generation runs. When a project is regenerated without the `force` flag, the cache allows docsfy to skip pages that haven't changed. The cache is stored separately from the site output so it survives site rebuilds.

#### `plan.json`

The documentation structure plan produced by the AI planner, stored at the project root (outside `site/`). Contains the project name, tagline, and full navigation tree:

```json
{
  "project_name": "my-project",
  "tagline": "A brief description",
  "navigation": [
    {
      "group": "Getting Started",
      "pages": [
        {
          "slug": "introduction",
          "title": "Introduction",
          "description": "Overview of the project"
        }
      ]
    }
  ],
  "repo_url": "https://github.com/org/my-project.git"
}
```

### The Rendering Process

The `render_site()` function in `src/docsfy/renderer.py` orchestrates the entire output generation:

1. **Clears the output directory** — removes any previous build and recreates it
2. **Creates `assets/`** — copies all static files (CSS, JS) from the bundled static directory
3. **Validates page slugs** — rejects slugs containing `/`, `\`, or starting with `.`
4. **Renders `index.html`** — generates the landing page from the index template
5. **Renders each page** — converts markdown to HTML, builds navigation with prev/next links, writes both `{slug}.html` and `{slug}.md`
6. **Generates `search-index.json`** — builds the client-side search index
7. **Generates `llms.txt` and `llms-full.txt`** — creates AI-consumable documentation files

> **Warning:** Rendering replaces the entire `site/` directory. Any manual modifications to files inside `site/` will be lost on the next generation.

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `/data` | Root directory for all project data and the SQLite database |
| `HOST` | `0.0.0.0` | Address the HTTP server binds to |
| `PORT` | `8000` | Port the HTTP server listens on |
| `DEBUG` | `false` | Set to `true` to enable auto-reload on code changes |

### Docker Compose

When running with Docker Compose, the data directory is mounted as a volume at `/data`:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

This means generated sites persist in `./data/projects/` on the host filesystem, surviving container restarts.

## End-to-End Example

A complete workflow from generation to serving and downloading:

```bash
# 1. Start documentation generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/my-project.git"}'
# Response: {"project": "my-project", "status": "generating"}

# 2. Poll until ready
curl -s http://localhost:8000/api/projects/my-project | jq .status
# "generating" ... wait ... "ready"

# 3. Browse the documentation
open http://localhost:8000/docs/my-project/

# 4. Download the complete site
curl http://localhost:8000/api/projects/my-project/download \
  -o my-project-docs.tar.gz

# 5. Extract and use offline
tar -xzf my-project-docs.tar.gz
ls my-project/
# assets/  index.html  introduction.html  introduction.md  search-index.json  llms.txt  llms-full.txt
```

> **Tip:** For local repositories, use `repo_path` instead of `repo_url` to skip cloning:
> ```bash
> curl -X POST http://localhost:8000/api/generate \
>   -H "Content-Type: application/json" \
>   -d '{"repo_path": "/home/user/my-project"}'
> ```
