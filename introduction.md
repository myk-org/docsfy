# Introduction

docsfy is an AI-powered documentation generator that produces polished static HTML documentation sites from GitHub repositories. Point it at any repository — public or private, local or remote — and docsfy will analyze the codebase, plan a documentation structure, generate content for every page, and render a complete, self-contained static site ready for hosting.

Instead of writing documentation manually, docsfy delegates the work to AI. It uses CLI-based AI tools like Claude Code, Gemini CLI, or Cursor Agent to deeply explore your repository's source code, configuration, tests, and CI/CD pipelines. The result is accurate, comprehensive documentation that reflects what your project actually does — not just what a README says.

## How It Works

docsfy follows a four-stage pipeline to transform a repository into a documentation site:

```
Repository → Clone → AI Plan → AI Generate → Render HTML
```

### Stage 1: Clone the Repository

docsfy performs a shallow clone of the target repository to a temporary directory. It captures the current commit SHA for tracking incremental updates later.

```python
# From src/docsfy/repository.py
def clone_repo(repo_url: str, base_dir: Path) -> tuple[Path, str]:
    repo_name = extract_repo_name(repo_url)
    repo_path = base_dir / repo_name
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--", repo_url, str(repo_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    # ...
    return repo_path, commit_sha
```

For local repositories, docsfy skips cloning and reads the project in place — only the commit SHA is extracted.

### Stage 2: AI Plans the Documentation

An AI agent explores the entire repository — source code, configuration files, tests, CI/CD pipelines — and outputs a structured JSON plan defining the documentation's table of contents.

```python
# From src/docsfy/prompts.py
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

The planner prompt instructs the AI to cover introduction, installation, configuration, usage guides, API reference, and any other sections relevant to the project. Critically, the AI is told not to rely on the README — it must understand the project from its code.

### Stage 3: AI Generates Each Page

With the plan in hand, docsfy sends a generation prompt for every page. Each page is generated independently, and up to five pages are generated concurrently using an async semaphore:

```python
# From src/docsfy/generator.py
MAX_CONCURRENT_PAGES = 5

async def generate_all_pages(
    repo_path: Path,
    plan: dict[str, Any],
    cache_dir: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    use_cache: bool = False,
    project_name: str = "",
) -> dict[str, str]:
    # ...
    results = await run_parallel_with_limit(
        coroutines, max_concurrency=MAX_CONCURRENT_PAGES
    )
```

Each generated page is cached to disk as a markdown file. If a page generation fails, docsfy gracefully falls back to a placeholder rather than aborting the entire run.

### Stage 4: Render to Static HTML

The final stage converts all generated markdown into a complete static website using Jinja2 templates and the Python `markdown` library with syntax highlighting via Pygments:

```python
# From src/docsfy/renderer.py
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

The rendered site includes an index page, individual HTML pages with navigation, and a full set of static assets.

## Key Features

### Multi-AI Provider Support

docsfy supports three AI providers through a unified interface powered by the `ai_cli_runner` package:

| Provider | CLI Tool | Description |
|----------|----------|-------------|
| **Claude** | `claude` | Anthropic's Claude Code CLI |
| **Gemini** | `gemini` | Google's Gemini CLI |
| **Cursor** | `agent` | Cursor's Agent CLI |

Switch providers at any time — per-request or via environment configuration:

```bash
# .env configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
```

```bash
# Or override per request
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/repo",
    "ai_provider": "gemini",
    "ai_model": "gemini-2.0-flash"
  }'
```

The provider can also be specified as a field in the API request model:

```python
# From src/docsfy/models.py
class GenerateRequest(BaseModel):
    repo_url: str | None = Field(default=None, description="Git repository URL (HTTPS or SSH)")
    repo_path: str | None = Field(default=None, description="Local git repository path")
    ai_provider: Literal["claude", "gemini", "cursor"] | None = None
    ai_model: str | None = None
    ai_cli_timeout: int | None = Field(default=None, gt=0)
    force: bool = Field(default=False, description="Force full regeneration, ignoring cache")
```

### Incremental Updates

docsfy tracks each project's last-generated commit SHA in an SQLite database. When you regenerate documentation for a repository, it compares the current HEAD against the stored SHA and skips regeneration if nothing has changed:

