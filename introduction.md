# Introduction

docsfy is an open-source service that automatically generates polished, production-quality documentation websites from GitHub repositories using AI CLI tools. Point it at a repository, and docsfy will analyze the codebase, plan a documentation structure, generate content for each page, and render a complete static HTML site -- all without writing a single line of documentation by hand.

## What is docsfy?

Documentation is one of the most valuable -- and most neglected -- parts of any software project. Writing and maintaining docs takes time that most teams would rather spend building features. docsfy solves this by leveraging AI to read your code and produce comprehensive, well-structured documentation sites automatically.

At its core, docsfy is a **FastAPI service** that orchestrates AI CLI tools to transform a repository URL into a fully navigable documentation website. The generated sites include sidebar navigation, dark/light theme toggling, client-side search, syntax-highlighted code blocks, and responsive layouts -- comparable to what you'd get from purpose-built documentation platforms like Mintlify.

## How It Works

docsfy processes each repository through a four-stage generation pipeline:

```
POST /api/generate  <-- repo URL
      |
      v
+----------+   +--------------+   +------------+   +----------+
|  Clone   |-->|  AI Planner  |-->| AI Content  |-->|   HTML   |
|  Repo    |   |  (plan.json) |   |  Generator  |   | Renderer |
+----------+   +--------------+   +------------+   +----------+
```

### Stage 1: Clone Repository

docsfy performs a shallow clone (`--depth 1`) of the target repository into a temporary directory. Both SSH and HTTPS URLs are supported, and private repositories work seamlessly using your system's existing git credentials.

### Stage 2: AI Planner

An AI CLI tool explores the entire cloned repository -- reading source files, configs, tests, and project structure -- then produces a `plan.json` that defines the documentation's pages, sections, and navigation hierarchy. The AI has full access to the codebase, so it can make informed decisions about what to document and how to organize it.

### Stage 3: AI Content Generator

For each page defined in `plan.json`, the AI CLI runs again with full repository access, generating detailed markdown content. Pages can be generated concurrently using async execution with semaphore-limited concurrency, and results are cached to disk for incremental updates:

```
/data/projects/{project-name}/
  plan.json             # doc structure from AI
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # final rendered HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

### Stage 4: HTML Renderer

The final stage converts the markdown pages and `plan.json` into a polished static HTML site using Jinja2 templates with bundled CSS and JavaScript. The rendered site includes:

- **Sidebar navigation** with hierarchical page structure
- **Dark/light theme toggle** with client-side persistence
- **Client-side search** powered by a pre-built search index
- **Syntax highlighting** via highlight.js
- **Card layouts and callout boxes** (note, warning, info)
- **Responsive design** for mobile and desktop

## Multi-Provider AI Support

docsfy supports three AI CLI providers through a standardized provider configuration pattern:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

Each provider has its own invocation style, but docsfy abstracts the differences behind a unified interface:

| Provider | Binary | Command Pattern | CWD Handling |
|----------|--------|-----------------|--------------|
| Claude | `claude` | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| Gemini | `gemini` | `gemini --model <model> --yolo` | subprocess `cwd` = repo path |
| Cursor | `agent` | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag |

Prompts are passed to AI CLIs via standard input using `subprocess.run()`, and async execution is handled through `asyncio.to_thread()`:

```python
# Invocation returns a success flag and the raw output
result: tuple[bool, str] = await run_ai_cli(prompt, cwd=repo_path)
```

Before starting a generation, docsfy performs an availability check by sending a lightweight "Hi" prompt to verify the configured AI CLI is reachable and authenticated.

> **Tip:** Claude is the default provider. You can switch providers by setting the `AI_PROVIDER` environment variable to `gemini` or `cursor`.

## AI Response Parsing

AI CLI tools don't always return clean JSON. docsfy uses a multi-strategy extraction approach to reliably parse structured responses:

1. **Direct JSON parse** -- try the output as-is
2. **Brace-matching** -- find the outermost `{...}` JSON object
3. **Markdown code block extraction** -- extract JSON from fenced code blocks
4. **Regex recovery** -- fallback pattern matching

This layered approach ensures robust handling of the varied output formats that different AI providers produce.

## API Endpoints

docsfy exposes a REST API for managing documentation generation:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start doc generation for a repository URL |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details, commit SHA, and page list |
| `DELETE` | `/api/projects/{name}` | Remove a project and its generated docs |
| `GET` | `/api/projects/{name}/download` | Download the site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve generated documentation directly |
| `GET` | `/health` | Health check |

You can either serve documentation directly from docsfy or download the generated site as a tarball for self-hosting on any static file server.

## Incremental Updates

docsfy doesn't regenerate everything from scratch each time. It tracks the last commit SHA per project in its SQLite database and uses an intelligent update strategy:

1. On re-generation, fetch the repository and compare the current commit SHA against the stored SHA
2. If the repository has changed, re-run the AI Planner to detect structural changes
3. If the documentation structure is unchanged, regenerate only pages affected by the code changes
4. If the structure itself changed, regenerate the full site

> **Note:** Incremental updates can dramatically reduce generation time and AI API costs for repositories that change frequently.

## Quick Start

### Running with Docker Compose

Create a `.env` file with your AI provider credentials:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Option 1: API Key
ANTHROPIC_API_KEY=your-api-key-here

# Claude - Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=us-central1
# ANTHROPIC_VERTEX_PROJECT_ID=your-project-id

# Logging
LOG_LEVEL=INFO
```

Start the service:

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

```bash
docker compose up -d
```

Then generate documentation for any repository:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/your-org/your-repo"}'
```

Once generation completes, view the docs at `http://localhost:8000/docs/your-repo/` or download them for self-hosting:

```bash
curl http://localhost:8000/api/projects/your-repo/download -o docs.tar.gz
```

> **Warning:** AI CLI tools are installed unpinned (always latest) inside the container. While this ensures you get the newest features, it means builds are not fully reproducible. Pin versions in your Dockerfile if reproducibility is critical.

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI + uvicorn |
| Templating | Jinja2 |
| Markdown processing | Python markdown library |
| Database | SQLite |
| Code highlighting | highlight.js |
| Client-side search | lunr.js |
| Build system | hatchling |
| Package manager | uv |
| Container | Docker (`python:3.12-slim`, multi-stage) |
| Python | 3.12+ |

## Core Value Proposition

docsfy occupies a unique space in the documentation tooling landscape:

- **Zero manual writing** -- AI reads your code and writes the docs for you
- **Always current** -- incremental updates keep documentation in sync with your codebase
- **Provider flexibility** -- choose between Claude, Gemini, or Cursor based on your preferences and API access
- **Self-hostable output** -- download generated sites as static HTML and host them anywhere
- **Production-quality rendering** -- dark/light themes, search, syntax highlighting, and responsive layouts out of the box
- **Simple deployment** -- a single Docker container with a REST API is all you need
