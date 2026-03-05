# Configuration Reference

docsfy is configured through environment variables. Values can be set directly in the shell environment or loaded from a `.env` file in the working directory.

## Loading Configuration

docsfy uses [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) to manage configuration. On startup, settings are resolved in the following order (highest priority first):

1. **Environment variables** set in the current shell
2. **`.env` file** in the current working directory
3. **Default values** defined in the application

Unknown environment variables are silently ignored.

```python
# src/docsfy/config.py
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

Settings are cached at first access via `@lru_cache`, so all callers within a single process see the same configuration.

## Quick Start

Copy the example file and edit it with your credentials:

```bash
cp .env.example .env
```

A minimal `.env` for the Claude provider:

```env
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

A minimal `.env` for the Gemini provider:

```env
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=AIza...
```

---

## Core Settings

### `AI_PROVIDER`

The AI backend used for documentation generation.

| | |
|---|---|
| **Type** | `string` |
| **Default** | `claude` |
| **Valid values** | `claude`, `gemini`, `cursor` |

Each provider requires its own CLI tool to be installed (handled automatically in the Docker image) and its own authentication credentials.

```env
AI_PROVIDER=claude
```

Per-request overrides are also supported via the API:

```json
{
  "repo_url": "https://github.com/org/repo",
  "ai_provider": "gemini"
}
```

### `AI_MODEL`

The specific model identifier passed to the AI CLI.

| | |
|---|---|
| **Type** | `string` |
| **Default** | `claude-opus-4-6[1m]` |

The `[1m]` suffix in the default value indicates a 1-million-token context window. Model identifiers are provider-specific; use whatever model string your chosen provider accepts.

```env
# Claude
AI_MODEL=claude-opus-4-6[1m]

# Gemini
AI_MODEL=gemini-2.5-pro

# Cursor
AI_MODEL=cursor-latest
```

### `AI_CLI_TIMEOUT`

Maximum time in seconds to wait for a single AI CLI invocation to complete.

| | |
|---|---|
| **Type** | `integer` |
| **Default** | `60` |
| **Constraint** | Must be greater than `0` |

This timeout applies independently to each AI call -- both the planning phase and each individual page generation. Setting a value of `0` or below will cause a validation error at startup.

```env
AI_CLI_TIMEOUT=120
```

> **Tip:** For large repositories or complex documentation plans, consider increasing this value. Each page is generated as a separate AI call, so the timeout does not need to cover the entire generation run.

### `LOG_LEVEL`

Controls the verbosity of application logging.

| | |
|---|---|
| **Type** | `string` |
| **Default** | `INFO` |
| **Valid values** | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

```env
LOG_LEVEL=DEBUG
```

### `DATA_DIR`

Root directory for all persistent data, including the SQLite database and generated documentation sites.

| | |
|---|---|
| **Type** | `string` (filesystem path) |
| **Default** | `/data` |

docsfy creates the following structure under `DATA_DIR`:

```
/data/
├── docsfy.db              # SQLite database
└── projects/
    └── <project-name>/
        ├── plan.json      # Documentation plan
        ├── cache/pages/   # Cached markdown per page
        └── site/          # Rendered static site
```

The paths are resolved at import time in `storage.py`:

```python
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"
```

