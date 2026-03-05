# Docker Deployment

This guide covers running docsfy in Docker, including building the image, configuring containers with docker-compose, understanding the multi-stage build, and deploying to OpenShift or other restricted container platforms.

## Quick Start

Build and run docsfy with a single command using docker-compose:

```bash
# Copy the example environment file and configure your AI provider credentials
cp .env.example .env

# Build and start the container
docker compose up --build
```

docsfy will be available at `http://localhost:8000`.

## Environment Configuration

Before starting the container, create a `.env` file from the provided example:

```bash
# AI Configuration
AI_PROVIDER=claude
# [1m] = 1 million token context window, this is a valid model identifier
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

Set `AI_PROVIDER` to one of `claude`, `gemini`, or `cursor`, then uncomment and fill in the matching credential variables.

> **Note:** The `DATA_DIR` environment variable controls where docsfy stores its database and generated sites. It defaults to `/data` inside the container and should not normally be changed when running in Docker.

## Docker Compose

The provided `docker-compose.yaml` defines a production-ready service:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Common Operations

```bash
# Start in the background
docker compose up -d --build

# View logs
docker compose logs -f docsfy

# Stop the service
docker compose down

# Rebuild after code changes
docker compose up --build --force-recreate
```

## Building the Image Directly

To build and run without docker-compose:

```bash
# Build the image
docker build -t docsfy .

# Run the container
docker run -d \
  --name docsfy \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/data \
  docsfy
```

## Multi-Stage Build

The Dockerfile uses a two-stage build to minimize the final image size and separate build-time dependencies from the runtime environment.

### Stage 1: Builder

The builder stage installs Python dependencies using [uv](https://github.com/astral-sh/uv), a fast Python package manager:

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /usr/local/bin/uv

# Install git (needed for gitpython dependency)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Create venv and install dependencies
RUN uv sync --frozen --no-dev
```

The `--frozen` flag ensures the lockfile (`uv.lock`) is used as-is, guaranteeing reproducible builds. The `--no-dev` flag excludes development dependencies (pytest, httpx, etc.) from the production image.

### Stage 2: Runtime

The runtime stage starts from a clean `python:3.12-slim` image and installs only what is needed at runtime:

- **bash** — required by CLI install scripts
- **git** — required at runtime for cloning repositories
- **curl** — used for health checks and CLI installation
- **nodejs/npm** — required for the Gemini CLI

The three AI CLI tools are installed in this stage:

```dockerfile
# Install Claude Code CLI (installs to ~/.local/bin)
RUN /bin/bash -o pipefail -c "curl -fsSL https://claude.ai/install.sh | bash"

# Install Cursor Agent CLI (installs to ~/.local/bin)
RUN /bin/bash -o pipefail -c "curl -fsSL https://cursor.com/install | bash"

# Configure npm for non-root global installs and install Gemini CLI
RUN mkdir -p /home/appuser/.npm-global \
    && npm config set prefix '/home/appuser/.npm-global' \
    && npm install -g @google/gemini-cli
```

The virtual environment, lockfile, and source code are then copied from the builder stage:

```dockerfile
COPY --chown=appuser:0 --from=builder /app/.venv /app/.venv
COPY --chown=appuser:0 --from=builder /app/pyproject.toml /app/uv.lock ./
COPY --chown=appuser:0 --from=builder /app/src /app/src
```

> **Tip:** All copied files use `--chown=appuser:0` to set ownership to the non-root user and the root group (GID 0), which is required for OpenShift compatibility.

## Exposed Ports

The container exposes a single port:

| Port | Protocol | Description |
|------|----------|-------------|
| 8000 | HTTP | FastAPI application server |

The application binds to `0.0.0.0:8000` via the entrypoint command:

```dockerfile
ENTRYPOINT ["uv", "run", "--no-sync", "uvicorn", "docsfy.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The `--no-sync` flag prevents `uv` from attempting to modify the virtual environment at runtime. This is required for OpenShift, where containers run as an arbitrary UID and may not have write access to the `.venv` directory.

To map a different host port, adjust the docker-compose port binding or the `docker run -p` flag:

```bash
# Map to host port 3000 instead
docker run -d -p 3000:8000 --env-file .env -v $(pwd)/data:/data docsfy
```

## Health Checks

The Dockerfile defines a built-in health check that polls the `/health` endpoint:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

The `/health` endpoint returns a simple JSON response:

```json
{"status": "ok"}
```

| Parameter | Value | Description |
|-----------|-------|-------------|
| Interval | 30s | Time between health check probes |
| Timeout | 10s | Maximum time to wait for a response |
| Retries | 3 | Consecutive failures before marking unhealthy |

Check container health status with:

```bash
docker inspect --format='{{.State.Health.Status}}' docsfy
```

### Kubernetes / OpenShift Probes

For Kubernetes or OpenShift deployments, configure liveness and readiness probes targeting the same endpoint:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 10
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Data Volume Persistence

docsfy stores all persistent state under a single `/data` directory inside the container. This directory **must** be mounted as a volume to preserve data across container restarts.

### What Is Stored

```
/data/
├── docsfy.db                        # SQLite database (project metadata)
└── projects/
    └── <project-name>/
        ├── plan.json                 # AI-generated documentation structure
        ├── cache/
        │   └── pages/
        │       └── *.md             # Cached markdown (for incremental updates)
        └── site/
            └── *.html               # Rendered static HTML output
