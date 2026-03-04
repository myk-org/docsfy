# Docker Deployment

docsfy is designed to run as a containerized service. This page covers building the Docker image, configuring Docker Compose, managing volumes and credentials, health checks, and production deployment best practices.

## Prerequisites

- Docker 20.10+ and Docker Compose v2
- An API key for your chosen AI provider (Claude, Gemini, or Cursor)
- For Vertex AI authentication: Google Cloud credentials configured on the host

## Dockerfile

docsfy uses a multi-stage build based on `python:3.12-slim`. The image includes all three AI CLI tools so you can switch providers at runtime via environment variables.

| Aspect | Detail |
|--------|--------|
| Base image | `python:3.12-slim` (multi-stage build) |
| Package manager | `uv` (no pip) |
| Non-root user | `appuser` with GID 0 (OpenShift compatible) |
| System dependencies | bash, git, curl, nodejs, npm, ca-certificates |
| Entrypoint | `uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000` |
| Exposed port | `8000` |

### AI CLI Tools

All three AI CLI tools are installed at build time (unpinned, always latest):

```dockerfile
# Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Cursor Agent
RUN curl -fsSL https://cursor.com/install | bash

# Gemini CLI
RUN npm install -g @google/gemini-cli
```

> **Note:** AI CLI tools are installed without pinned versions to ensure you always get the latest capabilities. Rebuild the image periodically to pick up updates.

### Building the Image

```bash
docker build -t docsfy .
```

## Docker Compose

The recommended way to run docsfy is with Docker Compose, which handles volume mounts, environment configuration, and health checks in a single declarative file.

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

Verify it's running:

```bash
docker compose ps
curl http://localhost:8000/health
```

## Volume Mounts

docsfy uses three volume mounts to persist data and inject credentials into the container.

### Data Volume (`./data:/data`)

The primary storage volume. All generated documentation and the SQLite database live here.

```
/data/
├── docsfy.db                           # SQLite database (project metadata)
└── projects/
    └── {project-name}/
        ├── plan.json                   # Documentation structure from AI
        ├── cache/
        │   └── pages/*.md              # AI-generated markdown (cached)
        └── site/                       # Final rendered HTML
            ├── index.html
            ├── *.html
            ├── assets/
            │   ├── style.css
            │   ├── search.js
            │   ├── theme-toggle.js
            │   └── highlight.js
            └── search-index.json
```

The SQLite database (`docsfy.db`) stores:

- Project name and repository URL
- Generation status (`generating`, `ready`, or `error`)
- Last generated timestamp and last commit SHA
- Generation history and logs

> **Warning:** Do not delete the `data` directory while the container is running. The SQLite database and cached markdown files are required for incremental updates.

### Google Cloud Credentials (`~/.config/gcloud:/home/appuser/.config/gcloud:ro`)

Required only when using Claude via Vertex AI (`CLAUDE_CODE_USE_VERTEX=1`). This mount injects your host's Google Cloud SDK credentials into the container as **read-only**.

```bash
# Ensure credentials exist on the host first
gcloud auth application-default login
```

> **Tip:** The `:ro` flag ensures the container cannot modify your host credentials.

### Cursor Configuration (`./cursor:/home/appuser/.config/cursor`)

Required only when using Cursor as the AI provider. This mount persists Cursor's configuration and authentication state across container restarts.

```bash
# Create the directory before first run
mkdir -p ./cursor
```

## Environment Variables

Create a `.env` file from the example template to configure your deployment:

```bash
# AI Configuration
AI_PROVIDER=claude                      # Options: claude, cursor, gemini
AI_MODEL=claude-opus-4-6                # Model specification
AI_CLI_TIMEOUT=60                       # Timeout per AI invocation (minutes)

# Claude - Option 1: API Key Authentication
# ANTHROPIC_API_KEY=sk-ant-...

# Claude - Option 2: Vertex AI Authentication
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=us-east5
# ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project

# Gemini
# GEMINI_API_KEY=AIza...

# Cursor
# CURSOR_API_KEY=cur-...

# Logging
LOG_LEVEL=INFO
```

### Provider-Specific Configuration

| Provider | Required Variables | Optional Volume |
|----------|-------------------|-----------------|
| Claude (API key) | `AI_PROVIDER=claude`, `ANTHROPIC_API_KEY` | — |
| Claude (Vertex AI) | `AI_PROVIDER=claude`, `CLAUDE_CODE_USE_VERTEX=1`, `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID` | `~/.config/gcloud` (read-only) |
| Gemini | `AI_PROVIDER=gemini`, `GEMINI_API_KEY` | — |
| Cursor | `AI_PROVIDER=cursor`, `CURSOR_API_KEY` | `./cursor` |

