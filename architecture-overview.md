# Architecture Overview

docsfy follows a layered architecture that separates concerns across five major subsystems: a FastAPI web layer for HTTP handling, a two-phase AI generation pipeline, a markdown-to-HTML rendering engine, SQLite-backed project storage, and a filesystem-based page cache. This page describes how these components fit together and how data flows through the system.

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        HTTP Clients                             │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│                   FastAPI Web Layer                              │
│  POST /api/generate  GET /api/status  GET /docs/{project}/{path}│
│  GET /api/projects   DELETE /api/projects  GET /health          │
└──────┬──────────────────────┬──────────────────────┬────────────┘
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐    ┌─────────────────┐    ┌─────────────────────┐
│  AI Pipeline │    │  SQLite Storage │    │  Static File Server  │
│  (2 phases)  │    │   (aiosqlite)   │    │  (rendered HTML)     │
│              │    │                 │    │                      │
│ ┌──────────┐ │    │  projects table │    │  /data/projects/     │
│ │ Planner  │ │    │  ┌───────────┐  │    │    {name}/site/      │
│ └────┬─────┘ │    │  │name (PK)  │  │    │      index.html      │
│      │       │    │  │repo_url   │  │    │      {slug}.html     │
│      ▼       │    │  │status     │  │    │      {slug}.md       │
│ ┌──────────┐ │    │  │commit_sha │  │    │      assets/         │
│ │ Content  │ │    │  │plan_json  │  │    │      search-index.json│
│ │Generator │ │    │  │page_count │  │    └─────────────────────┘
│ └──────────┘ │    │  └───────────┘  │
└──────┬───────┘    └────────┬────────┘
       │                     │
       ▼                     │
┌──────────────┐             │
│   Renderer   │◄────────────┘
│  (Markdown → │
│   HTML via   │
│   Jinja2)    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Filesystem  │
│    Cache     │
│ /cache/pages │
│   {slug}.md  │
└──────────────┘
```

## Module Map

Each Python module in `src/docsfy/` owns a single responsibility:

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI application, routes, background task orchestration |
| `config.py` | Pydantic settings loaded from environment / `.env` |
| `models.py` | Request/response Pydantic models with validation |
| `generator.py` | Two-phase AI generation pipeline (planning + content) |
| `ai_client.py` | Thin re-export wrapper around `ai-cli-runner` |
| `prompts.py` | Prompt templates for the planner and page writer |
| `json_parser.py` | Robust JSON extraction from AI responses |
| `repository.py` | Git clone and local repo operations |
| `storage.py` | SQLite database operations and filesystem path helpers |
| `renderer.py` | Markdown-to-HTML conversion and Jinja2 site rendering |

## FastAPI Web Layer

The web layer lives in `main.py` and provides six HTTP endpoints. The application uses FastAPI's async lifespan context manager to initialize the database on startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


app = FastAPI(
    title="docsfy",
    description="AI-powered documentation generator",
    version="0.1.0",
    lifespan=lifespan,
)
```

### API Endpoints

| Method | Route | Status | Purpose |
|---|---|---|---|
| `GET` | `/health` | 200 | Health check for container orchestrators |
| `GET` | `/api/status` | 200 | List all projects with their generation status |
| `POST` | `/api/generate` | 202 | Start documentation generation (async) |
| `GET` | `/api/projects/{name}` | 200 | Get project details including plan JSON |
| `DELETE` | `/api/projects/{name}` | 200 | Delete a project and its generated files |
| `GET` | `/api/projects/{name}/download` | 200 | Download generated docs as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path:path}` | 200 | Serve generated HTML documentation pages |

### Asynchronous Generation

The `POST /api/generate` endpoint returns `202 Accepted` immediately and spawns a background task with `asyncio.create_task`. A module-level `set` prevents concurrent generation of the same project:

```python
_generating: set[str] = set()

@app.post("/api/generate", status_code=202)
async def generate(request: GenerateRequest) -> dict[str, str]:
    settings = get_settings()
    ai_provider = request.ai_provider or settings.ai_provider
    ai_model = request.ai_model or settings.ai_model
    project_name = request.project_name

    if project_name in _generating:
        raise HTTPException(
            status_code=409,
            detail=f"Project '{project_name}' is already being generated",
        )

    _generating.add(project_name)
    await save_project(name=project_name, repo_url=request.repo_url or request.repo_path or "", status="generating")

    try:
        asyncio.create_task(
            _run_generation(
                repo_url=request.repo_url,
                repo_path=request.repo_path,
                project_name=project_name,
                ai_provider=ai_provider,
                ai_model=ai_model,
                ai_cli_timeout=request.ai_cli_timeout or settings.ai_cli_timeout,
                force=request.force,
            )
        )
    except Exception:
        _generating.discard(project_name)
        raise

    return {"project": project_name, "status": "generating"}
