# Docker Configuration

docsfy runs as a containerized FastAPI service using Docker. This page covers the Dockerfile, docker-compose.yaml, volume mounts, health checks, port mapping, and environment configuration.

## Dockerfile

The Dockerfile uses a `python:3.12-slim` base image with a multi-stage build. It runs as a non-root user for security and OpenShift compatibility.

### Base Image and System Dependencies

The container installs the system packages required for repository cloning, AI CLI tools, and HTTPS communication:

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    git \
    curl \
    nodejs \
    npm \
    ca-certificates
```

- **git** — clones target repositories (shallow clone with `--depth 1`)
- **nodejs / npm** — required for the Gemini CLI installation
- **curl** — used to install AI CLIs and for the Docker health check
- **ca-certificates** — ensures HTTPS connectivity for cloning and API calls

### Non-Root User

The container creates a dedicated `appuser` with GID 0 for OpenShift compatibility:

```dockerfile
RUN useradd --create-home --gid 0 appuser
USER appuser
```

> **Note:** Setting GID 0 (root group) is an OpenShift convention. It does not grant root privileges — it allows the container to run under OpenShift's arbitrary UID assignment while still having access to necessary group-owned files.

### Package Manager

docsfy uses `uv` as its Python package manager. No pip is used in the build or at runtime.

### AI CLI Installation

The Dockerfile installs all three supported AI CLI tools. These are intentionally **unpinned** so each build pulls the latest version:

```dockerfile
# Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Cursor Agent
RUN curl -fsSL https://cursor.com/install | bash

# Gemini CLI
RUN npm install -g @google/gemini-cli
```

> **Warning:** Because AI CLI versions are unpinned, builds are not fully reproducible. This is a deliberate design choice to always use the latest AI capabilities. Pin specific versions in a fork if you need deterministic builds.

### Entrypoint

The container starts the FastAPI application via uvicorn, binding to all interfaces on port 8000:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

The `--no-sync` flag tells `uv` to skip dependency resolution at startup, relying on packages already installed during the build stage.

## docker-compose.yaml

The full Compose configuration defines the service, port mapping, environment, volumes, and health check:

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

### Port Mapping

| Host Port | Container Port | Protocol | Purpose |
|-----------|---------------|----------|---------|
| 8000 | 8000 | TCP | FastAPI application (API + static doc serving) |

The application serves both the REST API endpoints (`/api/*`) and the generated documentation sites (`/docs/{project}/*`) on the same port.

To use a different host port, change only the left side of the mapping:

```yaml
ports:
  - "3000:8000"  # access via http://localhost:3000
```

## Volume Mounts

The Compose file defines three volume mounts, each serving a distinct purpose.

### Data Persistence (`./data:/data`)

```yaml
- ./data:/data
```

This is the primary read-write volume that persists all generated content and metadata across container restarts. It maps the `./data` directory on the host to `/data` inside the container.

The container stores two types of data here:

**SQLite Database** at `/data/docsfy.db` — project metadata including:
- Project name and repository URL
- Generation status (`generating`, `ready`, or `error`)
- Last generated timestamp and commit SHA
- Generation history and logs

**Project Files** under `/data/projects/` — generated documentation:

```
/data/projects/{project-name}/
  plan.json             # documentation structure from AI
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

> **Warning:** Deleting or losing the `./data` directory means losing all generated documentation and project history. Back up this directory in production deployments.

> **Tip:** The `cache/pages/*.md` files enable incremental updates. When a repository changes, docsfy compares commit SHAs and regenerates only affected pages rather than rebuilding the entire site.

### Google Cloud Credentials (`~/.config/gcloud:ro`)

```yaml
- ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

This volume mounts your host's Google Cloud SDK configuration into the container. It is required when using **Claude via Vertex AI** as the AI provider.

Key details:
- Mounted as **read-only** (`:ro`) — the container cannot modify your host credentials
- Maps to the `appuser` home directory inside the container
- Only needed when `CLAUDE_CODE_USE_VERTEX=1` is set in your `.env` file

If you are using API key authentication (e.g., `ANTHROPIC_API_KEY`) rather than Vertex AI, this volume mount can be safely removed.

### Cursor Agent Configuration (`./cursor`)

```yaml
- ./cursor:/home/appuser/.config/cursor
```

This volume mounts configuration for the Cursor Agent AI provider. Unlike the gcloud mount, this is **read-write** — Cursor may write configuration or session state during operation.

If you are not using Cursor as your AI provider, this volume mount can be safely removed.

### Volume Mount Summary

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `./data` | `/data` | read-write | SQLite database and generated documentation |
| `~/.config/gcloud` | `/home/appuser/.config/gcloud` | read-only | Google Cloud credentials (Vertex AI) |
| `./cursor` | `/home/appuser/.config/cursor` | read-write | Cursor Agent configuration |

## Health Checks

The application exposes a `GET /health` endpoint used by both Docker's built-in health check mechanism and external monitoring.

### Docker Health Check Configuration

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

| Parameter | Value | Description |
|-----------|-------|-------------|
| `test` | `curl -f http://localhost:8000/health` | Sends an HTTP request to the health endpoint; `-f` makes curl return a non-zero exit code on HTTP errors |
| `interval` | 30s | Time between consecutive health checks |
| `timeout` | 10s | Maximum time to wait for a response before marking the check as failed |
| `retries` | 3 | Number of consecutive failures required before the container is marked `unhealthy` |

With these settings, a container will be marked unhealthy after **90 seconds** of continuous failure (3 retries × 30s interval).

> **Tip:** You can check the container health status at any time with:
> ```bash
> docker inspect --format='{{.State.Health.Status}}' docsfy-docsfy-1
> ```

## Environment Variables

Configuration is managed through a `.env` file loaded via the `env_file` directive in docker-compose.yaml. Create your `.env` file based on this template:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

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

### AI Provider Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI backend to use: `claude`, `gemini`, or `cursor` |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | Maximum time in **minutes** for a single AI CLI invocation |

### Authentication Variables

Configure credentials based on your chosen provider:

**Claude with API Key:**
```bash
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

**Claude with Vertex AI:**
```bash
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

> **Note:** When using Vertex AI, ensure the `~/.config/gcloud` volume mount is configured in your docker-compose.yaml and that your local gcloud credentials are valid (`gcloud auth application-default login`).

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

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

## Quick Start

1. **Clone the repository and create your environment file:**

   ```bash
   git clone <repo-url> && cd docsfy
   cp .env.example .env
   ```

2. **Configure your AI provider credentials** in the `.env` file (see [Environment Variables](#environment-variables) above).

3. **Create the data directory:**

   ```bash
   mkdir -p data
   ```

4. **Build and start the container:**

   ```bash
   docker compose up --build -d
   ```

5. **Verify the service is healthy:**

   ```bash
   docker compose ps
   # Look for "(healthy)" in the STATUS column
   ```

6. **Access the API** at `http://localhost:8000`.

## Production Considerations

### Persistent Storage

In production, consider using a named Docker volume instead of a bind mount for the data directory:

```yaml
volumes:
  docsfy-data:

services:
  docsfy:
    volumes:
      - docsfy-data:/data
```

This provides better isolation and is managed by the Docker storage driver rather than the host filesystem.

### Resource Limits

AI CLI invocations can be resource-intensive. Consider adding resource constraints:

```yaml
services:
  docsfy:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 1G
```

### Restarting on Failure

Add a restart policy to ensure the service recovers from crashes:

```yaml
services:
  docsfy:
    restart: unless-stopped
```