```python
# From src/docsfy/main.py
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

When a repository does have new commits, docsfy re-runs the full pipeline. You can also force a complete regeneration by setting `force: true`, which clears the page cache:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/repo", "force": true}'
```

### Beautiful Static Site Output

Every generated site is a self-contained collection of HTML, CSS, and JavaScript — no server-side runtime required. The output includes:

```
site/
├── index.html              # Homepage with navigation cards
├── {slug}.html             # Individual documentation pages
├── {slug}.md               # Markdown source for each page
├── assets/
│   ├── style.css           # Responsive CSS with dark/light themes
│   ├── theme.js            # Theme toggle with localStorage persistence
│   ├── search.js           # Client-side full-text search
│   ├── copy.js             # Copy-to-clipboard for code blocks
│   ├── callouts.js         # Note/Warning/Tip block styling
│   ├── scrollspy.js        # Active navigation highlighting
│   ├── codelabels.js       # Language labels on fenced code blocks
│   └── github.js           # GitHub star count badge
├── search-index.json       # Search index for client-side search
├── llms.txt                # LLM-friendly page index
└── llms-full.txt           # All content concatenated for LLM consumption
```

The generated sites feature:

- **Dark and light themes** with automatic persistence
- **Client-side search** powered by a pre-built JSON index
- **Syntax highlighting** via Pygments for all code blocks
- **Responsive layout** with a collapsible sidebar for mobile
- **Previous/next navigation** between pages
- **Copy-to-clipboard buttons** on code blocks
- **Table of contents** auto-generated from page headings (h2–h3)
- **LLM-friendly output** via `llms.txt` and `llms-full.txt` files

> **Tip:** Download any project's generated site as a `.tar.gz` archive via the `/api/projects/{name}/download` endpoint and host it anywhere — GitHub Pages, Netlify, S3, or your own server.

### Asynchronous Generation

Documentation generation runs in the background. The API returns immediately with a `202 Accepted` status while the pipeline runs asynchronously:

```python
# From src/docsfy/main.py
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
return {"project": project_name, "status": "generating"}
```

Duplicate generation requests for the same project are rejected with `409 Conflict`, preventing wasted compute.

### Local and Remote Repositories

docsfy accepts both GitHub URLs and local filesystem paths:

```bash
# Remote repository (HTTPS)
{"repo_url": "https://github.com/org/repo"}

# Remote repository (SSH)
{"repo_url": "git@github.com:org/repo.git"}

# Local repository
{"repo_path": "/home/user/my-project"}
```

> **Note:** You must provide exactly one of `repo_url` or `repo_path` — not both. The API validates this constraint and returns a clear error if violated.

## Architecture Overview

docsfy is built as a FastAPI application with a modular architecture:

| Module | Responsibility |
|--------|---------------|
| `main.py` | FastAPI app, HTTP endpoints, generation orchestration |
| `generator.py` | AI planning and concurrent page generation |
| `renderer.py` | Markdown-to-HTML conversion, Jinja2 templates, site assembly |
| `repository.py` | Git clone and commit SHA extraction |
| `storage.py` | SQLite database and filesystem path management |
| `prompts.py` | AI prompt construction for planning and writing |
| `json_parser.py` | Multi-strategy JSON extraction from AI responses |
| `config.py` | Pydantic-based settings from environment variables |
| `models.py` | Request/response validation models |
| `ai_client.py` | Unified AI provider interface via `ai_cli_runner` |

The application uses `aiosqlite` for non-blocking database access and `asyncio.to_thread()` to run blocking operations (git, AI CLI calls) without stalling the event loop.

## Quick Example

Start the server and generate documentation for any public repository:

```bash
# Start docsfy
docker compose up

# Generate docs
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/repo"}'

# Check status
curl http://localhost:8000/api/status

# View the docs once ready
open http://localhost:8000/docs/repo/index.html

# Download for self-hosting
curl -O http://localhost:8000/api/projects/repo/download
```

> **Note:** Generation time depends on repository size and the AI provider used. The API returns immediately — poll `/api/projects/{name}` to check when the status transitions from `"generating"` to `"ready"`.
