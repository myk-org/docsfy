# Docker Deployment

docsfy is designed to run as a containerized service using a multi-stage Docker build based on `python:3.12-slim`. This page covers building the image, configuring the container for production use, setting up data persistence, mounting cloud credentials, and running health checks.

## Container Overview

The docsfy container packages the FastAPI application along with all three supported AI CLI tools (Claude Code, Cursor Agent, Gemini CLI) into a single image. The container runs as a non-root user for security and is compatible with restricted platforms like OpenShift.

| Aspect | Detail |
|--------|--------|
| Base image | `python:3.12-slim` (multi-stage build) |
| Package manager | `uv` |
| Non-root user | `appuser` (GID 0, OpenShift compatible) |
| System dependencies | bash, git, curl, nodejs, npm, ca-certificates |
| Exposed port | `8000` |
| Entrypoint | `uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000` |
| Health check | `GET /health` |

## Building the Image

### Multi-Stage Dockerfile

The Dockerfile uses a multi-stage build to keep the final image lean. The build stage installs `uv` and resolves Python dependencies, while the runtime stage copies only what is needed and installs the AI CLI tools.

```dockerfile
# Build stage
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
RUN uv build

# Runtime stage
FROM python:3.12-slim

# System dependencies required by AI CLIs and git operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    git \
    curl \
    nodejs \
    npm \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install AI CLI tools (unpinned, always latest)
RUN curl -fsSL https://claude.ai/install.sh | bash
RUN curl -fsSL https://cursor.com/install | bash
RUN npm install -g @google/gemini-cli

# Create non-root user (OpenShift compatible)
RUN groupadd -r appuser && \
    useradd -r -g 0 -d /home/appuser -m appuser && \
    mkdir -p /data && \
    chown -R appuser:0 /data /home/appuser && \
    chmod -R g=u /data /home/appuser

# Copy application from builder
COPY --from=builder /app /app
WORKDIR /app

# Install the application
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
RUN uv sync --frozen --no-dev

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD ["curl", "-f", "http://localhost:8000/health"]

ENTRYPOINT ["uv", "run", "--no-sync", "uvicorn", "docsfy.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build the image with:

```bash
docker build -t docsfy .
```

> **Note:** The AI CLI tools (Claude Code, Cursor Agent, Gemini CLI) are installed unpinned and always pull the latest version at image build time. Rebuild the image periodically to pick up updates.

## Non-Root User and OpenShift Compatibility

The container runs as a non-root user named `appuser` for security hardening. The user is configured with GID 0 (the root group), which is a requirement for OpenShift compatibility.

```dockerfile
RUN groupadd -r appuser && \
    useradd -r -g 0 -d /home/appuser -m appuser && \
    mkdir -p /data && \
    chown -R appuser:0 /data /home/appuser && \
    chmod -R g=u /data /home/appuser
```

Key details of this configuration:

- **`-g 0`** — Assigns `appuser` to GID 0 (root group). OpenShift runs containers with an arbitrary UID but always assigns GID 0, so all directories must be group-writable by group 0.
- **`chmod -R g=u`** — Sets group permissions equal to user permissions, ensuring the arbitrary UID assigned by OpenShift can read and write to all required directories.
- **`/data`** — The persistent data directory is owned by `appuser:0` so it remains writable under both standard Docker and OpenShift runtimes.
- **`/home/appuser`** — The home directory stores AI CLI configurations and credentials mounted at runtime.

> **Warning:** Do not run this container with `--user root` or `USER root` in production. The non-root configuration is a security boundary that prevents container escape vulnerabilities from gaining host-level access.

## Running with Docker Compose

The recommended way to run docsfy in production is with Docker Compose. Create a `docker-compose.yaml`:

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

Start the service:

```bash
docker compose up -d
```

Or run with `docker run` directly:

```bash
docker run -d \
  --name docsfy \
  -p 8000:8000 \
  --env-file .env \
  -v ./data:/data \
  -v ~/.config/gcloud:/home/appuser/.config/gcloud:ro \
  -v ./cursor:/home/appuser/.config/cursor \
  docsfy
