# Installation

docsfy can be deployed using Docker (recommended) or set up locally for development. This guide covers both approaches, along with the required AI CLI binary installation.

## Prerequisites

Before installing docsfy, ensure you have the following:

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — the sole package manager (pip is not supported)
- **Git** — for cloning repositories during documentation generation
- **Node.js and npm** — required if using the Gemini CLI provider

For Docker deployment:

- **Docker** and **Docker Compose**

## Docker Deployment (Recommended)

Docker is the recommended way to run docsfy. The image includes all system dependencies, AI CLI binaries, and the application itself.

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your AI provider credentials:

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

> **Note:** You only need to configure credentials for the AI provider you intend to use. The default provider is `claude`.

### 3. Start the Service

```bash
docker compose up -d
```

This builds and starts the docsfy service using the following `docker-compose.yaml` configuration:

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

### 4. Verify the Installation

Check that the service is healthy:

```bash
curl http://localhost:8000/health
```

Or check container status:

```bash
docker compose ps
```

### Volume Mounts

The Docker setup uses three volume mounts:

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `./data` | `/data` | read-write | SQLite database and generated project files |
| `~/.config/gcloud` | `/home/appuser/.config/gcloud` | read-only | Google Cloud credentials (for Vertex AI) |
| `./cursor` | `/home/appuser/.config/cursor` | read-write | Cursor CLI configuration |

> **Tip:** The `./data` directory is where all persistent state lives — the SQLite database at `/data/docsfy.db` and generated documentation sites under `/data/projects/`. Back up this directory to preserve your generated documentation.

### Docker Image Details

The Dockerfile uses a multi-stage build with the following specifications:

| Aspect | Detail |
|--------|--------|
| Base image | `python:3.12-slim` |
| Package manager | `uv` (not pip) |
| Non-root user | `appuser` (OpenShift compatible, GID 0) |
| System dependencies | bash, git, curl, nodejs, npm, ca-certificates |
| Entrypoint | `uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000` |
| Exposed port | `8000` |
| Health check | `GET /health` |

> **Note:** The container runs as a non-root user (`appuser`) with GID 0 for OpenShift compatibility. If you encounter permission issues with volume mounts, ensure the host directories are writable by GID 0.

## Local Development Setup

### 1. Install Python 3.12+

Ensure Python 3.12 or later is installed on your system:

```bash
python3 --version
```

### 2. Install uv

