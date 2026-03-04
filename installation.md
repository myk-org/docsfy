# Installation

docsfy requires a working Python environment, system-level tools for repository cloning and AI integration, and at least one configured AI provider. This page covers every installation path: Docker-based deployment, local development setup, and manual prerequisite installation.

## Prerequisites

Before installing docsfy, ensure the following system dependencies are available.

### Python 3.12+

docsfy requires Python 3.12 or later. Verify your version:

```bash
python3 --version
```

### uv Package Manager

docsfy uses [uv](https://docs.astral.sh/uv/) exclusively as its Python package manager. pip is not supported.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify the installation:

```bash
uv --version
```

> **Warning:** Do not use `pip` to install or manage docsfy dependencies. The project relies on `uv` for dependency resolution, virtual environment management, and runtime execution.

### Git

Git is required for cloning target repositories during documentation generation. docsfy performs shallow clones (`--depth 1`) to minimize bandwidth.

```bash
git --version
```

For generating documentation from **private repositories**, ensure your git credentials (SSH keys or HTTPS tokens) are configured on the host system.

### Node.js and npm

Node.js and npm are required for installing the Gemini CLI. If you only plan to use Claude or Cursor as your AI provider, this dependency is optional.

```bash
node --version
npm --version
```

### curl

Used for installing AI CLI tools and for container health checks.

```bash
curl --version
```

## AI CLI Tools

docsfy delegates documentation generation to AI CLI tools. You must install at least one provider. All tools are installed unpinned (always latest version).

### Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Verify:

```bash
claude --version
```

### Cursor Agent

```bash
curl -fsSL https://cursor.com/install | bash
```

Verify:

```bash
agent --version
```

### Gemini CLI

Requires Node.js and npm:

```bash
npm install -g @google/gemini-cli
```

Verify:

```bash
gemini --version
```

> **Tip:** You only need one AI provider to run docsfy. Claude is the default provider. Install additional providers if you want the flexibility to switch between them.

## Docker Deployment (Recommended)

Docker is the simplest way to deploy docsfy. The multi-stage Dockerfile uses `python:3.12-slim` as the base image, installs all system dependencies and AI CLI tools, and runs the application as a non-root user (`appuser`).

### Clone the Repository

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
```

### Configure Environment Variables

Copy the example environment file and edit it with your credentials:

```bash
cp .env.example .env
```

The `.env` file controls AI provider selection, model configuration, and authentication:

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

Uncomment and fill in the credentials for your chosen provider. See [Configuring AI Providers](#configuring-ai-providers) below for details on each option.

### Run with Docker Compose

The `docker-compose.yaml` defines the full service configuration:

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

Build and start the service:

```bash
docker compose up --build
```

Run in detached mode:

```bash
docker compose up --build -d
```

The service will be available at `http://localhost:8000`. Verify it is running:

```bash
curl http://localhost:8000/health
```

### Volume Mounts

The Docker Compose configuration mounts three volumes:

| Mount | Container Path | Purpose |
|-------|---------------|---------|
| `./data` | `/data` | Persistent storage for the SQLite database (`docsfy.db`) and generated documentation (`projects/`) |
| `~/.config/gcloud` | `/home/appuser/.config/gcloud` | Google Cloud credentials for Gemini via Vertex AI (read-only) |
| `./cursor` | `/home/appuser/.config/cursor` | Cursor Agent configuration |

> **Note:** The `./data` volume persists across container restarts. It holds both the SQLite database and all generated documentation sites. Back up this directory to preserve your generated docs.

### Dockerfile Details

The Dockerfile builds the image in multiple stages for optimization:

| Aspect | Detail |
|--------|--------|
| Base image | `python:3.12-slim` |
| Package manager | `uv` (not pip) |
| Non-root user | `appuser` (OpenShift compatible, GID 0) |
| System packages | `bash`, `git`, `curl`, `nodejs`, `npm`, `ca-certificates` |
| Exposed port | `8000` |
| Entrypoint | `uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000` |
| Health check | `GET /health` |

To build the Docker image without Compose:

```bash
docker build -t docsfy .
```

To run the image directly:

```bash
docker run -p 8000:8000 \
  --env-file .env \
  -v ./data:/data \
  docsfy
```

## Local Development Setup

For contributors and local development, docsfy uses `uv` for dependency management, `hatchling` as the build system, and `tox` for test orchestration.

### Clone and Install

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
uv sync
```

This creates a virtual environment and installs all project dependencies.

### Configure Environment

Create your local `.env` file:

```bash
cp .env.example .env
```

Edit `.env` to configure your AI provider credentials (see [Configuring AI Providers](#configuring-ai-providers)).

### Run the Development Server

Start the FastAPI server with hot-reload enabled:

```bash
uv run uvicorn docsfy.main:app --reload
```

The server starts at `http://localhost:8000` with automatic reloading on code changes.

### Pre-commit Hooks

docsfy uses pre-commit hooks for code quality enforcement:

| Hook | Purpose |
|------|---------|
| ruff | Linting and code formatting |
| mypy | Strict static type checking |
| flake8 | Additional style checks |
| gitleaks | Secret detection in commits |
| detect-secrets | Additional secret scanning |

Install and activate the hooks:

```bash
uv run pre-commit install
```

Run all hooks manually against the entire codebase:

```bash
uv run pre-commit run --all-files
```

### Running Tests

Tests are orchestrated through tox, executed via uv:

```bash
uv run tox
```

> **Note:** The project enforces strict mypy type checking. All code contributions must pass type checking with no errors.

## Configuring AI Providers

docsfy supports three AI providers. Configure your chosen provider by setting the appropriate environment variables in your `.env` file.

### Selecting a Provider

Set `AI_PROVIDER` to one of: `claude`, `gemini`, or `cursor`.

```bash
AI_PROVIDER=claude
```

### Provider Defaults

| Setting | Default Value |
|---------|--------------|
| `AI_PROVIDER` | `claude` |
| `AI_MODEL` | `claude-opus-4-6[1m]` |
| `AI_CLI_TIMEOUT` | `60` (minutes) |

### Claude (Default)

Claude supports two authentication methods:

**Option 1: API Key (Direct)**

```bash
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

**Option 2: Google Cloud Vertex AI**

```bash
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

When using Vertex AI with Docker, mount your Google Cloud credentials:

```bash
volumes:
  - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

### Gemini

```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=...
```

### Cursor

```bash
AI_PROVIDER=cursor
CURSOR_API_KEY=...
```

When using Cursor with Docker, mount the configuration directory:

```bash
volumes:
  - ./cursor:/home/appuser/.config/cursor
```

> **Tip:** docsfy runs an availability check before starting documentation generation. It sends a lightweight test prompt to confirm the configured AI CLI tool is installed and authenticated. If this check fails, the generation request will return an error with details about what went wrong.

## Data Storage

docsfy stores all persistent data under the `/data` directory (configurable via volume mounts in Docker):

```
/data/
  docsfy.db                          # SQLite database (project metadata)
  projects/
    {project-name}/
      plan.json                      # Documentation structure from AI Planner
      cache/
        pages/*.md                   # Cached AI-generated markdown
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

For local development, this directory is created in the project root. For Docker deployments, it is mounted as a volume to persist data across container restarts.

## Verifying the Installation

After starting docsfy, verify that everything is working:

1. **Check the health endpoint:**

```bash
curl http://localhost:8000/health
```

2. **List projects (should return an empty list initially):**

```bash
curl http://localhost:8000/api/status
```

3. **Generate documentation for a test repository:**

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/repo"}'
```

4. **Check generation status:**

```bash
curl http://localhost:8000/api/status
```

Once the status shows `ready`, the generated documentation is available at `http://localhost:8000/docs/{project-name}/`.

## Troubleshooting

### AI CLI tool not found

Ensure the AI CLI binary is in your system `PATH`. For Docker deployments, the Dockerfile installs all three CLI tools automatically. For local development, install them manually (see [AI CLI Tools](#ai-cli-tools)).

### Authentication errors

Verify that the environment variables for your chosen provider are set correctly. For Claude with Vertex AI, ensure your `gcloud` credentials are current:

```bash
gcloud auth application-default login
```

### Private repository access

docsfy uses your system's git credentials to clone repositories. Ensure SSH keys or HTTPS tokens are configured:

```bash
# Test SSH access
ssh -T git@github.com

# Or configure HTTPS credentials
git config --global credential.helper store
```

For Docker deployments, mount your SSH keys or git credential store into the container.

### Port conflicts

If port 8000 is already in use, change the port mapping in `docker-compose.yaml`:

```yaml
ports:
  - "9000:8000"
```

Or for local development:

```bash
uv run uvicorn docsfy.main:app --reload --port 9000
```
