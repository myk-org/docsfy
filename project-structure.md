# Project Structure

This page describes the directory layout, module organization, key source files, and how the major components of docsfy fit together.

## Directory Layout

docsfy follows a standard Python project layout using `hatchling` as the build system and `uv` as the package manager.

```
docsfy/
├── docs/
│   └── plans/
│       └── 2026-03-04-docsfy-design.md   # Architecture design document
├── docsfy/                                # Main application package
│   ├── __init__.py
│   ├── main.py                            # FastAPI app entry point
│   ├── ai/                                # AI provider integrations
│   │   ├── __init__.py
│   │   ├── provider.py                    # ProviderConfig and registry
│   │   ├── runner.py                      # Subprocess execution logic
│   │   └── parser.py                      # JSON response extraction
│   ├── pipeline/                          # Generation pipeline stages
│   │   ├── __init__.py
│   │   ├── clone.py                       # Stage 1: Repository cloning
│   │   ├── planner.py                     # Stage 2: AI-driven doc planning
│   │   ├── generator.py                   # Stage 3: AI content generation
│   │   └── renderer.py                    # Stage 4: HTML rendering
│   ├── routers/                           # FastAPI route definitions
│   │   ├── __init__.py
│   │   ├── generate.py                    # POST /api/generate
│   │   ├── projects.py                    # Project CRUD + download
│   │   ├── docs.py                        # Static doc serving
│   │   └── health.py                      # GET /health
│   ├── db.py                              # SQLite database layer
│   ├── models.py                          # Pydantic models / schemas
│   └── templates/                         # Jinja2 HTML templates
│       ├── base.html
│       ├── page.html
│       └── assets/
│           ├── style.css
│           ├── search.js
│           ├── theme-toggle.js
│           └── highlight.js
├── tests/                                 # Test suite
├── pyproject.toml                         # Build config and dependencies
├── Dockerfile                             # Multi-stage container build
├── docker-compose.yaml                    # Local development stack
├── .env.example                           # Environment variable template
└── .pre-commit-config.yaml                # Linting and formatting hooks
```

## Runtime Data Directory

At runtime, docsfy stores all generated content and metadata under `/data`:

```
/data/
├── docsfy.db                              # SQLite database (project metadata)
└── projects/
    └── {project-name}/
        ├── plan.json                      # Documentation structure from AI
        ├── cache/
        │   └── pages/*.md                 # AI-generated markdown (cached)
        └── site/                          # Final rendered HTML
            ├── index.html
            ├── *.html
            ├── assets/
            │   ├── style.css
            │   ├── search.js
            │   ├── theme-toggle.js
            │   └── highlight.js
            └── search-index.json
```

> **Note:** The `/data` directory is mounted as a Docker volume so generated documentation persists across container restarts.

## Module Organization

The application is organized into four top-level module groups, each with a distinct responsibility.

### `docsfy/main.py` — Application Entry Point

The FastAPI application is defined here and serves as the central wiring point. It registers routers, configures middleware, and sets up the database connection on startup. The application is launched via uvicorn:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

### `docsfy/routers/` — API Endpoints

Route handlers are split by domain into separate router modules, then included by the main app.

| Module | Prefix | Endpoints |
|--------|--------|-----------|
| `generate.py` | `/api` | `POST /api/generate` — Start doc generation for a repo URL |
| `projects.py` | `/api/projects` | `GET /api/status`, `GET /api/projects/{name}`, `DELETE /api/projects/{name}`, `GET /api/projects/{name}/download` |
| `docs.py` | `/docs` | `GET /docs/{project}/{path}` — Serve rendered static HTML |
| `health.py` | `/` | `GET /health` — Health check |

### `docsfy/ai/` — AI Provider Integrations

