# Generation Pipeline

Every documentation site produced by docsfy passes through a four-stage pipeline. When a `POST /api/generate` request arrives with a repository URL, the server executes these stages sequentially — clone, plan, generate, render — transforming a raw codebase into a polished static HTML documentation site.

```
POST /api/generate { "repo_url": "https://github.com/org/repo" }
        │
        ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Stage 1    │     │   Stage 2    │     │   Stage 3    │     │   Stage 4    │
│  Clone Repo  │────▶│  AI Planner  │────▶│  AI Content  │────▶│    HTML      │
│              │     │ (plan.json)  │     │  Generator   │     │  Renderer    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                      │
                                                                      ▼
                                                           /data/projects/{name}/site/
```

This page covers each stage in depth — what it does, how it works internally, and how its output feeds into the next stage.

---

## Stage 1: Repository Cloning

The pipeline begins by obtaining a local copy of the target repository. This clone serves as the working directory for all subsequent AI operations, giving the AI full filesystem access to explore source code, configuration files, tests, and any other project artifacts.

### How It Works

docsfy performs a **shallow clone** (`--depth 1`) into a temporary directory. A shallow clone fetches only the latest commit rather than the full history, significantly reducing clone time and disk usage for large repositories.

```bash
git clone --depth 1 <repo_url> <temp_directory>
```

### Supported Repository Types

| URL Format | Example | Auth Method |
|------------|---------|-------------|
| HTTPS (public) | `https://github.com/org/repo` | None required |
| HTTPS (private) | `https://github.com/org/private-repo` | System git credentials |
| SSH | `git@github.com:org/repo.git` | SSH keys on the host |

Private repository access relies on the credentials available in the container's environment. When running via Docker, SSH keys or git credential helpers must be mounted into the container.

### SHA Tracking

