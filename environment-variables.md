# Environment Variables

docsfy is configured entirely through environment variables. This page is a complete reference for every variable the service recognizes, organized by category.

## Quick Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AI_PROVIDER` | `claude` | No | AI provider to use |
| `AI_MODEL` | `claude-opus-4-6[1m]` | No | Model identifier |
| `AI_CLI_TIMEOUT` | `60` | No | CLI timeout in minutes |
| `ANTHROPIC_API_KEY` | — | Conditional | Claude API key |
| `CLAUDE_CODE_USE_VERTEX` | — | Conditional | Enable Vertex AI for Claude |
| `CLOUD_ML_REGION` | — | Conditional | Google Cloud region |
| `ANTHROPIC_VERTEX_PROJECT_ID` | — | Conditional | GCP project ID |
| `GEMINI_API_KEY` | — | Conditional | Gemini API key |
| `CURSOR_API_KEY` | — | Conditional | Cursor API key |
| `LOG_LEVEL` | `INFO` | No | Application log level |

## Core AI Configuration

These variables control which AI provider and model docsfy uses for documentation generation.

### `AI_PROVIDER`

Selects the AI CLI tool used for both the planning and content-generation stages of the pipeline.

| | |
|---|---|
| **Default** | `claude` |
| **Accepted values** | `claude`, `gemini`, `cursor` |
| **Required** | No |

Each provider maps to a different CLI binary and invocation pattern:

| Provider value | Binary | Command pattern |
|----------------|--------|-----------------|
| `claude` | `claude` | `claude --model <model> --dangerously-skip-permissions -p` |
| `gemini` | `gemini` | `gemini --model <model> --yolo` |
| `cursor` | `agent` | `agent --force --model <model> --print --workspace <path>` |

```bash
# Use Gemini as the AI provider
AI_PROVIDER=gemini
```

> **Note:** The selected provider's CLI binary must be installed and available on `$PATH` inside the container. The default Dockerfile installs all three providers.

### `AI_MODEL`

Specifies the model identifier passed to the AI CLI tool.

| | |
|---|---|
| **Default** | `claude-opus-4-6[1m]` |
| **Required** | No |

The value is passed directly to the provider's `--model` flag. Valid model identifiers depend on the provider you have selected.

```bash
# Claude examples
AI_MODEL=claude-opus-4-6[1m]
AI_MODEL=claude-sonnet-4-6

# Gemini examples
AI_MODEL=gemini-2.5-pro

# Cursor examples
AI_MODEL=claude-sonnet-4-6
```

> **Tip:** When using Vertex AI with Claude, confirm that your chosen model is available in your configured `CLOUD_ML_REGION`.

### `AI_CLI_TIMEOUT`

Maximum time in **minutes** that a single AI CLI invocation is allowed to run before the process is terminated.

| | |
|---|---|
| **Default** | `60` |
| **Unit** | Minutes |
| **Required** | No |

This timeout applies individually to each CLI call — both planning and per-page content generation. Because the AI explores the full repository during generation, large codebases may need a higher timeout.

```bash
# Allow up to 90 minutes per AI CLI call
AI_CLI_TIMEOUT=90
```

> **Warning:** Setting this value too low may cause generation to fail on large repositories. The planner and each page generator run as separate CLI invocations, so the timeout applies per invocation, not to the entire pipeline.

## Authentication Keys

Each AI provider requires its own authentication credentials. You only need to configure credentials for the provider selected by `AI_PROVIDER`.

### `ANTHROPIC_API_KEY`

