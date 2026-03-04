# AI CLI Integration

## Overview

docsfy delegates all AI-powered analysis and content generation to external CLI tools running as subprocesses. Rather than embedding SDK clients or managing API connections directly, docsfy invokes AI command-line interfaces — Claude Code, Gemini CLI, and Cursor Agent — through a unified **provider pattern**. This architecture keeps the core application thin, avoids tight coupling to any single AI vendor, and allows operators to swap providers with a single environment variable.

This page covers the provider abstraction, subprocess lifecycle, asynchronous execution model, response parsing strategies, and runtime availability checking.

## Provider Pattern

### The ProviderConfig Dataclass

Each supported AI CLI tool is represented by a frozen dataclass that captures three concerns: which binary to invoke, how to assemble the command, and whether the tool manages its own working directory.

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

| Field | Type | Purpose |
|-------|------|---------|
| `binary` | `str` | Name of the CLI executable (used for availability checks and invocation) |
| `build_cmd` | `Callable` | Factory function that assembles the full command list from model name, prompt, and repository path |
| `uses_own_cwd` | `bool` | When `False`, the subprocess `cwd` is set to the repo path. When `True`, the provider handles workspace targeting via its own flags |

The dataclass is frozen (`frozen=True`) to ensure provider configurations are immutable after creation — no runtime code can accidentally mutate a provider's binary path or command builder.

### Registered Providers

Three providers are registered, each with distinct invocation semantics:

```python
PROVIDERS = {
    "claude": ProviderConfig(
        binary="claude",
        build_cmd=lambda model, path: [
            "claude", "--model", model,
            "--dangerously-skip-permissions", "-p"
        ],
    ),
    "gemini": ProviderConfig(
        binary="gemini",
        build_cmd=lambda model, path: [
            "gemini", "--model", model, "--yolo"
        ],
    ),
    "cursor": ProviderConfig(
        binary="agent",
        build_cmd=lambda model, path: [
            "agent", "--force", "--model", model,
            "--print", "--workspace", str(path)
        ],
        uses_own_cwd=True,
    ),
}
```

#### Provider Command Reference

| Provider | Binary | Key Flags | CWD Strategy |
|----------|--------|-----------|-------------|
| **Claude Code** | `claude` | `--dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| **Gemini CLI** | `gemini` | `--yolo` | subprocess `cwd` = repo path |
| **Cursor Agent** | `agent` | `--force --print --workspace <path>` | `--workspace` flag (`uses_own_cwd=True`) |

> **Warning:** Claude Code's `--dangerously-skip-permissions` flag bypasses all interactive permission prompts. This is required for unattended subprocess execution but means the AI has unrestricted access to the cloned repository. docsfy mitigates this by running generation against temporary shallow clones, never against production codebases.

#### Why `uses_own_cwd` Matters

Most CLI tools inherit their working directory from the subprocess `cwd` parameter, giving them implicit access to the target repository. Cursor Agent is the exception — it requires an explicit `--workspace` flag to specify which directory to analyze. The `uses_own_cwd` field controls this branching:

```python
def build_subprocess_args(provider: ProviderConfig, model: str, repo_path: Path) -> dict:
    cmd = provider.build_cmd(model, repo_path)
    kwargs = {
        "input": prompt,
        "capture_output": True,
        "text": True,
        "timeout": timeout_seconds,
    }
    if not provider.uses_own_cwd:
        kwargs["cwd"] = str(repo_path)
    return cmd, kwargs
```

## Subprocess Invocation

### Execution Model

All AI CLI tools are invoked via `subprocess.run()`. Prompts are passed through **stdin** rather than command-line arguments, which avoids shell escaping issues and removes prompt length limitations imposed by argument list size limits.

```python
result = subprocess.run(
    cmd,
    input=prompt,
    capture_output=True,
    text=True,
    timeout=timeout_seconds,
    cwd=repo_path,  # omitted when uses_own_cwd=True
)
```

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `input` | The prompt string | Feeds the prompt to the CLI tool via stdin |
| `capture_output` | `True` | Captures both stdout and stderr |
| `text` | `True` | Decodes output as UTF-8 strings (not bytes) |
| `timeout` | Configurable (default: 3600s) | Kills the process if it exceeds the time limit |
| `cwd` | Repository path | Sets the working directory for filesystem-aware providers |

### Return Convention

The invocation function returns a `tuple[bool, str]` representing success status and raw output:

```python
def run_ai_cli(provider: str, model: str, prompt: str, repo_path: Path) -> tuple[bool, str]:
    config = PROVIDERS[provider]
    cmd = config.build_cmd(model, repo_path)

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=AI_CLI_TIMEOUT * 60,
            **({"cwd": str(repo_path)} if not config.uses_own_cwd else {}),
        )
        if result.returncode == 0:
            return True, result.stdout
        return False, result.stderr or result.stdout
    except subprocess.TimeoutExpired:
        return False, f"AI CLI timed out after {AI_CLI_TIMEOUT} minutes"
    except FileNotFoundError:
        return False, f"AI CLI binary '{config.binary}' not found"
