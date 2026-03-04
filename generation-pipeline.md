# Generation Pipeline

## Overview

Every documentation site produced by docsfy flows through a four-stage generation pipeline. When a `POST /api/generate` request arrives with a repository URL, the pipeline executes each stage sequentially — cloning the repository, planning the documentation structure with AI, generating page content concurrently, and rendering the final static HTML site.

```
POST /api/generate { repo_url }
        │
        ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Stage 1     │     │  Stage 2     │     │  Stage 3     │     │  Stage 4     │
│  Clone Repo  │────▶│  AI Planner  │────▶│  AI Content  │────▶│    HTML      │
│              │     │  (plan.json) │     │  Generator   │     │  Renderer    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
   temp dir              plan.json          cache/pages/*.md     site/*.html
```

The pipeline stores all intermediate and final artifacts under `/data/projects/{project-name}/`, making each stage's output inspectable and cacheable for incremental updates.

## Stage 1: Repository Cloning

The first stage acquires the source code by performing a **shallow clone** of the target repository into a temporary directory.

### How It Works

docsfy uses a `--depth 1` shallow clone to minimize bandwidth and disk usage. Only the latest commit on the default branch is fetched — historical commits are unnecessary since the AI analyzes the current state of the codebase.

```bash
git clone --depth 1 <repo_url> /tmp/<temp_dir>
```

### URL Support

Both major Git transport protocols are supported:

| Protocol | Example | Authentication |
|----------|---------|----------------|
| HTTPS | `https://github.com/org/repo.git` | Public repos work out of the box; private repos use system git credential helpers |
| SSH | `git@github.com:org/repo.git` | Uses SSH keys available to the container's `appuser` |

### Temporary Directory Lifecycle

The cloned repository lives in a temporary directory for the duration of the pipeline. This directory serves as the **working directory** for both Stage 2 (planning) and Stage 3 (content generation), giving the AI CLI full filesystem access to explore source code, configuration files, tests, and any other repository artifacts. The temporary directory is cleaned up after the pipeline completes.

> **Note:** The shallow clone captures only the repository's current state. If your documentation needs to reference version history or changelogs, that content should be maintained in files within the repository itself (e.g., `CHANGELOG.md`).

## Stage 2: AI-Driven Documentation Planning

The second stage is where AI analyzes the entire repository and produces a structured documentation plan. This plan determines what pages will be generated, how they're organized, and what navigation hierarchy the final site will have.

### AI CLI Invocation

The AI CLI is executed as a subprocess with the cloned repository set as the working directory. This gives the AI full access to explore every file in the repo:

```python
subprocess.run(
    cmd,
    input=prompt,
    capture_output=True,
    text=True,
    cwd=repo_path,       # AI can explore the entire cloned repo
    timeout=ai_cli_timeout * 60
)
```

For asynchronous execution within the FastAPI service, the blocking subprocess call is wrapped with `asyncio.to_thread`:

```python
success, output = await asyncio.to_thread(
    subprocess.run, cmd, input=prompt, capture_output=True, text=True, cwd=repo_path
)
```

The prompt instructs the AI to analyze the repository structure — reading source files, configs, tests, CI/CD pipelines, and any existing documentation — then output a `plan.json` that defines the complete documentation site structure.

### Provider-Specific Commands

The command constructed depends on the configured AI provider:

| Provider | Command |
|----------|---------|
| Claude | `claude --model <model> --dangerously-skip-permissions -p` |
| Gemini | `gemini --model <model> --yolo` |
| Cursor | `agent --force --model <model> --print --workspace <repo_path>` |

> **Note:** Cursor uses a `--workspace` flag instead of subprocess `cwd` to point the AI at the repository. This is handled by the `uses_own_cwd` flag in the provider configuration.

Each provider is defined through a common configuration pattern:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

### The plan.json Output

The AI's response is parsed using a multi-strategy JSON extraction approach that handles the variety of output formats AI CLIs can produce:

1. **Direct JSON parse** — attempt to parse the entire output as JSON
2. **Brace-matching** — find the outermost `{...}` JSON object in the output
3. **Markdown code block extraction** — extract JSON from `` ```json ``` `` blocks
4. **Regex fallback** — recover JSON fragments using pattern matching

