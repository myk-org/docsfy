# Project Structure

This page describes the docsfy directory layout, module organization, and how each component fits into the documentation generation pipeline.

## Directory Layout

```
docsfy/
├── src/docsfy/                  # Application source code
│   ├── __init__.py
│   ├── main.py                  # FastAPI application and HTTP endpoints
│   ├── generator.py             # AI-powered content orchestration
│   ├── renderer.py              # Markdown-to-HTML and static site output
│   ├── storage.py               # SQLite persistence layer
│   ├── repository.py            # Git clone and repo info extraction
│   ├── models.py                # Pydantic request/response schemas
│   ├── config.py                # Environment-based settings
│   ├── prompts.py               # AI prompt templates
│   ├── json_parser.py           # Robust JSON extraction from AI output
│   ├── ai_client.py             # AI provider re-exports
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── index.html           # Homepage template
│   │   └── page.html            # Documentation page template
│   └── static/                  # Frontend assets
│       ├── style.css            # Main stylesheet
│       ├── theme.js             # Dark/light theme toggle
│       ├── search.js            # Client-side search
│       ├── github.js            # GitHub link integration
│       ├── scrollspy.js         # Active navigation tracking
│       ├── callouts.js          # Note/warning/tip rendering
│       ├── codelabels.js        # Code block language labels
│       └── copy.js              # Copy-to-clipboard for code blocks
├── tests/                       # Test suite (mirrors src/ modules)
│   ├── test_main.py
│   ├── test_generator.py
│   ├── test_renderer.py
│   ├── test_storage.py
│   ├── test_repository.py
│   ├── test_models.py
│   ├── test_config.py
│   ├── test_prompts.py
│   ├── test_json_parser.py
│   ├── test_ai_client.py
│   └── test_integration.py
├── pyproject.toml               # Project metadata and dependencies
├── Dockerfile                   # Multi-stage production build
├── docker-compose.yaml          # Local development stack
├── tox.toml                     # Test automation
├── .env.example                 # Environment variable template
├── .pre-commit-config.yaml      # Linting and formatting hooks
├── .flake8                      # Flake8 configuration
└── .gitleaks.toml               # Secret detection rules
```

## Runtime Data Layout

When docsfy runs, it stores all project data under a configurable `DATA_DIR` (default `/data`):

```
/data/
├── docsfy.db                        # SQLite database
└── projects/
    └── <project-name>/
        ├── plan.json                 # Documentation structure plan
        ├── cache/
        │   └── pages/
        │       ├── getting-started.md   # Cached AI-generated markdown
        │       └── configuration.md
        └── site/                     # Rendered static site
            ├── index.html
            ├── getting-started.html
            ├── getting-started.md
            ├── search-index.json
            ├── llms.txt
            ├── llms-full.txt
            └── assets/
                ├── style.css
                └── *.js
```

## Module Reference

### `main.py` — FastAPI Application

The central orchestrator. Defines all HTTP endpoints and coordinates the documentation generation workflow by delegating to the other modules.

**Key components:**

- `app` — the FastAPI instance, initialized with a `lifespan` handler that calls `init_db()` on startup
- `_generating: set[str]` — an in-memory set that tracks projects currently being generated, preventing duplicate runs
- `_validate_project_name()` — guards all project-name inputs against path traversal using a strict regex