```

> **Note:** The function catches `FileNotFoundError` separately from general subprocess failures. This exception is raised by `subprocess.run()` when the binary specified in the command list does not exist on `PATH`, providing a clear diagnostic distinct from a tool that exists but exits with an error.

## Async Execution via `asyncio.to_thread`

### The Problem

docsfy is a FastAPI application running on an asyncio event loop. `subprocess.run()` is a **blocking** call — it halts the calling thread until the subprocess completes. For AI CLI invocations that can run for several minutes, blocking the event loop would freeze the entire server: no health checks, no status queries, no concurrent generation requests.

### The Solution

docsfy wraps blocking subprocess calls with `asyncio.to_thread()`, which offloads the blocking function to a separate thread from the default executor's thread pool:

```python
async def run_ai_cli_async(
    provider: str, model: str, prompt: str, repo_path: Path
) -> tuple[bool, str]:
    return await asyncio.to_thread(
        run_ai_cli, provider, model, prompt, repo_path
    )
```

This keeps the event loop free to handle other requests while the AI CLI runs in a background thread.

### Concurrent Page Generation

During the content generation stage, multiple documentation pages can be generated concurrently. A semaphore limits parallelism to prevent resource exhaustion:

```python
async def generate_pages(pages: list[dict], repo_path: Path) -> list[str]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)

    async def generate_one(page: dict) -> str:
        async with semaphore:
            success, content = await run_ai_cli_async(
                provider=AI_PROVIDER,
                model=AI_MODEL,
                prompt=build_page_prompt(page, repo_path),
                repo_path=repo_path,
            )
            if not success:
                raise GenerationError(f"Failed to generate page: {page['title']}")
            return content

    return await asyncio.gather(*[generate_one(page) for page in pages])
