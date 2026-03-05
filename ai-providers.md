# AI Providers

docsfy supports multiple AI CLI providers for documentation generation. Each provider is an external CLI tool that docsfy invokes as a subprocess to analyze repositories and generate content. This page covers the supported providers, how they are configured, and how docsfy interacts with them.

## Supported Providers

docsfy supports three AI CLI providers out of the box:

| Provider | CLI Binary | Description |
|----------|-----------|-------------|
| **Claude Code** | `claude` | Anthropic's CLI for Claude models |
| **Cursor Agent** | `agent` | Cursor's autonomous coding agent |
| **Gemini CLI** | `gemini` | Google's Gemini CLI tool |

All three providers are installed in the Docker image during build and are available at runtime regardless of which one is selected.

### Installation in Docker

Each provider is installed using its official installation method:

```bash
# Claude Code
curl -fsSL https://claude.ai/install.sh | bash

# Cursor Agent
curl -fsSL https://cursor.com/install | bash

# Gemini CLI
npm install -g @google/gemini-cli
```

> **Note:** Provider CLIs are unpinned and always install the latest version. This ensures access to the newest features and models but means builds are not fully reproducible.

## Provider Configuration

### The `ProviderConfig` Dataclass

Each provider is represented by a frozen dataclass that defines its binary, command builder, and CWD behavior:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

| Field | Type | Description |
|-------|------|-------------|
| `binary` | `str` | The CLI executable name (e.g., `claude`, `gemini`, `agent`) |
| `build_cmd` | `Callable` | A function that constructs the full command with arguments |
| `uses_own_cwd` | `bool` | Whether the provider manages its own working directory. Defaults to `False` |

## Command Interfaces

Each provider has a distinct CLI interface with different flags for model selection, permission handling, and output control.

### Claude Code

```bash
claude --model <model> --dangerously-skip-permissions -p
```

| Flag | Purpose |
|------|---------|
| `--model <model>` | Specifies which Claude model to use |
| `--dangerously-skip-permissions` | Bypasses interactive permission prompts for file access |
| `-p` | Enables prompt mode — reads the prompt from stdin |

Claude Code accepts the prompt via stdin and writes its response to stdout. It relies on the subprocess working directory to access repository files.

### Gemini CLI

```bash
gemini --model <model> --yolo
```

| Flag | Purpose |
|------|---------|
| `--model <model>` | Specifies which Gemini model to use |
| `--yolo` | Runs in unrestricted mode, skipping confirmation prompts |

Like Claude Code, Gemini CLI reads from stdin and uses the subprocess working directory for file access.

### Cursor Agent

```bash
agent --force --model <model> --print --workspace <path>
```

| Flag | Purpose |
|------|---------|
| `--force` | Forces execution without interactive confirmations |
| `--model <model>` | Specifies which model to use |
| `--print` | Outputs results to stdout instead of applying changes |
| `--workspace <path>` | Sets the working directory for the agent explicitly |

