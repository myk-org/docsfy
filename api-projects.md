# Project Endpoints

The docsfy API provides endpoints for managing individual projects. These endpoints allow you to retrieve project details, delete projects and their generated documentation, and download complete documentation sites as portable archives.

All project endpoints operate on a specific project identified by its `{name}` path parameter, which corresponds to the project name assigned during generation.

## Base URL

```
http://localhost:8000
```

## Get Project Details

Retrieve detailed information about a specific project, including its current status, last generation timestamp, commit SHA, and the list of generated documentation pages.

```
GET /api/projects/{name}
```

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The project name |

### Response

**200 OK** — Returns project metadata and page listing.

```json
{
  "name": "my-project",
  "repo_url": "https://github.com/org/my-project",
  "status": "ready",
  "last_generated": "2026-03-04T14:30:00Z",
  "last_commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
  "pages": [
    "index.html",
    "getting-started.html",
    "api-reference.html",
    "configuration.html"
  ]
}
```

**404 Not Found** — The specified project does not exist.

```json
{
  "detail": "Project not found"
}
```

### Project Status Values

| Status | Description |
|--------|-------------|
| `generating` | Documentation generation is currently in progress |
| `ready` | Generation completed successfully; docs are available to serve or download |
| `error` | Generation failed; check logs for details |

### Example

```bash
curl http://localhost:8000/api/projects/my-project
```

> **Tip:** Use the `GET /api/status` endpoint first to list all available project names if you don't know the exact project name.

### Storage Context

Project metadata is persisted in the SQLite database at `/data/docsfy.db`. The page listing is derived from the rendered site directory on the filesystem:

```
/data/projects/{name}/
  plan.json             # doc structure from AI
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # final rendered HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

> **Note:** If the project status is `generating`, the page list may be incomplete or empty as the generation pipeline is still running.

---

## Delete Project

Remove a project and all of its associated data, including generated documentation, cached markdown, the documentation plan, and the database record.

```
DELETE /api/projects/{name}
```

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The project name to delete |

### Response

**200 OK** — The project was successfully deleted.

```json
{
  "detail": "Project deleted"
}
```

**404 Not Found** — The specified project does not exist.

```json
{
  "detail": "Project not found"
}
```

### Example

```bash
curl -X DELETE http://localhost:8000/api/projects/my-project
```

> **Warning:** This operation is irreversible. Deleting a project removes the SQLite metadata record and the entire `/data/projects/{name}/` directory, including all cached markdown pages and rendered HTML. To regenerate, you must submit a new `POST /api/generate` request.

### What Gets Deleted

| Resource | Location |
|----------|----------|
| Database record | `/data/docsfy.db` (project row) |
| Documentation plan | `/data/projects/{name}/plan.json` |
| Cached markdown pages | `/data/projects/{name}/cache/pages/*.md` |
| Rendered HTML site | `/data/projects/{name}/site/` |

After deletion, the served documentation at `GET /docs/{name}/{path}` will no longer be accessible.

---

## Download Project Site

Download the complete generated documentation site as a `.tar.gz` archive. This allows you to self-host the static HTML documentation on any web server, CDN, or static hosting platform (GitHub Pages, Netlify, Vercel, S3, etc.).

```
GET /api/projects/{name}/download
```

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The project name to download |

### Response

**200 OK** — Returns the site as a `.tar.gz` archive.

| Header | Value |
|--------|-------|
| `Content-Type` | `application/gzip` |
| `Content-Disposition` | `attachment; filename="{name}-docs.tar.gz"` |

**404 Not Found** — The specified project does not exist.

```json
{
  "detail": "Project not found"
}
```

### Example

Download and extract the documentation site:

```bash
# Download the archive
curl -O http://localhost:8000/api/projects/my-project/download

# Extract to a directory
mkdir my-project-docs
tar -xzf my-project-docs.tar.gz -C my-project-docs
```

### Archive Contents

The archive contains the full rendered static site from `/data/projects/{name}/site/`:

```
site/
├── index.html
├── getting-started.html
├── api-reference.html
├── configuration.html
├── assets/
│   ├── style.css
│   ├── search.js
│   ├── theme-toggle.js
│   └── highlight.js
└── search-index.json
```

The extracted site is fully self-contained — all CSS, JavaScript, and search index files are bundled. No external dependencies are required to serve it.

> **Note:** The download endpoint is only available when the project status is `ready`. Projects with a status of `generating` or `error` do not have a complete site to download.

### Self-Hosting

After extracting the archive, serve the static files with any HTTP server:

```bash
# Python
cd my-project-docs/site && python -m http.server 3000

# Node.js (npx)
npx serve my-project-docs/site

# Nginx (copy to web root)
cp -r my-project-docs/site/* /usr/share/nginx/html/
```

> **Tip:** The generated site includes client-side search (via the bundled `search.js` and `search-index.json`), dark/light theme toggling, and syntax highlighting — all of which work without a backend server.

---

## Error Handling

All project endpoints return standard HTTP error responses with a JSON body containing a `detail` field:

| Status Code | Description |
|-------------|-------------|
| `200` | Request completed successfully |
| `404` | The specified project name was not found |
| `422` | Validation error (invalid path parameter) |
| `500` | Internal server error |

```json
{
  "detail": "Project not found"
}
```

---

## Related Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/generate` | Start documentation generation for a repository |
| `GET /api/status` | List all projects and their generation status |
| `GET /docs/{project}/{path}` | Serve generated HTML documentation directly |
| `GET /health` | Service health check |
