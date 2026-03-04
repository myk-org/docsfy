# Docker & Deployment

docsfy ships as a single Docker container that bundles the FastAPI service, AI CLI tools, and all runtime dependencies. This page covers the Dockerfile internals, docker-compose configuration, persistent storage, health checks, and running in OpenShift or other restricted environments.

## Dockerfile

The image uses a multi-stage build on `python:3.12-slim` with `uv` as the package manager.

### Base Image and System Dependencies

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    git \
    curl \
    nodejs \
    npm \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*
```

The image includes `git` for repository cloning, `curl` for health checks and CLI installers, and `nodejs`/`npm` for the Gemini CLI.

### AI CLI Installation

All three supported AI CLI tools are installed at build time. Versions are unpinned to always pull the latest release:

```dockerfile
# Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Cursor Agent
RUN curl -fsSL https://cursor.com/install | bash

# Gemini CLI
RUN npm install -g @google/gemini-cli
```

> **Note:** Because CLI versions are unpinned, image builds are not fully reproducible. Pin to a specific version in production if you need deterministic builds.

### Non-root User (OpenShift Compatible)

The image creates a non-root user `appuser` with GID 0, which is required for OpenShift compatibility:

```dockerfile
RUN groupadd -r appuser && \
    useradd -r -g 0 -m -d /home/appuser -s /bin/bash appuser && \
    mkdir -p /data && \
    chown -R appuser:0 /data && \
    chmod -R g=u /data /home/appuser

USER appuser
WORKDIR /home/appuser
```

Setting the group to `0` (root GID) allows OpenShift's arbitrary UID assignment to work correctly — the container runs as a non-root user, but files remain accessible because the group permissions mirror user permissions (`g=u`).

### Package Installation with uv

```dockerfile
COPY --chown=appuser:0 pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=appuser:0 . .
RUN uv sync --frozen --no-dev
```

> **Tip:** The two-step `COPY` + `uv sync` pattern leverages Docker layer caching — dependency layers are only rebuilt when `pyproject.toml` or `uv.lock` change, not on every source code edit.

### Entrypoint

The container starts uvicorn bound to all interfaces on port 8000:

```dockerfile
EXPOSE 8000

