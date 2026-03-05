# Installation

docsfy can be installed using Docker, Docker Compose, or set up locally for development. Choose the method that best fits your use case.

## Prerequisites

Before installing docsfy, ensure you have the following:

- **Git** -- required for cloning repositories during documentation generation
- At least one AI CLI tool configured (see [AI Provider Setup](#ai-provider-setup) below)
- API keys or credentials for your chosen AI provider

## Quick Start with Docker

The fastest way to get docsfy running is with a single Docker command.

### Build the Image

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
docker build -t docsfy .
```

The Dockerfile uses a multi-stage build based on `python:3.12-slim` and installs all required system dependencies automatically:

- bash, git, curl, ca-certificates
- Node.js and npm (for Gemini CLI)
- `uv` package manager
- AI CLI tools (Claude Code, Cursor Agent, Gemini CLI)

### Run the Container

```bash
docker run -d \
  --name docsfy \
  -p 8000:8000 \
  -v ./data:/data \
  -e ANTHROPIC_API_KEY=your-api-key \
  docsfy
```

Verify the service is running:

```bash
curl http://localhost:8000/health
```

> **Note:** The container runs as a non-root user (`appuser`) and is compatible with OpenShift (GID 0). The data directory at `/data` stores the SQLite database and all generated documentation.

## Docker Compose (Recommended)

Docker Compose provides a complete setup with health checks, persistent storage, and environment configuration.

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
```

### 2. Create an Environment File

Copy the example environment file and configure your AI provider credentials:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Option 1: API Key
ANTHROPIC_API_KEY=sk-ant-...

# Claude - Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=us-central1
# ANTHROPIC_VERTEX_PROJECT_ID=my-project

# Gemini
# GEMINI_API_KEY=

# Cursor
# CURSOR_API_KEY=

# Logging
LOG_LEVEL=INFO
```

### 3. Start the Service

```bash
docker compose up -d
```

This uses the following `docker-compose.yaml` configuration:

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

### Volume Mounts

| Mount | Purpose |
|-------|---------|
| `./data:/data` | Persistent storage for the SQLite database (`docsfy.db`) and generated documentation sites |
| `~/.config/gcloud:/home/appuser/.config/gcloud:ro` | Google Cloud credentials (required for Vertex AI or Gemini) |
| `./cursor:/home/appuser/.config/cursor` | Cursor agent configuration (required if using Cursor provider) |

> **Tip:** The `gcloud` mount is read-only (`:ro`). Only mount it if you are using Claude via Vertex AI or the Gemini provider.

### 4. Verify

```bash
# Check the health endpoint
curl http://localhost:8000/health

# View logs
docker compose logs -f docsfy
```

## Local Development Setup

For contributing to docsfy or running it outside of Docker, set up a local development environment using `uv` and Python 3.12+.

### Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.12 or higher |
| uv | Latest |
| Git | Any recent version |
| Node.js + npm | Required only if using Gemini CLI |

### 1. Install uv

If you don't have `uv` installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> **Warning:** docsfy uses `uv` exclusively as its package manager. Do not use `pip` to install dependencies -- this is unsupported and may lead to version conflicts.

### 2. Clone and Install Dependencies

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
uv sync
```

`uv sync` reads `pyproject.toml` and installs all required dependencies into an isolated virtual environment. The project uses `hatchling` as its build system.

### 3. Install an AI CLI Tool

You need at least one AI CLI tool installed and available on your `PATH`:

**Claude Code** (default provider):

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Gemini CLI:**

```bash
npm install -g @google/gemini-cli
```

**Cursor Agent:**

```bash
curl -fsSL https://cursor.com/install | bash
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

At minimum, set your AI provider and its corresponding API key:

```bash
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Run the Development Server

```bash
uv run uvicorn docsfy.main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag enables auto-reloading on code changes, which is useful during development.

The server will be available at `http://localhost:8000`.

### 6. Development Tools

docsfy uses several development tools to maintain code quality:

```bash
# Run linting and formatting with ruff
uv run pre-commit run --all-files

# Run type checking with mypy (strict mode)
uv run mypy .

# Run tests
uv run tox

# Check for unused code
uv run tox -e unused
```

> **Tip:** Install the pre-commit hooks to automatically check code on every commit:
> ```bash
> uv run pre-commit install
> ```

## AI Provider Setup

docsfy supports three AI providers. Configure one based on your preference and available credentials.

### Claude Code (Default)

Claude is the default provider. You can authenticate in two ways:

**Option 1 -- API Key (simplest):**

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Option 2 -- Google Vertex AI:**

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
```

When using Vertex AI, ensure your Google Cloud credentials are configured. In Docker, mount your gcloud config directory as shown in the Docker Compose section.

### Gemini CLI

```bash
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=your-gemini-api-key
```

> **Note:** Gemini CLI requires Node.js and npm. These are included in the Docker image but must be installed manually for local development.

### Cursor Agent

```bash
AI_PROVIDER=cursor
AI_MODEL=claude-opus-4-6[1m]
CURSOR_API_KEY=your-cursor-api-key
```

> **Note:** Cursor uses a `--workspace` flag instead of subprocess `cwd` for repository access. This is handled automatically by docsfy.

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI provider to use (`claude`, `gemini`, or `cursor`) |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | Maximum time in minutes for a single AI CLI invocation |
| `ANTHROPIC_API_KEY` | -- | API key for Claude (direct API access) |
| `CLAUDE_CODE_USE_VERTEX` | -- | Set to `1` to use Claude via Vertex AI |
| `CLOUD_ML_REGION` | -- | GCP region for Vertex AI |
| `ANTHROPIC_VERTEX_PROJECT_ID` | -- | GCP project ID for Vertex AI |
| `GEMINI_API_KEY` | -- | API key for Gemini |
| `CURSOR_API_KEY` | -- | API key for Cursor |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Data Directory Structure

All persistent data is stored under `/data` (or `./data` when mounted via Docker):

```
/data/
  docsfy.db                        # SQLite database (project metadata, status, history)
  projects/
    {project-name}/
      plan.json                    # Documentation structure from AI planner
      cache/
        pages/*.md                 # AI-generated markdown (cached for incremental updates)
      site/                        # Final rendered static HTML
        index.html
        *.html
        assets/
          style.css
          search.js
          theme-toggle.js
          highlight.js
        search-index.json
```

### Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 8000 | HTTP | FastAPI server (API + documentation hosting) |

## Verifying Your Installation

After starting docsfy with any method, run through these checks:

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Check project status (should return an empty list initially)
curl http://localhost:8000/api/status

# 3. Generate documentation for a repository
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo"}'

# 4. Monitor generation status
curl http://localhost:8000/api/status
```

> **Warning:** Documentation generation invokes AI CLI tools and may take several minutes depending on repository size and the AI model used. The default timeout is 60 minutes per AI CLI invocation.

## Troubleshooting

### AI CLI not found

If you see errors about the AI CLI binary not being found, verify it is installed and on your `PATH`:

```bash
which claude    # For Claude provider
which gemini    # For Gemini provider
which agent     # For Cursor provider
```

docsfy runs an availability check before starting generation. If the CLI is not accessible, the generation request will fail immediately.

### Permission denied on `/data`

When running in Docker, ensure the data volume is writable by the `appuser` (non-root) user:

```bash
mkdir -p ./data
chmod 777 ./data
```

### Container health check failing

The health check hits `http://localhost:8000/health` inside the container. If it fails repeatedly:

```bash
# Check container logs for startup errors
docker compose logs docsfy

# Verify the port is not in use by another process
lsof -i :8000
```