```python
def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise HTTPException(status_code=400, detail=f"Invalid project name: '{name}'")
    return name
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `GET` | `/api/status` | Lists all projects and their statuses |
| `POST` | `/api/generate` | Triggers documentation generation (returns 202) |
| `GET` | `/api/projects/{name}` | Retrieves project metadata |
| `DELETE` | `/api/projects/{name}` | Deletes a project and its files |
| `GET` | `/api/projects/{name}/download` | Downloads the rendered site as `.tar.gz` |
| `GET` | `/docs/{project}/{path}` | Serves generated documentation files |

The generation endpoint fires an async background task via `asyncio.create_task()`. This internal `_run_generation()` function handles the full pipeline:

```python
async def _run_generation(
    repo_url: str | None,
    repo_path: str | None,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int,
    force: bool = False,
) -> None:
```

1. Validates AI CLI availability
2. Clones the remote repo (or reads the local one)
3. Runs the AI planner to produce a documentation structure
4. Generates all pages in parallel
5. Renders the static site
6. Updates the project status in the database

**CLI entry point:**

The `run()` function at the bottom of the file serves as the CLI entry point registered in `pyproject.toml`:

```python
def run() -> None:
    import uvicorn
    reload = os.getenv("DEBUG", "").lower() == "true"
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
```

---

### `generator.py` — AI Orchestration

Manages the two-phase AI workflow: **planning** (structure) and **page generation** (content). Delegates actual AI calls to `ai_client` and prompt construction to `prompts`.

**Planning phase — `run_planner()`:**

Sends the planner prompt to the AI provider and parses the JSON response into a documentation plan:

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

**Page generation — `generate_page()` and `generate_all_pages()`:**

Individual pages are generated with caching support. The `generate_all_pages()` function iterates through the plan's navigation structure and generates all pages in parallel, limited by `MAX_CONCURRENT_PAGES = 5`:

```python
results = await run_parallel_with_limit(
    coroutines, max_concurrency=MAX_CONCURRENT_PAGES
)
```

Each page goes through `_strip_ai_preamble()` to remove any thinking/planning text the AI may include before the actual markdown content. Failed pages get a placeholder instead of crashing the entire generation run.

> **Note:** The page cache lives at `{project_cache_dir}/{slug}.md`. Set `force=True` on the generate request to bypass the cache and regenerate all pages.

---

### `renderer.py` — HTML Output

Converts AI-generated markdown into a complete static documentation site. Uses the Python `markdown` library for conversion and Jinja2 for HTML templating.

**Markdown conversion:**

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

The `codehilite` extension uses Pygments for syntax highlighting. The `toc` extension auto-generates a table of contents from h2 and h3 headings.

**Site rendering — `render_site()`:**

The main entry point for building the full static site. It:

1. Creates the output directory and copies static assets into `assets/`
2. Validates all page slugs (filters out path-unsafe values)
3. Renders `index.html` as the homepage
4. Renders each page with previous/next navigation links
5. Writes both `.html` and `.md` versions of every page
6. Generates `search-index.json` for client-side search
7. Generates `llms.txt` (page index) and `llms-full.txt` (all content concatenated) for AI tool consumption

> **Tip:** The `llms.txt` and `llms-full.txt` files follow the emerging convention for making documentation accessible to LLMs. They are generated automatically for every project.

---

### `storage.py` — SQLite Persistence

Manages all database operations using `aiosqlite` for async SQLite access. Stores project metadata, generation status, and documentation plans.

**Database schema:**

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

**Module-level path configuration:**

```python
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"
VALID_STATUSES = frozenset({"generating", "ready", "error"})
```

**Key functions:**

| Function | Description |
|----------|-------------|
| `init_db()` | Creates the `projects` table if it doesn't exist |
| `save_project()` | Inserts or updates a project record (upsert) |
| `update_project_status()` | Partial update — only modifies provided fields |
| `get_project()` | Fetches a single project by name |
| `list_projects()` | Returns all projects ordered by last update |
| `delete_project()` | Removes a project from the database |
| `get_project_dir()` | Returns `PROJECTS_DIR / name` |
| `get_project_site_dir()` | Returns `PROJECTS_DIR / name / "site"` |
| `get_project_cache_dir()` | Returns `PROJECTS_DIR / name / "cache" / "pages"` |

All path-returning functions validate the project name through `_validate_name()` to prevent path traversal.

> **Warning:** The module-level path variables (`DB_PATH`, `DATA_DIR`, `PROJECTS_DIR`) are set at import time from environment variables. In tests, these globals are overridden directly for isolation.

---

### `repository.py` — Git Operations

Handles cloning remote repositories and extracting commit information from local ones. All git operations use `subprocess.run()` directly.

**`clone_repo()`** performs a shallow clone (`--depth 1`) for speed, then extracts the HEAD commit SHA:

```python
def clone_repo(repo_url: str, base_dir: Path) -> tuple[Path, str]:
    repo_name = extract_repo_name(repo_url)
    repo_path = base_dir / repo_name
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--", repo_url, str(repo_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        msg = f"Clone failed: {result.stderr or result.stdout}"
        raise RuntimeError(msg)
    # ... extract commit SHA ...
    return repo_path, commit_sha
