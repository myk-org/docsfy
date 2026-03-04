# GET /api/projects/{name}/download

Download a project's generated documentation site as a `.tar.gz` archive for self-hosting.

## Overview

This endpoint packages the complete static HTML documentation site for a project into a compressed `.tar.gz` archive. The downloaded archive contains everything needed to host the documentation independently — HTML pages, CSS stylesheets, JavaScript assets, and the search index — with no dependency on the docsfy server.

## Request

```
GET /api/projects/{name}/download
```

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | Yes | The project name as registered in docsfy |

### Example Request

```bash
curl -O -J http://localhost:8000/api/projects/my-project/download
```

Or with an explicit output filename:

```bash
curl -o my-project-docs.tar.gz http://localhost:8000/api/projects/my-project/download
```

## Response

### Success (200 OK)

On success, the endpoint returns a `.tar.gz` binary stream.

| Header | Value |
|--------|-------|
| `Content-Type` | `application/gzip` |

**Response body:** Binary `.tar.gz` archive containing the project's generated static site.

### Error Responses

| Status Code | Condition |
|-------------|-----------|
| `404 Not Found` | The project `{name}` does not exist |
| `409 Conflict` | The project exists but documentation is still generating (status is `generating`) |
| `500 Internal Server Error` | The site directory is missing or the archive could not be created |

## Archive Contents

The downloaded archive mirrors the contents of the rendered site directory at `/data/projects/{name}/site/`. Once extracted, it produces a fully self-contained static website:

```
site/
  index.html
  *.html
  assets/
    style.css
    search.js
    theme-toggle.js
    highlight.js
  search-index.json
```

| File / Directory | Description |
|-----------------|-------------|
| `index.html` | Landing page for the documentation site |
| `*.html` | Individual documentation pages generated from the AI content pipeline |
| `assets/style.css` | Theme stylesheet with dark/light mode support |
| `assets/search.js` | Client-side search functionality (powered by lunr.js) |
| `assets/theme-toggle.js` | Dark/light theme switcher |
| `assets/highlight.js` | Code syntax highlighting |
| `search-index.json` | Pre-built search index for client-side search |

> **Note:** The HTML pages include sidebar navigation, code syntax highlighting, callout boxes, card layouts, and responsive design — all bundled within the archive. No external CDN or runtime dependency is required.

## Self-Hosting the Downloaded Archive

### Extract the Archive

```bash
tar -xzf my-project-docs.tar.gz
```

### Serve with Python (Quick Preview)

```bash
cd site/
python3 -m http.server 3000
```

Then open `http://localhost:3000` in your browser.

### Serve with Nginx

```nginx
server {
    listen 80;
    server_name docs.example.com;

    root /var/www/docs/site;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### Serve with Docker (Nginx)

```dockerfile
FROM nginx:alpine
COPY site/ /usr/share/nginx/html/
EXPOSE 80
```

```bash
docker build -t my-docs .
docker run -p 8080:80 my-docs
```

## How the Archive Is Built

The archive is generated from the output of docsfy's four-stage generation pipeline:

1. **Clone** — The target repository is shallow-cloned (`--depth 1`)
2. **AI Planner** — An AI CLI analyzes the repo and produces `plan.json` with the documentation structure
3. **AI Content Generator** — For each page in the plan, the AI generates markdown content (pages run concurrently with semaphore-limited concurrency)
4. **HTML Renderer** — Markdown pages and `plan.json` are rendered into static HTML via Jinja2 templates with bundled CSS/JS

The final rendered site at `/data/projects/{name}/site/` is what gets packaged into the `.tar.gz` archive when you call this endpoint.

> **Tip:** You can check whether a project's documentation is ready for download by calling `GET /api/projects/{name}` and verifying the status is `ready`. Projects with a status of `generating` or `error` are not available for download.

## Project Status and Download Availability

The project must have a `ready` status for the download to succeed. Project status is tracked in the SQLite database at `/data/docsfy.db`:

| Status | Download Available | Description |
|--------|--------------------|-------------|
| `generating` | No | Documentation is currently being generated |
| `ready` | Yes | Generation complete, archive can be downloaded |
| `error` | No | Generation failed; check project details for logs |

### Checking Project Status Before Download

```bash
# Check if the project is ready
curl http://localhost:8000/api/projects/my-project

# Only then download
curl -o docs.tar.gz http://localhost:8000/api/projects/my-project/download
```

## Incremental Updates and Re-downloading

docsfy tracks the last commit SHA for each project. When documentation is regenerated (via `POST /api/generate`), only affected pages are rebuilt. After regeneration completes, calling the download endpoint again returns an updated archive reflecting the latest changes.

```bash
# Regenerate docs after repo changes
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/my-project"}'

# Poll until status is "ready"
curl http://localhost:8000/api/projects/my-project

# Download the updated archive
curl -o my-project-docs.tar.gz http://localhost:8000/api/projects/my-project/download
```

> **Warning:** Downloading while the project status is `generating` will result in an error. Always verify the project status is `ready` before attempting a download.

## Storage and Volume Configuration

The site files that back this endpoint are stored on the filesystem under `/data/projects/`. When running with Docker, this path is controlled by the volume mount in `docker-compose.yaml`:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
```

The local `./data` directory maps to `/data` inside the container. The generated site for each project lives at:

```
./data/projects/{project-name}/site/
```

> **Tip:** You can also access the generated static files directly from the host filesystem at `./data/projects/{name}/site/` without using the download endpoint. The endpoint is a convenience for packaging everything into a single portable archive.

## Related Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository |
| `GET` | `/api/projects/{name}` | Get project details including status, last commit SHA, and page list |
| `GET` | `/api/status` | List all projects and their generation status |
| `DELETE` | `/api/projects/{name}` | Remove a project and all its generated documentation |
| `GET` | `/docs/{project}/{path}` | Serve generated docs directly from docsfy (alternative to self-hosting) |
