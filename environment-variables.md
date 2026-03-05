# Environment Variables

docsfy is configured entirely through environment variables. This page provides a complete reference for every variable the service recognizes, organized by category.

## Quick Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AI_PROVIDER` | `claude` | No | AI provider to use for documentation generation |
| `AI_MODEL` | `claude-opus-4-6[1m]` | No | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | No | Timeout for AI CLI calls (minutes) |
| `ANTHROPIC_API_KEY` | — | Conditional | API key for Claude (direct access) |
| `CLAUDE_CODE_USE_VERTEX` | — | Conditional | Enable Claude via Google Vertex AI |
| `CLOUD_ML_REGION` | — | Conditional | Google Cloud region for Vertex AI |
| `ANTHROPIC_VERTEX_PROJECT_ID` | — | Conditional | GCP project ID for Vertex AI |
| `GEMINI_API_KEY` | — | Conditional | API key for Gemini CLI |
| `CURSOR_API_KEY` | — | Conditional | API key for Cursor agent |
| `LOG_LEVEL` | `INFO` | No | Application logging level |

---

## AI Configuration

These core variables control which AI provider and model docsfy uses to analyze repositories and generate documentation content.

### `AI_PROVIDER`

Selects the AI CLI tool used for both the planning and content generation stages of the pipeline.

- **Default:** `claude`
- **Valid values:** `claude`, `gemini`, `cursor`

Each provider maps to a specific binary and command invocation pattern:

| Provider Value | Binary | Command Pattern |
|---------------|--------|-----------------|
| `claude` | `claude` | `claude --model <model> --dangerously-skip-permissions -p` |
| `gemini` | `gemini` | `gemini --model <model> --yolo` |
| `cursor` | `agent` | `agent --force --model <model> --print --workspace <path>` |

```bash
AI_PROVIDER=claude
```

> **Note:** The selected provider's CLI tool must be installed and available on the system `PATH`. The Dockerfile installs all three providers by default.

### `AI_MODEL`

Specifies the model identifier passed to the AI CLI via its `--model` flag. The appropriate value depends on your chosen `AI_PROVIDER`.

- **Default:** `claude-opus-4-6[1m]`

```bash
# Claude (default)
AI_MODEL=claude-opus-4-6[1m]

# Gemini
AI_MODEL=gemini-2.5-pro

# Cursor
AI_MODEL=claude-opus-4-6
```

> **Tip:** Consult your AI provider's documentation for a list of available model identifiers. Using a model with a large context window is recommended since docsfy feeds entire repository contents to the AI.

### `AI_CLI_TIMEOUT`

Maximum time in **minutes** that a single AI CLI subprocess is allowed to run before being terminated. This applies to each individual AI invocation — both the planning stage and each page generation call.

- **Default:** `60`
- **Unit:** Minutes

```bash
AI_CLI_TIMEOUT=60
```

Large repositories with many files may require a longer timeout for the planning stage. If you encounter timeout errors during generation, increase this value.

> **Warning:** Setting this value too high means a stuck AI process could block a generation job for an extended period. Setting it too low may cause generation failures on complex repositories.

---

## Provider API Keys

Each AI provider requires its own authentication credentials. You only need to configure the key(s) for the provider you have selected via `AI_PROVIDER`.

### Claude

Claude Code supports two authentication methods. Use **one** of the following options.

#### Option 1: Direct API Key

Authenticate directly with the Anthropic API using an API key.

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
```

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

#### Option 2: Google Vertex AI

Route Claude requests through Google Cloud's Vertex AI platform. This is useful for organizations that manage AI access through GCP.

```bash
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project-id
```

| Variable | Description |
|----------|-------------|
| `CLAUDE_CODE_USE_VERTEX` | Set to `1` to enable Vertex AI mode |
| `CLOUD_ML_REGION` | GCP region where the Vertex AI endpoint is available (e.g., `us-east5`) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Your Google Cloud project ID with Vertex AI enabled |

> **Note:** When using Vertex AI, you must also mount your gcloud credentials into the container. The docker-compose configuration handles this automatically by mounting `~/.config/gcloud` as a read-only volume:
> ```yaml
> volumes:
>   - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
> ```

### Gemini

Authenticate with the Gemini CLI using a Google AI API key.

```bash
GEMINI_API_KEY=AIza...
```

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Your Google AI API key for Gemini |

### Cursor

Authenticate with the Cursor agent CLI using a Cursor API key.

```bash
CURSOR_API_KEY=cur-...
```

| Variable | Description |
|----------|-------------|
| `CURSOR_API_KEY` | Your Cursor API key |

> **Note:** Cursor also requires a configuration directory mount. The docker-compose configuration maps `./cursor` to `/home/appuser/.config/cursor` inside the container.

---

## Logging

### `LOG_LEVEL`

Controls the verbosity of the application's log output.

- **Default:** `INFO`
- **Valid values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

```bash
LOG_LEVEL=INFO
```

| Level | Use Case |
|-------|----------|
| `DEBUG` | Troubleshooting generation failures; includes AI CLI stdout/stderr and detailed pipeline tracing |
| `INFO` | Normal operation; logs generation start/completion, API requests, and stage transitions |
| `WARNING` | Only unexpected conditions that don't prevent operation |
| `ERROR` | Failures in generation, AI CLI crashes, and unhandled exceptions |
| `CRITICAL` | Application startup failures |

> **Tip:** Set `LOG_LEVEL=DEBUG` when troubleshooting generation issues. This will include the full AI CLI output in the logs, making it easier to diagnose prompt or model problems.

---

## Complete `.env` Example

Below is a complete `.env` file showing all available variables. Uncomment and fill in the values for your chosen provider.

```bash
# ── AI Configuration ──────────────────────────────────────
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# ── Claude - Option 1: Direct API Key ────────────────────
# ANTHROPIC_API_KEY=

# ── Claude - Option 2: Vertex AI ─────────────────────────
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=
# ANTHROPIC_VERTEX_PROJECT_ID=

# ── Gemini ────────────────────────────────────────────────
# GEMINI_API_KEY=

# ── Cursor ────────────────────────────────────────────────
# CURSOR_API_KEY=

# ── Logging ───────────────────────────────────────────────
LOG_LEVEL=INFO
```

> **Warning:** Never commit your `.env` file to version control. Add `.env` to your `.gitignore` to prevent accidental exposure of API keys.

---

## Docker Compose Usage

Environment variables are loaded from the `.env` file automatically by docker-compose:

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

You can also override individual variables directly in the `environment` section:

```yaml
services:
  docsfy:
    build: .
    env_file: .env
    environment:
      - AI_PROVIDER=gemini
      - AI_MODEL=gemini-2.5-pro
      - LOG_LEVEL=DEBUG
```

> **Note:** Variables set in the `environment` section take precedence over those in the `env_file`.

---

## Provider Configuration Examples

### Minimal setup with Claude (API Key)

```bash
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx
```

### Claude via Vertex AI

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-docs-project
```

### Gemini

```bash
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxx
```

### Cursor

```bash
AI_PROVIDER=cursor
AI_MODEL=claude-opus-4-6
CURSOR_API_KEY=cur-xxxxxxxxxxxxxxxxxx
```