```

**`extract_repo_name()`** parses repository names from both HTTPS and SSH URLs:

```python
def extract_repo_name(repo_url: str) -> str:
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    if ":" in name:
        name = name.split(":")[-1].split("/")[-1]
    return name
```

**`get_local_repo_info()`** reads the HEAD SHA from an existing local repository without cloning.

> **Note:** `clone_repo()` is a synchronous function. In `main.py`, it is wrapped with `asyncio.to_thread()` to avoid blocking the event loop.

---

### `models.py` — Pydantic Schemas

Defines all request/response data structures with built-in validation using Pydantic v2.

**`GenerateRequest`** — the primary API input model:

```python
class GenerateRequest(BaseModel):
    repo_url: str | None = Field(
        default=None, description="Git repository URL (HTTPS or SSH)"
    )
    repo_path: str | None = Field(default=None, description="Local git repository path")
    ai_provider: Literal["claude", "gemini", "cursor"] | None = None
    ai_model: str | None = None
    ai_cli_timeout: int | None = Field(default=None, gt=0)
    force: bool = Field(
        default=False, description="Force full regeneration, ignoring cache"
    )
```

Validation rules enforced by Pydantic validators:

- Exactly one of `repo_url` or `repo_path` must be provided (not both, not neither)
- `repo_url` must match HTTPS (`https://host/org/repo`) or SSH (`git@host:org/repo`) patterns
- `repo_path` must point to an existing directory containing a `.git` subdirectory
- The `project_name` property extracts the repository name from whichever source is provided

**Documentation plan models:**

```python
class DocPage(BaseModel):
    slug: str          # URL-friendly identifier (e.g., "getting-started")
    title: str         # Human-readable title (e.g., "Getting Started")
    description: str = ""

class NavGroup(BaseModel):
    group: str         # Section heading (e.g., "Guides")
    pages: list[DocPage]

class DocPlan(BaseModel):
    project_name: str
    tagline: str = ""
    navigation: list[NavGroup] = Field(default_factory=list)
```

**`ProjectStatus`** — returned by the status API:

```python
class ProjectStatus(BaseModel):
    name: str
    repo_url: str
    status: Literal["generating", "ready", "error"] = "generating"
    last_commit_sha: str | None = None
    last_generated: str | None = None
    error_message: str | None = None
    page_count: int = 0
```

---

### `config.py` — Settings

Loads configuration from environment variables and `.env` files using `pydantic-settings`. The settings instance is cached with `@lru_cache` so it is created once per process.

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

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

| Setting | Env Variable | Default | Description |
|---------|-------------|---------|-------------|
| `ai_provider` | `AI_PROVIDER` | `"claude"` | AI backend (`claude`, `gemini`, or `cursor`) |
| `ai_model` | `AI_MODEL` | `"claude-opus-4-6[1m]"` | Model identifier |
| `ai_cli_timeout` | `AI_CLI_TIMEOUT` | `60` | Timeout in seconds per AI call |
| `log_level` | `LOG_LEVEL` | `"INFO"` | Logging verbosity |
| `data_dir` | `DATA_DIR` | `"/data"` | Root directory for project storage |

> **Tip:** The `extra="ignore"` setting means unrecognized environment variables are silently ignored rather than causing errors. This makes it safe to have additional variables in your `.env` file.

---

### `prompts.py` — AI Prompt Templates

Contains the prompt templates that instruct the AI during both phases of documentation generation. These are plain Python strings — no external template engine required.

**`PLAN_SCHEMA`** defines the expected JSON output structure for the planner:

```python
PLAN_SCHEMA = """{
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
}"""
```

**`build_planner_prompt(project_name)`** instructs the AI to explore the repository and produce a documentation plan as JSON. The prompt explicitly tells the AI to examine source code, configuration, tests, and CI/CD — not just the README.

**`build_page_prompt(project_name, page_title, page_description)`** instructs the AI to write a single documentation page in markdown, using real code examples from the codebase and callout formatting for notes, warnings, and tips.

> **Note:** Both prompts include the directive to output **only** the expected format (JSON for the planner, markdown for pages) with no surrounding text. This works in tandem with `json_parser.py` and `_strip_ai_preamble()` as fallback handling for when AI providers include extra output anyway.

---

### `json_parser.py` — JSON Extraction

AI responses often contain surrounding text, thinking output, or markdown formatting around the actual JSON payload. This module provides robust extraction using a three-strategy fallback approach:

```python
def parse_json_response(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    # Strategy 1: Direct parse if text starts with "{"
    if text.startswith("{"):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
    # Strategy 2: Find matching braces in the text
    result = _extract_json_by_braces(text)
    if result is not None:
        return result
    # Strategy 3: Extract from markdown code blocks
    result = _extract_json_from_code_blocks(text)
    if result is not None:
        return result
    return None
```

**Strategy details:**

1. **Direct parse** — handles clean AI output that starts with `{`
2. **Brace matching** (`_extract_json_by_braces`) — walks through the text tracking brace depth and string escaping to find the outermost JSON object, even when surrounded by arbitrary text
3. **Code block extraction** (`_extract_json_from_code_blocks`) — extracts JSON from `` ```json ... ``` `` markdown blocks using regex

If all three strategies fail, the function returns `None` and the caller (typically `run_planner()`) raises a `RuntimeError`.

---

### `ai_client.py` — AI Provider Integration

A thin re-export layer that surfaces the `ai-cli-runner` external package into the docsfy namespace:

```python
from ai_cli_runner import (
    PROVIDERS,                  # Dict of provider configurations
    VALID_AI_PROVIDERS,         # frozenset: {"claude", "gemini", "cursor"}
    ProviderConfig,             # Provider configuration dataclass
    call_ai_cli,                # Async function to invoke an AI provider
    check_ai_cli_available,     # Check if a provider's CLI is installed
    get_ai_cli_timeout,         # Get timeout for a provider
    run_parallel_with_limit,    # Run coroutines with bounded concurrency
)
```

This indirection allows the rest of the codebase to import from `docsfy.ai_client` rather than directly from `ai_cli_runner`, making it straightforward to swap the underlying package or add docsfy-specific wrappers in the future.

## Module Dependency Graph

The following diagram shows how modules import from each other. Arrows point from the importing module to the imported module.

```
main.py
├── config.py          (get_settings)
├── models.py          (GenerateRequest)
├── ai_client.py       (check_ai_cli_available)
├── repository.py      (clone_repo, get_local_repo_info)
├── generator.py       (run_planner, generate_all_pages)
│   ├── ai_client.py   (call_ai_cli, run_parallel_with_limit)
│   ├── prompts.py     (build_planner_prompt, build_page_prompt)
│   └── json_parser.py (parse_json_response)
├── renderer.py        (render_site)
│   └── [jinja2, markdown]  (external)
└── storage.py         (init_db, save_project, get_project, ...)
    └── [aiosqlite]    (external)
```

Modules at the bottom of the graph (`config.py`, `models.py`, `prompts.py`, `json_parser.py`) have no internal dependencies — they only import from the standard library or external packages. This keeps the dependency tree acyclic and each module independently testable.

> **Note:** `generator.py` has one deferred import — it imports `update_project_status` from `storage` inside `generate_page()` rather than at module level. This avoids a circular dependency while still allowing page generation to update progress in the database.

## Test Organization

Every source module has a corresponding test file in the `tests/` directory. Tests use `pytest` with `pytest-asyncio` for async support and `pytest-xdist` for parallel execution.

| Test File | Module Under Test | Focus |
|-----------|------------------|-------|
| `test_main.py` | `main.py` | API endpoint behavior via `httpx.AsyncClient` |
| `test_generator.py` | `generator.py` | Planner and page generation with mocked AI calls |
| `test_renderer.py` | `renderer.py` | HTML output and site rendering |
| `test_storage.py` | `storage.py` | Database CRUD with temporary SQLite databases |
| `test_repository.py` | `repository.py` | Git cloning and URL parsing |
| `test_models.py` | `models.py` | Pydantic validation (valid and invalid inputs) |
| `test_config.py` | `config.py` | Settings loading from environment |
| `test_prompts.py` | `prompts.py` | Prompt template construction |
| `test_json_parser.py` | `json_parser.py` | JSON extraction strategies |
| `test_ai_client.py` | `ai_client.py` | Re-export verification |
| `test_integration.py` | Full pipeline | End-to-end generation flow |

Run the full test suite with:

```bash
uv run --extra dev pytest tests/
```

Or in parallel via tox:

```bash
tox -e unittests
```

The pytest configuration in `pyproject.toml` enables automatic async test detection:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```
