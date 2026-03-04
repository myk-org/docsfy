# Introduction

docsfy is an open-source FastAPI service that automatically generates polished, production-quality static HTML documentation sites from GitHub repositories using AI CLI tools. Point it at a repository, and docsfy will analyze the codebase, plan a documentation structure, generate content for each page, and render a complete static site — all without manual intervention.

## The Problem

Documentation is one of the most important aspects of any software project, yet it remains one of the most neglected. The reasons are familiar:

- **Manual documentation is time-consuming.** Writing comprehensive docs for an evolving codebase requires significant ongoing effort.
- **Documentation drifts out of sync.** As code changes, docs become stale. Keeping them aligned is a constant maintenance burden.
- **Smaller projects can't justify the cost.** Many open-source projects lack the resources to maintain professional-quality documentation.
- **The tooling gap.** Existing documentation generators extract API signatures and docstrings, but they don't produce the kind of explanatory, tutorial-style content that helps users actually understand a project.

## The Solution

docsfy bridges this gap by leveraging AI CLI tools to read, understand, and document entire codebases. Rather than simply extracting existing comments, docsfy uses AI to analyze source code, configuration files, tests, and project structure — then generates comprehensive, well-structured documentation that explains not just *what* the code does, but *how* and *why*.

The result is a Mintlify-quality static HTML site with sidebar navigation, dark/light theme support, client-side search, syntax highlighting, and responsive design — ready to serve or self-host.

## Key Features

- **AI-powered content generation** — Uses AI to deeply analyze code and produce explanatory documentation, not just API stubs
- **Multiple AI providers** — Supports Claude Code, Cursor Agent, and Gemini CLI through a pluggable provider architecture
- **Full static site output** — Generates complete HTML sites with navigation, search, theming, and code highlighting
- **Incremental updates** — Tracks repository changes and regenerates only affected pages when code evolves
- **Serve or self-host** — Access docs directly from the API, or download as a `.tar.gz` archive to host anywhere
- **Simple API** — A single `POST` request kicks off the entire generation pipeline

## How It Works

docsfy runs a four-stage pipeline for each documentation generation request:

```
                    FastAPI Server
+--------------------------------------------------+
|                                                  |
|  POST /api/generate  <-- repo URL                |
|       |                                          |
|       v                                          |
|  +----------+   +--------------+   +----------+  |
|  |  Clone   |-->|  AI Planner  |-->| AI Content|  |
|  |  Repo    |   |  (plan.json) |   | Generator |  |
|  +----------+   +--------------+   +----------+  |
|                                         |        |
|                                         v        |
|                                    +----------+  |
|                                    |   HTML    |  |
|                                    | Renderer  |  |
|                                    +----+-----+  |
|                                         |        |
|  GET /docs/{project}/  <-- serves ------+        |
|  GET /api/status       <-- project list          |
|  GET /api/projects/{name}/download <-- tar.gz    |
|  GET /health           <-- health check          |
|                                                  |
|  Storage:                                        |
|  /data/docsfy.db  (SQLite: metadata)             |
|  /data/projects/  (filesystem: docs)             |
+--------------------------------------------------+
```

### Stage 1: Clone Repository

The target GitHub repository is shallow-cloned (`--depth 1`) into a temporary directory. Both SSH and HTTPS URLs are supported, and private repositories work through system git credentials.

### Stage 2: AI Planner

The AI CLI tool runs with its working directory set to the cloned repository, giving it full access to explore the codebase. It analyzes the project structure and produces a `plan.json` — a structured documentation plan containing pages, sections, and navigation hierarchy.

### Stage 3: AI Content Generator

For each page defined in `plan.json`, the AI CLI is invoked again with access to the repository. Pages can be generated concurrently using async execution with semaphore-limited concurrency. The resulting markdown files are cached for incremental updates.

### Stage 4: HTML Renderer

The markdown pages and `plan.json` are combined into a polished static HTML site using Jinja2 templates with bundled CSS and JavaScript assets. The rendered site includes sidebar navigation, dark/light theme toggle, client-side search (via lunr.js), and syntax highlighting (via highlight.js).

## AI Provider Support

docsfy uses a provider abstraction pattern to support multiple AI CLI tools. Each provider is configured as a dataclass:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

Three providers are supported out of the box:

| Provider | Binary | Command Pattern | CWD Handling |
|----------|--------|-----------------|--------------|
| Claude | `claude` | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| Gemini | `gemini` | `gemini --model <model> --yolo` | subprocess `cwd` = repo path |
| Cursor | `agent` | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag |

All providers use the same invocation pattern — prompts are passed via stdin to `subprocess.run()`, with async execution handled through `asyncio.to_thread()`:

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

> **Tip:** The default provider is Claude with the `claude-opus-4-6[1m]` model. You can switch providers by setting the `AI_PROVIDER` and `AI_MODEL` environment variables.

## Quick Start

Generate documentation for any GitHub repository with a single API call:

```bash
# Start the service
docker compose up -d

# Generate documentation for a repository
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/username/repo"}'

# Check generation status
curl http://localhost:8000/api/status

# View the generated documentation
open http://localhost:8000/docs/repo/

# Or download as a static site
curl http://localhost:8000/api/projects/repo/download > docs.tar.gz
```

## Configuration

docsfy is configured through environment variables. Create a `.env` file to customize the AI provider, model, and authentication:

```bash
# AI Configuration
AI_PROVIDER=claude              # Options: claude, gemini, cursor
AI_MODEL=claude-opus-4-6[1m]    # Model identifier
AI_CLI_TIMEOUT=60               # Timeout in minutes

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

> **Note:** AI CLI tools are installed unpinned (always latest) inside the Docker container. Claude, Cursor, and Gemini CLIs are all included in the container image.

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI + uvicorn |
| Language | Python 3.12+ |
| Templating | Jinja2 |
| Markdown processing | Python markdown library |
| Database | SQLite |
| Client-side search | lunr.js |
| Code highlighting | highlight.js |
| Build system | hatchling |
| Package manager | uv |
| Container | Docker (multi-stage, `python:3.12-slim`) |

## What's Next

Explore the rest of the documentation to learn about:

- **Getting Started** — Detailed setup and installation instructions
- **Configuration** — Full reference for all environment variables and options
- **API Reference** — Complete documentation of all API endpoints
- **AI Providers** — In-depth guide to configuring and switching between AI providers
- **Architecture** — Deep dive into the generation pipeline and system design
- **Deployment** — Production deployment with Docker and docker-compose