After cloning, docsfy records the **commit SHA** of the cloned repository in its SQLite database (`/data/docsfy.db`). This SHA is critical for the [incremental update](#incremental-updates) mechanism — on subsequent generation requests for the same repository, docsfy compares the current HEAD against the stored SHA to determine whether regeneration is necessary.

> **Note:** The temporary clone directory is used as the working directory (`cwd`) for both Stage 2 and Stage 3. The AI CLI processes run with this directory as their current working directory, giving them full access to browse and read any file in the repository.

---

## Stage 2: AI-Powered Planning

With the repository cloned locally, docsfy invokes an AI CLI tool to analyze the codebase and produce a structured documentation plan. This is the "brain" of the pipeline — the AI explores the repository's source code, configuration, tests, and structure to decide what pages the documentation site should contain and how they should be organized.

### AI CLI Invocation

The AI CLI is executed as a subprocess with its working directory set to the cloned repository:

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

For async execution within the FastAPI server, this is wrapped with:

```python
asyncio.to_thread(subprocess.run, ...)
```

The specific command varies by provider:

| Provider | Command |
|----------|---------|
| Claude | `claude --model <model> --dangerously-skip-permissions -p` |
| Gemini | `gemini --model <model> --yolo` |
| Cursor | `agent --force --model <model> --print --workspace <path>` |

> **Tip:** Most providers use the subprocess `cwd` parameter to set the repository path. Cursor is the exception — it accepts a `--workspace` flag instead, and its `ProviderConfig` sets `uses_own_cwd=True` to reflect this difference.

### Provider Configuration

All providers share a common configuration structure:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

The `binary` field identifies the CLI executable, `build_cmd` constructs the full command with model and path arguments, and `uses_own_cwd` indicates whether the provider handles its own working directory (via a flag like `--workspace`) rather than relying on the subprocess `cwd`.

### Availability Check

Before starting a generation, docsfy verifies that the configured AI CLI is available and functional by sending a lightweight prompt (e.g., `"Hi"`). If the CLI is unreachable or returns an error, the generation fails early with a clear error message rather than timing out deep in the pipeline.

### The Planning Prompt

The planner prompt instructs the AI to:

1. Explore the repository's directory structure, source files, configuration, and tests
2. Identify the major components, features, and concepts worth documenting
3. Produce a JSON documentation plan defining pages, sections, and navigation hierarchy

### Output: `plan.json`

The AI's response is parsed to extract a JSON object that defines the entire documentation structure. This file is saved at `/data/projects/{name}/plan.json`.

The `plan.json` contains the page hierarchy, titles, descriptions, and ordering that will drive both content generation (Stage 3) and HTML rendering (Stage 4).

### JSON Response Parsing

Since AI models don't always return clean JSON, docsfy uses a multi-strategy extraction approach to reliably parse the planner's output:

1. **Direct JSON parse** — try `json.loads()` on the raw output
2. **Brace-matching** — find the outermost `{...}` in the response and parse that
3. **Markdown code block extraction** — look for JSON inside ` ```json ` fenced blocks
4. **Regex fallback** — last-resort pattern matching to recover JSON fragments

This layered strategy ensures that even when the AI wraps its JSON response in conversational text or markdown formatting, docsfy can still extract the structured plan.

> **Warning:** If all four parsing strategies fail, the generation request transitions to an `error` status in the database. Check the generation logs via `GET /api/projects/{name}` for diagnostic details.

---

## Stage 3: Concurrent Content Generation

With the documentation plan in hand, docsfy generates the actual content for each page. This stage invokes the AI CLI once per page defined in `plan.json`, with each invocation having full access to the cloned repository to explore source code as needed.

### Page-Level Generation

For each page in the plan, the AI receives:

- The page's title, description, and section outline from `plan.json`
- Instructions to explore the codebase and write comprehensive markdown content
- Guidelines for formatting, code examples, and documentation style

The AI runs with `cwd` set to the cloned repository, so it can read any source file, configuration, or test to produce accurate documentation with real code examples.

### Concurrent Execution

Pages are generated **concurrently** using Python's async capabilities. Since each page generation is an independent operation — every AI invocation gets its own subprocess with its own context — multiple pages can be produced in parallel.

To prevent overwhelming the system, concurrency is controlled via a **semaphore**:

```python
# Conceptual pattern — limit concurrent AI CLI invocations
semaphore = asyncio.Semaphore(max_concurrent)

async def generate_page(page):
    async with semaphore:
        result = await asyncio.to_thread(
            subprocess.run, cmd, input=prompt,
            capture_output=True, text=True
        )
        return result
```

This pattern allows docsfy to generate multiple pages simultaneously while respecting resource limits on the host machine. The semaphore prevents scenarios where dozens of AI CLI processes compete for CPU and memory.

### Return Type

Each AI CLI invocation returns a `tuple[bool, str]` — a success flag and the raw output string. On success, the output contains the markdown content for the page. On failure, the error details are logged.

### Caching

Generated markdown files are cached in the project's filesystem:

```
/data/projects/{project-name}/
  cache/
    pages/
      getting-started.md
      configuration.md
      api-reference.md
      ...
```

This cache serves two purposes:

1. **Incremental updates** — when a repository changes, only affected pages need regeneration. Unchanged pages are served from cache.
2. **Resilience** — if generation is interrupted (e.g., timeout on a single page), previously generated pages are preserved.

### Timeout Handling

Each AI CLI invocation is subject to the `AI_CLI_TIMEOUT` setting, which defaults to **60 minutes**. This generous timeout accommodates large repositories where the AI may need significant time to explore the codebase and produce detailed content.

```bash
# Default configuration
AI_CLI_TIMEOUT=60  # minutes
```

> **Note:** The timeout applies per-page, not to the entire generation. A 10-page site with a 60-minute timeout could theoretically take up to 10 hours if pages are generated sequentially. With concurrent execution, wall-clock time is significantly reduced.

---

## Stage 4: HTML Rendering

The final stage transforms the AI-generated markdown content and the `plan.json` structure into a complete, self-contained static HTML documentation site.

### Rendering Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Templates | Jinja2 | HTML page structure and layout |
| Markdown processing | Python markdown library | Convert `.md` to HTML |
| Syntax highlighting | highlight.js | Code block formatting |
| Search | lunr.js (or similar) | Client-side full-text search |
| Theming | Custom CSS/JS | Dark/light mode, responsive design |

### Features

The rendered site includes production-quality features out of the box:

- **Sidebar navigation** — hierarchical navigation generated from `plan.json`
- **Dark/light theme** — toggleable with user preference persistence
- **Client-side search** — full-text search powered by a pre-built `search-index.json`
- **Syntax highlighting** — automatic language detection for code blocks
- **Card layouts** — visual grouping for related content
- **Callout boxes** — styled note, warning, and info blocks
- **Responsive design** — works on desktop, tablet, and mobile

### Output Structure

The rendered site is written to `/data/projects/{name}/site/`:

```
/data/projects/{project-name}/
  site/
    index.html              # Landing page
    getting-started.html    # Documentation pages...
    configuration.html
    api-reference.html
    assets/
      style.css             # Site stylesheet
      search.js             # Search functionality
      theme-toggle.js       # Dark/light theme toggle
      highlight.js          # Code syntax highlighting
    search-index.json       # Pre-built search index
```

### Search Index Generation

During rendering, docsfy builds a `search-index.json` file that maps page content to their URLs. This index is loaded by the client-side JavaScript search implementation, enabling instant full-text search without a server backend.

### Serving the Output

Once rendering completes, the generated site is available through two channels:

1. **Direct serving** — access pages at `GET /docs/{project}/{path}` via the FastAPI server
2. **Download** — fetch the entire site as a `.tar.gz` archive via `GET /api/projects/{name}/download` for self-hosting on any static file server (Nginx, S3, GitHub Pages, Netlify, etc.)

---

## Incremental Updates

docsfy avoids regenerating entire documentation sites when a repository changes. The incremental update mechanism minimizes AI CLI invocations by intelligently detecting what changed.

### Update Flow

```
Re-generate request arrives
        │
        ▼
Fetch repo, get current commit SHA
        │
        ▼
Compare against stored SHA in SQLite
        │
        ├── Same SHA ──▶ Skip (docs are current)
        │
        ▼ Different SHA
Re-run AI Planner (Stage 2)
        │
        ├── Plan structure unchanged ──▶ Regenerate only affected pages
        │
        ▼ Plan structure changed
Regenerate all pages (full Stage 3 + Stage 4)
```

### How Affected Pages Are Identified

1. docsfy tracks the **last commit SHA** per project in its SQLite database
2. On a re-generate request, the repository is fetched and the current HEAD SHA is compared against the stored value
3. If the SHA differs, the AI Planner runs again to check whether the documentation structure changed
4. If the plan structure is unchanged and only specific source files changed, docsfy regenerates only the pages whose content may reference those files
5. If the plan structure itself changed (new pages, removed pages, reorganized sections), a full regeneration is triggered

> **Tip:** Incremental updates are particularly valuable for large repositories where full generation may involve many AI CLI invocations. By caching page markdown in `/data/projects/{name}/cache/pages/`, docsfy can skip regenerating pages that remain valid after a code change.

---

## Pipeline Configuration Reference

The pipeline's behavior is controlled through environment variables:

```bash
# Which AI provider to use for planning and content generation
AI_PROVIDER=claude          # Options: claude, gemini, cursor

# Which model the AI provider should use
AI_MODEL=claude-opus-4-6[1m]

# Maximum time (in minutes) for each AI CLI invocation
AI_CLI_TIMEOUT=60
```

### Provider-Specific Authentication

Each provider requires its own authentication credentials:

```bash
# Claude - API Key authentication
ANTHROPIC_API_KEY=sk-ant-...

# Claude - Vertex AI authentication (alternative)
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-project

# Gemini
GEMINI_API_KEY=...

# Cursor
CURSOR_API_KEY=...
```

> **Warning:** Never commit API keys to version control. Use the `.env` file (excluded via `.gitignore`) or inject secrets through your deployment platform's secret management.

---

## Pipeline Status Tracking

Throughout all four stages, docsfy tracks the generation status in its SQLite database. The project status transitions through these states:

| Status | Meaning |
|--------|---------|
| `generating` | Pipeline is currently running (any stage) |
| `ready` | All four stages completed successfully; site is available |
| `error` | A stage failed; check logs for details |

Query project status at any time via the API:

```bash
# List all projects and their statuses
curl http://localhost:8000/api/status

# Get detailed info for a specific project
curl http://localhost:8000/api/projects/{name}
```

The `/api/projects/{name}` endpoint returns the last generated timestamp, commit SHA, page list, and any error details — useful for debugging failed generations or confirming that incremental updates completed correctly.