This module abstracts the differences between AI CLI tools behind a unified interface. See [AI Provider Integration](#ai-provider-integration) below for details.

### `docsfy/pipeline/` — Generation Pipeline

The four-stage pipeline that transforms a repository URL into a static documentation site. See [Generation Pipeline](#generation-pipeline) below for details.

## AI Provider Integration

docsfy supports three AI CLI providers through a pluggable provider pattern. Each provider is described by a `ProviderConfig` dataclass:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

### Supported Providers

| Provider | Binary | Command Pattern | CWD Handling |
|----------|--------|-----------------|-------------|
| Claude | `claude` | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| Gemini | `gemini` | `gemini --model <model> --yolo` | subprocess `cwd` = repo path |
| Cursor | `agent` | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag (`uses_own_cwd=True`) |

The `uses_own_cwd` flag distinguishes providers that accept a workspace path as a CLI argument (Cursor) from those that rely on the subprocess working directory (Claude, Gemini).

### Runner (`docsfy/ai/runner.py`)

The runner executes AI CLI commands as subprocesses:

- Prompts are passed via `stdin` using `subprocess.run(cmd, input=prompt, capture_output=True, text=True)`
- Async execution is achieved with `asyncio.to_thread(subprocess.run, ...)`
- Each invocation returns a `tuple[bool, str]` — a success flag and the raw output
- Before generation begins, a lightweight availability check sends a "Hi" prompt to verify the CLI is functional

### JSON Parser (`docsfy/ai/parser.py`)

AI responses are parsed using a multi-strategy extraction approach:

1. **Direct parse** — Attempt `json.loads()` on the full output
2. **Brace matching** — Locate the outermost `{...}` JSON object
3. **Code block extraction** — Find JSON inside markdown `` ```json `` fences
4. **Regex fallback** — Pattern-based recovery for malformed output

> **Tip:** This layered parsing strategy ensures robust JSON extraction regardless of how the AI CLI formats its response (with preamble text, markdown wrappers, or trailing content).

### Default Configuration

| Setting | Default Value | Environment Variable |
|---------|--------------|---------------------|
| Provider | `claude` | `AI_PROVIDER` |
| Model | `claude-opus-4-6[1m]` | `AI_MODEL` |
| Timeout | 60 minutes | `AI_CLI_TIMEOUT` |

## Generation Pipeline

The pipeline runs four sequential stages for each documentation generation request.

```
POST /api/generate (repo URL)
        │
        ▼
┌─────────────────┐
│  Stage 1: Clone │  Shallow clone (--depth 1) to temp directory
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Stage 2: Plan  │  AI analyzes repo → plan.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Stage 3: Gen   │  AI generates markdown per page (concurrent)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Stage 4: HTML  │  Jinja2 + markdown → static site
└────────┬────────┘
         │
         ▼
   Site ready at /docs/{project}/
```

### Stage 1: Clone Repository (`clone.py`)

- Performs a shallow clone (`git clone --depth 1`) into a temporary directory
- Supports both SSH and HTTPS URLs for public and private repositories
- Uses system git credentials for private repository access

### Stage 2: AI Planner (`planner.py`)

- Runs the AI CLI with its working directory set to the cloned repository
- The AI explores the full repository structure to understand the codebase
- Produces a `plan.json` file that defines pages, sections, and navigation hierarchy
- This plan drives all subsequent content generation

### Stage 3: AI Content Generator (`generator.py`)

- Iterates over each page defined in `plan.json`
- For each page, invokes the AI CLI with access to the cloned repository
- Pages can be generated **concurrently** using `asyncio` with semaphore-limited concurrency
- Generated markdown is cached at `/data/projects/{name}/cache/pages/*.md`

> **Note:** The cache enables incremental updates — only pages affected by repository changes need to be regenerated.

### Stage 4: HTML Renderer (`renderer.py`)

Converts the markdown pages and `plan.json` into a polished static HTML site using Jinja2 templates. The rendered site includes:

- **Sidebar navigation** — Generated from the `plan.json` hierarchy
- **Dark/light theme** — Client-side toggle with `theme-toggle.js`
- **Client-side search** — Full-text search via `search-index.json` and `search.js`
- **Code syntax highlighting** — Powered by highlight.js
- **Responsive design** — Mobile-friendly layout
- **Callout boxes** — Styled note, warning, and info blocks
- **Card layouts** — Visual grouping for related content

Output is written to `/data/projects/{name}/site/`.

## Database Layer (`docsfy/db.py`)

docsfy uses SQLite (via aiosqlite) stored at `/data/docsfy.db` for project metadata:

| Field | Description |
|-------|-------------|
| Project name | Unique identifier derived from the repo |
| Repo URL | Source repository URL |
| Status | `generating`, `ready`, or `error` |
| Last generated | Timestamp of last successful generation |
| Last commit SHA | Used for incremental update detection |
| Generation logs | History and diagnostic output |

### Incremental Updates

The database tracks the last commit SHA for each project. When a regeneration is requested:

1. Fetch the repository and compare the current SHA against the stored SHA
2. If changed, re-run the AI Planner to check for structural changes
3. Regenerate only the pages whose content may be affected
4. If the plan structure is unchanged and only specific files changed, regenerate only the relevant pages

## Rendering Engine (`docsfy/templates/`)

The rendering engine uses Jinja2 templates with a bundled asset pipeline.

### Template Hierarchy

- **`base.html`** — Root layout with HTML head, theme initialization, sidebar skeleton, and asset loading
- **`page.html`** — Extends `base.html`; renders a single documentation page with its converted markdown content

### Bundled Assets

| Asset | Purpose |
|-------|---------|
| `style.css` | Complete site styling including responsive layout, dark/light themes, sidebar, callout boxes, and card components |
| `search.js` | Client-side full-text search against `search-index.json` |
| `theme-toggle.js` | Dark/light mode toggle with `localStorage` persistence |
| `highlight.js` | Syntax highlighting for code blocks |

> **Tip:** Because all assets are bundled, the generated documentation site is fully self-contained and can be hosted on any static file server with no external dependencies.

## Configuration and Environment

### Environment Variables

All configuration is managed through environment variables. A template is provided in `.env.example`:

```bash
# AI Configuration
AI_PROVIDER=claude           # claude | gemini | cursor
AI_MODEL=claude-opus-4-6[1m] # Model identifier for the chosen provider
AI_CLI_TIMEOUT=60            # Timeout in minutes per AI invocation

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

> **Warning:** Never commit `.env` files with real API keys. Use `.env.example` as a reference and create your own `.env` locally.

### Docker Compose

The `docker-compose.yaml` mounts credential directories and the data volume:

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

### Container Build

The Dockerfile uses a multi-stage build based on `python:3.12-slim`:

| Aspect | Detail |
|--------|--------|
| Base image | `python:3.12-slim` (multi-stage) |
| Package manager | `uv` (no pip) |
| Non-root user | `appuser` (OpenShift compatible, GID 0) |
| System dependencies | bash, git, curl, nodejs, npm, ca-certificates |
| AI CLIs | Installed at build time (always latest) |

## Development Tooling

| Tool | Purpose |
|------|---------|
| **uv** | Package management and virtual environment |
| **hatchling** | Python build system |
| **Pre-commit** | ruff (lint + format), mypy (strict), flake8, gitleaks, detect-secrets |
| **Tox** | Unused-code checks, unit test execution |
| **Python** | 3.12+ required |

## Technology Stack Summary

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI + uvicorn |
| Templating | Jinja2 |
| Markdown processing | Python `markdown` library |
| Database | SQLite (via aiosqlite) |
| HTML theme | Custom CSS/JS (bundled) |
| Client-side search | lunr.js or similar |
| Code highlighting | highlight.js |
| Build system | hatchling |
| Package manager | uv |
| Container | Docker (multi-stage, `python:3.12-slim`) |

## How Components Fit Together

The following diagram shows the runtime request flow connecting all major components:

```
User Request                      docsfy Application
─────────────                     ──────────────────

POST /api/generate ──────────►  routers/generate.py
  { "repo_url": "..." }              │
                                      ├──► pipeline/clone.py ──► git clone
                                      │
                                      ├──► ai/provider.py ──► Select provider
                                      │         │
                                      ├──► pipeline/planner.py
                                      │         │
                                      │         └──► ai/runner.py ──► AI CLI subprocess
                                      │                   │
                                      │              ai/parser.py ──► Extract plan.json
                                      │
                                      ├──► pipeline/generator.py
                                      │         │
                                      │         └──► ai/runner.py ──► AI CLI (per page, concurrent)
                                      │                   │
                                      │              ai/parser.py ──► Extract markdown
                                      │
                                      └──► pipeline/renderer.py
                                                │
                                                ├──► templates/ (Jinja2)
                                                ├──► markdown ──► HTML
                                                └──► Write to /data/projects/{name}/site/

GET /docs/{project}/ ───────►  routers/docs.py
                                      │
                                      └──► Serve static files from /data/projects/{name}/site/

GET /api/status ────────────►  routers/projects.py
                                      │
                                      └──► db.py ──► Query SQLite /data/docsfy.db
```

The `ai/` module provides a clean abstraction layer: the pipeline stages interact only with the runner and parser interfaces, never with provider-specific CLI details. Swapping providers requires only changing the `AI_PROVIDER` environment variable — no code changes are needed.
