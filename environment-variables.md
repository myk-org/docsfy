# Environment Variables

Complete reference for all environment variables used to configure docsfy. These variables control AI provider selection, authentication, CLI behavior, and logging.

## Quick Reference

| Variable | Default | Required | Category |
|----------|---------|----------|----------|
| [`AI_PROVIDER`](#ai_provider) | `claude` | No | AI Configuration |
| [`AI_MODEL`](#ai_model) | `claude-opus-4-6[1m]` | No | AI Configuration |
| [`AI_CLI_TIMEOUT`](#ai_cli_timeout) | `60` | No | AI Configuration |
| [`ANTHROPIC_API_KEY`](#anthropic_api_key) | — | Conditional | Claude Authentication |
| [`CLAUDE_CODE_USE_VERTEX`](#claude_code_use_vertex) | — | Conditional | Claude Authentication |
| [`CLOUD_ML_REGION`](#cloud_ml_region) | — | Conditional | Claude Authentication |
| [`ANTHROPIC_VERTEX_PROJECT_ID`](#anthropic_vertex_project_id) | — | Conditional | Claude Authentication |
| [`GEMINI_API_KEY`](#gemini_api_key) | Conditional | Gemini Authentication |
| [`CURSOR_API_KEY`](#cursor_api_key) | — | Conditional | Cursor Authentication |
| [`LOG_LEVEL`](#log_level) | `INFO` | No | Logging |

## Setting Environment Variables

docsfy reads environment variables from a `.env` file at startup via `docker-compose.yaml`:

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

Create a `.env` file in the project root based on the provided `.env.example` template. See the [complete example](#complete-env-example) at the bottom of this page.

---

## AI Configuration

These variables control which AI provider and model docsfy uses for documentation generation, and how long CLI operations are allowed to run.

### `AI_PROVIDER`

Selects the AI CLI tool used to analyze repositories and generate documentation content.

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

The provider determines which authentication variables are required. See [Authentication](#authentication) below.

```bash
AI_PROVIDER=claude
```

> **Note:** docsfy performs an availability check (a lightweight "Hi" prompt) before starting generation to verify the selected provider's CLI is installed and authenticated.

### `AI_MODEL`

Specifies the AI model identifier passed to the selected provider's CLI via the `--model` flag.

| | |
|---|---|
| **Default** | `claude-opus-4-6[1m]` |
| **Accepted values** | Any valid model identifier for the selected provider |
| **Required** | No |

The model identifier is passed directly to the provider binary. Use a model identifier supported by your chosen provider:

```bash
# Claude (default)
AI_MODEL=claude-opus-4-6[1m]

# Gemini example
AI_MODEL=gemini-2.5-pro

# Cursor example
AI_MODEL=claude-opus-4-6
```

> **Tip:** The default model `claude-opus-4-6[1m]` uses Claude's 1M token context window, which allows the AI to analyze large repositories more effectively during the planning and content generation stages.

### `AI_CLI_TIMEOUT`

Maximum time in **minutes** that a single AI CLI subprocess is allowed to run before being terminated.

| | |
|---|---|
| **Default** | `60` |
| **Unit** | Minutes |
| **Required** | No |

This timeout applies to each individual AI CLI invocation during the generation pipeline — both the planning stage (Stage 2) and each page generation call (Stage 3). Prompts are passed to the subprocess via stdin:

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

```bash
AI_CLI_TIMEOUT=60
```

> **Warning:** Setting this value too low may cause generation to fail for large repositories that require extensive analysis. If you experience timeout errors, increase this value.

---

## Authentication

Each AI provider requires its own authentication credentials. You only need to configure credentials for the provider specified by `AI_PROVIDER`.

### Claude Authentication

Claude supports two authentication methods. Use **one** of the following options.

#### Option 1: Direct API Key

##### `ANTHROPIC_API_KEY`

API key for direct authentication with the Anthropic API.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, if using Claude with direct API key authentication |

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

> **Warning:** Never commit API keys to version control. Always use the `.env` file or a secrets manager.

#### Option 2: Google Cloud Vertex AI

For organizations using Claude through Google Cloud's Vertex AI platform, set all three of the following variables:

##### `CLAUDE_CODE_USE_VERTEX`

Enables Vertex AI authentication mode for Claude Code CLI.

| | |
|---|---|
| **Default** | — |
| **Accepted values** | `1` (to enable) |
| **Required** | Yes, if using Vertex AI authentication |

```bash
CLAUDE_CODE_USE_VERTEX=1
```

##### `CLOUD_ML_REGION`

Google Cloud region where the Vertex AI endpoint is deployed.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, if `CLAUDE_CODE_USE_VERTEX=1` |

```bash
CLOUD_ML_REGION=us-east5
```

##### `ANTHROPIC_VERTEX_PROJECT_ID`

Google Cloud project ID that has Vertex AI enabled with Claude model access.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, if `CLAUDE_CODE_USE_VERTEX=1` |

```bash
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project-id
```

> **Note:** When using Vertex AI, you must also mount your Google Cloud credentials into the container. The `docker-compose.yaml` maps `~/.config/gcloud` as a read-only volume:
> ```yaml
> volumes:
>   - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
> ```

#### Complete Vertex AI Example

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project-id
```

### Gemini Authentication

##### `GEMINI_API_KEY`

API key for authenticating with the Google Gemini CLI.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, if `AI_PROVIDER=gemini` |

```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=AIza...
```

### Cursor Authentication

##### `CURSOR_API_KEY`

API key for authenticating with the Cursor Agent CLI.

| | |
|---|---|
| **Default** | — |
| **Required** | Yes, if `AI_PROVIDER=cursor` |

```bash
AI_PROVIDER=cursor
CURSOR_API_KEY=cur-...
```

> **Note:** Cursor uses the `--workspace` flag instead of setting the subprocess `cwd`, so its provider configuration sets `uses_own_cwd=True` internally.

---

## Logging

### `LOG_LEVEL`

Controls the verbosity of application logging output.

| | |
|---|---|
| **Default** | `INFO` |
| **Accepted values** | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| **Required** | No |

```bash
LOG_LEVEL=INFO
```

| Level | Use case |
|-------|----------|
| `DEBUG` | Verbose output including AI CLI commands, subprocess I/O, and JSON parsing details. Useful for troubleshooting generation failures. |
| `INFO` | Standard operational logging — generation requests, stage transitions, completion status. |
| `WARNING` | Unexpected conditions that don't prevent operation, such as retried parsing attempts. |
| `ERROR` | Failures in generation, CLI invocation errors, and database issues. |
| `CRITICAL` | Application-level failures that prevent the service from operating. |

> **Tip:** Set `LOG_LEVEL=DEBUG` when troubleshooting AI CLI integration issues. This will log the full commands being executed and the raw output from the AI provider, which is invaluable for diagnosing parsing or authentication failures.

---

## Complete `.env` Example

A fully annotated `.env` file covering all available environment variables:

```bash
# ===================
# AI Configuration
# ===================

# AI provider: claude | gemini | cursor
AI_PROVIDER=claude

# Model identifier passed to the provider's --model flag
AI_MODEL=claude-opus-4-6[1m]

# Timeout (in minutes) for each AI CLI subprocess invocation
AI_CLI_TIMEOUT=60

# ===================
# Claude - Option 1: API Key
# ===================
# ANTHROPIC_API_KEY=sk-ant-...

# ===================
# Claude - Option 2: Vertex AI
# ===================
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=us-east5
# ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project-id

# ===================
# Gemini
# ===================
# GEMINI_API_KEY=AIza...

# ===================
# Cursor
# ===================
# CURSOR_API_KEY=cur-...

# ===================
# Logging
# ===================
LOG_LEVEL=INFO
```

---

## Provider Configuration Summary

The following table shows which environment variables are relevant for each provider:

| Variable | Claude (API Key) | Claude (Vertex) | Gemini | Cursor |
|----------|:---:|:---:|:---:|:---:|
| `AI_PROVIDER` | `claude` | `claude` | `gemini` | `cursor` |
| `AI_MODEL` | Yes | Yes | Yes | Yes |
| `AI_CLI_TIMEOUT` | Yes | Yes | Yes | Yes |
| `ANTHROPIC_API_KEY` | **Required** | — | — | — |
| `CLAUDE_CODE_USE_VERTEX` | — | **Required** | — | — |
| `CLOUD_ML_REGION` | — | **Required** | — | — |
| `ANTHROPIC_VERTEX_PROJECT_ID` | — | **Required** | — | — |
| `GEMINI_API_KEY` | — | — | **Required** | — |
| `CURSOR_API_KEY` | — | — | — | **Required** |
| `LOG_LEVEL` | Yes | Yes | Yes | Yes |
