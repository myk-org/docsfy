# Introduction

docsfy is an open-source FastAPI service that automatically generates polished, production-ready documentation sites from GitHub repositories using AI CLI tools. Point it at any repository — public or private — and docsfy will analyze the entire codebase, plan a documentation structure, generate content page by page, and render it all into a static HTML site with sidebar navigation, dark/light theme support, client-side search, and syntax highlighting.

## Why docsfy?

Writing documentation is one of the most valuable — and most neglected — parts of software development. Teams skip it because it's time-consuming, and existing tools still require you to write the content yourself. docsfy takes a different approach: let AI read your code and write the docs for you.

Instead of parsing syntax trees or extracting docstrings, docsfy gives an AI CLI tool full access to your repository. The AI explores your codebase the same way a developer would — reading source files, configuration, tests, and project structure — then produces comprehensive, Mintlify-quality documentation that explains not just *what* the code does, but *how* and *why*.

## How It Works

docsfy runs a four-stage generation pipeline for every documentation request:

```
POST /api/generate  ←  repo URL
      |
      v
 +-----------+    +---------------+    +---------------+    +------------+
 |  1. Clone |───>|  2. AI Planner|───>| 3. AI Content |───>| 4. HTML    |
 |  Repo     |    |  (plan.json)  |    |  Generator    |    | Renderer   |
 +-----------+    +---------------+    +---------------+    +------------+
                                                                  |
                                                                  v
                                                          Static HTML site
```

1. **Clone Repository** — Shallow clone (`--depth 1`) of the target GitHub repo into a temporary directory. Supports both HTTPS and SSH URLs.

2. **AI Planner** — The AI CLI runs with its working directory set to the cloned repo. It explores the entire repository and outputs a `plan.json` file defining pages, sections, and navigation hierarchy.

3. **AI Content Generator** — For each page defined in `plan.json`, the AI CLI runs again with full repo access. Pages are generated concurrently using async execution with semaphore-limited concurrency. Each page is cached as Markdown at `/data/projects/{name}/cache/pages/*.md`.

4. **HTML Renderer** — Converts Markdown pages and `plan.json` into a polished static HTML site using Jinja2 templates with bundled CSS and JavaScript assets.

## Multi-Provider AI Support

docsfy is provider-agnostic. It supports three AI CLI tools through a unified provider configuration:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

| Provider | Binary | Command | CWD Handling |
|----------|--------|---------|--------------|
| Claude Code | `claude` | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| Gemini CLI | `gemini` | `gemini --model <model> --yolo` | subprocess `cwd` = repo path |
| Cursor Agent | `agent` | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag |

All providers receive prompts via stdin and return output via stdout:

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

Async execution is handled through `asyncio.to_thread(subprocess.run, ...)`, returning a `tuple[bool, str]` of success status and output. Before generation begins, docsfy runs a lightweight availability check against the configured provider.

> **Tip:** The default provider is Claude Code with the `claude-opus-4-6[1m]` model, which provides a 1M token context window — large enough to analyze substantial codebases in a single pass.

## Configuration

docsfy is configured through environment variables. Create a `.env` file based on the following template:

```bash
# AI Configuration
AI_PROVIDER=claude                    # claude, gemini, or cursor
AI_MODEL=claude-opus-4-6[1m]         # Model to use for generation
AI_CLI_TIMEOUT=60                    # Timeout in minutes

# Claude - Option 1: API Key
ANTHROPIC_API_KEY=sk-ant-...

# Claude - Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=us-central1
# ANTHROPIC_VERTEX_PROJECT_ID=my-project

# Gemini
# GEMINI_API_KEY=...

# Cursor
# CURSOR_API_KEY=...

# Logging
LOG_LEVEL=INFO
```

| Setting | Default | Description |
|---------|---------|-------------|
| `AI_PROVIDER` | `claude` | Which AI CLI tool to use |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI |
| `AI_CLI_TIMEOUT` | `60` | Maximum generation time in minutes |

> **Note:** Only one provider needs to be configured. Set the `AI_PROVIDER` variable and provide the corresponding API key or credentials.

## API

docsfy exposes a REST API for managing documentation generation:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository URL |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details (timestamp, commit SHA, pages) |
| `DELETE` | `/api/projects/{name}` | Remove a project and its generated docs |
| `GET` | `/api/projects/{name}/download` | Download the generated site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve the generated static HTML documentation |
| `GET` | `/health` | Health check endpoint |

Generate documentation for any GitHub repository with a single API call:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo"}'
```

## Generated Output

The rendered documentation site includes features you'd expect from premium documentation platforms:

- **Sidebar navigation** — Structured from the AI-generated `plan.json`
- **Dark/light theme** — Toggle with persistent preference
- **Client-side search** — Full-text search via lunr.js or similar
- **Syntax highlighting** — Code blocks rendered with highlight.js
- **Responsive design** — Works on desktop and mobile
- **Card layouts and callout boxes** — Note, warning, and info styles

The generated output is organized on disk as:

```
/data/projects/{project-name}/
  plan.json             # Documentation structure from AI
  cache/
    pages/*.md          # AI-generated Markdown (cached for incremental updates)
  site/                 # Final rendered HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

## Incremental Updates

docsfy tracks the last commit SHA for each project in its SQLite database. When you request regeneration:

1. The repository is fetched and the current SHA is compared against the stored SHA
2. If the code has changed, the AI Planner re-evaluates the documentation structure
3. Only pages affected by the changes are regenerated
4. Unchanged pages are served from the Markdown cache

This means subsequent updates are significantly faster than the initial generation.

> **Note:** Incremental updates rely on the cached Markdown files in `/data/projects/{name}/cache/pages/`. If the cache is cleared, a full regeneration will be triggered.

## Deployment

docsfy ships as a Docker container built on `python:3.12-slim`. The container includes all three AI CLI tools pre-installed so you can switch providers without rebuilding.

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

The service runs as a non-root user (`appuser`) with OpenShift-compatible GID 0 permissions and starts with:

```bash
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

> **Warning:** The `--dangerously-skip-permissions` flag (Claude) and `--yolo` flag (Gemini) grant the AI CLI unrestricted access within the container. Always run docsfy in an isolated environment and never mount sensitive host directories.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Web framework | FastAPI + uvicorn |
| Templating | Jinja2 |
| Markdown processing | Python markdown library |
| Database | SQLite (via aiosqlite) |
| Code highlighting | highlight.js |
| Client-side search | lunr.js |
| Build system | hatchling |
| Package manager | uv |
| Container | Docker (multi-stage, `python:3.12-slim`) |
| Python | 3.12+ |
