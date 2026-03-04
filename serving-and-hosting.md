# Serving & Hosting

docsfy provides flexible options for accessing your generated documentation. You can serve docs directly through the built-in FastAPI server, download a complete static site archive for self-hosting, or deploy to any static hosting platform.

## Serving Directly from docsfy

Once documentation has been generated for a project, docsfy serves it immediately at a predictable URL path through its built-in web server.

### Accessing Generated Docs

Every project's documentation is available at:

```
GET /docs/{project}/{path}
```

For example, if you generated docs for a project named `my-api`, the documentation is accessible at:

```
http://localhost:8000/docs/my-api/
```

The server resolves `{path}` against the project's rendered site directory on disk at `/data/projects/{project-name}/site/`, serving the static HTML pages along with all bundled assets (CSS, JavaScript, search index).

### Checking Project Availability

Before accessing docs, you can verify a project's status through the API:

```bash
# List all projects and their generation status
curl http://localhost:8000/api/status

# Get details for a specific project
curl http://localhost:8000/api/projects/my-api
```

The project detail endpoint returns metadata including the generation status (`generating`, `ready`, or `error`), the last generated timestamp, the commit SHA, and the list of pages.

> **Note:** Documentation is only available at `/docs/{project}/` once the project status is `ready`. Projects with a status of `generating` or `error` will not serve docs.

### What Gets Served

The generated site at `/data/projects/{project-name}/site/` includes everything needed for a fully functional documentation experience:

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

This includes sidebar navigation, dark/light theme toggle, client-side search powered by lunr.js, code syntax highlighting via highlight.js, responsive layouts, and callout boxes.

### Running the Server

With Docker Compose (recommended):

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
      - ./cursor:/home/appuser/.config/cursor
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Or directly with uvicorn:

```bash
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

The health check endpoint at `GET /health` can be used for monitoring and load balancer integration.

## Downloading as a Static Archive

For self-hosting or offline access, docsfy provides a download endpoint that packages the entire generated site into a `.tar.gz` archive.

### Download Endpoint

```
GET /api/projects/{name}/download
```

Example usage with `curl`:

```bash
# Download the generated docs as a tar.gz archive
curl -o my-api-docs.tar.gz http://localhost:8000/api/projects/my-api/download

# Extract the archive
tar -xzf my-api-docs.tar.gz
```

The archive contains the complete contents of the `site/` directory — all HTML pages, CSS, JavaScript assets, and the search index. The extracted files are fully self-contained and require no external dependencies or server-side processing.

> **Tip:** You can use the download endpoint in CI/CD pipelines to automatically fetch updated documentation after triggering a regeneration via `POST /api/generate`.

### Automation Example

Combine generation and download in a script:

```bash
#!/bin/bash
PROJECT="my-api"
DOCSFY_URL="http://localhost:8000"

# Trigger generation
curl -X POST "$DOCSFY_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/my-api"}'

# Poll until ready
while true; do
  STATUS=$(curl -s "$DOCSFY_URL/api/projects/$PROJECT" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  if [ "$STATUS" = "ready" ]; then
    break
  elif [ "$STATUS" = "error" ]; then
    echo "Generation failed"
    exit 1
  fi
  sleep 10
done

# Download the archive
curl -o docs.tar.gz "$DOCSFY_URL/api/projects/$PROJECT/download"
```

## Hosting on Static Platforms

Since docsfy produces fully static HTML sites, the downloaded archive can be deployed to any static hosting platform without modification.

### Nginx

Serve the extracted archive with a minimal nginx configuration:

```nginx
server {
    listen 80;
    server_name docs.example.com;

    root /var/www/docs;
    index index.html;

    location / {
        try_files $uri $uri/ $uri.html =404;
    }
}
```

```bash
# Extract docs to the serving directory
tar -xzf my-api-docs.tar.gz -C /var/www/docs
```

### GitHub Pages

Deploy to GitHub Pages by extracting the archive into a repository:

```bash
# Clone your GitHub Pages repository
git clone https://github.com/org/org.github.io.git
cd org.github.io

# Extract docs into a subdirectory
mkdir -p my-api
tar -xzf my-api-docs.tar.gz -C my-api

# Push to deploy
git add my-api/
git commit -m "Update my-api documentation"
git push origin main
```

> **Tip:** Use a GitHub Actions workflow to automate this — trigger docsfy generation on push events, download the archive, and commit the result to your Pages repository.

### Amazon S3 + CloudFront

Upload the extracted files to an S3 bucket configured for static hosting:

```bash
# Extract the archive
tar -xzf my-api-docs.tar.gz -C ./docs-output

# Sync to S3
aws s3 sync ./docs-output s3://my-docs-bucket/my-api/ \
  --delete \
  --cache-control "max-age=3600"
```

### Cloudflare Pages / Netlify / Vercel

These platforms can serve the static output directly. Extract the archive and point the platform's build output directory to the extracted folder, or use their CLI tools:

```bash
# Netlify
tar -xzf my-api-docs.tar.gz -C ./dist
netlify deploy --prod --dir=./dist

# Vercel
tar -xzf my-api-docs.tar.gz -C ./out
vercel --prod
```

### Docker (Standalone)

Package the generated docs into a lightweight container for isolated deployment:

```dockerfile
FROM nginx:alpine
COPY site/ /usr/share/nginx/html/
EXPOSE 80
```

```bash
tar -xzf my-api-docs.tar.gz -C ./site
docker build -t my-api-docs .
docker run -p 8080:80 my-api-docs
```

## Persistent Storage

docsfy stores all generated documentation on the filesystem under `/data/projects/`. When running with Docker, mount this path as a volume to persist docs across container restarts:

```yaml
volumes:
  - ./data:/data
```

This directory contains:

| Path | Purpose |
|------|---------|
| `/data/docsfy.db` | SQLite database with project metadata and generation history |
| `/data/projects/{name}/plan.json` | Documentation structure produced by the AI planner |
| `/data/projects/{name}/cache/pages/*.md` | Cached markdown pages for incremental updates |
| `/data/projects/{name}/site/` | Rendered static HTML site (what gets served and downloaded) |

> **Warning:** Deleting the `/data` volume removes all generated documentation. The `DELETE /api/projects/{name}` endpoint removes a single project and its docs. Use these operations with care.

## Incremental Updates

docsfy tracks the last commit SHA for each project. When you re-trigger generation for a project, it:

1. Fetches the latest repository state
2. Compares the current commit SHA against the stored SHA
3. Re-runs the AI planner to detect documentation structure changes
4. Regenerates only the pages affected by code changes

This means the docs served at `/docs/{project}/` and available via the download endpoint stay current with minimal regeneration overhead. Cached markdown pages at `cache/pages/*.md` are reused when their content is unaffected by repository changes.