```

The background task is cancellation-safe — a `finally` block guarantees the project name is removed from the `_generating` set regardless of how the task ends.

### Path Traversal Protection

All user-supplied project names and file paths are validated before they reach the filesystem. The document serving endpoint uses `resolve().relative_to()` to ensure the requested path stays inside the site directory:

```python
@app.get("/docs/{project}/{path:path}")
async def serve_docs(project: str, path: str = "index.html") -> FileResponse:
    project = _validate_project_name(project)
    site_dir = get_project_site_dir(project)
    file_path = site_dir / path
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
```

## Two-Phase AI Generation Pipeline

Documentation generation is split into two distinct phases: **planning** (structure) and **content** (writing). This separation enables caching, parallel content generation, and incremental progress tracking.

### Phase 1: Planning

The planner calls the AI CLI with the repository as its working directory. The AI analyzes the full codebase — source files, tests, configurations — and produces a structured documentation plan as JSON:

```python
async def run_planner(
    repo_path: Path,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
) -> dict[str, Any]:
    prompt = build_planner_prompt(project_name)
    success, output = await call_ai_cli(
        prompt=prompt,
        cwd=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )
    if not success:
        msg = f"Planner failed: {output}"
        raise RuntimeError(msg)

    plan = parse_json_response(output)
    if plan is None:
        msg = "Failed to parse planner output as JSON"
        raise RuntimeError(msg)
    return plan
```

The planner prompt (from `prompts.py`) instructs the AI to produce a JSON object following this schema:

```json
{
  "project_name": "string - project name",
  "tagline": "string - one-line project description",
  "navigation": [
    {
      "group": "string - section group name",
      "pages": [
        {
          "slug": "string - URL-friendly page identifier",
          "title": "string - human-readable page title",
          "description": "string - brief description of what this page covers"
        }
      ]
    }
  ]
}
```

The plan is stored in the database as JSON, allowing API consumers to see the documentation structure while pages are still being generated.

### Phase 2: Content Generation

With the plan in hand, `generate_all_pages` dispatches individual page generation tasks. Each task sends a page-specific prompt to the AI CLI with the repository as context:

```python
MAX_CONCURRENT_PAGES = 5

results = await run_parallel_with_limit(
    coroutines, max_concurrency=MAX_CONCURRENT_PAGES
)
```

Concurrency is capped at 5 simultaneous page generations to avoid overloading AI provider rate limits. Each page task follows this flow:

1. **Check cache** — if `use_cache=True` and a cached markdown file exists, return it immediately
2. **Call AI** — generate markdown content using `build_page_prompt()`
3. **Strip preamble** — remove any AI thinking/planning text before the first `#` heading (within the first 10 lines)
4. **Write cache** — save the generated markdown to the filesystem cache
5. **Update progress** — increment `page_count` in the database so clients can track progress

If any individual page fails, the pipeline does not abort. Instead, it inserts a placeholder:

```python
if not success:
    output = f"# {title}\n\n*Documentation generation failed. Please re-run.*"
```

### Robust JSON Parsing

AI models don't always produce clean JSON. The `json_parser.py` module implements a three-strategy fallback to extract JSON from AI responses:

```python
def parse_json_response(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    # Strategy 1: Direct parse (text starts with "{")
    if text.startswith("{"):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
    # Strategy 2: Find balanced braces
    result = _extract_json_by_braces(text)
    if result is not None:
        return result
    # Strategy 3: Extract from markdown code blocks
    result = _extract_json_from_code_blocks(text)
    if result is not None:
        return result
    return None
```

The brace-matching strategy (`_extract_json_by_braces`) tracks brace depth while respecting string literals, handling cases where the AI includes explanatory text before or after the JSON.

### AI Provider Abstraction

The `ai_client.py` module re-exports the `ai-cli-runner` package, which provides a unified interface across multiple AI providers:

```python
from ai_cli_runner import (
    PROVIDERS,
    VALID_AI_PROVIDERS,
    ProviderConfig,
    call_ai_cli,
    check_ai_cli_available,
    get_ai_cli_timeout,
    run_parallel_with_limit,
)
```

Three providers are supported: `claude` (Anthropic), `gemini` (Google), and `cursor` (Cursor). The provider is selected per-request or falls back to the configured default. Before generation starts, `check_ai_cli_available()` verifies that the CLI and credentials are properly set up.

## Markdown-to-HTML Rendering

The `renderer.py` module converts AI-generated markdown into a complete static documentation site using Python-Markdown and Jinja2.

### Markdown Processing

Markdown is converted to HTML with four extensions enabled:

```python
def _md_to_html(md_text: str) -> tuple[str, str]:
    md = markdown.Markdown(
        extensions=["fenced_code", "codehilite", "tables", "toc"],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False},
            "toc": {"toc_depth": "2-3"},
        },
    )
    content_html = md.convert(md_text)
    toc_html = getattr(md, "toc", "")
    return content_html, toc_html
```

| Extension | Purpose |
|---|---|
| `fenced_code` | Triple-backtick code blocks with language annotations |
| `codehilite` | Syntax highlighting via Pygments |
| `tables` | Pipe-delimited markdown tables |
| `toc` | Auto-generated table of contents from h2–h3 headings |

### Jinja2 Templates

The Jinja2 environment is lazily initialized as a module-level singleton with HTML auto-escaping enabled:

```python
_jinja_env: Environment | None = None

def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )
    return _jinja_env
```

Two templates drive the output:

**`page.html`** — Individual documentation pages with:
- Sidebar navigation with grouped page links and active page highlighting
- Client-side search input (bound to `search-index.json`)
- Main content area with rendered HTML
- Table of contents sidebar (generated from h2/h3 headings)
- Previous/next page navigation links
- Theme toggle (light/dark) and GitHub repository link

**`index.html`** — Landing page with:
- Hero section with project name, tagline, and "Get Started" call-to-action
- Card grid showing each navigation group and its pages

### Site Output Structure

The `render_site` function orchestrates the full rendering pipeline. It produces this file structure:

```
site/
├── index.html              # Landing page
├── {slug}.html             # One HTML page per documentation topic
├── {slug}.md               # Source markdown (also published)
├── assets/
│   ├── style.css           # Main stylesheet with dark mode support
│   ├── theme.js            # Light/dark theme toggle
│   ├── search.js           # Client-side full-text search (⌘K)
│   ├── copy.js             # Copy-to-clipboard for code blocks
│   ├── callouts.js         # Styled Note/Warning/Tip blocks
│   ├── scrollspy.js        # Active sidebar link tracking
│   ├── codelabels.js       # Language labels on code fences
│   └── github.js           # GitHub star count widget
├── search-index.json       # Search index (first 2000 chars per page)
├── llms.txt                # LLM-readable page index
└── llms-full.txt           # LLM-readable full content dump
```

> **Note:** Both `llms.txt` and `llms-full.txt` follow the emerging convention for making documentation accessible to large language models. `llms.txt` contains a structured index with page titles and descriptions, while `llms-full.txt` concatenates the full markdown content of every page.

## SQLite Storage

Project metadata is stored in a single SQLite table using `aiosqlite` for async-compatible access. The database file defaults to `/data/docsfy.db`.

### Schema

```sql
CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'generating',
    last_commit_sha TEXT,
    last_generated TEXT,
    page_count INTEGER DEFAULT 0,
    error_message TEXT,
    plan_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Project Lifecycle States

A project moves through three statuses during its lifecycle:

```
generating ──► ready
     │
     └──────► error
```

| Status | Meaning |
|---|---|
| `generating` | AI pipeline is running; `page_count` updates incrementally |
| `ready` | Generation complete; HTML is being served |
| `error` | Generation failed; `error_message` contains details |

Status transitions are enforced with a validation set:

```python
VALID_STATUSES = frozenset({"generating", "ready", "error"})
```

### Upsert and Partial Updates

The `save_project` function uses `ON CONFLICT` for upsert behavior, allowing re-generation of an existing project without deleting the record first. The `update_project_status` function dynamically builds its `SET` clause to only update provided fields:

```python
async def update_project_status(
    name: str,
    status: str,
    last_commit_sha: str | None = None,
    page_count: int | None = None,
    error_message: str | None = None,
    plan_json: str | None = None,
) -> None:
    fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values: list[str | int | None] = [status]
    if last_commit_sha is not None:
        fields.append("last_commit_sha = ?")
        values.append(last_commit_sha)
    if page_count is not None:
        fields.append("page_count = ?")
        values.append(page_count)
    # ... additional optional fields
    if status == "ready":
        fields.append("last_generated = CURRENT_TIMESTAMP")
    values.append(name)
    await db.execute(
        f"UPDATE projects SET {', '.join(fields)} WHERE name = ?", values
    )
```

> **Tip:** All queries use parameterized values. The `fields` list is built from hardcoded column names only — no user input is interpolated into the SQL.

## Filesystem-Based Caching

docsfy uses a simple filesystem cache to avoid re-generating pages when the repository hasn't changed. Each project's files live under a validated directory structure:

```python
def get_project_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name)

def get_project_site_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "site"