```

## Volume Mounts

docsfy uses three volume mounts to persist data and provide access to cloud credentials.

### Data Volume (`./data:/data`)

The primary data volume stores all persistent state:

```
/data/
├── docsfy.db                    # SQLite database (project metadata)
└── projects/
    └── {project-name}/
        ├── plan.json            # Documentation structure from AI
        ├── cache/
        │   └── pages/*.md       # AI-generated markdown (cached)
        └── site/                # Final rendered HTML
            ├── index.html
            ├── *.html
            ├── assets/
            │   ├── style.css
            │   ├── search.js
            │   ├── theme-toggle.js
            │   └── highlight.js
            └── search-index.json
```

- **`docsfy.db`** — SQLite database storing project metadata: name, repo URL, status (`generating` / `ready` / `error`), last generated timestamp, last commit SHA, and generation history.
- **`projects/`** — Each generated documentation project gets its own directory containing the AI plan, cached markdown pages, and the final rendered static HTML site.

> **Tip:** Back up the `./data` directory regularly. The SQLite database and cached markdown pages allow docsfy to perform incremental updates, only regenerating pages affected by repository changes.

### Google Cloud Credentials (`~/.config/gcloud:/home/appuser/.config/gcloud:ro`)

When using Claude via Vertex AI, docsfy needs access to Google Cloud credentials. The gcloud configuration directory is mounted read-only (`:ro`) into the container.

```yaml
volumes:
  - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

This mount provides authentication for the Vertex AI integration, which is configured via environment variables:

```bash
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

> **Warning:** Always mount cloud credentials as read-only (`:ro`). This prevents the container from modifying or deleting your local credentials if compromised.

If you are not using Vertex AI (i.e., using direct API keys instead), you can omit this volume mount entirely.

### Cursor Configuration (`./cursor:/home/appuser/.config/cursor`)

When using Cursor Agent as the AI provider, its configuration directory is mounted into the container:

```yaml
volumes:
  - ./cursor:/home/appuser/.config/cursor
```

This volume is read-write because Cursor may need to update its local state during operation.

## Environment Variables

Create a `.env` file from the example template to configure docsfy:

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

### AI Provider Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI provider to use: `claude`, `gemini`, or `cursor` |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | Timeout in minutes for AI CLI operations |

### Provider Credentials

Configure credentials for your chosen provider:

**Claude (API Key)**
```bash
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

**Claude (Vertex AI)**
```bash
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-project-id
```

When using Vertex AI, ensure the Google Cloud credentials volume is mounted and that the service account has the appropriate Vertex AI permissions.

**Gemini**
```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=...
```

**Cursor**
```bash
AI_PROVIDER=cursor
CURSOR_API_KEY=...
```

## Health Check Configuration

docsfy exposes a `GET /health` endpoint for container health monitoring. The Docker health check is configured both in the Dockerfile and in `docker-compose.yaml`:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

| Parameter | Value | Description |
|-----------|-------|-------------|
| `test` | `curl -f http://localhost:8000/health` | Sends an HTTP request to the health endpoint; fails on non-2xx responses |
| `interval` | `30s` | Time between health checks |
| `timeout` | `10s` | Maximum time to wait for a health check response |
| `retries` | `3` | Number of consecutive failures before marking the container as unhealthy |

Check the container health status with:

```bash
docker inspect --format='{{.State.Health.Status}}' docsfy
```

> **Tip:** If deploying behind a load balancer or reverse proxy, point the upstream health check at the same `/health` endpoint on port 8000.

## Production Deployment Considerations

### Reverse Proxy

In production, place docsfy behind a reverse proxy such as Nginx or Traefik to handle TLS termination, rate limiting, and request buffering. Example Nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name docs.example.com;

    ssl_certificate     /etc/ssl/certs/docs.example.com.pem;
    ssl_certificate_key /etc/ssl/private/docs.example.com.key;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Resource Limits

AI documentation generation is resource-intensive. Set appropriate resource limits in your Compose file:

```yaml
services:
  docsfy:
    build: .
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

### Logging

Control log verbosity with the `LOG_LEVEL` environment variable:

```bash
LOG_LEVEL=INFO    # Default: standard operational logging
LOG_LEVEL=DEBUG   # Verbose: includes AI CLI output and timing details
LOG_LEVEL=WARNING # Minimal: only warnings and errors
```

View container logs:

```bash
docker compose logs -f docsfy
```

### Data Backup

The `./data` directory contains all persistent state. Back it up regularly:

```bash
# Stop the container to ensure SQLite consistency
docker compose stop docsfy

# Create a backup archive
tar czf docsfy-backup-$(date +%Y%m%d).tar.gz ./data

# Restart
docker compose start docsfy
```

> **Note:** SQLite does not handle concurrent writes from multiple processes. Run only a single instance of docsfy against a given `/data` directory.

### OpenShift Deployment

No additional configuration is needed for OpenShift. The container is built with OpenShift compatibility by default:

1. The `appuser` has GID 0, matching OpenShift's arbitrary UID assignment.
2. All writable directories (`/data`, `/home/appuser`) have `g=u` permissions.
3. The container does not require any elevated capabilities or privileges.

Create an OpenShift deployment using the standard `oc` commands:

```bash
oc new-app --docker-image=your-registry/docsfy:latest \
  --name=docsfy \
  -e AI_PROVIDER=claude \
  -e ANTHROPIC_API_KEY=sk-ant-...

oc expose svc/docsfy --port=8000
```

Use OpenShift PersistentVolumeClaims for the `/data` directory to ensure documentation persists across pod restarts.
