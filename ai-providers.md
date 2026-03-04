# AI Providers

docsfy supports three AI CLI tools for documentation generation: **Claude Code**, **Gemini CLI**, and **Cursor Agent**. Each provider is invoked as a subprocess, receiving prompts via stdin and returning structured output. You can switch between providers at any time through environment configuration.

## Provider Overview

| Provider | Binary | Default | Authentication |
|----------|--------|---------|----------------|
| Claude Code | `claude` | Yes | API key or Vertex AI |
| Gemini CLI | `gemini` | No | API key |
| Cursor Agent | `agent` | No | API key |

All three providers are installed in the Docker image at build time and available immediately. docsfy verifies the selected provider is reachable with a lightweight availability check before starting any generation.

## Configuration

Provider selection and behavior are controlled through three environment variables in your `.env` file:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60
```

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_PROVIDER` | Which provider to use (`claude`, `gemini`, or `agent`) | `claude` |
| `AI_MODEL` | The model identifier passed to the provider CLI | `claude-opus-4-6[1m]` |
| `AI_CLI_TIMEOUT` | Maximum time in minutes for a single AI invocation | `60` |

> **Note:** The `AI_MODEL` value is passed directly to the selected provider's `--model` flag. Make sure the model identifier is valid for your chosen provider.

## Provider Architecture

Each provider is defined as a `ProviderConfig` dataclass:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

- **`binary`** — the CLI executable name
- **`build_cmd`** — a callable that constructs the full command with model and path arguments
- **`uses_own_cwd`** — whether the provider manages its own working directory (via a flag) instead of relying on subprocess `cwd`

All providers are invoked the same way internally:

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

Async execution is handled via `asyncio.to_thread(subprocess.run, ...)`, returning a `tuple[bool, str]` of success status and output.

## Claude Code

Claude Code is the default provider. It uses Anthropic's `claude` CLI tool in pipe mode.

### Command

```
claude --model <model> --dangerously-skip-permissions -p
```

| Flag | Purpose |
|------|---------|
| `--model <model>` | Specifies the AI model to use |
| `--dangerously-skip-permissions` | Skips interactive permission prompts for automated use |
| `-p` | Pipe mode — reads prompt from stdin and writes output to stdout |

The subprocess `cwd` is set to the cloned repository path, giving Claude full filesystem access to explore the codebase.

### Authentication

Claude Code supports two authentication methods.

#### Option 1: API Key

The simplest setup — provide your Anthropic API key:

```bash
# .env
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

#### Option 2: Google Cloud Vertex AI

For organizations using Google Cloud, Claude Code can authenticate through Vertex AI:

```bash
# .env
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

When using Vertex AI, you also need to mount your Google Cloud credentials into the container:

```yaml
# docker-compose.yaml
volumes:
  - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

> **Tip:** Vertex AI authentication is useful in enterprise environments where API keys are managed centrally through Google Cloud IAM.

### Installation

Claude Code is installed in the Docker image during build:

```dockerfile
RUN curl -fsSL https://claude.ai/install.sh | bash
```

## Gemini CLI

Gemini CLI uses Google's `gemini` command-line tool with auto-approval enabled.

### Command

```
gemini --model <model> --yolo
```

| Flag | Purpose |
|------|---------|
| `--model <model>` | Specifies the Gemini model to use |
| `--yolo` | Allows operations without interactive confirmation |

Like Claude Code, the subprocess `cwd` is set to the cloned repository path.

### Authentication

Gemini CLI authenticates with a Google API key:

```bash
# .env
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=AIza...
```

### Installation

Gemini CLI is installed globally via npm during the Docker build:

```dockerfile
RUN npm install -g @google/gemini-cli
```

## Cursor Agent

Cursor Agent uses the `agent` CLI tool. Unlike the other providers, it manages its own working directory through a `--workspace` flag rather than subprocess `cwd`.

### Command

```
agent --force --model <model> --print --workspace <path>
```

| Flag | Purpose |
|------|---------|
| `--force` | Forces execution without prompts |
| `--model <model>` | Specifies the model to use |
| `--print` | Prints output to stdout instead of applying changes |
| `--workspace <path>` | Points the agent at the cloned repository path |

### Authentication

Cursor Agent authenticates with a Cursor API key:

```bash
# .env
AI_PROVIDER=agent
AI_MODEL=claude-opus-4-6
CURSOR_API_KEY=cur_...
```

When running in Docker, mount the Cursor configuration directory:

```yaml
# docker-compose.yaml
volumes:
  - ./cursor:/home/appuser/.config/cursor
```

### Installation

Cursor Agent is installed in the Docker image during build:

```dockerfile
RUN curl -fsSL https://cursor.com/install | bash
```

## Switching Providers

To switch providers, update `AI_PROVIDER` and the relevant authentication variable in your `.env` file, then restart the service.

**Switch to Gemini:**

```bash
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=AIza...
```

**Switch to Cursor Agent:**

```bash
AI_PROVIDER=agent
AI_MODEL=claude-opus-4-6
CURSOR_API_KEY=cur_...
```

**Switch back to Claude (default):**

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
ANTHROPIC_API_KEY=sk-ant-...
```

> **Warning:** Changing the provider or model between regenerations may produce inconsistent documentation style. For best results, use the same provider for the full lifecycle of a project's docs.

## Complete `.env` Example

A full `.env` file with all provider options (uncomment the section matching your provider):

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Option 1: API Key
ANTHROPIC_API_KEY=sk-ant-...

# Claude - Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=us-east5
# ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project

# Gemini
# GEMINI_API_KEY=AIza...

# Cursor
# CURSOR_API_KEY=cur_...

# Logging
LOG_LEVEL=INFO
```

## Docker Compose with All Providers

The `docker-compose.yaml` mounts credentials for all providers. Only the volumes relevant to your chosen provider are needed, but including all of them allows switching without modifying the compose file:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro  # Claude (Vertex AI)
      - ./cursor:/home/appuser/.config/cursor              # Cursor Agent
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Availability Check

Before starting a generation, docsfy sends a lightweight "Hi" prompt to the configured provider. This validates that:

- The CLI binary is installed and accessible
- Authentication credentials are valid
- The provider is responsive

If the availability check fails, the generation request returns an error immediately rather than failing partway through the pipeline.

## Response Parsing

All providers return free-form text that may contain JSON. docsfy extracts structured data using a multi-strategy parser:

1. **Direct JSON parse** — attempt to parse the entire output as JSON
2. **Brace matching** — extract the outermost `{...}` object from the output
3. **Code block extraction** — find JSON inside markdown code blocks (`` ```json ... ``` ``)
4. **Regex recovery** — fallback pattern matching for malformed JSON

This approach ensures reliable structured output regardless of which provider is used or how it formats its response.