The resulting `plan.json` is saved to `/data/projects/{project-name}/plan.json` and defines the documentation structure:

```
/data/projects/{project-name}/
  plan.json             # Documentation structure from AI
```

The plan contains pages, sections, and the navigation hierarchy that will drive both Stage 3 (what content to generate) and Stage 4 (how to render the site navigation).

### Availability Check

Before starting a generation pipeline, docsfy verifies that the configured AI CLI is functional by running a lightweight "Hi" prompt. This fast-fails the pipeline if the AI provider is unavailable or misconfigured, rather than discovering the problem after the clone stage has already completed.

## Stage 3: Concurrent Page Content Generation

The third stage iterates over every page defined in `plan.json` and generates the markdown content for each one. This is the most time-intensive stage, and docsfy uses **async concurrency with semaphore-limited parallelism** to accelerate it.

### Concurrency Model

Each page generation is an independent AI CLI invocation — the AI explores the codebase and writes markdown for that specific page. Since these invocations are independent, they can run concurrently.

docsfy uses an `asyncio.Semaphore` to control the level of parallelism:

```python
semaphore = asyncio.Semaphore(max_concurrent_pages)

async def generate_page(page_def):
    async with semaphore:
        prompt = build_page_prompt(page_def, plan)
        success, markdown = await asyncio.to_thread(
            subprocess.run, cmd, input=prompt,
            capture_output=True, text=True, cwd=repo_path
        )
        return page_def, markdown
```

The semaphore ensures that no more than `max_concurrent_pages` AI CLI processes run simultaneously. This prevents resource exhaustion (CPU, memory, API rate limits) while still achieving significant speedup over sequential generation.

All page tasks are gathered and executed concurrently:

```python
tasks = [generate_page(page) for page in plan["pages"]]
results = await asyncio.gather(*tasks)
```

### Per-Page AI Invocation

For each page, the AI CLI runs with `cwd` set to the cloned repository, just like the planning stage. The prompt provides:

- The page's title and description from `plan.json`
- The section it belongs to
- Instructions to explore the codebase as needed and produce comprehensive markdown

This means the AI can read any file in the repository — source code, tests, configuration — to produce accurate, code-grounded documentation for each page.

### Markdown Caching

Generated markdown files are cached at:

```
/data/projects/{project-name}/
  cache/
    pages/*.md          # AI-generated markdown (one file per page)
```

This cache serves a critical purpose for **incremental updates**. When a repository is re-generated after changes:

1. docsfy compares the current commit SHA against the stored SHA in SQLite
2. If the plan structure is unchanged, only pages affected by code changes are regenerated
3. Unchanged pages are served from the markdown cache, avoiding redundant AI invocations

> **Tip:** The markdown cache means that re-generating documentation after small code changes is significantly faster than the initial generation. Only the affected pages trigger new AI CLI calls.

### Return Value Convention

Each AI CLI invocation returns a `tuple[bool, str]` — a success boolean and the output string. This consistent interface allows uniform error handling across all three providers:

```python
success, output = await run_ai_cli(prompt, cwd=repo_path)
if not success:
    log.error(f"Page generation failed: {output}")
```

## Stage 4: HTML Rendering with Jinja2

The final stage transforms the markdown content and navigation plan into a polished static HTML documentation site.

### Rendering Process

The renderer takes two inputs:

- **`plan.json`** — defines the navigation hierarchy (sections, pages, ordering)
- **`cache/pages/*.md`** — the AI-generated markdown content for each page

Each markdown file is converted to HTML using the Python `markdown` library, then wrapped in a Jinja2 template that provides the complete page shell — header, sidebar navigation, content area, and footer.

### Jinja2 Templates

docsfy uses Jinja2 as its templating engine to produce the final HTML. Templates receive the rendered HTML content, navigation structure, page metadata, and project information as context variables:

```python
template = jinja_env.get_template("page.html")
html = template.render(
    content=rendered_markdown,
    navigation=plan["pages"],
    page_title=page["title"],
    project_name=project_name,
    # ... additional context
)
```

### Built-in Features

The rendered HTML site includes several features out of the box, powered by bundled CSS and JavaScript assets:

| Feature | Implementation |
|---------|---------------|
| Sidebar navigation | Generated from `plan.json` hierarchy |
| Dark/light theme toggle | `theme-toggle.js` with CSS custom properties |
| Client-side search | `search.js` powered by a pre-built `search-index.json` |
| Code syntax highlighting | `highlight.js` for fenced code blocks |
| Card layouts | CSS grid-based component cards |
| Callout boxes | Styled note, warning, and info blocks |
| Responsive design | Mobile-friendly layout with CSS media queries |

### Output Structure

The rendered site is written to `/data/projects/{project-name}/site/`:

```
/data/projects/{project-name}/
  site/
    index.html            # Landing page
    *.html                # One HTML file per documentation page
    assets/
      style.css           # Theme and layout styles
      search.js           # Client-side search engine
      theme-toggle.js     # Dark/light mode toggle
      highlight.js        # Code syntax highlighting
    search-index.json     # Pre-built search index for client-side search
```

### Serving and Distribution

Once the site is generated, it can be accessed in two ways:

- **Direct serving** — Access pages via `GET /docs/{project}/{path}`, where docsfy serves the static files directly from the FastAPI server
- **Download and self-host** — Download the entire site as a `.tar.gz` archive via `GET /api/projects/{name}/download` and deploy it to any static hosting provider (Nginx, S3, Cloudflare Pages, GitHub Pages, etc.)

> **Tip:** The generated site is fully self-contained with all assets bundled inline. No external CDN dependencies are required, making it suitable for air-gapped or intranet deployments.

## Configuration

The generation pipeline is controlled by environment variables:

```bash
# AI provider selection: claude, gemini, or cursor
AI_PROVIDER=claude

# Model to use for the selected provider
AI_MODEL=claude-opus-4-6[1m]

# Timeout for each AI CLI invocation (in minutes)
AI_CLI_TIMEOUT=60

# Logging verbosity
LOG_LEVEL=INFO
```

### Provider Authentication

Each provider requires its own authentication setup:

| Provider | Authentication Options |
|----------|----------------------|
| **Claude** | `ANTHROPIC_API_KEY` for direct API access, or Vertex AI via `CLAUDE_CODE_USE_VERTEX=1` with `CLOUD_ML_REGION` and `ANTHROPIC_VERTEX_PROJECT_ID` |
| **Gemini** | `GEMINI_API_KEY` |
| **Cursor** | `CURSOR_API_KEY` |

> **Warning:** The `AI_CLI_TIMEOUT` applies per invocation — once for the planner stage and once for each page in the content generation stage. For large repositories with many pages, the total pipeline time can be significantly longer than this single-invocation timeout.

## Pipeline State Tracking

docsfy tracks the state of each project's generation pipeline in a SQLite database at `/data/docsfy.db`:

| Field | Description |
|-------|-------------|
| Project name | Derived from the repository URL |
| Repository URL | The source repository |
| Status | `generating`, `ready`, or `error` |
| Last generated | Timestamp of the most recent successful generation |
| Last commit SHA | The HEAD commit of the last processed clone |
| Generation logs | Diagnostic output from the pipeline stages |

The status field transitions through the pipeline:

```
POST /api/generate
    │
    ▼
generating ──────▶ ready     (on success)
    │
    └────────────▶ error     (on failure at any stage)
```

You can query the current status of all projects via `GET /api/status` or get detailed information about a specific project with `GET /api/projects/{name}`.

## Incremental Updates

When `POST /api/generate` is called for a repository that has already been generated, docsfy performs an **incremental update** rather than a full regeneration:

1. **SHA comparison** — The current HEAD commit SHA is compared against the stored SHA in SQLite
2. **Plan re-evaluation** — If the SHA has changed, the AI Planner re-runs to check whether the documentation structure needs updating
3. **Selective regeneration** — Only pages whose content may be affected by the code changes are regenerated; unchanged pages are served from the markdown cache
4. **Re-render** — Stage 4 always runs to produce a fresh HTML site from the (updated) markdown files

This approach dramatically reduces the cost and time of keeping documentation up to date with a rapidly evolving codebase.

> **Note:** The incremental update strategy relies on the AI planner's ability to identify which pages are affected by code changes. For maximum accuracy, ensure your `plan.json` pages have clear, well-scoped topics that map to identifiable areas of the codebase.
