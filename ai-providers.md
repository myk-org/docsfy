# AI Providers

docsfy delegates documentation generation to external AI CLI tools. It supports three providers out of the box: **Claude Code**, **Gemini CLI**, and **Cursor Agent**. Each provider is invoked as a subprocess, receiving prompts via stdin and returning generated content via stdout.

## Supported Providers

| Provider | CLI Binary | Installation Method |
|----------|-----------|---------------------|
| Claude Code | `claude` | `curl -fsSL https://claude.ai/install.sh \| bash` |
| Gemini CLI | `gemini` | `npm install -g @google/gemini-cli` |
| Cursor Agent | `agent` | `curl -fsSL https://cursor.com/install \| bash` |

All three CLIs are installed automatically in the Docker image. When running outside Docker, you must install the CLI for your chosen provider manually.

### How Providers Are Invoked

Each provider uses different CLI flags and working-directory strategies:

| Provider | Command Pattern | CWD Handling |
|----------|----------------|--------------|
| Claude | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` set to repo path |
| Gemini | `gemini --model <model> --yolo` | subprocess `cwd` set to repo path |
| Cursor | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag (manages its own cwd) |

Prompts are passed via stdin to all providers:

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

Execution is non-blocking — each invocation runs inside `asyncio.to_thread()`, and up to 5 pages are generated concurrently:

```python
MAX_CONCURRENT_PAGES = 5
```

### Provider Architecture

Provider configuration is managed by the `ai-cli-runner` package, which docsfy re-exports through its `ai_client` module:

```python
# src/docsfy/ai_client.py
from ai_cli_runner import (
    PROVIDERS,
    VALID_AI_PROVIDERS,
    ProviderConfig,
    call_ai_cli,
    check_ai_cli_available,
    get_ai_cli_timeout,
    run_parallel_with_limit,
)
```

Each provider is represented as a `ProviderConfig` dataclass:

```python
@dataclass
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

The valid provider set is enforced at runtime:

```python
VALID_AI_PROVIDERS = frozenset({"claude", "gemini", "cursor"})
```

## Selecting a Provider

The AI provider is resolved through a layered configuration system. Per-request values take precedence over environment defaults.

### Priority Order

1. **Request-level override** — `ai_provider` field in the API request body
2. **Environment variable** — `AI_PROVIDER` in your `.env` file
3. **Default** — `claude`

The resolution happens in the API handler:

```python
# src/docsfy/main.py
ai_provider = request.ai_provider or settings.ai_provider
```

### Setting the Provider via Environment

Create or edit your `.env` file:

```bash
AI_PROVIDER=claude
```

Valid values are `claude`, `gemini`, or `cursor`.

### Setting the Provider per Request

Override the provider for a single generation request:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/my-project",
    "ai_provider": "gemini"
  }'
```

The `ai_provider` field accepts a `Literal["claude", "gemini", "cursor"]` value. Any other value will be rejected by Pydantic validation.

### Availability Check

Before starting generation, docsfy verifies the selected provider is installed and responsive:

```python
# src/docsfy/main.py
available, msg = await check_ai_cli_available(ai_provider, ai_model)
if not available:
    await update_project_status(project_name, status="error", error_message=msg)
    return
```

If the CLI binary is missing or fails the availability check, the project status is set to `error` with a descriptive message.

## Model Selection

Model selection follows the same layered resolution pattern as provider selection.

### Priority Order

1. **Request-level override** — `ai_model` field in the API request body
2. **Environment variable** — `AI_MODEL` in your `.env` file
3. **Default** — `claude-opus-4-6[1m]`

```python
# src/docsfy/main.py
ai_model = request.ai_model or settings.ai_model
```

### The `[1m]` Notation

The default model identifier `claude-opus-4-6[1m]` uses a bracket suffix to specify the context window size — in this case, 1 million tokens. This is a valid part of the Claude model identifier, not docsfy-specific syntax.

```python
# src/docsfy/config.py
ai_model: str = "claude-opus-4-6[1m]"  # [1m] = 1 million token context window
```

### Configuring via Environment

```bash
# .env
AI_MODEL=claude-opus-4-6[1m]
```

### Configuring per Request

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/my-project",
    "ai_provider": "gemini",
    "ai_model": "gemini-2.5-pro"
  }'
```