API key for authenticating with Claude when using direct API access (not Vertex AI).

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, when `AI_PROVIDER=claude` and Vertex AI is **not** configured |

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
```

> **Note:** This variable is ignored when Vertex AI authentication is enabled via `CLAUDE_CODE_USE_VERTEX=1`. You must use one authentication method or the other — not both.

### `GEMINI_API_KEY`

API key for authenticating with the Gemini CLI.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, when `AI_PROVIDER=gemini` |

```bash
GEMINI_API_KEY=AIzaSy...
```

### `CURSOR_API_KEY`

API key for authenticating with the Cursor Agent CLI.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, when `AI_PROVIDER=cursor` |

```bash
CURSOR_API_KEY=cur_...
```

## Vertex AI Settings (Claude)

As an alternative to `ANTHROPIC_API_KEY`, Claude can authenticate through Google Cloud Vertex AI. When Vertex AI is enabled, all three variables in this section must be set.

### `CLAUDE_CODE_USE_VERTEX`

Flag that switches Claude Code from direct API authentication to Vertex AI authentication.

| | |
|---|---|
| **Default** | — (disabled) |
| **Accepted values** | `1` to enable |
| **Required** | No |

```bash
CLAUDE_CODE_USE_VERTEX=1
```

### `CLOUD_ML_REGION`

The Google Cloud region where Vertex AI requests are routed.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, when `CLAUDE_CODE_USE_VERTEX=1` |

```bash
CLOUD_ML_REGION=us-east5
```

### `ANTHROPIC_VERTEX_PROJECT_ID`

The Google Cloud project ID that has the Vertex AI API enabled and contains your Claude model access.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, when `CLAUDE_CODE_USE_VERTEX=1` |

```bash
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project-123
```

> **Note:** When using Vertex AI, the container also needs access to Google Cloud credentials. The default `docker-compose.yaml` mounts the host's `gcloud` config directory as a read-only volume:
>
> ```yaml
> volumes:
>   - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
> ```

## Logging

### `LOG_LEVEL`

Controls the verbosity of docsfy's application logs.

| | |
|---|---|
| **Default** | `INFO` |
| **Accepted values** | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| **Required** | No |

```bash
# Enable verbose debug output
LOG_LEVEL=DEBUG
```

| Level | Use case |
|-------|----------|
| `DEBUG` | Troubleshooting generation failures — logs full CLI commands, raw AI output, and template rendering details |
| `INFO` | Normal operation — logs pipeline stage transitions, project status changes, and request handling |
| `WARNING` | Highlights non-fatal issues such as cache misses during incremental updates |
| `ERROR` | Logs failures in individual pipeline stages or API requests |
| `CRITICAL` | Logs only unrecoverable startup or runtime failures |

> **Tip:** Set `LOG_LEVEL=DEBUG` when diagnosing AI CLI failures. Debug output includes the full command invocation and raw CLI output, which makes it much easier to tell whether a problem is in the prompt, the model, or the authentication.

## Example `.env` File

A minimal configuration using Claude with a direct API key:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - API Key
ANTHROPIC_API_KEY=sk-ant-api03-...

# Logging
LOG_LEVEL=INFO
```

A configuration using Claude through Vertex AI:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Vertex AI
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project-123

# Logging
LOG_LEVEL=INFO
```

A configuration using Gemini:

```bash
# AI Configuration
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
AI_CLI_TIMEOUT=60

# Gemini
GEMINI_API_KEY=AIzaSy...

# Logging
LOG_LEVEL=INFO
```

> **Warning:** Never commit `.env` files containing real API keys to version control. The repository includes a `.env.example` template with placeholder values that is safe to commit.

## Provider Authentication Summary

The table below shows which authentication variables are required for each provider.

| Variable | `claude` (API key) | `claude` (Vertex AI) | `gemini` | `cursor` |
|----------|:------------------:|:--------------------:|:--------:|:--------:|
| `ANTHROPIC_API_KEY` | Required | — | — | — |
| `CLAUDE_CODE_USE_VERTEX` | — | Required (`1`) | — | — |
| `CLOUD_ML_REGION` | — | Required | — | — |
| `ANTHROPIC_VERTEX_PROJECT_ID` | — | Required | — | — |
| `GEMINI_API_KEY` | — | — | Required | — |
| `CURSOR_API_KEY` | — | — | — | Required |