> **Warning:** Never commit your `.env` file to version control. Add it to `.gitignore` and `.dockerignore`.

## Health Checks

docsfy exposes a `GET /health` endpoint for container orchestration and monitoring.

### Docker Compose Health Check

The health check configuration in `docker-compose.yaml`:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s          # Check every 30 seconds
  timeout: 10s           # Fail if no response within 10 seconds
  retries: 3             # Mark unhealthy after 3 consecutive failures
```

### Checking Health Status

```bash
# Via Docker
docker inspect --format='{{.State.Health.Status}}' docsfy-docsfy-1

# Via curl
curl -f http://localhost:8000/health
```

### Kubernetes Liveness/Readiness Probes

If deploying to Kubernetes, configure probes against the same endpoint:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 30
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Production Deployment

### Running with a Pre-Built Image

For production, build and tag the image explicitly rather than using `build: .`:

```yaml
services:
  docsfy:
    image: docsfy:1.0.0
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - docsfy-data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  docsfy-data:
```

> **Tip:** Use a named volume (`docsfy-data`) instead of a bind mount for production deployments. Named volumes are managed by Docker and are less likely to encounter permission issues.

### Restart Policy

Always set a restart policy for production:

```yaml
restart: unless-stopped
```

This ensures the container automatically recovers from crashes while still respecting manual `docker compose stop` commands.

### Resource Limits

Documentation generation is CPU- and memory-intensive due to AI CLI invocations. Set appropriate resource constraints:

```yaml
services:
  docsfy:
    # ...
    deploy:
      resources:
        limits:
          cpus: "4.0"
          memory: 4G
        reservations:
          cpus: "1.0"
          memory: 1G
```

### Reverse Proxy

In production, place docsfy behind a reverse proxy (nginx, Caddy, Traefik) to handle TLS termination, rate limiting, and static asset caching.

Example with Traefik labels:

```yaml
services:
  docsfy:
    # ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.docsfy.rule=Host(`docs.example.com`)"
      - "traefik.http.routers.docsfy.tls.certresolver=letsencrypt"
      - "traefik.http.services.docsfy.loadbalancer.server.port=8000"
```

### Logging

Control log verbosity via the `LOG_LEVEL` environment variable:

```bash
LOG_LEVEL=INFO      # Default — request logs and generation status
LOG_LEVEL=DEBUG     # Verbose — includes AI CLI output and subprocess details
LOG_LEVEL=WARNING   # Quiet — only warnings and errors
```

View container logs:

```bash
# Follow logs
docker compose logs -f docsfy

# Last 100 lines
docker compose logs --tail 100 docsfy
```

### Backup Strategy

Back up the `/data` volume regularly to preserve generated documentation and project metadata:

```bash
# Stop the service to ensure SQLite consistency
docker compose stop docsfy

# Create a backup archive
tar -czf docsfy-backup-$(date +%Y%m%d).tar.gz ./data/

# Restart
docker compose start docsfy
```

> **Tip:** For zero-downtime backups, use SQLite's `.backup` command on the database file while the service is running, then archive the projects directory separately.

### Security Considerations

The docsfy container follows security best practices:

- **Non-root execution** — The container runs as `appuser` (not root), with GID 0 for OpenShift compatibility
- **Read-only credential mounts** — GCP credentials are mounted with the `:ro` flag
- **No privileged mode** — The container does not require `--privileged`
- **Secrets via environment** — API keys are injected through `.env` files, never baked into the image

For additional hardening:

```yaml
services:
  docsfy:
    # ...
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
```

> **Warning:** When using `read_only: true`, ensure the `/data` volume is properly mounted as writable, and add a `tmpfs` mount at `/tmp` since the generation pipeline uses temporary directories for cloning repositories.

### OpenShift Deployment

docsfy is designed for OpenShift compatibility. The `appuser` account uses GID 0, which allows OpenShift's random UID assignment to work correctly:

```yaml
securityContext:
  runAsNonRoot: true
```

No special SCCs (Security Context Constraints) are required.

## Quick Reference

| Action | Command |
|--------|---------|
| Build image | `docker build -t docsfy .` |
| Start service | `docker compose up -d` |
| Stop service | `docker compose stop` |
| View logs | `docker compose logs -f docsfy` |
| Check health | `curl http://localhost:8000/health` |
| Rebuild image | `docker compose build --no-cache` |
| Remove everything | `docker compose down -v` |
