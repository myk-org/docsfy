# AI Providers

docsfy supports three AI CLI providers for documentation generation. Each provider uses its respective command-line tool to analyze repositories and produce content. This page covers how to configure, authenticate, and switch between providers.

## Supported Providers

| Provider | Binary | Description |
|----------|--------|-------------|
| Claude Code | `claude` | Anthropic's CLI for Claude models |
| Gemini CLI | `gemini` | Google's CLI for Gemini models |
| Cursor Agent | `agent` | Cursor's autonomous coding agent |

## Configuration

Provider selection is controlled through environment variables. Set these in your `.env` file or pass them directly to the container.

### Core Settings

```bash
# Which provider to use: claude, gemini, or cursor
AI_PROVIDER=claude

# Model identifier (provider-specific)
AI_MODEL=claude-opus-4-6[1m]

# Maximum time in minutes for a single AI CLI invocation
AI_CLI_TIMEOUT=60
```

### Switching Providers

To switch providers, update both `AI_PROVIDER` and `AI_MODEL` to match the target provider:

```bash
# Claude (default)
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]

# Gemini
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro

# Cursor
AI_PROVIDER=cursor
AI_MODEL=claude-opus-4-6[1m]
```

> **Warning:** The `AI_MODEL` value is passed directly to the provider's CLI. Make sure the model identifier is valid for your chosen provider. Using an incompatible model string will cause generation to fail.

## Provider Details

### How Providers Are Defined

Each provider is registered as a `ProviderConfig` with three properties:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

- **`binary`** — The CLI executable name that must be available on `$PATH`.
- **`build_cmd`** — A callable that constructs the full command list for the provider.
- **`uses_own_cwd`** — Whether the provider manages its own working directory via a flag (rather than relying on subprocess `cwd`).

### Claude Code

Claude Code is the default provider. It runs as a subprocess with the working directory set to the cloned repository.

**Command structure:**

```
claude --model <model> --dangerously-skip-permissions -p
```

| Aspect | Detail |
|--------|--------|
| Binary | `claude` |
| CWD handling | subprocess `cwd` set to repo path |
| Prompt delivery | via `stdin` (`subprocess.run(cmd, input=prompt)`) |
| `--dangerously-skip-permissions` | Allows unattended execution without interactive permission prompts |
| `-p` | Print mode — outputs result to stdout |

**Authentication — Option 1: API Key**

Set your Anthropic API key directly:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

**Authentication — Option 2: Vertex AI**

For Google Cloud Vertex AI-hosted Claude models, set these variables and mount your gcloud credentials:

```bash
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

When using Docker, mount your local gcloud config as a read-only volume:

```yaml
services:
  docsfy:
    volumes:
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

> **Tip:** Vertex AI authentication uses Application Default Credentials (ADC). Run `gcloud auth application-default login` on your host machine before starting the container.

**Installation:**

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

---

### Gemini CLI

Gemini CLI is Google's command-line interface for Gemini models.

**Command structure:**

```
gemini --model <model> --yolo
```

| Aspect | Detail |
|--------|--------|
| Binary | `gemini` |
| CWD handling | subprocess `cwd` set to repo path |
| Prompt delivery | via `stdin` (`subprocess.run(cmd, input=prompt)`) |
| `--yolo` | Skips confirmation prompts for unattended execution |

**Authentication:**

Set your Gemini API key:

```bash
GEMINI_API_KEY=...
```

**Installation:**

```bash
npm install -g @google/gemini-cli
```

> **Note:** Gemini CLI requires Node.js and npm to be installed. Both are included in the docsfy Docker image.

---

### Cursor Agent

Cursor Agent differs from the other providers in how it handles the working directory. Instead of relying on the subprocess `cwd`, it accepts a `--workspace` flag pointing to the repository path.

**Command structure:**

```
agent --force --model <model> --print --workspace <repo-path>
```

