# GET /docs/{project}/{path}

The `GET /docs/{project}/{path}` endpoint is docsfy's primary documentation serving route. It delivers generated HTML documentation directly to the browser, turning docsfy from a generation-only tool into a fully hosted documentation platform.

## Overview

Once docsfy generates a documentation site for a project, the rendered HTML is stored on the filesystem under `/data/projects/{project-name}/site/`. This endpoint maps incoming URL paths to those static files, serving them with the correct content types so that browsers render full documentation sites — complete with navigation, search, syntax highlighting, and theme toggling.

```
GET /docs/{project}/{path}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `project` | path | The project name (as specified during generation) |
| `path` | path | The file path within the project's rendered site directory |

## URL Routing

The FastAPI route captures two path parameters to resolve which file to serve:

1. **`{project}`** — identifies which project's documentation to serve, matching a subdirectory under `/data/projects/`
2. **`{path}`** — the remaining URL segments, mapping to files within that project's `site/` directory

### Example URLs

| URL | Resolved File |
|-----|---------------|
| `/docs/my-api/index.html` | `/data/projects/my-api/site/index.html` |
| `/docs/my-api/getting-started.html` | `/data/projects/my-api/site/getting-started.html` |
| `/docs/my-api/assets/style.css` | `/data/projects/my-api/site/assets/style.css` |
| `/docs/my-api/assets/search.js` | `/data/projects/my-api/site/assets/search.js` |
| `/docs/my-api/search-index.json` | `/data/projects/my-api/site/search-index.json` |

## Path Resolution

The endpoint resolves the requested path against the project's rendered site directory on the filesystem. The storage layout that backs this endpoint is:

```
/data/projects/{project-name}/
  plan.json             # doc structure from AI
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # final rendered HTML — served by this endpoint
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

The resolution flow works as follows:

1. Extract `{project}` and `{path}` from the URL
2. Construct the filesystem path: `/data/projects/{project}/site/{path}`
3. If the path points to a directory (or is empty), serve `index.html` from that directory
4. Serve the resolved file with the appropriate `Content-Type` header
5. Return `404 Not Found` if the project or file does not exist

> **Note:** Only files inside the `site/` subdirectory are served. The `plan.json` and `cache/` directories are internal to the generation pipeline and are never exposed through this endpoint.

## Served File Types

The rendered site includes several file types, all served through this single endpoint:

| File | Content-Type | Purpose |
|------|-------------|---------|
| `*.html` | `text/html` | Documentation pages generated from AI-written markdown |
| `style.css` | `text/css` | Theme styles supporting dark/light mode, responsive layout |
| `search.js` | `application/javascript` | Client-side search powered by lunr.js (or similar) |
| `theme-toggle.js` | `application/javascript` | Dark/light theme switching logic |
| `highlight.js` | `application/javascript` | Code syntax highlighting |
| `search-index.json` | `application/json` | Pre-built search index for client-side search |

## How Content Gets Here

Before this endpoint can serve anything, the project must go through docsfy's four-stage generation pipeline:

```
POST /api/generate (repo URL)
        │
        ▼
   Clone Repository
        │
        ▼
   AI Planner → plan.json
        │
        ▼
   AI Content Generator → cache/pages/*.md
        │
        ▼
   HTML Renderer → site/   ← served by GET /docs/{project}/{path}
```

The final **HTML Renderer** stage (Stage 4) converts the AI-generated markdown pages and the `plan.json` structure into a polished static site using Jinja2 templates with bundled CSS/JS assets. The rendered site includes:

- Sidebar navigation (derived from `plan.json` hierarchy)
- Dark/light theme toggle
- Client-side full-text search
- Code syntax highlighting via highlight.js
- Callout boxes (note, warning, info)
- Card layouts
- Responsive design

## Project Status and Availability

The endpoint only serves documentation for projects whose status is `ready` in the SQLite database (`/data/docsfy.db`). Projects can have one of three statuses:

| Status | Docs Available | Description |
|--------|---------------|-------------|
| `generating` | No | Pipeline is still running |
| `ready` | **Yes** | Generation complete, docs are served |
| `error` | No | Generation failed |

> **Tip:** Use `GET /api/projects/{name}` to check a project's status, last generated timestamp, and commit SHA before requesting its documentation.

## Usage Examples

### Browsing Documentation

Point your browser directly at a project's documentation root:

```
http://localhost:8000/docs/my-api/index.html
```

This serves the full documentation site with working navigation, search, and theme toggling — just like any static documentation host.

### Fetching Assets Programmatically

```bash
# Fetch the main page
curl http://localhost:8000/docs/my-api/index.html

# Fetch the search index
curl http://localhost:8000/docs/my-api/search-index.json

# Fetch a specific documentation page
curl http://localhost:8000/docs/my-api/getting-started.html
```

### Checking if Documentation Exists

```bash
# Check project status first
curl http://localhost:8000/api/projects/my-api

# Response includes:
# {
#   "name": "my-api",
#   "status": "ready",
#   "last_generated": "2026-03-04T12:00:00Z",
#   "last_commit_sha": "abc123..."
# }
```

## Relationship to the Download Endpoint

docsfy provides two ways to access generated documentation:

| Method | Endpoint | Use Case |
|--------|----------|----------|
| **Hosted serving** | `GET /docs/{project}/{path}` | Browse docs directly from the docsfy server |
| **Static download** | `GET /api/projects/{name}/download` | Download docs as `.tar.gz` to self-host anywhere |

Both methods serve the same content from the same `site/` directory. The download endpoint packages the entire directory into an archive, while this endpoint serves files individually on demand.

> **Tip:** If you want to host the documentation on your own infrastructure (e.g., GitHub Pages, Netlify, S3), use the download endpoint to get the `.tar.gz` archive. If you want zero-config hosting, use this endpoint directly.

## Docker Volume Configuration

When running docsfy in Docker, the `/data` directory must be mounted as a persistent volume so that generated documentation survives container restarts:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data    # persists generated docs across restarts
```

The `./data/projects/` directory on the host will contain all generated sites, and the endpoint serves directly from this mounted path.

> **Warning:** If the `/data` volume is not mounted, generated documentation will be lost when the container stops. Always use a persistent volume or bind mount for production deployments.

## Error Responses

| Status Code | Condition |
|------------|-----------|
| `200 OK` | File found and served successfully |
| `404 Not Found` | Project does not exist, project is not in `ready` status, or the requested file path does not exist within the project's `site/` directory |