```

| Path | Purpose |
|------|---------|
| `docsfy.db` | SQLite database storing project records, status, commit SHAs, and generation timestamps |
| `projects/<name>/plan.json` | The documentation plan produced by the AI planner stage |
| `projects/<name>/cache/pages/` | Cached markdown pages — enables incremental regeneration when the source repo hasn't changed |
| `projects/<name>/site/` | Final rendered HTML documentation, served at `/docs/<name>/` |

### Volume Mount Options

**Bind mount (development):**

```yaml
volumes:
  - ./data:/data
```

**Named volume (production):**

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - docsfy-data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  docsfy-data:
```

> **Warning:** Without a volume mount on `/data`, all generated documentation and project metadata will be lost when the container is removed.

### Incremental Updates

docsfy tracks the last commit SHA for each project. When regeneration is requested, it compares the current SHA against the stored one. If they match and the project status is `ready`, generation is skipped entirely. This makes re-running generation on an unchanged repository a no-op, saving time and AI API costs.

To force a full regeneration and clear cached pages, use the `force` parameter in the API request.

## OpenShift-Compatible Non-Root Container Setup

The Dockerfile is designed to run on OpenShift and other platforms that enforce non-root container execution with arbitrary user IDs.

### How It Works

OpenShift assigns a random UID at runtime but always uses GID 0 (the root group). The Dockerfile accounts for this with several key configurations:

**1. User creation with GID 0:**

```dockerfile
RUN useradd --create-home --shell /bin/bash -g 0 appuser \
    && mkdir -p /data \
    && chown appuser:0 /data \
    && chmod -R g+w /data
```

The `-g 0` flag adds `appuser` to the root group. The `/data` directory is owned by `appuser:0` with group-write permissions.

**2. Group-writable application directory:**

```dockerfile
RUN chmod -R g+w /app
```

This allows OpenShift's arbitrary UID (which is a member of GID 0) to read and interact with application files.

**3. Group-writable home directory:**

```dockerfile
RUN find /home/appuser -type d -exec chmod g=u {} + \
    && npm cache clean --force 2>/dev/null; \
    rm -rf /home/appuser/.npm/_cacache
```

Only directories are modified — files retain default permissions. Directories need group write+execute so the arbitrary UID can create runtime configuration and cache files (e.g., for the AI CLIs).

**4. Explicit HOME environment variable:**

```dockerfile
ENV HOME="/home/appuser"
```

OpenShift's arbitrary UID has no entry in `/etc/passwd`, so `HOME` must be set explicitly. Without this, CLI tools may fail to locate their configuration directories.

**5. Read-only virtual environment at runtime:**

```dockerfile
ENTRYPOINT ["uv", "run", "--no-sync", "uvicorn", "docsfy.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

The `--no-sync` flag prevents `uv` from writing to the `.venv` directory, which may not be writable under an arbitrary UID.

### OpenShift Deployment Checklist

- The container runs as `USER appuser` (non-root) by default
- All writable directories (`/data`, `/app`, `/home/appuser`) are group-writable for GID 0
- No `VOLUME` instruction is used in the Dockerfile — volume mounts are configured at deployment time
- The container does not require any Linux capabilities or privilege escalation
- The `HOME` environment variable is explicitly set for arbitrary UID compatibility

> **Note:** The AI CLI tools (Claude Code, Cursor Agent, Gemini CLI) are installed to `/home/appuser/.local/bin` and `/home/appuser/.npm-global/bin`. Both paths are added to `PATH` so they remain accessible regardless of the runtime UID.

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
      containers:
        - name: docsfy
          image: docsfy:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: docsfy-env
          volumeMounts:
            - name: data
              mountPath: /data
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
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: docsfy-data
```

## Troubleshooting

### Container starts but health check fails

The application takes a moment to initialize the database on first start. If health checks fail immediately after startup, increase the `initialDelaySeconds` for probes or wait for the startup to complete:

```bash
docker compose logs -f docsfy
```

Look for the uvicorn startup log message confirming the server is listening.

### Permission denied errors on /data

If you see permission errors when using a bind mount, ensure the host directory has appropriate permissions:

```bash
mkdir -p data
chmod 775 data
```

On SELinux-enabled systems (Fedora, RHEL), you may need to add the `:z` volume flag:

```yaml
volumes:
  - ./data:/data:z
```

### AI CLI not found at runtime

Verify the CLIs are installed and accessible inside the container:

```bash
docker compose exec docsfy bash -c 'echo $PATH'
docker compose exec docsfy which claude
docker compose exec docsfy which gemini
```

The expected `PATH` includes `/home/appuser/.local/bin` and `/home/appuser/.npm-global/bin`.
