# API Overview

docsfy exposes a REST API built on [FastAPI](https://fastapi.tiangolo.com/) for generating, managing, and serving AI-powered documentation sites from GitHub repositories. This page covers the essentials for interacting with the API: base URL, request and response conventions, authentication, and common patterns.

## Base URL

The docsfy server listens on port **8000** by default. All management endpoints are prefixed with `/api/`, while generated documentation is served under `/docs/`.

```
http://localhost:8000
```

When running via Docker Compose, the port mapping is configured in `docker-compose.yaml`:

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

The server is started with uvicorn bound to all interfaces:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

> **Tip:** FastAPI automatically generates interactive API documentation at `/docs` (Swagger UI) and `/redoc` (ReDoc). Use these to explore and test endpoints directly in your browser.

## Endpoints at a Glance

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details (last generated, commit SHA, pages) |
| `DELETE` | `/api/projects/{name}` | Remove a project and its generated docs |
| `GET` | `/api/projects/{name}/download` | Download the generated site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve generated static HTML documentation |
| `GET` | `/health` | Health check |

## Request Format

The API accepts **JSON** request bodies for endpoints that require input. Set the `Content-Type` header accordingly:

```
Content-Type: application/json
```

### Example: Start Documentation Generation

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/repo"}'
```

Path parameters use standard URL segments. For example, to query a specific project:

```bash
curl http://localhost:8000/api/projects/my-project
```

## Response Format

All API responses are returned as **JSON** with the `Content-Type: application/json` header, with two exceptions:

- **`GET /docs/{project}/{path}`** — returns static HTML (`text/html`)
- **`GET /api/projects/{name}/download`** — returns a `.tar.gz` archive (`application/gzip`)

### Project Status Values

Project status is tracked in SQLite and returned in API responses. A project will be in one of three states:

| Status | Description |
|--------|-------------|
| `generating` | Documentation generation is in progress |
| `ready` | Generation complete; docs are available for viewing or download |
| `error` | Generation failed; check project details for error information |

### Example: List Project Status

```bash
curl http://localhost:8000/api/status
```

```json
[
  {
    "name": "my-project",
    "repo_url": "https://github.com/owner/repo",
    "status": "ready",
    "last_generated": "2026-03-04T12:30:00Z",
    "last_commit_sha": "a1b2c3d"
  }
]
```

### Example: Get Project Details

```bash
curl http://localhost:8000/api/projects/my-project
```

```json
{
  "name": "my-project",
  "repo_url": "https://github.com/owner/repo",
  "status": "ready",
  "last_generated": "2026-03-04T12:30:00Z",
  "last_commit_sha": "a1b2c3d",
  "pages": ["index", "getting-started", "api-overview", "configuration"]
}
```

## Health Check

The `/health` endpoint provides a simple liveness check, used by Docker's built-in health check and orchestration systems:

```bash
curl http://localhost:8000/health
```

The Docker Compose health check is configured as:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Authentication

The docsfy API itself does **not** require authentication to call. However, the server must be configured with credentials for the **AI provider** it uses to generate documentation.

### AI Provider Credentials

docsfy supports three AI providers. Configure credentials via environment variables in your `.env` file:

**Claude (default provider):**

```bash
# Option 1: API Key
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...

# Option 2: Google Cloud Vertex AI
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

**Gemini:**

```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=...
```

**Cursor:**

```bash
AI_PROVIDER=cursor
CURSOR_API_KEY=...
```

> **Warning:** Without valid AI provider credentials, the `/api/generate` endpoint will fail. docsfy performs an availability check before starting generation by sending a lightweight prompt to the configured provider.

### Private Repository Access

docsfy clones repositories using system git credentials. For private repositories, ensure the server environment has appropriate access configured:

- **HTTPS:** Git credential helper or token-based authentication
- **SSH:** SSH keys available to the `appuser` running the container

When using Docker, mount credentials as read-only volumes:

```yaml
volumes:
  - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
  - ./cursor:/home/appuser/.config/cursor
```

## Configuration Reference

All configuration is handled through environment variables. Here is the complete set of options from the `.env.example`:

```bash
# AI Configuration
AI_PROVIDER=claude                # claude | gemini | cursor
AI_MODEL=claude-opus-4-6[1m]     # Model identifier for the chosen provider
AI_CLI_TIMEOUT=60                 # Timeout in minutes for AI CLI operations

# Claude - Option 1: API Key
# ANTHROPIC_API_KEY=

# Claude - Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=
# ANTHROPIC_VERTEX_PROJECT_ID=

# Gemini
# GEMINI_API_KEY=

# Cursor
# CURSOR_API_KEY=

# Logging
LOG_LEVEL=INFO
```

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI provider to use for generation |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | Maximum time (in minutes) for each AI CLI invocation |
| `LOG_LEVEL` | `INFO` | Application log level |

## Downloading Generated Sites

The download endpoint packages the complete generated documentation site into a `.tar.gz` archive for self-hosting:

```bash
curl -O http://localhost:8000/api/projects/my-project/download
```

The archive contains the full static site from `/data/projects/{name}/site/`, including:

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

> **Tip:** The downloaded archive is a fully self-contained static site. You can deploy it to any static hosting provider (GitHub Pages, Netlify, S3, Nginx) without any runtime dependencies.

## Deleting a Project

To remove a project and all its generated documentation:

```bash
curl -X DELETE http://localhost:8000/api/projects/my-project
```

> **Warning:** This permanently removes the project metadata from the database and deletes all generated files from the filesystem. This action cannot be undone.

## Next Steps

- See the **Generation Pipeline** page for details on how docsfy transforms a repository into documentation
- See the **Configuration** page for advanced deployment options
- See the **AI Providers** page for provider-specific setup and tuning