docsfy uses `uv` exclusively as its package manager. Install it following the [official instructions](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> **Warning:** Do not use `pip` to manage docsfy dependencies. The project is configured to work with `uv` only. Using `pip` may result in dependency resolution issues.

### 3. Clone and Install Dependencies

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
uv sync
```

The `uv sync` command reads the `pyproject.toml` and installs all dependencies into a virtual environment managed by `uv`. The project uses `hatchling` as its build system.

### 4. Install System Dependencies

docsfy requires several system-level packages for full functionality:

**Debian/Ubuntu:**

```bash
sudo apt-get update
sudo apt-get install -y bash git curl nodejs npm ca-certificates
```

**Fedora/RHEL:**

```bash
sudo dnf install -y bash git curl nodejs npm ca-certificates
```

**macOS (Homebrew):**

```bash
brew install git curl node
```

### 5. Install AI CLI Binaries

At least one AI CLI binary must be installed. See the [AI CLI Binary Installation](#ai-cli-binary-installation) section below.

### 6. Configure Environment

Create your `.env` file from the example:

```bash
cp .env.example .env
```

Edit the file to configure your chosen AI provider (see the environment variables table in the Docker section above).

### 7. Run the Development Server

```bash
uv run uvicorn docsfy.main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag enables auto-reload on code changes, which is useful during development.

The service will be available at `http://localhost:8000`.

## AI CLI Binary Installation

docsfy orchestrates AI CLI tools to generate documentation. You need to install at least one provider's CLI binary. The Docker image installs all three automatically, but for local development you can install only the one(s) you need.

### Claude Code CLI

Claude is the default AI provider (`AI_PROVIDER=claude`).

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

After installation, authenticate using either an API key or Vertex AI credentials:

**Option 1 — API Key:**

Set the `ANTHROPIC_API_KEY` environment variable in your `.env` file.

**Option 2 — Google Vertex AI:**

```bash
# In your .env file:
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=your-region
ANTHROPIC_VERTEX_PROJECT_ID=your-project-id
```

Ensure your Google Cloud credentials are available (e.g., via `gcloud auth application-default login`).

The Claude CLI is invoked as:

```
claude --model <model> --dangerously-skip-permissions -p
```

### Cursor Agent CLI

```bash
curl -fsSL https://cursor.com/install | bash
```

Set the `CURSOR_API_KEY` environment variable in your `.env` file.

The Cursor agent is invoked with a `--workspace` flag pointing to the repository path:

```
agent --force --model <model> --print --workspace <path>
```

### Gemini CLI

Gemini CLI requires Node.js and npm:

```bash
npm install -g @google/gemini-cli
```

Set the `GEMINI_API_KEY` environment variable in your `.env` file.

The Gemini CLI is invoked as:

```
gemini --model <model> --yolo
```

> **Warning:** AI CLI binaries are installed unpinned (always fetching the latest version). In production, consider pinning to specific versions for reproducibility.

## Development Tooling

For contributors working on docsfy itself, the project includes a comprehensive development toolchain:

| Tool | Purpose |
|------|---------|
| **Pre-commit** | ruff (lint + format), mypy (strict), flake8, gitleaks, detect-secrets |
| **Tox** | Unused-code checks, unit tests (via uv) |
| **hatchling** | Python build system |
| **ruff** | Linting and formatting |
| **mypy** | Static type checking (strict mode) |

Install pre-commit hooks:

```bash
uv run pre-commit install
```

Run the test suite:

```bash
uv run tox
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI provider to use (`claude`, `gemini`, or `cursor`) |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | Maximum time in minutes for AI CLI operations |
| `ANTHROPIC_API_KEY` | — | API key for Claude (direct API access) |
| `CLAUDE_CODE_USE_VERTEX` | — | Set to `1` to use Claude via Google Vertex AI |
| `CLOUD_ML_REGION` | — | Google Cloud region for Vertex AI |
| `ANTHROPIC_VERTEX_PROJECT_ID` | — | Google Cloud project ID for Vertex AI |
| `GEMINI_API_KEY` | — | API key for Gemini |
| `CURSOR_API_KEY` | — | API key for Cursor |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Storage Layout

Once running, docsfy stores all data under the `/data` directory (or `./data` on the host when using Docker):

```
/data/
  docsfy.db                         # SQLite database (project metadata)
  projects/
    {project-name}/
      plan.json                     # Documentation structure from AI
      cache/
        pages/*.md                  # AI-generated markdown (cached)
      site/                         # Final rendered HTML
        index.html
        *.html
        assets/
          style.css
          search.js
          theme-toggle.js
          highlight.js
        search-index.json
```

> **Tip:** The `cache/pages/` directory enables incremental updates. When regenerating documentation, docsfy compares the repository's commit SHA against the stored SHA and only regenerates pages whose content may have changed.

## Verifying Your Installation

After completing the installation, verify everything is working:

1. **Check the health endpoint:**

   ```bash
   curl http://localhost:8000/health
   ```

2. **Generate documentation for a test repository:**

   ```bash
   curl -X POST http://localhost:8000/api/generate \
     -H "Content-Type: application/json" \
     -d '{"repo_url": "https://github.com/your-org/sample-repo"}'
   ```

3. **Check generation status:**

   ```bash
   curl http://localhost:8000/api/status
   ```

4. **View generated documentation** in your browser at `http://localhost:8000/docs/{project-name}/`.
