# docsfy - Design Document

**Date:** 2026-03-04
**Status:** Approved

## Overview

docsfy is an open-source FastAPI service that generates polished, production-quality static HTML documentation sites from GitHub repositories using AI CLI tools. It supports multiple AI providers (Claude Code, Cursor Agent, Gemini CLI), incremental updates on repository changes, and flexible hosting -- serve docs directly from the API or download the static HTML to host anywhere.

## Architecture

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

## Generation Pipeline

The pipeline runs four sequential stages per generation request.

### Stage 1: Clone Repository

- Shallow clone (`--depth 1`) to a temporary directory
- Supports both SSH and HTTPS URLs (public and private repos)
- Uses system git credentials for private repo access

### Stage 2: AI Planner

- AI CLI runs with `cwd` set to the cloned repo directory (or `--workspace` for Cursor)
- AI has full access to explore the entire repository
- Prompt instructs the AI to analyze the repo and output a documentation plan
- Output: `plan.json` containing pages, sections, and navigation hierarchy

### Stage 3: AI Content Generator

- For each page defined in `plan.json`, run the AI CLI with `cwd` set to the cloned repo
- AI explores the codebase as needed for each page
- Pages can be generated concurrently (async with semaphore-limited concurrency)
- Output: Markdown files per page, cached at `/data/projects/{name}/cache/pages/*.md`

### Stage 4: HTML Renderer

- Converts markdown pages and `plan.json` into polished static HTML
- Uses Jinja2 templates with bundled CSS/JS assets
- Features: sidebar navigation, dark/light theme, client-side search, code syntax highlighting, card layouts, callout boxes (note/warning/info), responsive design
- Output: Static site at `/data/projects/{name}/site/`

## AI CLI Integration

Uses the same provider pattern as jenkins-job-insight.

### Provider Configuration

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

### Provider Commands

| Provider | Binary | Command | CWD Handling |
|----------|--------|---------|-------------|
| Claude | `claude` | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| Gemini | `gemini` | `gemini --model <model> --yolo` | subprocess `cwd` = repo path |
| Cursor | `agent` | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag, `uses_own_cwd=True` |

### Invocation

- Prompts passed via `subprocess.run(cmd, input=prompt, capture_output=True, text=True)`
- Async execution via `asyncio.to_thread(subprocess.run, ...)`
- Returns `tuple[bool, str]` (success, output)
- Availability check before generation (lightweight "Hi" prompt)

### JSON Response Parsing

Multi-strategy extraction (same as jenkins-job-insight):

1. Direct JSON parse
2. Brace-matching for outermost JSON object
3. Markdown code block extraction
4. Fallback with regex recovery

### Defaults

| Setting | Default Value |
|---------|--------------|
| `AI_PROVIDER` | `claude` |
| `AI_MODEL` | `claude-opus-4-6[1m]` |
| `AI_CLI_TIMEOUT` | `60` (minutes) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start doc generation for a repo URL |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details (last generated, commit SHA, pages) |
| `DELETE` | `/api/projects/{name}` | Remove a project and its generated docs |
| `GET` | `/api/projects/{name}/download` | Download site as `.tar.gz` archive for self-hosting |
| `GET` | `/docs/{project}/{path}` | Serve generated static HTML docs |
| `GET` | `/health` | Health check |

## Storage

### SQLite Database (`/data/docsfy.db`)

Stores project metadata:

- Project name, repo URL, status (`generating` / `ready` / `error`)
- Last generated timestamp, last commit SHA
- Generation history and logs

### Filesystem (`/data/projects/`)

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

## Incremental Updates

1. Track last commit SHA per project in SQLite
2. On re-generate: fetch repo, compare current SHA against stored SHA
3. If changed: re-run AI Planner to check if doc structure changed
4. Regenerate only pages whose content may be affected
5. If plan structure is unchanged and only specific files changed, regenerate relevant pages only

## Container and Deployment

### Dockerfile

| Aspect | Detail |
|--------|--------|
| Base image | `python:3.12-slim` (multi-stage build) |
| Package manager | `uv` |
| Non-root user | `appuser` (OpenShift compatible, GID 0) |
| System deps | bash, git, curl, nodejs, npm, ca-certificates |
| Entrypoint | `uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000` |
| Health check | `/health` |

AI CLI installation (unpinned, always latest):

- **Claude:** `curl -fsSL https://claude.ai/install.sh | bash`
- **Cursor:** `curl -fsSL https://cursor.com/install | bash`
- **Gemini:** `npm install -g @google/gemini-cli`

### docker-compose.yaml

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

### Environment Variables (`.env.example`)

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

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

## Development Tooling

Copied from pr-test-oracle:

| Tool | Purpose |
|------|---------|
| Pre-commit | ruff (lint + format), mypy (strict), flake8, gitleaks, detect-secrets, standard hooks |
| Tox | unused-code check, unit tests (via uv) |
| Build system | hatchling |
| Python | 3.12+ |
| Package manager | uv only (no pip) |

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI + uvicorn |
| Templating | Jinja2 |
| Markdown | Python markdown library |
| Database | SQLite (via aiosqlite or similar) |
| HTML theme | Custom CSS/JS (bundled) |
| Search | Client-side (lunr.js or similar) |
| Code highlighting | highlight.js |
| Build system | hatchling |
| Package manager | uv |
| Container | Docker (multi-stage, `python:3.12-slim`) |
