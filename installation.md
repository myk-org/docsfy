# Installation

This guide covers how to install docsfy and its dependencies so you can start generating AI-powered documentation from your repositories.

## Requirements

- **Python 3.12 or later** — docsfy uses modern Python features and requires `>=3.12`
- **Git** — used at runtime to clone repositories
- **At least one AI CLI provider** — Claude Code, Gemini CLI, or Cursor Agent (see [Installing AI CLI Providers](#installing-ai-cli-providers))

## Installing docsfy

### Using uv (recommended)

[uv](https://docs.astral.sh/uv/) is the recommended way to install and run docsfy. It handles dependency resolution and virtual environment management automatically.

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
uv sync
```

This creates a virtual environment and installs all dependencies defined in `pyproject.toml`:

```
ai-cli-runner
fastapi
uvicorn
pydantic-settings
python-simple-logger
aiosqlite
jinja2
markdown
pygments
```

To start the server:

```bash
uv run docsfy
```

The `docsfy` command is registered as a CLI entry point in `pyproject.toml`:

```toml
[project.scripts]
docsfy = "docsfy.main:run"
```

### Using pip

You can also install docsfy from the cloned source using pip:

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
pip install .
```

Then start the server:

```bash
docsfy
```

### Installing development dependencies

If you plan to contribute or run the test suite, install the optional `dev` extras:

```bash
# With uv
uv sync --extra dev

# With pip
pip install ".[dev]"
```

This adds `pytest`, `pytest-asyncio`, `pytest-xdist`, and `httpx` for testing.

## Installing AI CLI Providers

docsfy delegates documentation generation to external AI CLI tools via the [`ai-cli-runner`](https://github.com/myk-org/ai-cli-runner) package. You need at least one provider installed and authenticated.

### Claude Code (default)

Claude Code is the default AI provider. Install it with:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

This installs the `claude` binary to `~/.local/bin`. Make sure this directory is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Authenticate using one of two methods:

**Option 1 — API key:**

```bash
export ANTHROPIC_API_KEY=your-api-key
```

**Option 2 — Google Vertex AI:**

```bash
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=your-region
export ANTHROPIC_VERTEX_PROJECT_ID=your-project-id
```

### Gemini CLI

Gemini CLI requires Node.js and npm:

```bash
npm install -g @google/gemini-cli
```

Set your API key:

```bash
export GEMINI_API_KEY=your-api-key
```

### Cursor Agent

Install the Cursor Agent CLI:

```bash
curl -fsSL https://cursor.com/install | bash
```

Set your API key:

```bash
export CURSOR_API_KEY=your-api-key
```

> **Tip:** If you're unsure which provider to start with, Claude Code is the default and recommended option. You can switch providers at any time using the `AI_PROVIDER` environment variable.

## Environment Variables

docsfy is configured through environment variables or a `.env` file. The project includes a `.env.example` file you can use as a starting point:

```bash
cp .env.example .env
```

Settings are loaded via [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) in `src/docsfy/config.py`, which reads from both environment variables and the `.env` file automatically:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: str = "claude"
    ai_model: str = "claude-opus-4-6[1m]"
    ai_cli_timeout: int = Field(default=60, gt=0)
    log_level: str = "INFO"
    data_dir: str = "/data"
```

### Configuration reference

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `claude` | AI provider to use: `claude`, `gemini`, or `cursor` |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | Timeout in seconds for each AI CLI invocation (must be > 0) |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATA_DIR` | `/data` | Directory for generated documentation and database storage |
| `DEBUG` | `false` | Enable auto-reload for development (`true`/`false`) |
| `HOST` | `0.0.0.0` | Address the server binds to |
| `PORT` | `8000` | Port the server listens on |

### Provider-specific variables

| Variable | Provider | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude | API key for direct Anthropic access |
| `CLAUDE_CODE_USE_VERTEX` | Claude | Set to `1` to use Google Vertex AI |
| `CLOUD_ML_REGION` | Claude | Google Cloud region for Vertex AI |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Claude | Google Cloud project ID for Vertex AI |
| `GEMINI_API_KEY` | Gemini | Google Gemini API key |
| `CURSOR_API_KEY` | Cursor | Cursor API key |

> **Note:** The `[1m]` suffix in the default `AI_MODEL` value (`claude-opus-4-6[1m]`) specifies the 1-million-token context window variant. This is a valid model identifier, not a typo.

## Running with Docker

For production deployments, Docker is the recommended approach. The provided `Dockerfile` uses a multi-stage build with `python:3.12-slim` and pre-installs all three AI CLI providers.

### Using Docker Compose

Create your `.env` file, then start the service:

```bash
cp .env.example .env
# Edit .env with your API keys and settings
docker compose up
```

The `docker-compose.yaml` mounts a local `./data` directory for persistent storage and reads configuration from your `.env` file:

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

### Building the image directly

```bash
docker build -t docsfy .
docker run -p 8000:8000 --env-file .env -v ./data:/data docsfy
```

> **Warning:** The Docker image runs as a non-root user (`appuser`) for security. The `/data` directory inside the container is pre-configured with the correct permissions. If you mount a host volume, ensure the host directory is writable by UID 1000 or GID 0.

## Verifying the installation

After starting docsfy, confirm the server is running by hitting the health endpoint:

```bash
curl http://localhost:8000/health
```

You can also verify that your chosen AI provider is reachable — docsfy performs an availability check by sending a lightweight prompt to the CLI before starting any generation job.
