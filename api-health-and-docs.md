# Health Check & Doc Serving

docsfy exposes two read-only GET endpoints for operational monitoring and serving generated documentation to end users. These endpoints require no authentication and are available as soon as the FastAPI server starts.

## Health Check — `GET /health`

The `/health` endpoint provides a lightweight probe for container orchestrators, load balancers, and monitoring systems to verify that the docsfy service is running and accepting requests.

### Basic Usage

```bash
curl -f http://localhost:8000/health
```

The `-f` flag causes curl to return a non-zero exit code on HTTP error responses, making it suitable for use in shell scripts and health check commands.

### Docker Compose Health Check

docsfy's `docker-compose.yaml` configures automatic health checking against this endpoint:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

| Parameter | Value | Description |
|-----------|-------|-------------|
| `interval` | `30s` | Time between consecutive health checks |
| `timeout` | `10s` | Maximum time to wait for a response before marking the check as failed |
| `retries` | `3` | Number of consecutive failures before the container is considered unhealthy |

With these defaults, Docker will declare the container unhealthy after **90 seconds** of consecutive failures (3 retries × 30s interval).

> **Note:** The health check requires `curl` to be available inside the container. The docsfy Dockerfile includes `curl` in its system dependencies (`bash, git, curl, nodejs, npm, ca-certificates`), so no additional installation is needed.

### Kubernetes Liveness Probe

If deploying to Kubernetes, configure a liveness probe targeting the same endpoint:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3
```

### Server Binding

The health check endpoint is served by uvicorn on all interfaces at port `8000`, as defined by the container entrypoint:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

> **Tip:** When running behind a reverse proxy, point your upstream health checks to the internal container port (`8000`), not the externally mapped port.

---

## Doc Serving — `GET /docs/{project}/{path}`

The `/docs/{project}/{path}` endpoint serves the generated static HTML documentation sites directly from the docsfy API. After a project's documentation has been generated via `POST /api/generate`, the rendered site is immediately available at this path.

### URL Structure

```
GET /docs/{project}/{path}
```

| Parameter | Description | Example |
|-----------|-------------|---------|
| `{project}` | The project name as registered during generation | `my-api` |
| `{path}` | Path to a specific page or asset within the generated site | `index.html`, `getting-started.html`, `assets/style.css` |

### Accessing a Project's Documentation

Once a project reaches `ready` status, its documentation is served from the filesystem at `/data/projects/{project-name}/site/`:

```bash
# Serve the landing page
curl http://localhost:8000/docs/my-api/index.html

# Serve a specific documentation page
curl http://localhost:8000/docs/my-api/getting-started.html

# Serve a static asset
curl http://localhost:8000/docs/my-api/assets/style.css
```

In a browser, navigate directly to:

```
http://localhost:8000/docs/my-api/
```

### Filesystem Layout

Each project's rendered site is stored under `/data/projects/` following this structure:

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

The `GET /docs/{project}/{path}` endpoint maps directly into the `site/` directory. A request to `/docs/my-api/assets/style.css` resolves to the file at `/data/projects/my-api/site/assets/style.css`.

### Client-Side Features

Every generated documentation site includes bundled assets that provide a rich browsing experience with no external dependencies:

| Feature | Asset | Description |
|---------|-------|-------------|
| Sidebar navigation | Built into HTML via Jinja2 | Hierarchical page navigation generated from `plan.json` |
| Dark/light theme | `theme-toggle.js` | User-togglable color scheme |
| Client-side search | `search.js` + `search-index.json` | Full-text search across all pages without server round-trips |
| Code highlighting | `highlight.js` | Syntax highlighting for code blocks |
| Responsive design | `style.css` | Mobile-friendly layout with card layouts and callout boxes |

> **Tip:** Since the rendered site is fully static HTML with bundled assets, you can also download it as a `.tar.gz` archive via `GET /api/projects/{name}/download` and host it on any static file server (Nginx, S3, GitHub Pages, etc.).

### Project Status and Availability

Documentation is only available for serving when the project's status is `ready`. The project status lifecycle is:

| Status | Description | Docs Available? |
|--------|-------------|-----------------|
| `generating` | AI pipeline is actively producing documentation | No |
| `ready` | Generation completed successfully | Yes |
| `error` | Generation failed | No |

Check a project's current status before attempting to serve its docs:

```bash
# List all projects and their statuses
curl http://localhost:8000/api/status

# Get details for a specific project
curl http://localhost:8000/api/projects/my-api
```

> **Warning:** Requesting docs for a project that is still in `generating` status or that does not exist will result in an error response. Always verify the project status via `GET /api/status` or `GET /api/projects/{name}` before linking to documentation URLs.

### Persistence via Volume Mount

The generated documentation persists across container restarts through a Docker volume mount:

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

The `./data:/data` volume mount ensures that both the SQLite database (`/data/docsfy.db`) and all generated project files (`/data/projects/`) survive container restarts and redeployments.

> **Note:** If the volume is not mounted, all generated documentation will be lost when the container stops.

### Incremental Updates

When documentation is regenerated for an existing project, docsfy uses an incremental update strategy to minimize unnecessary AI calls:

1. The last commit SHA is tracked per project in the SQLite database
2. On re-generation, the current repo SHA is compared against the stored SHA
3. If the repository has changed, the AI Planner re-evaluates the doc structure
4. Only pages whose source content may be affected are regenerated
5. If the plan structure is unchanged, only pages mapping to changed files are rebuilt

The served documentation at `/docs/{project}/` automatically reflects the latest successful generation — no restart or cache invalidation is required.

### Reverse Proxy Configuration

When serving docsfy behind a reverse proxy, ensure the `/docs/` path prefix is forwarded correctly. Example Nginx configuration:

```nginx
location /docs/ {
    proxy_pass http://docsfy:8000/docs/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /health {
    proxy_pass http://docsfy:8000/health;
}
```

> **Tip:** Both `/health` and `/docs/{project}/{path}` are read-only GET endpoints, making them safe to cache at the reverse proxy layer for improved performance.
