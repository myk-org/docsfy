# GET /docs/{project}/{path}

Serve generated static HTML documentation pages directly from the docsfy server. This endpoint acts as a built-in static file server, letting you browse AI-generated documentation sites without deploying them separately.

## Endpoint Overview

| Property | Value |
|----------|-------|
| **Method** | `GET` |
| **Path** | `/docs/{project}/{path}` |
| **Authentication** | None |
| **Response** | Static file content (HTML, CSS, JS, JSON) |

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | `string` | Yes | The project name used during generation (derived from the repository name) |
| `path` | `string` | No | Path to the specific file within the generated site. Defaults to `index.html` when omitted or when a directory is requested |

## How It Works

When documentation is generated via `POST /api/generate`, the final pipeline stage renders all markdown content into a complete static HTML site stored on the filesystem. The `GET /docs/{project}/{path}` endpoint maps incoming requests directly to files within that rendered output.

### Request-to-Filesystem Resolution

Each request resolves to a file under the project's `site/` directory:

```
GET /docs/{project}/{path}
        │          │
        ▼          ▼
/data/projects/{project}/site/{path}
```

The storage layout for a generated project looks like this:

```
/data/projects/{project-name}/
  plan.json                 # doc structure from AI
  cache/
    pages/*.md              # AI-generated markdown (cached for incremental updates)
  site/                     # final rendered HTML ← served by this endpoint
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

The endpoint serves everything under `site/` — HTML pages, CSS stylesheets, JavaScript files, and the search index.

## Usage Examples

### Browse the documentation root

```bash
curl http://localhost:8000/docs/my-project/
```

This returns the `index.html` landing page for the `my-project` documentation site. Open this URL in a browser to get the full documentation experience with sidebar navigation, theme toggling, and client-side search.

### Fetch a specific documentation page

```bash
curl http://localhost:8000/docs/my-project/getting-started.html
```

### Load static assets

```bash
# Stylesheet
curl http://localhost:8000/docs/my-project/assets/style.css

# Client-side search logic
curl http://localhost:8000/docs/my-project/assets/search.js

# Theme toggle
curl http://localhost:8000/docs/my-project/assets/theme-toggle.js

# Code syntax highlighting
curl http://localhost:8000/docs/my-project/assets/highlight.js
```

### Fetch the search index

```bash
curl http://localhost:8000/docs/my-project/search-index.json
```

The search index is a JSON file built at render time. It powers the client-side search feature embedded in every documentation page.

## Content Types

The server returns the appropriate `Content-Type` header based on the file extension:

| Extension | Content-Type |
|-----------|-------------|
| `.html` | `text/html` |
| `.css` | `text/css` |
| `.js` | `application/javascript` |
| `.json` | `application/json` |

## Response Status Codes

| Status Code | Meaning |
|-------------|---------|
| `200 OK` | File found and returned successfully |
| `404 Not Found` | The project does not exist, documentation has not been generated yet, or the requested path does not match any file in the site |

## Generated Site Features

The HTML pages served by this endpoint include several built-in features rendered during the generation pipeline (Stage 4 — HTML Renderer):

| Feature | Description |
|---------|-------------|
| **Sidebar navigation** | Hierarchical navigation built from `plan.json` |
| **Dark/light theme** | Toggle between themes via `theme-toggle.js` |
| **Client-side search** | Full-text search powered by `search-index.json` |
| **Code syntax highlighting** | Automatic highlighting via `highlight.js` |
| **Card layouts** | Structured content cards for overview pages |
| **Callout boxes** | Note, warning, and info callouts for emphasized content |
| **Responsive design** | Mobile-friendly layout |

## End-to-End Workflow

To go from a repository URL to browsable documentation:

```bash
# 1. Start generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/my-project"}'

# 2. Check status until "ready"
curl http://localhost:8000/api/projects/my-project
# Response includes: "status": "generating" → "ready"

# 3. Browse the generated docs
open http://localhost:8000/docs/my-project/
```

> **Note:** Documentation is only available after the generation pipeline completes successfully. Requests to `/docs/{project}/` while the project status is `generating` will return a `404` until the site has been fully rendered.

## Self-Hosting Alternative

If you prefer to host the documentation on your own infrastructure rather than serving it through docsfy, you can download the entire generated site as a tarball:

```bash
curl -o docs.tar.gz http://localhost:8000/api/projects/my-project/download
tar -xzf docs.tar.gz -C /var/www/my-project-docs/
```

The downloaded archive contains the exact same static files served by this endpoint — the `site/` directory is fully self-contained with no external dependencies.

> **Tip:** Use the download approach for production deployments where you want to serve documentation from a CDN or dedicated web server like nginx. Use `GET /docs/{project}/{path}` for development previews and lightweight setups.

## Configuration

This endpoint requires no dedicated configuration. It relies on the data volume where generated sites are stored.

### Docker Compose volume mapping

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data    # Generated sites live under /data/projects/
```

The `./data` volume must be persistent. If the volume is lost, all generated documentation must be regenerated via `POST /api/generate`.

> **Warning:** Do not modify files under `/data/projects/{name}/site/` manually. These files are overwritten during each generation or incremental update cycle. Custom edits will be lost.

## Incremental Updates and Cache Behavior

When a project is regenerated (e.g., after a repository update), docsfy compares the current commit SHA against the stored SHA in the database. If the documentation structure from `plan.json` is unchanged, only affected pages are re-rendered — the rest are served from cached markdown under `cache/pages/*.md`.

After an incremental update completes, the `site/` directory is refreshed and subsequent requests to this endpoint immediately reflect the updated content. There is no separate cache layer between the endpoint and the filesystem.