| Aspect | Detail |
|--------|--------|
| Binary | `agent` |
| CWD handling | `--workspace` flag (`uses_own_cwd=True`) |
| Prompt delivery | via `stdin` (`subprocess.run(cmd, input=prompt)`) |
| `--force` | Bypasses confirmation prompts |
| `--print` | Outputs result to stdout |

**Authentication:**

Set your Cursor API key:

```bash
CURSOR_API_KEY=...
```

When using Docker, mount the Cursor config directory:

```yaml
services:
  docsfy:
    volumes:
      - ./cursor:/home/appuser/.config/cursor
```

**Installation:**

```bash
curl -fsSL https://cursor.com/install | bash
```

## How Invocation Works

All providers follow the same invocation pattern regardless of their CLI differences:

1. **Availability check** — Before starting a generation job, docsfy sends a lightweight `"Hi"` prompt to verify the provider binary is installed, authenticated, and responsive.
2. **Prompt delivery** — The documentation prompt is passed via `stdin` using `subprocess.run(cmd, input=prompt, capture_output=True, text=True)`.
3. **Async execution** — Subprocess calls are wrapped with `asyncio.to_thread()` so they don't block the FastAPI event loop.
4. **Result** — Each invocation returns a `tuple[bool, str]` containing a success flag and the CLI output.

> **Note:** The `AI_CLI_TIMEOUT` setting (default: 60 minutes) applies to each individual AI CLI call. Complex repositories with many pages may require increasing this value.

## JSON Response Parsing

AI providers return structured data (such as `plan.json`) embedded in their output. docsfy uses a multi-strategy extraction pipeline to reliably parse JSON from the raw CLI output:

1. **Direct JSON parse** — Attempt to parse the entire output as JSON.
2. **Brace matching** — Locate the outermost `{...}` in the output and parse that substring.
3. **Markdown code block extraction** — Extract content from `` ```json `` fenced blocks.
4. **Regex fallback** — Last-resort pattern matching to recover JSON fragments.

This layered approach handles the variety of output formats different providers produce (some wrap JSON in markdown, others include preamble text, etc.).

## Docker Compose Reference

A complete `docker-compose.yaml` with all provider volumes and environment variables:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      # Claude: Vertex AI credentials (if using Vertex)
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
      # Cursor: config directory
      - ./cursor:/home/appuser/.config/cursor
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Complete `.env` Example

```bash
# --- Provider Selection ---
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# --- Claude Authentication ---
# Option 1: Direct API key
# ANTHROPIC_API_KEY=sk-ant-...

# Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=us-east5
# ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project

# --- Gemini Authentication ---
# GEMINI_API_KEY=...

# --- Cursor Authentication ---
# CURSOR_API_KEY=...

# --- General ---
LOG_LEVEL=INFO
```

> **Warning:** Never commit `.env` files containing API keys to version control. The project includes secret-detection tools (gitleaks, detect-secrets) in pre-commit hooks to help prevent accidental exposure.

## Troubleshooting

### Provider binary not found

If generation fails immediately, verify the provider binary is installed and on `$PATH`:

```bash
which claude   # Claude Code
which gemini   # Gemini CLI
which agent    # Cursor Agent
```

All three binaries are installed in the Docker image automatically. If running outside Docker, install them manually using the commands listed in each provider's section above.

### Authentication errors

- **Claude (API key):** Verify `ANTHROPIC_API_KEY` is set and valid.
- **Claude (Vertex):** Ensure all three Vertex variables are set (`CLAUDE_CODE_USE_VERTEX`, `CLOUD_ML_REGION`, `ANTHROPIC_VERTEX_PROJECT_ID`) and that your gcloud credentials are current. Run `gcloud auth application-default login` to refresh.
- **Gemini:** Verify `GEMINI_API_KEY` is set and valid.
- **Cursor:** Verify `CURSOR_API_KEY` is set and that the Cursor config directory is properly mounted.

### Timeout errors

If generation times out on large repositories, increase the timeout:

```bash
AI_CLI_TIMEOUT=120  # 2 hours
```
