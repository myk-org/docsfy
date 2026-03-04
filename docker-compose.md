# Docker Compose Setup

This guide walks through running docsfy with Docker Compose, covering port mapping, environment configuration, volume mounts, and health checks.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)
- A valid AI provider API key or Google Cloud credentials (for Vertex AI)

## docker-compose.yaml

Create a `docker-compose.yaml` in your project root:

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

## Port Mapping

The docsfy service runs a FastAPI/Uvicorn server on port `8000` inside the container. The compose file maps this to port `8000` on the host:

```yaml
ports:
  - "8000:8000"
```

The container entrypoint binds to all interfaces:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

To change the host port (for example, to avoid conflicts), modify only the left side of the mapping:

```yaml
ports:
  - "3000:8000"
```

This would make docsfy available at `http://localhost:3000` while the container still listens internally on port `8000`.

## Environment File Configuration

docsfy reads its configuration from a `.env` file loaded via the `env_file` directive:

```yaml
env_file: .env
```

Create your `.env` file by copying from the provided example:

```bash
cp .env.example .env
```

### Full Configuration Reference

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
| `AI_CLI_TIMEOUT` | `60` | Maximum time (in minutes) for a single AI CLI invocation |

### Claude Authentication

Claude supports two mutually exclusive authentication methods. Configure **one** of the following:

**Option 1 — Direct API Key:**

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

**Option 2 — Google Cloud Vertex AI:**

```bash
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

> **Note:** When using Vertex AI, you must also mount your gcloud credentials as a volume. See the [Volume Mounts](#volume-mounts) section below.

### Other Providers

Uncomment and set the appropriate key for your chosen provider:

```bash
# Gemini
GEMINI_API_KEY=your-gemini-api-key

# Cursor
CURSOR_API_KEY=your-cursor-api-key
```

### Logging

```bash
LOG_LEVEL=INFO
```

Set to `DEBUG` for verbose output during troubleshooting, or `WARNING`/`ERROR` for quieter production logs.

## Volume Mounts

The compose file defines three volume mounts, each serving a distinct purpose:

```yaml
volumes:
  - ./data:/data
  - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
  - ./cursor:/home/appuser/.config/cursor
```

### Data Directory (`./data:/data`)

The primary persistent storage for docsfy. This directory holds the SQLite database and all generated documentation:

```
./data/
├── docsfy.db                        # SQLite metadata database
└── projects/
    └── {project-name}/
        ├── plan.json                # Documentation structure from AI
        ├── cache/
        │   └── pages/*.md           # AI-generated markdown (cached)
        └── site/                    # Final rendered HTML
            ├── index.html
            ├── *.html
            ├── assets/
            │   ├── style.css
            │   ├── search.js
            │   ├── theme-toggle.js
            │   └── highlight.js
            └── search-index.json
```

The SQLite database (`docsfy.db`) tracks project metadata including repository URLs, generation status (`generating` / `ready` / `error`), last commit SHA, and generation history.

> **Warning:** Do not delete the `./data` directory while the container is running. This would remove all project metadata and generated documentation.

Create the data directory before starting the service:

```bash
mkdir -p ./data
```

### Google Cloud Credentials (`~/.config/gcloud`)

```yaml
- ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

This mount provides Google Cloud authentication credentials to the container. It is **required** when using Claude via Vertex AI (`CLAUDE_CODE_USE_VERTEX=1`) and is mounted **read-only** (`:ro`) to prevent the container from modifying your host credentials.

The container runs as the `appuser` non-root user, so credentials are mapped to `/home/appuser/.config/gcloud`.

To set up gcloud credentials on the host:

```bash
gcloud auth application-default login
```

> **Tip:** If you are not using Vertex AI (i.e., you are authenticating with `ANTHROPIC_API_KEY` directly), you can safely remove this volume mount from your `docker-compose.yaml`.

### Cursor Configuration (`./cursor`)

```yaml
- ./cursor:/home/appuser/.config/cursor
```

This mount persists Cursor IDE configuration and API keys. It is only needed when `AI_PROVIDER=cursor`.

Create the directory before starting:

```bash
mkdir -p ./cursor
```

> **Tip:** If you are not using Cursor as your AI provider, you can remove this volume mount.

## Health Check

The compose file configures a Docker health check that probes the `/health` endpoint:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

| Parameter | Value | Description |
|-----------|-------|-------------|
| `test` | `curl -f http://localhost:8000/health` | Hits the health endpoint; fails on non-2xx responses |
| `interval` | `30s` | Time between health checks |
| `timeout` | `10s` | Maximum time to wait for a response |
| `retries` | `3` | Number of consecutive failures before marking unhealthy |

The container transitions to `unhealthy` status after 3 consecutive failed checks (i.e., after 90 seconds of downtime at most).

Check container health status with:

```bash
docker compose ps
```

Or inspect the health check log:

```bash
docker inspect --format='{{json .State.Health}}' docsfy-docsfy-1 | python -m json.tool
```

## Running the Service

### Start docsfy

```bash
docker compose up --build
```

Add `-d` to run in detached (background) mode:

```bash
docker compose up --build -d
```

### Verify the service is running

```bash
curl http://localhost:8000/health
```

### View logs

```bash
docker compose logs -f docsfy
```

### Stop the service

```bash
docker compose down
```

> **Note:** `docker compose down` stops and removes the containers but preserves the `./data` volume on the host. Your generated documentation and database persist across restarts.

## Minimal Setup by Provider

Depending on your AI provider, you can strip down the compose file and environment to only what you need.

### Claude with API Key (Simplest)

**`.env`:**
```bash
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

**`docker-compose.yaml`:**
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

### Claude with Vertex AI

**`.env`:**
```bash
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

**`docker-compose.yaml`:**
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
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Gemini

**`.env`:**
```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key
```

**`docker-compose.yaml`:**
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

## Container Details

The docsfy container is built with the following characteristics relevant to volume permissions and runtime behavior:

| Aspect | Detail |
|--------|--------|
| Base image | `python:3.12-slim` (multi-stage build) |
| Runtime user | `appuser` (non-root, OpenShift-compatible with GID 0) |
| Package manager | `uv` |
| System dependencies | bash, git, curl, nodejs, npm, ca-certificates |
| Internal port | `8000` |

> **Warning:** The container runs as a non-root user (`appuser`). Ensure the `./data` directory on the host has appropriate write permissions. If you encounter permission errors, run:
> ```bash
> chmod -R 777 ./data
> ```
> For production environments, prefer setting ownership to match the container's UID/GID instead of using broad permissions.