ENTRYPOINT ["uv", "run", "--no-sync", "uvicorn", "docsfy.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The `--no-sync` flag skips dependency resolution at startup since packages were already installed during the build.

### Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

The `/health` endpoint returns a simple status response that Docker uses to determine container health.

## docker-compose.yaml

The full Compose configuration for running docsfy:

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

Rebuild after code changes:

```bash
docker compose up -d --build
```

## Volume Mounts

docsfy uses three volume mounts for persistent data and credentials.

### Data Volume (`./data:/data`)

The primary persistent volume stores all generated documentation and the SQLite database:

```
/data/
  docsfy.db                          # SQLite metadata database
  projects/
    {project-name}/
      plan.json                      # AI-generated doc structure
      cache/
        pages/*.md                   # AI-generated markdown (cached for incremental updates)
      site/                          # Final rendered static HTML
        index.html
        *.html
        assets/
          style.css
          search.js
          theme-toggle.js
          highlight.js
        search-index.json
```

The SQLite database at `/data/docsfy.db` tracks:

- Project name and repository URL
- Generation status (`generating`, `ready`, or `error`)
- Last generated timestamp and commit SHA
- Generation history and logs

> **Warning:** The `./data` directory must be writable by the container user. If running with a non-root UID (e.g., on OpenShift), ensure the directory has group-writable permissions: `chmod -R g+w ./data`.

### Google Cloud Credentials (`~/.config/gcloud:/home/appuser/.config/gcloud:ro`)

Mounted read-only (`:ro`) when using Claude via Vertex AI. This volume passes your local `gcloud` Application Default Credentials into the container.

This mount is only needed when `CLAUDE_CODE_USE_VERTEX=1` is set. If you use API key authentication instead, this volume can be omitted.

### Cursor Configuration (`./cursor:/home/appuser/.config/cursor`)

Stores Cursor CLI configuration and credentials. This mount is read-write so the Cursor agent can persist session state.

This mount is only needed when `AI_PROVIDER=cursor`. It can be omitted for other providers.

> **Tip:** Only mount the credential volumes you actually need. If you're using Claude with an API key, you can simplify your Compose file to just the data volume:
> ```yaml
> volumes:
>   - ./data:/data
> ```

## Environment Variables

Create a `.env` file from the example template. All variables have sensible defaults except provider-specific API keys.

```bash
# AI Configuration
AI_PROVIDER=claude                    # Options: claude, gemini, cursor
AI_MODEL=claude-opus-4-6[1m]         # Model identifier for the chosen provider
AI_CLI_TIMEOUT=60                     # Timeout in minutes (default: 60)

# Claude - Option 1: API Key
# ANTHROPIC_API_KEY=sk-ant-...

# Claude - Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=us-central1
# ANTHROPIC_VERTEX_PROJECT_ID=my-project

# Gemini
# GEMINI_API_KEY=...

# Cursor
# CURSOR_API_KEY=...

# Logging
LOG_LEVEL=INFO                        # Options: DEBUG, INFO, WARNING, ERROR
```

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI backend: `claude`, `gemini`, or `cursor` |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | Maximum minutes per AI CLI invocation |
| `ANTHROPIC_API_KEY` | — | Claude API key (mutually exclusive with Vertex AI) |
| `CLAUDE_CODE_USE_VERTEX` | — | Set to `1` to use Vertex AI for Claude |
| `CLOUD_ML_REGION` | — | Google Cloud region for Vertex AI |
| `ANTHROPIC_VERTEX_PROJECT_ID` | — | Google Cloud project ID for Vertex AI |
| `GEMINI_API_KEY` | — | API key for Gemini CLI |
| `CURSOR_API_KEY` | — | API key for Cursor Agent |
| `LOG_LEVEL` | `INFO` | Application log level |

> **Warning:** Never commit your `.env` file to version control. Add it to `.gitignore` and distribute credentials through a secrets manager in production.

## Health Checks

The `/health` endpoint provides a lightweight liveness check for container orchestrators.

### Docker Health Check

The Dockerfile and `docker-compose.yaml` both configure the same health check:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

- **interval**: Checks every 30 seconds
- **timeout**: Each check must respond within 10 seconds
- **retries**: The container is marked unhealthy after 3 consecutive failures

Inspect health status:

```bash
docker inspect --format='{{.State.Health.Status}}' docsfy-docsfy-1
```

### Kubernetes / OpenShift Probes

When deploying to Kubernetes or OpenShift, map the health endpoint to liveness and readiness probes:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

## OpenShift-Compatible Non-root Setup

docsfy is designed to run on OpenShift, which assigns an arbitrary UID at runtime for security. The key requirements are:

1. **GID 0 membership** — The `appuser` is created with group `0` (root). OpenShift assigns a random UID but always uses GID 0.

2. **Group-equals-user permissions** — All writable directories use `chmod g=u`, meaning the group has the same permissions as the owner. This ensures the arbitrary UID can read and write through the group.

3. **No hardcoded UID** — The `USER` directive sets the default, but the container does not assume a specific UID at runtime.

The following directories must be writable by GID 0:

| Path | Purpose |
|------|---------|
| `/data` | SQLite database and generated documentation |
| `/home/appuser` | AI CLI configurations and cache |

### OpenShift DeploymentConfig Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docsfy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: docsfy
  template:
    metadata:
      labels:
        app: docsfy
    spec:
      securityContext:
        runAsNonRoot: true
      containers:
        - name: docsfy
          image: docsfy:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: docsfy-secrets
          volumeMounts:
            - name: data
              mountPath: /data
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "2000m"
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: docsfy-data
```

> **Note:** AI documentation generation is CPU- and memory-intensive. The resource limits above are starting points — adjust based on the size of repositories you plan to document.

### Kubernetes Secret for Credentials

Store API keys in a Kubernetes Secret rather than environment variables:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: docsfy-secrets
type: Opaque
stringData:
  AI_PROVIDER: claude
  AI_MODEL: claude-opus-4-6[1m]
  ANTHROPIC_API_KEY: sk-ant-...
  LOG_LEVEL: INFO
```

### PersistentVolumeClaim for Data

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: docsfy-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

## Building the Image

### Local Build

```bash
docker build -t docsfy:latest .
```

### Multi-platform Build

To build for both `amd64` and `arm64`:

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t docsfy:latest .
```

### Build Arguments

Override the default Python version or other base image settings using build args if the Dockerfile supports them:

```bash
docker build --build-arg PYTHON_VERSION=3.12 -t docsfy:latest .
```

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/myk-org/docsfy.git
   cd docsfy
   ```

2. **Create your environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your API key(s)
   ```

3. **Start the service:**
   ```bash
   docker compose up -d
   ```

4. **Verify it's running:**
   ```bash
   curl http://localhost:8000/health
   ```

5. **Generate documentation for a repository:**
   ```bash
   curl -X POST http://localhost:8000/api/generate \
     -H "Content-Type: application/json" \
     -d '{"repo_url": "https://github.com/owner/repo"}'
   ```

6. **View generated docs:**
   Open `http://localhost:8000/docs/{project-name}/` in your browser, or download the static site:
   ```bash
   curl -o docs.tar.gz http://localhost:8000/api/projects/{project-name}/download
   ```