```

> **Tip:** The semaphore value should be tuned based on available system resources and the AI provider's rate limits. Each concurrent page generation spawns a separate CLI subprocess, consuming memory and (for API-backed providers) an API connection.

## Multi-Strategy JSON Response Parsing

AI CLI tools return their output as raw text on stdout. When docsfy expects structured data — such as the `plan.json` documentation structure from the planning stage — it must extract valid JSON from output that often contains conversational preamble, markdown formatting, or trailing commentary.

docsfy uses a **multi-strategy extraction pipeline** that tries four parsing approaches in order of specificity, falling through to the next strategy on failure.

### Strategy 1: Direct JSON Parse

The simplest case — the entire output is valid JSON:

```python
def try_direct_parse(text: str) -> dict | None:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None
```

This succeeds when the AI CLI returns clean JSON with no surrounding text.

### Strategy 2: Brace-Matching Extraction

Finds the outermost `{...}` pair and attempts to parse the substring between them:

```python
def try_brace_matching(text: str) -> dict | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, char in enumerate(text[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
```

This handles output like:

```
Here's the documentation plan I created:
{"pages": [...], "navigation": [...]}
Let me know if you need changes.
```

### Strategy 3: Markdown Code Block Extraction

AI tools frequently wrap JSON in markdown fenced code blocks. This strategy extracts content from `` ```json `` or bare `` ``` `` blocks:

```python
def try_code_block_extraction(text: str) -> dict | None:
    pattern = r"```(?:json)?\s*\n(.*?)\n\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue
    return None
```

This handles output like:

````
I've analyzed the repository. Here's the plan:

```json
{
  "pages": [
    {"title": "Getting Started", "slug": "getting-started"}
  ]
}
```
````

### Strategy 4: Regex Recovery Fallback

A last-resort strategy that attempts to find JSON-like structures using pattern matching with more permissive rules:

```python
def try_regex_recovery(text: str) -> dict | None:
    # Find anything that looks like a JSON object
    pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    return None
```

### Combined Pipeline

The strategies execute in sequence, returning the first successful result:

```python
def extract_json(text: str) -> dict:
    strategies = [
        ("direct_parse", try_direct_parse),
        ("brace_matching", try_brace_matching),
        ("code_block", try_code_block_extraction),
        ("regex_recovery", try_regex_recovery),
    ]

    for name, strategy in strategies:
        result = strategy(text)
        if result is not None:
            logger.debug(f"JSON extracted via {name} strategy")
            return result

    raise JSONExtractionError(
        f"Failed to extract JSON from AI response ({len(text)} chars)"
    )
```

> **Note:** The ordering is deliberate. Direct parse is cheapest and handles the ideal case. Brace-matching handles most real-world outputs. Code block extraction catches markdown-wrapped responses. Regex recovery is the most permissive but also the most likely to produce false positives, so it runs last.

## Availability Checking

Before starting a generation pipeline, docsfy verifies that the configured AI CLI tool is installed, accessible, and functional. This prevents long-running pipelines from failing minutes into execution because of a missing binary or expired credentials.

### The Check

Availability is tested by running a lightweight prompt — a simple "Hi" — through the full invocation pipeline:

```python
async def check_ai_availability(provider: str, model: str) -> tuple[bool, str]:
    """Verify the AI CLI tool is installed and responding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        success, output = await run_ai_cli_async(
            provider=provider,
            model=model,
            prompt="Hi",
            repo_path=Path(tmpdir),
        )
        if success:
            return True, f"Provider '{provider}' is available"
        return False, f"Provider '{provider}' check failed: {output}"
```

This check exercises the entire code path:

1. **Binary resolution** — verifies the CLI executable exists on `PATH`
2. **Authentication** — confirms API keys or credentials are valid
3. **Model access** — validates the configured model is available to the account
4. **Network connectivity** — ensures the CLI can reach its backend API

> **Tip:** The availability check uses a temporary directory as the `cwd` rather than an actual repository. This keeps the check fast and avoids side effects — no files are read or created in any project directory.

### When the Check Runs

The availability check executes at the start of every generation request, before the repository is cloned:

```python
async def generate_docs(repo_url: str, project_name: str):
    # Step 0: Verify AI CLI is available
    available, message = await check_ai_availability(AI_PROVIDER, AI_MODEL)
    if not available:
        raise AIProviderUnavailable(message)

    # Step 1: Clone repository
    repo_path = await clone_repo(repo_url)
    # ... continue pipeline
```

This fail-fast approach provides immediate feedback through the API response rather than leaving a project stuck in `generating` status.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | Which AI CLI to use (`claude`, `gemini`, or `cursor`) |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the CLI's `--model` flag |
| `AI_CLI_TIMEOUT` | `60` | Maximum execution time per CLI invocation, in **minutes** |

### Example `.env` Configuration

```bash
# Use Claude Code with Vertex AI backend
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude authentication via Vertex AI
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project

# Or use a direct API key instead
# ANTHROPIC_API_KEY=sk-ant-...
```

```bash
# Use Gemini CLI
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
AI_CLI_TIMEOUT=45
GEMINI_API_KEY=AIza...
```

```bash
# Use Cursor Agent
AI_PROVIDER=cursor
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60
CURSOR_API_KEY=cur_...
```

> **Warning:** The `AI_CLI_TIMEOUT` value is specified in **minutes**, not seconds. It is converted to seconds (`AI_CLI_TIMEOUT * 60`) before being passed to `subprocess.run(timeout=...)`. Setting this too low will cause generation failures on large repositories; setting it too high may leave zombie processes consuming resources.

## Container Setup

The AI CLI tools are installed in the Docker image at build time. Since docsfy supports multiple providers, **all three** CLIs are installed regardless of which provider is configured at runtime:

```dockerfile
# Install Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Install Cursor Agent
RUN curl -fsSL https://cursor.com/install | bash

# Install Gemini CLI
RUN npm install -g @google/gemini-cli
```

> **Warning:** CLI tools are installed without version pinning (always latest). This means Docker image rebuilds may pull newer CLI versions with different behavior. For reproducible builds, consider pinning versions or using a fixed base image tag.

### Credential Mounting

AI CLI tools require authentication credentials at runtime. These are mounted as Docker volumes rather than baked into the image:

```yaml
# docker-compose.yaml
volumes:
  - ~/.config/gcloud:/home/appuser/.config/gcloud:ro  # Gemini / Vertex AI
  - ./cursor:/home/appuser/.config/cursor              # Cursor Agent
```

API key-based authentication (Claude, Gemini) is configured through environment variables in the `.env` file.

## Adding a New Provider

To add support for a new AI CLI tool, register a new entry in the `PROVIDERS` dictionary:

```python
PROVIDERS["new-tool"] = ProviderConfig(
    binary="new-tool-cli",
    build_cmd=lambda model, path: [
        "new-tool-cli", "--model", model, "--noninteractive"
    ],
    uses_own_cwd=False,  # True if the tool has its own workspace flag
)
```

Then set the environment variables:

```bash
AI_PROVIDER=new-tool
AI_MODEL=preferred-model-name
```

No other code changes are needed. The provider pattern, subprocess invocation, JSON parsing, and availability checking all work generically across any CLI tool that accepts prompts on stdin and returns output on stdout.
