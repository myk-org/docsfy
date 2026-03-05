# Architecture

docsfy is an open-source FastAPI service that generates polished, static HTML documentation sites from GitHub repositories using AI CLI tools. This page describes the system's high-level architecture, the four-stage generation pipeline, storage layout, and how internal components interact.

## System Overview

At its core, docsfy is a single FastAPI process backed by SQLite for metadata and a local filesystem for generated artifacts. When a user submits a repository URL, the server orchestrates a four-stage pipeline — clone, plan, generate, render — that produces a complete static documentation site.

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

## FastAPI Server

The application entry point is `docsfy.main:app`, served by uvicorn:

```
uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

### API Endpoints

The server exposes a REST API for triggering generation, querying status, and serving output:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository URL |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details (last generated, commit SHA, pages) |
| `DELETE` | `/api/projects/{name}` | Remove a project and all its generated docs |
| `GET` | `/api/projects/{name}/download` | Download the generated site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve generated static HTML documentation |
| `GET` | `/health` | Health check endpoint |

The `POST /api/generate` endpoint accepts a repository URL and kicks off the generation pipeline asynchronously. The `GET /docs/{project}/{path}` endpoint serves the final rendered HTML site directly from the filesystem, making docsfy a self-contained documentation host.

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI + uvicorn |
| Async runtime | asyncio with `threading` for subprocess calls |
| Templating | Jinja2 |
| Markdown parsing | Python markdown library |
| Database | SQLite (via aiosqlite or similar) |
| Client-side search | lunr.js |
| Code highlighting | highlight.js |
| Build system | hatchling |
| Package manager | uv (no pip) |
| Container runtime | Docker (multi-stage, `python:3.12-slim`) |

## The Four-Stage Generation Pipeline

Every documentation generation request passes through four sequential stages. The pipeline is designed so that intermediate artifacts are cached, enabling incremental updates on subsequent runs.

```
POST /api/generate (repo URL)
        │
        ▼
   Stage 1: Clone Repository
        │
        ▼
   Stage 2: AI Planner → plan.json
        │
        ▼
   Stage 3: AI Content Generator → cache/pages/*.md
        │
        ▼
   Stage 4: HTML Renderer → site/
        │
        ▼
Database: Update status, commit SHA, timestamps
        │
        ▼
GET /docs/{project}/{path} → Serve static HTML
```

### Stage 1: Clone Repository

The first stage performs a shallow clone of the target repository into a temporary directory.

- Uses `git clone --depth 1` to minimize download size
- Supports both HTTPS and SSH URLs
- Works with public and private repositories
- Authenticates via system git credentials (SSH keys, credential helpers, or mounted cloud configs)

The shallow clone ensures fast startup even for large repositories — only the latest snapshot of the codebase is needed for documentation analysis.

### Stage 2: AI Planner

The AI Planner stage analyzes the entire repository and produces a structured documentation plan.

- The AI CLI process runs with its working directory (`cwd`) set to the cloned repo, giving it full access to explore all files
- A carefully crafted prompt instructs the AI to analyze the repository structure, identify key components, and design a documentation hierarchy
- The output is a `plan.json` file containing pages, sections, and navigation structure

The plan is stored at `/data/projects/{name}/plan.json` and serves as the blueprint for all subsequent stages.

> **Note:** The AI has unrestricted read access to the cloned repository during planning. It explores source files, configs, tests, and any other project artifacts to build a comprehensive documentation plan.

### Stage 3: AI Content Generator

With the plan in hand, the content generator creates individual documentation pages.

- For each page defined in `plan.json`, a separate AI CLI invocation runs with `cwd` set to the cloned repo
- Each invocation can explore the codebase as needed to write accurate, detailed content for its assigned page
- Pages can be generated **concurrently** using async execution with semaphore-limited concurrency to avoid overwhelming the AI provider
- Output is a set of Markdown files, cached at `/data/projects/{name}/cache/pages/*.md`

The concurrency model uses `asyncio.to_thread` to run subprocess calls without blocking the event loop:

```python
# Async execution of AI CLI subprocess
result = await asyncio.to_thread(subprocess.run, cmd, input=prompt, capture_output=True, text=True)
```

> **Tip:** Cached markdown files enable incremental updates — if only a few pages need regeneration on subsequent runs, the unchanged pages are reused from cache.

### Stage 4: HTML Renderer

The final stage converts the markdown pages and `plan.json` into a polished static HTML site.

- Uses **Jinja2 templates** with bundled CSS and JavaScript assets
- Generates a complete static site with no server-side rendering dependencies

The rendered site includes these features:

| Feature | Implementation |
|---------|---------------|
| Sidebar navigation | Generated from `plan.json` hierarchy |
| Dark/light theme toggle | `theme-toggle.js` with CSS custom properties |
| Client-side search | `search.js` powered by lunr.js with `search-index.json` |
| Code syntax highlighting | highlight.js with language auto-detection |
| Card layouts | CSS grid-based component cards |
| Callout boxes | Note, warning, and info styled blocks |
| Responsive design | Mobile-first CSS with breakpoints |

Output is written to `/data/projects/{name}/site/`, ready to be served by the FastAPI static file handler or downloaded as a `.tar.gz` archive.

## AI CLI Integration

docsfy uses a provider abstraction to support multiple AI CLI tools through a consistent interface.

### Provider Configuration

Each AI provider is represented as a frozen dataclass:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

The `uses_own_cwd` flag controls whether the provider manages its own working directory (via a CLI flag) or relies on the subprocess `cwd` parameter.

### Supported Providers

| Provider | Binary | Command Pattern | CWD Handling |
|----------|--------|----------------|-------------|
| Claude | `claude` | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| Gemini | `gemini` | `gemini --model <model> --yolo` | subprocess `cwd` = repo path |
| Cursor | `agent` | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag (`uses_own_cwd=True`) |

### Invocation Pattern

All providers follow the same invocation pattern:

1. **Availability check** — a lightweight "Hi" prompt verifies the CLI tool is installed and authenticated
2. **Prompt delivery** — prompts are passed via stdin to the subprocess
3. **Async execution** — `asyncio.to_thread(subprocess.run, ...)` keeps the event loop responsive
4. **Result extraction** — returns a `tuple[bool, str]` (success flag, output text)

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

### JSON Response Parsing

AI CLI output is free-form text that may contain JSON embedded within conversational responses. docsfy uses a multi-strategy extraction approach to reliably parse structured data:

1. **Direct JSON parse** — attempt `json.loads()` on the raw output
2. **Brace-matching** — scan for the outermost `{...}` JSON object
3. **Markdown code block extraction** — extract content from `` ```json `` fenced blocks
4. **Regex fallback** — last-resort recovery using pattern matching

This layered approach ensures robust parsing regardless of how the AI formats its response.

### Default Configuration

| Setting | Default Value |
|---------|--------------|
| `AI_PROVIDER` | `claude` |
| `AI_MODEL` | `claude-opus-4-6[1m]` |
| `AI_CLI_TIMEOUT` | `60` (minutes) |

## Storage Layout

docsfy uses a dual storage strategy: SQLite for metadata and the filesystem for generated artifacts. Both live under the `/data` directory, which is mounted as a Docker volume for persistence.

### SQLite Database

The database at `/data/docsfy.db` stores project metadata:

- **Project identity** — name, repository URL
- **Generation state** — status (`generating`, `ready`, or `error`)
- **Tracking data** — last generated timestamp, last commit SHA
- **History** — generation logs and run history

The commit SHA is critical for the incremental update mechanism (see below).

### Filesystem Structure

Each project gets its own directory under `/data/projects/`:

```
/data/projects/{project-name}/
  plan.json             # documentation structure from AI Planner (Stage 2)
  cache/
    pages/*.md          # AI-generated markdown, one file per page (Stage 3)
  site/                 # final rendered static HTML (Stage 4)
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

| Directory | Purpose | Written By |
|-----------|---------|-----------|
| `plan.json` | Navigation hierarchy and page definitions | Stage 2 (AI Planner) |
| `cache/pages/` | Markdown content for each page | Stage 3 (AI Content Generator) |
| `site/` | Final static HTML site with all assets | Stage 4 (HTML Renderer) |
| `site/assets/` | Bundled CSS, JavaScript, and search index | Stage 4 (HTML Renderer) |

> **Note:** The `cache/pages/` directory is the key to incremental updates. By preserving generated markdown between runs, docsfy avoids re-generating unchanged pages.

## Incremental Updates

docsfy tracks repository state to minimize redundant AI calls on subsequent generation requests for the same project:

1. **Store commit SHA** — after each generation, the current `HEAD` commit SHA is saved in SQLite
2. **Compare on re-generate** — when `POST /api/generate` is called for an existing project, the repo is fetched and its current SHA is compared against the stored value
3. **Re-plan if changed** — if the SHA differs, the AI Planner re-runs to check whether the documentation structure has changed
4. **Selective regeneration** — only pages whose content may be affected by the code changes are regenerated
5. **Plan-level optimization** — if the plan structure is unchanged and only specific source files changed, only the relevant pages are regenerated

This approach significantly reduces generation time and AI API costs for active projects that are updated frequently.

## Container and Deployment

### Docker Image

The Docker image uses a multi-stage build based on `python:3.12-slim`:

| Aspect | Detail |
|--------|--------|
| Base image | `python:3.12-slim` (multi-stage build) |
| Package manager | `uv` (no pip) |
| Non-root user | `appuser` (OpenShift compatible, GID 0) |
| System dependencies | bash, git, curl, nodejs, npm, ca-certificates |
| Health check | HTTP probe on `/health` |

AI CLI tools are installed at build time (unpinned, always latest):

```dockerfile
# Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Cursor Agent
RUN curl -fsSL https://cursor.com/install | bash

# Gemini CLI
RUN npm install -g @google/gemini-cli
```

> **Warning:** AI CLI tools are installed without version pinning. This ensures access to the latest features but means builds are not fully reproducible. Pin versions in production if build reproducibility is critical.

### Docker Compose

The provided `docker-compose.yaml` mounts the data volume and credential directories:

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

Key volume mounts:

- `./data:/data` — persists the SQLite database and all generated project artifacts
- `~/.config/gcloud:ro` — read-only mount of Google Cloud credentials (for Vertex AI authentication with Claude)
- `./cursor` — Cursor agent configuration and credentials

### Environment Variables

Configuration is managed through environment variables, typically loaded from a `.env` file:

```bash
# AI Configuration
AI_PROVIDER=claude           # Which AI provider to use (claude, gemini, cursor)
AI_MODEL=claude-opus-4-6[1m] # Model identifier for the chosen provider
AI_CLI_TIMEOUT=60            # Timeout per AI invocation in minutes

# Claude - Option 1: Direct API Key
# ANTHROPIC_API_KEY=

# Claude - Option 2: Google Vertex AI
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

> **Tip:** Only configure the credentials for your chosen `AI_PROVIDER`. You do not need API keys for providers you are not using.

## Component Interaction Summary

The following table summarizes how the major components communicate:

| From | To | Mechanism | Data |
|------|----|-----------|------|
| Client | FastAPI | HTTP REST | Repo URL, project name |
| FastAPI | Git | `subprocess` (shell) | Clone/fetch commands |
| FastAPI | AI CLI | `subprocess` via `asyncio.to_thread` | Prompts via stdin, responses via stdout |
| AI CLI | Cloned Repo | Filesystem read | Source code, configs, tests |
| FastAPI | SQLite | aiosqlite / DB driver | Project metadata, status, SHA |
| FastAPI | Filesystem | File I/O | `plan.json`, markdown cache, HTML site |
| HTML Renderer | Jinja2 | Python API | Templates + data → HTML |
| Client | FastAPI | HTTP GET | Static HTML, CSS, JS, search index |

## Development Tooling

| Tool | Purpose |
|------|---------|
| Pre-commit hooks | ruff (lint + format), mypy (strict), flake8, gitleaks, detect-secrets |
| Tox | Unused-code checks, unit tests (via uv) |
| Build system | hatchling |
| Python version | 3.12+ |
| Package manager | uv only (no pip) |