> **Warning:** The `DATA_DIR` directory must be writable by the application process. When running in Docker, mount a volume to this path (see [Docker Configuration](#docker-configuration)).

---

## Provider Authentication

Each AI provider requires its own credentials. Only the credentials for your chosen `AI_PROVIDER` need to be set.

### Claude (Anthropic)

Claude supports two authentication methods. Use **one** of the following:

#### Option 1: API Key

Authenticate directly with an Anthropic API key.

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

```env
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-api03-...
```

#### Option 2: Vertex AI

Use Claude through Google Cloud's Vertex AI platform.

| Variable | Description |
|---|---|
| `CLAUDE_CODE_USE_VERTEX` | Set to `1` to enable Vertex AI |
| `CLOUD_ML_REGION` | Google Cloud region (e.g., `us-central1`) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Your Google Cloud project ID |

```env
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

> **Note:** When using Vertex AI, the `ANTHROPIC_API_KEY` variable is not required. Authentication is handled through Google Cloud credentials (e.g., Application Default Credentials).

### Gemini (Google)

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API key |

```env
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=AIza...
```

### Cursor

| Variable | Description |
|---|---|
| `CURSOR_API_KEY` | Your Cursor API key |

```env
AI_PROVIDER=cursor
CURSOR_API_KEY=cur-...
```

---

## Server Settings

These variables control the uvicorn server and are read directly via `os.getenv()` in `main.py`. They are **not** part of the Pydantic `Settings` class and cannot be set in the `.env` file loaded by Pydantic.

### `HOST`

Network interface to bind the server to.

| | |
|---|---|
| **Type** | `string` |
| **Default** | `0.0.0.0` |

```env
HOST=127.0.0.1
```

### `PORT`

Port number for the HTTP server.

| | |
|---|---|
| **Type** | `integer` |
| **Default** | `8000` |

```env
PORT=3000
```

### `DEBUG`

Enables uvicorn's auto-reload mode for development.

| | |
|---|---|
| **Type** | `string` |
| **Default** | `false` |
| **Activates when** | Set to `true` (case-insensitive) |

```env
DEBUG=true
```

The reload check in `main.py`:

```python
reload = os.getenv("DEBUG", "").lower() == "true"
```

> **Warning:** Do not enable `DEBUG` in production. Auto-reload watches the filesystem for changes and restarts the server process, which is unsuitable for serving real traffic.

---

## Per-Request Overrides

The `/api/generate` endpoint accepts optional fields that override the global configuration for a single request. This allows different projects to use different providers or models without changing server-wide settings.

```python
# src/docsfy/models.py
class GenerateRequest(BaseModel):
    ai_provider: Literal["claude", "gemini", "cursor"] | None = None
    ai_model: str | None = None
    ai_cli_timeout: int | None = Field(default=None, gt=0)
```

When a field is `None` (omitted from the request), the global setting is used:

```python
# src/docsfy/main.py
ai_provider = request.ai_provider or settings.ai_provider
ai_model = request.ai_model or settings.ai_model
ai_cli_timeout = request.ai_cli_timeout or settings.ai_cli_timeout
```

Example API call with overrides:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/repo",
    "ai_provider": "gemini",
    "ai_model": "gemini-2.5-pro",
    "ai_cli_timeout": 180
  }'
```

---

## Docker Configuration

The Docker image pre-installs all three provider CLIs (Claude Code, Cursor Agent, and Gemini CLI) and exposes port `8000`.

### docker-compose.yaml

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

Key points:

- **`env_file: .env`** -- loads your `.env` file into the container environment.
- **`./data:/data`** -- maps a local `data/` directory to the container's `/data` path, matching the `DATA_DIR` default. This persists the database and generated sites across container restarts.

### Environment in the Dockerfile

The Dockerfile sets two environment variables for runtime:

```dockerfile
ENV PATH="/home/appuser/.local/bin:/home/appuser/.npm-global/bin:${PATH}"
ENV HOME="/home/appuser"
```

- `PATH` ensures the Claude, Cursor, and Gemini CLI binaries are discoverable.
- `HOME` is set explicitly for OpenShift compatibility, where containers run as a random UID without a passwd entry.

---

## Complete `.env.example`

```env
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

---

## Reference Table

| Variable | Default | Type | Required | Description |
|---|---|---|---|---|
| `AI_PROVIDER` | `claude` | `string` | No | AI backend (`claude`, `gemini`, `cursor`) |
| `AI_MODEL` | `claude-opus-4-6[1m]` | `string` | No | Provider-specific model identifier |
| `AI_CLI_TIMEOUT` | `60` | `int` (> 0) | No | Seconds before an AI call times out |
| `LOG_LEVEL` | `INFO` | `string` | No | Logging verbosity |
| `DATA_DIR` | `/data` | `path` | No | Root directory for database and projects |
| `ANTHROPIC_API_KEY` | -- | `string` | For Claude (API) | Anthropic API key |
| `CLAUDE_CODE_USE_VERTEX` | -- | `flag` | For Claude (Vertex) | Set to `1` to use Vertex AI |
| `CLOUD_ML_REGION` | -- | `string` | For Claude (Vertex) | Google Cloud region |
| `ANTHROPIC_VERTEX_PROJECT_ID` | -- | `string` | For Claude (Vertex) | Google Cloud project ID |
| `GEMINI_API_KEY` | -- | `string` | For Gemini | Google Gemini API key |
| `CURSOR_API_KEY` | -- | `string` | For Cursor | Cursor API key |
| `HOST` | `0.0.0.0` | `string` | No | Server bind address |
| `PORT` | `8000` | `int` | No | Server port |
| `DEBUG` | `false` | `string` | No | Enable auto-reload (`true`/`false`) |