> **Warning:** Cursor Agent is the only provider that manages its own working directory via the `--workspace` flag. Its `ProviderConfig` sets `uses_own_cwd=True`, which changes how docsfy invokes the subprocess. See [CWD Handling](#cwd-handling) below.

## CWD Handling

docsfy needs each AI provider to have access to the cloned repository so it can explore the codebase and generate accurate documentation. How the working directory is set depends on the provider.

### Standard Approach (Claude Code & Gemini CLI)

For providers where `uses_own_cwd=False` (the default), docsfy sets the working directory using the `cwd` parameter of `subprocess.run`:

```python
subprocess.run(
    cmd,
    input=prompt,
    capture_output=True,
    text=True,
    cwd=repo_path  # subprocess starts in the cloned repo directory
)
```

This means the AI CLI process starts with its current working directory set to the repository root. The AI can then use relative paths to read any file in the repo.

### Workspace Flag Approach (Cursor Agent)

Cursor Agent handles its own CWD via the `--workspace` flag. When `uses_own_cwd=True`, docsfy passes the repository path as a command-line argument instead of setting `cwd`:

```python
# Cursor handles CWD internally via --workspace
cmd = f"agent --force --model {model} --print --workspace {repo_path}"

subprocess.run(
    cmd,
    input=prompt,
    capture_output=True,
    text=True
    # No cwd parameter — Cursor uses --workspace instead
)
```

> **Tip:** The `uses_own_cwd` flag in `ProviderConfig` allows docsfy to transparently handle both CWD strategies. The pipeline code checks this flag to decide whether to set `cwd` on the subprocess or let the provider handle it.

### CWD in the Pipeline

The working directory is set for both AI-driven pipeline stages:

1. **Stage 2 — AI Planner:** The AI runs with access to the full repository so it can analyze the codebase and produce a `plan.json` with the documentation structure.
2. **Stage 3 — AI Content Generator:** For each page defined in `plan.json`, the AI runs with access to the repository so it can explore relevant source files and write accurate content.

## Provider Selection

### Environment Variable

The active provider is selected via the `AI_PROVIDER` environment variable:

```bash
AI_PROVIDER=claude    # Use Claude Code (default)
AI_PROVIDER=gemini    # Use Gemini CLI
AI_PROVIDER=cursor    # Use Cursor Agent
```

### Default Configuration

| Setting | Environment Variable | Default Value |
|---------|---------------------|---------------|
| Provider | `AI_PROVIDER` | `claude` |
| Model | `AI_MODEL` | `claude-opus-4-6[1m]` |
| Timeout | `AI_CLI_TIMEOUT` | `60` (minutes) |

### Full `.env` Example

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
# ANTHROPIC_VERTEX_PROJECT_ID=my-project

# Gemini
# GEMINI_API_KEY=AIza...

# Cursor
# CURSOR_API_KEY=cur_...

# Logging
LOG_LEVEL=INFO
```

> **Note:** Only the credentials for your selected provider need to be set. Claude Code supports two authentication methods: direct API key (`ANTHROPIC_API_KEY`) or Google Cloud Vertex AI (`CLAUDE_CODE_USE_VERTEX` with associated GCP settings).

### Mounting Credentials in Docker

When running with Docker Compose, provider credentials can be passed via the `.env` file or mounted as volumes. For example, Claude Code with Vertex AI authentication requires GCP credentials:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro  # GCP credentials for Vertex AI
      - ./cursor:/home/appuser/.config/cursor              # Cursor config
```

## Invocation Details

### Subprocess Execution

All providers follow the same invocation pattern regardless of their specific CLI flags:

```python
subprocess.run(
    cmd,
    input=prompt,          # Prompt is passed via stdin
    capture_output=True,   # Capture stdout and stderr
    text=True              # Use text mode (not binary)
)
```

Execution is wrapped in `asyncio.to_thread()` for non-blocking operation within the async FastAPI pipeline:

```python
result = await asyncio.to_thread(subprocess.run, ...)
```

The return type from the invocation wrapper is `tuple[bool, str]` — a boolean success flag and the output string.

### Availability Check

Before starting the generation pipeline, docsfy performs a lightweight availability check by sending a simple `"Hi"` prompt to the configured provider. This validates that:

- The CLI binary is installed and on `PATH`
- Authentication credentials are valid
- The provider is responsive

If this check fails, the generation request is rejected before any expensive operations (like cloning the repository) begin.

### JSON Response Parsing

AI providers return free-form text that contains JSON. docsfy uses a multi-strategy extraction approach to reliably parse structured data from provider responses:

1. **Direct parse** — Attempt `json.loads()` on the raw output
2. **Brace matching** — Find the outermost `{...}` block by matching braces
3. **Code block extraction** — Look for ` ```json ... ``` ` markdown fenced blocks
4. **Regex recovery** — Use regex patterns as a last-resort fallback

This layered approach handles the variety of response formats that different AI providers produce — some return pure JSON, others wrap it in markdown, and others include conversational text around the structured data.

## Provider Comparison

| Aspect | Claude Code | Gemini CLI | Cursor Agent |
|--------|------------|-----------|--------------|
| Binary | `claude` | `gemini` | `agent` |
| Permission bypass | `--dangerously-skip-permissions` | `--yolo` | `--force` |
| Output mode | `-p` (prompt mode) | Implicit (stdin/stdout) | `--print` |
| CWD method | Subprocess `cwd` param | Subprocess `cwd` param | `--workspace` flag |
| `uses_own_cwd` | `False` | `False` | `True` |
| Auth options | API Key or Vertex AI | API Key | API Key |
| Install method | Shell script (`curl`) | Shell script (`curl`) | npm global package |
