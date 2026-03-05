# GET /api/projects/{name}/download

Download the complete generated documentation site as a `.tar.gz` archive for self-hosting.

## Overview

This endpoint packages the rendered static HTML site for a project into a compressed tarball archive. Use it to download the full documentation site and host it on your own infrastructure — any static file server (Nginx, Apache, Caddy, S3, GitHub Pages, etc.) can serve the result.

The archive contains the complete contents of the project's `site/` directory, including all HTML pages, CSS/JS assets, and the client-side search index.

## Request

```
GET /api/projects/{name}/download
```

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The project name identifier, as set during generation via `POST /api/generate` |

### Example Request

```bash
curl -O -J http://localhost:8000/api/projects/my-project/download
```

The `-O` flag saves the file using the server-provided filename, and `-J` uses the name from the `Content-Disposition` header.

You can also specify a custom output path:

```bash
curl -o my-project-docs.tar.gz http://localhost:8000/api/projects/my-project/download
```

### Python Example

```python
import httpx

response = httpx.get("http://localhost:8000/api/projects/my-project/download")
response.raise_for_status()

with open("my-project-docs.tar.gz", "wb") as f:
    f.write(response.content)
```

## Response

### Success (200 OK)

Returns the `.tar.gz` archive as a binary stream.

**Response Headers:**

| Header | Value |
|--------|-------|
| `Content-Type` | `application/gzip` |
| `Content-Disposition` | `attachment; filename="{name}.tar.gz"` |

### Archive Contents

The archive mirrors the project's rendered `site/` directory:

```
{name}/
  index.html
  *.html
  assets/
    style.css
    search.js
    theme-toggle.js
    highlight.js
  search-index.json
```

| Path | Description |
|------|-------------|
| `index.html` | Documentation landing page |
| `*.html` | Individual documentation pages generated from the AI content pipeline |
| `assets/style.css` | Stylesheet with dark/light theme support and responsive layout |
| `assets/search.js` | Client-side search powered by the bundled search index |
| `assets/theme-toggle.js` | Dark/light theme toggle logic |
| `assets/highlight.js` | Code syntax highlighting |
| `search-index.json` | Pre-built search index for client-side full-text search |

### Error Responses

| Status Code | Description |
|-------------|-------------|
| `404 Not Found` | Project with the given `name` does not exist |
| `409 Conflict` | Project exists but documentation is still being generated (status is `generating`) |
| `500 Internal Server Error` | Archive creation failed due to a server-side error |

**Example error response (404):**

```json
{
  "detail": "Project 'unknown-project' not found"
}
```

**Example error response (409):**

```json
{
  "detail": "Project 'my-project' is still generating"
}
```

> **Note:** You can check whether a project's documentation is ready before attempting a download by calling `GET /api/projects/{name}` and verifying that the `status` field is `ready`.

## Self-Hosting the Downloaded Site

### Extract the Archive

```bash
tar -xzf my-project.tar.gz
```

### Serve with Nginx

```nginx
server {
    listen 80;
    server_name docs.example.com;

    root /var/www/my-project;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### Serve with Caddy

```
docs.example.com {
    root * /var/www/my-project
    file_server
}
```

### Serve with Python (Development)

```bash
cd my-project
python -m http.server 3000
```

Then open `http://localhost:3000` in your browser.

### Host on Amazon S3

```bash
tar -xzf my-project.tar.gz
aws s3 sync my-project/ s3://my-docs-bucket/ --delete
```

### Host on GitHub Pages

```bash
tar -xzf my-project.tar.gz
cd my-project
git init
git add .
git commit -m "Deploy documentation"
git remote add origin git@github.com:yourorg/yourorg.github.io.git
git push -u origin main
```

> **Tip:** Automate documentation updates by scripting the download and deployment. Combine `POST /api/generate` with a poll on `GET /api/projects/{name}` until the status is `ready`, then call this download endpoint to fetch the latest build.

## Typical Workflow

The download endpoint fits into the broader docsfy pipeline as the final step:

```
1. POST /api/generate          # Start documentation generation
       ↓
2. GET /api/projects/{name}    # Poll until status is "ready"
       ↓
3. GET /api/projects/{name}/download   # Download the .tar.gz
       ↓
4. Extract & deploy to your server
```

### Full Automation Example

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT="my-project"
BASE_URL="http://localhost:8000"

# 1. Trigger generation
curl -s -X POST "$BASE_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d "{\"repo_url\": \"https://github.com/myorg/myrepo\"}"

# 2. Wait for generation to complete
echo "Waiting for documentation to be generated..."
while true; do
  STATUS=$(curl -s "$BASE_URL/api/projects/$PROJECT" | python -c \
    "import sys,json; print(json.load(sys.stdin)['status'])")
  case "$STATUS" in
    ready) echo "Done!"; break ;;
    error) echo "Generation failed"; exit 1 ;;
    *)     sleep 10 ;;
  esac
done

# 3. Download the archive
curl -o "${PROJECT}-docs.tar.gz" \
  "$BASE_URL/api/projects/$PROJECT/download"

# 4. Extract and deploy
tar -xzf "${PROJECT}-docs.tar.gz" -C /var/www/
echo "Documentation deployed to /var/www/$PROJECT"
```

> **Warning:** Large repositories may produce sizable documentation archives. Ensure sufficient disk space on both the docsfy server (under `/data/projects/`) and your download destination.

## Storage Details

The archive is generated on-the-fly from the project's rendered site directory on the server filesystem:

```
/data/projects/{name}/
  plan.json              # Documentation structure from AI planner
  cache/
    pages/*.md           # Cached AI-generated markdown
  site/                  # ← This directory is packaged into the archive
    index.html
    *.html
    assets/
    search-index.json
```

The `site/` directory is produced by Stage 4 (HTML Renderer) of the generation pipeline, which converts the AI-generated markdown pages and `plan.json` structure into a polished static HTML site using Jinja2 templates with bundled CSS and JavaScript.

> **Note:** If you are running docsfy with Docker, the `/data` directory is typically mounted as a volume (e.g., `./data:/data` in `docker-compose.yaml`). The archive is generated from this persistent storage.

## Related Endpoints

| Endpoint | Description |
|----------|-------------|
| [`POST /api/generate`](./post-generate.md) | Trigger documentation generation for a repository |
| [`GET /api/projects/{name}`](./get-project.md) | Check project status and metadata before downloading |
| [`GET /api/status`](./get-status.md) | List all projects and their current generation status |
| [`GET /docs/{project}/{path}`](./get-docs.md) | Serve documentation directly from the docsfy server (alternative to self-hosting) |