def get_project_cache_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "cache" / "pages"
```

This produces the following layout on disk:

```
/data/projects/{project_name}/
├── plan.json                # Saved documentation plan
├── cache/
│   └── pages/
│       ├── overview.md      # Cached AI-generated markdown
│       ├── installation.md
│       └── api-reference.md
└── site/
    ├── index.html           # Final rendered output
    ├── overview.html
    └── ...
```

### Cache Invalidation Strategy

Cache validity is determined by **git commit SHA**. When a generation request arrives, the system checks whether the stored commit SHA matches the current HEAD:

```python
existing = await get_project(project_name)
if (
    existing
    and existing.get("last_commit_sha") == commit_sha
    and existing.get("status") == "ready"
):
    logger.info(f"[{project_name}] Project is up to date at {commit_sha[:8]}")
    await update_project_status(project_name, status="ready")
    return
```

When `force=True` is set, the entire cache directory is cleared and generation runs from scratch:

```python
if force:
    cache_dir = get_project_cache_dir(project_name)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
```

> **Warning:** Setting `force=True` deletes all cached pages and triggers full AI regeneration, which consumes additional API credits and time.

## Request Lifecycle

The complete lifecycle of a documentation generation request:

```
1. Client sends POST /api/generate
      │
2. Pydantic validates request (repo_url XOR repo_path, URL format, etc.)
      │
3. Check _generating set → 409 if already in progress
      │
4. Save project to SQLite (status="generating")
      │
5. Spawn asyncio background task → return 202 Accepted
      │
      ▼ (background)
6. Verify AI CLI availability (check_ai_cli_available)
      │
7. Clone repo (--depth 1) or read local repo → get commit SHA
      │
8. Check if up-to-date (same SHA + status=ready + !force) → skip if yes
      │
9. Phase 1: run_planner() → AI analyzes codebase → JSON plan
      │
10. Store plan_json in database
      │
11. Phase 2: generate_all_pages() → up to 5 concurrent AI calls
      │       Each page: check cache → call AI → strip preamble → write cache
      │
12. render_site() → markdown to HTML via Jinja2
      │       Outputs: HTML pages, search index, static assets, llms.txt
      │
13. Update database (status="ready", commit_sha, page_count)
      │
14. Client polls GET /api/projects/{name} to check status
      │
15. Client views docs at GET /docs/{project}/{slug}.html
```

## Configuration

Application settings are managed through Pydantic's `BaseSettings`, which reads from environment variables and an optional `.env` file:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: str = "claude"
    ai_model: str = "claude-opus-4-6[1m]"
    ai_cli_timeout: int = Field(default=60, gt=0)
    log_level: str = "INFO"
    data_dir: str = "/data"
```

Settings are cached in memory with `@lru_cache` so the `.env` file is read only once:

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Per-request overrides (provider, model, timeout) take precedence over the global settings:

```python
ai_provider = request.ai_provider or settings.ai_provider
ai_model = request.ai_model or settings.ai_model
```

## Containerization

The Dockerfile uses a multi-stage build to keep the production image small while installing all three AI CLI tools:

```dockerfile
# Builder stage: install Python dependencies
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /usr/local/bin/uv
RUN uv sync --frozen --no-dev

# Production stage: install AI CLIs + copy venv
FROM python:3.12-slim
RUN curl -fsSL https://claude.ai/install.sh | bash      # Claude Code CLI
RUN curl -fsSL https://cursor.com/install | bash         # Cursor Agent CLI
RUN npm install -g @google/gemini-cli                     # Gemini CLI

ENTRYPOINT ["uv", "run", "--no-sync", "uvicorn", "docsfy.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> **Note:** The `--no-sync` flag prevents `uv` from modifying the virtual environment at runtime. This is required for OpenShift compatibility, where containers run as an arbitrary UID that may not have write access to the `.venv` directory.

## Design Decisions

| Decision | Rationale |
|---|---|
| **Two-phase pipeline** | Separating planning from content enables cached page-level regeneration and concurrent writing |
| **Background tasks via `asyncio.create_task`** | Avoids blocking the HTTP response; clients poll for status |
| **SQLite with `aiosqlite`** | Zero infrastructure dependencies; sufficient for metadata storage; async-compatible |
| **Filesystem cache** | Simple cache invalidation (by commit SHA); easy to inspect and clear; no external service |
| **Jinja2 with `autoescape`** | Industry-standard templating with built-in XSS protection |
| **Static site output** | Generated docs are plain HTML files — fast to serve, easy to download, no runtime dependencies |
| **`MAX_CONCURRENT_PAGES = 5`** | Balances generation speed against AI provider rate limits |
| **Slug validation at multiple layers** | Prevents path traversal in cache writes, site rendering, and HTTP serving |