### Model Examples by Provider

| Provider | Example Models |
|----------|---------------|
| Claude | `claude-opus-4-6[1m]`, `claude-opus-4-6` |
| Gemini | `gemini-2.5-pro` |
| Cursor | `opus` |

> **Note:** The model string is passed directly to the provider CLI via the `--model` flag. Refer to each provider's documentation for the full list of supported model identifiers.

## Timeout Tuning

AI CLI calls can take significant time for large repositories. The timeout controls how long docsfy waits for each CLI invocation before treating it as a failure.

### Configuration

The timeout is specified in seconds and must be a positive integer (greater than 0).

```python
# src/docsfy/config.py
ai_cli_timeout: int = Field(default=60, gt=0)
```

### Priority Order

1. **Request-level override** — `ai_cli_timeout` field in the API request body
2. **Environment variable** — `AI_CLI_TIMEOUT` in your `.env` file
3. **Default** — `60` seconds

```python
# src/docsfy/main.py
ai_cli_timeout=request.ai_cli_timeout or settings.ai_cli_timeout,
```

### Setting via Environment

```bash
# .env
AI_CLI_TIMEOUT=120
```

### Setting per Request

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/my-project",
    "ai_cli_timeout": 180
  }'
```

### Validation

A timeout of `0` or any negative value is rejected at startup or request time:

```python
ai_cli_timeout: int | None = Field(default=None, gt=0)
```

> **Tip:** Large repositories with many source files may need higher timeouts. Start with the default of 60 seconds and increase if you see timeout errors in the generation logs.

> **Warning:** Setting an extremely high timeout (e.g., 600+) means a stuck provider process will block that generation slot for the entire duration. The system runs up to 5 page generations concurrently, so stuck processes can exhaust capacity.

## Provider-Specific Setup

Each provider requires its own authentication credentials. Configure these in your `.env` file.

### Claude Code

Claude Code supports two authentication methods: a direct API key or Vertex AI.

#### Option 1: API Key

```bash
# .env
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

#### Option 2: Vertex AI

For organizations using Google Cloud's Vertex AI to access Claude models:

```bash
# .env
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project-id
```

When running in Docker, mount your gcloud credentials as a read-only volume so the Claude CLI can authenticate with Vertex AI:

```yaml
# docker-compose.yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

> **Note:** The `CLAUDE_CODE_USE_VERTEX`, `CLOUD_ML_REGION`, and `ANTHROPIC_VERTEX_PROJECT_ID` variables are read directly by the Claude Code CLI — docsfy passes them through to the subprocess environment automatically.

### Gemini CLI

```bash
# .env
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
```

The Gemini CLI is installed globally via npm during the Docker build:

```dockerfile
RUN mkdir -p /home/appuser/.npm-global \
    && npm config set prefix '/home/appuser/.npm-global' \
    && npm install -g @google/gemini-cli
```

### Cursor Agent

```bash
# .env
AI_PROVIDER=cursor
CURSOR_API_KEY=your-cursor-api-key
```

When running in Docker, you may need to mount the Cursor configuration directory for persistent settings:

```yaml
volumes:
  - ./cursor:/home/appuser/.config/cursor
```

## Full Configuration Reference

Here is the complete `.env.example` with all AI-related settings:

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

The configuration is loaded using Pydantic Settings, which reads from the `.env` file automatically:

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

Settings are cached for the lifetime of the process via `@lru_cache`, so environment changes require a restart.

## Combining Provider, Model, and Timeout

All three settings can be overridden together in a single request:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/my-project",
    "ai_provider": "gemini",
    "ai_model": "gemini-2.5-pro",
    "ai_cli_timeout": 120
  }'
```

This generates documentation using the Gemini CLI with the `gemini-2.5-pro` model and a 2-minute timeout per page — regardless of what is configured in the `.env` file.

> **Tip:** Per-request overrides are useful for testing a different provider without changing your deployment configuration. The `.env` values remain the defaults for all other requests.
