# Project Structure

This page provides a comprehensive overview of the docsfy codebase layout, covering source modules, templates, static assets, tests, and configuration files. Understanding this structure will help you navigate the project and contribute effectively.

## Top-Level Directory

```
docsfy/
├── src/
│   └── docsfy/              # Main application package
├── tests/                    # Test suite
├── templates/                # Jinja2 HTML templates
├── docs/                     # Project documentation
│   └── plans/                # Design documents and RFCs
├── data/                     # Runtime data (gitignored)
├── Dockerfile                # Multi-stage container build
├── docker-compose.yaml       # Local development services
├── pyproject.toml            # Build config (hatchling) and dependencies
├── tox.ini                   # Test orchestration
├── .pre-commit-config.yaml   # Linting and formatting hooks
├── .env.example              # Environment variable template
└── uv.lock                   # Dependency lockfile (uv)
```

## Source Modules

All application source code lives under `src/docsfy/`. The project uses the `src` layout convention with [hatchling](https://hatch.pypa.io/) as the build backend.

### `docsfy.main` — Application Entrypoint

The FastAPI application is defined and mounted here. This is the entrypoint referenced by the container's uvicorn command:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

This module registers all API routes and configures static file serving for generated documentation sites.

### `docsfy.api` — API Endpoints

Defines the REST API that drives documentation generation and project management:

| Method   | Path                             | Description                                  |
|----------|----------------------------------|----------------------------------------------|
| `POST`   | `/api/generate`                  | Start doc generation for a repo URL          |
| `GET`    | `/api/status`                    | List all projects and their generation status|
| `GET`    | `/api/projects/{name}`           | Get project details (commit SHA, pages, etc.)|
| `DELETE` | `/api/projects/{name}`           | Remove a project and its generated docs      |
| `GET`    | `/api/projects/{name}/download`  | Download site as `.tar.gz` for self-hosting  |
| `GET`    | `/docs/{project}/{path}`         | Serve generated static HTML docs             |
| `GET`    | `/health`                        | Health check                                 |

### `docsfy.pipeline` — Generation Pipeline

Orchestrates the four-stage documentation generation process:

1. **Clone** — Shallow-clone (`--depth 1`) the target repository to a temporary directory
2. **Plan** — Invoke the AI CLI to analyze the repo and produce a `plan.json`
3. **Generate** — For each page in the plan, invoke the AI CLI to produce markdown content (concurrently, with semaphore-limited parallelism)
4. **Render** — Convert markdown + plan into a polished static HTML site

Pages are generated concurrently using `asyncio.to_thread` to avoid blocking the event loop:

```python
# Async execution via asyncio.to_thread
result = await asyncio.to_thread(subprocess.run, cmd, input=prompt, capture_output=True, text=True)
```

### `docsfy.providers` — AI CLI Integration

Implements the provider abstraction for invoking different AI CLI tools. Each provider is defined by a frozen dataclass:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

Three providers are supported:

| Provider | Binary   | CWD Handling                                       |
|----------|----------|----------------------------------------------------|
| Claude   | `claude` | subprocess `cwd` set to repo path                 |
| Gemini   | `gemini` | subprocess `cwd` set to repo path                 |
| Cursor   | `agent`  | `--workspace` flag (`uses_own_cwd=True`)           |

The provider invocation passes prompts via stdin and returns a `tuple[bool, str]` indicating success and the raw output.

### `docsfy.parser` — JSON Response Parsing

Extracts structured JSON from AI CLI output using a multi-strategy approach:

1. Direct JSON parse of the full output
2. Brace-matching to locate the outermost JSON object
3. Markdown code block extraction (` ```json ... ``` `)
4. Fallback with regex recovery

> **Note:** This multi-strategy approach is necessary because AI CLI tools may wrap their JSON output in conversational text, markdown formatting, or other decoration.

### `docsfy.renderer` — HTML Rendering

Converts markdown pages and the `plan.json` navigation structure into a static HTML site using Jinja2 templates. The renderer produces:

- Sidebar navigation derived from the plan hierarchy
- Dark/light theme toggle
- Client-side full-text search via a generated `search-index.json`
- Syntax-highlighted code blocks (highlight.js)
- Callout boxes for notes, warnings, and info blocks
- Responsive layout with card components

### `docsfy.db` — Database Layer

Manages the SQLite database at `/data/docsfy.db` for project metadata. Tracks:

- Project name and repository URL
- Generation status (`generating`, `ready`, `error`)
- Last generated timestamp and commit SHA
- Generation history and logs

> **Tip:** The database is used for metadata only. All generated content — markdown cache and rendered HTML — lives on the filesystem under `/data/projects/`.

## Templates

Jinja2 HTML templates power the rendered documentation sites. These live in the `templates/` directory and define the overall page structure, navigation sidebar, and content layout.

Key template features:
- **Base layout** — common HTML skeleton with head, navigation, and footer
- **Page template** — renders a single documentation page with sidebar and content area
- **Search integration** — includes the search UI components
- **Theme support** — dark/light mode toggle wired into CSS custom properties

## Static Assets

Bundled CSS and JavaScript assets are copied into each generated site under `site/assets/`:

```
site/assets/
├── style.css           # Documentation theme styles
├── search.js           # Client-side full-text search
├── theme-toggle.js     # Dark/light mode switcher
└── highlight.js        # Code syntax highlighting
```

These assets are self-contained — generated sites have no external CDN dependencies and can be served from any static file host.

## Tests

The test suite lives in the `tests/` directory and is executed through **tox** using **uv** as the package manager:

```ini
# tox.ini (excerpt)
[testenv]
# runs unit tests via uv
```

The development toolchain enforces code quality through pre-commit hooks:

| Tool            | Purpose                                    |
|-----------------|--------------------------------------------|
| ruff            | Linting and auto-formatting                |
| mypy (strict)   | Static type checking                       |
| flake8          | Additional lint rules                      |
| gitleaks        | Secret detection in commits                |
| detect-secrets  | Secret detection in staged files           |

> **Warning:** All pre-commit hooks must pass before code can be committed. Run `pre-commit run --all-files` to check your changes locally before pushing.

## Configuration Files

### `pyproject.toml`

The central project configuration file. Uses **hatchling** as the build system and defines all project metadata and dependencies:

- Build backend: `hatchling`
- Python requirement: `3.12+`
- Key dependencies: FastAPI, uvicorn, Jinja2, markdown, aiosqlite

### `.env.example`

Template for required environment variables. Copy to `.env` and fill in your values:

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

> **Note:** The default AI provider is `claude` with model `claude-opus-4-6[1m]`. The CLI timeout defaults to 60 minutes per invocation, reflecting the time needed for large repository analysis.

### `docker-compose.yaml`

Defines the local development setup with volume mounts for persistent data and cloud credentials:

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

### `Dockerfile`

Multi-stage build based on `python:3.12-slim`. Key characteristics:

| Aspect           | Detail                                                    |
|------------------|-----------------------------------------------------------|
| Base image       | `python:3.12-slim` (multi-stage)                          |
| Package manager  | `uv` (no pip)                                             |
| Non-root user    | `appuser` (OpenShift compatible, GID 0)                   |
| System deps      | bash, git, curl, nodejs, npm, ca-certificates             |
| Health check     | `GET /health`                                             |

AI CLI tools are installed at build time (unpinned, always latest):

- **Claude:** `curl -fsSL https://claude.ai/install.sh | bash`
- **Cursor:** `curl -fsSL https://cursor.com/install | bash`
- **Gemini:** `npm install -g @google/gemini-cli`

## Runtime Data Directory

The `/data/` directory is created at runtime and is **not** checked into version control. It holds all persistent state:

```
/data/
├── docsfy.db                          # SQLite metadata database
└── projects/
    └── {project-name}/
        ├── plan.json                  # Documentation structure from AI
        ├── cache/
        │   └── pages/
        │       └── *.md               # AI-generated markdown (cached)
        └── site/                      # Final rendered HTML
            ├── index.html
            ├── *.html
            ├── assets/
            │   ├── style.css
            │   ├── search.js
            │   ├── theme-toggle.js
            │   └── highlight.js
            └── search-index.json
```

> **Tip:** The `cache/pages/*.md` files enable incremental updates. When a repository changes, docsfy compares the current commit SHA against the stored SHA and only regenerates pages whose content may be affected, reusing cached markdown for unchanged sections.

## Design Documents

Architectural decisions and design specifications are stored in `docs/plans/`:

```
docs/plans/
└── 2026-03-04-docsfy-design.md    # Original design document
```

These documents capture the rationale behind major architectural choices and serve as the canonical reference for how the system is intended to work.
