# Generation Pipeline

The docsfy generation pipeline transforms a GitHub repository URL into a polished static HTML documentation site through four sequential stages. Each stage builds on the output of the previous one, progressing from raw source code to a fully rendered, searchable documentation website.

```
POST /api/generate { "repo_url": "..." }
         │
         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Stage 1: Clone │────▶│  Stage 2: Plan  │────▶│  Stage 3: Gen   │────▶│  Stage 4: Render │
│  Repository     │     │  (AI Planner)   │     │  (AI Content)   │     │  (Jinja2 + HTML) │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
     git clone            plan.json              cache/pages/*.md        site/*.html
     --depth 1            (doc structure)        (markdown per page)     (static site)
```

## Overview

When a user submits a repository URL via `POST /api/generate`, the pipeline executes these four stages sequentially:

| Stage | Input | Process | Output |
|-------|-------|---------|--------|
| **1. Clone** | GitHub repo URL | Shallow git clone | Temporary directory with source code |
| **2. Plan** | Cloned repository | AI analyzes codebase structure | `plan.json` (documentation hierarchy) |
| **3. Generate** | `plan.json` + cloned repo | AI writes content per page (concurrent) | Markdown files in `cache/pages/*.md` |
| **4. Render** | Markdown files + `plan.json` | Jinja2 templating + asset bundling | Static HTML site in `site/` |

The pipeline status is tracked in SQLite throughout execution, transitioning from `generating` to either `ready` or `error` upon completion.

---

## Stage 1: Repository Cloning

The first stage acquires the source code that will be documented. docsfy performs a **shallow clone** to minimize bandwidth and disk usage — only the latest commit is needed since documentation reflects the current state of the codebase.

### How It Works

```
Input:  GitHub repository URL (SSH or HTTPS)
Output: Temporary directory containing the cloned repository
```

The clone operation uses `--depth 1` to fetch only the most recent commit:

```bash
git clone --depth 1 <repo_url> <temp_directory>
```

### Supported URL Formats

Both SSH and HTTPS URLs are supported for public and private repositories:

| Format | Example | Authentication |
|--------|---------|---------------|
| HTTPS (public) | `https://github.com/org/repo.git` | None required |
| HTTPS (private) | `https://github.com/org/repo.git` | System git credentials |
| SSH | `git@github.com:org/repo.git` | SSH keys configured on host |

Private repository access relies on the git credentials available in the container environment. When running via Docker, SSH keys or credential helpers must be mounted into the container.

### Execution Model

The clone runs asynchronously using `asyncio.to_thread` to avoid blocking the FastAPI event loop:

```python
asyncio.to_thread(subprocess.run, ["git", "clone", "--depth", "1", repo_url, temp_dir], ...)
```

> **Note:** The cloned repository is stored in a temporary directory for the duration of the pipeline. After all stages complete, this temporary directory can be cleaned up. For incremental updates, docsfy tracks the last commit SHA in SQLite to determine if regeneration is needed.

---

## Stage 2: AI-Driven Planning

The planning stage is where AI analyzes the entire repository and produces a structured documentation plan. This is the architectural blueprint that determines what pages will be generated, how they're organized, and what the navigation hierarchy looks like.

### How It Works

```
Input:  Cloned repository directory
Output: plan.json (documentation structure with pages, sections, and navigation)
```

The AI CLI is invoked with its **working directory set to the cloned repository**, giving it full access to explore every file, read source code, examine configuration, and understand the project's architecture.

### AI Provider Configuration

docsfy supports three AI providers, each configured through the `ProviderConfig` dataclass:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

The `uses_own_cwd` flag controls how the repository path is communicated to the AI CLI:

- **`False` (default):** The subprocess `cwd` is set to the repository path. Used by Claude and Gemini.
- **`True`:** The repository path is passed via a CLI flag (e.g., `--workspace`). Used by Cursor.

### Provider Commands

Each provider has a specific invocation pattern:

| Provider | Binary | Command | CWD Handling |
|----------|--------|---------|-------------|
| Claude (default) | `claude` | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| Gemini | `gemini` | `gemini --model <model> --yolo` | subprocess `cwd` = repo path |
| Cursor | `agent` | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag, `uses_own_cwd=True` |

### Invocation Pattern

Prompts are passed to the AI CLI via stdin, and the response is captured from stdout:

```python
asyncio.to_thread(
    subprocess.run,
    cmd,
    input=prompt,
    capture_output=True,
    text=True
)
# Returns: tuple[bool, str] (success, output)
```

> **Tip:** Before starting a full generation, docsfy performs an availability check by sending a lightweight `"Hi"` prompt to verify the AI CLI is properly configured and responding. This catches authentication or configuration issues early, before committing to the full pipeline.

### JSON Response Parsing

AI models don't always return clean JSON. docsfy uses a multi-strategy extraction approach (with a cascading fallback chain) to reliably extract the `plan.json` structure from the AI response:

1. **Direct JSON parse** — Try `json.loads()` on the raw output
2. **Brace-matching** — Find the outermost `{...}` JSON object in the response
3. **Markdown code block extraction** — Extract JSON from triple-backtick code blocks
4. **Regex recovery** — Last-resort pattern matching to salvage JSON fragments

```
AI Response                          Extraction Strategy
─────────────────────────────────    ─────────────────────
'{"pages": [...]}'               →  Strategy 1: Direct parse ✓
'Here is the plan: {"pages":..}' →  Strategy 2: Brace-matching ✓
'```json\n{"pages": [...]}\n```' →  Strategy 3: Code block extraction ✓
'The plan has {"pages":[...'     →  Strategy 4: Regex recovery ✓
```

### The plan.json Output

The planner produces a `plan.json` file that defines the complete documentation structure. This file is saved at `/data/projects/{project-name}/plan.json` and serves as the contract between the planning and generation stages. It contains:

- **Pages** — Individual documentation pages with titles and descriptions
- **Sections** — Logical groupings of related pages
- **Navigation hierarchy** — The sidebar structure and page ordering

### Default Configuration

| Setting | Default Value | Description |
|---------|--------------|-------------|
| `AI_PROVIDER` | `claude` | Which AI CLI to use |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the CLI |
| `AI_CLI_TIMEOUT` | `60` (minutes) | Maximum time for a single AI invocation |

These are configured via environment variables:

```bash
# .env
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60
```

> **Warning:** The `--dangerously-skip-permissions` flag (Claude) and `--yolo` flag (Gemini) grant the AI CLI unrestricted access within the cloned repository. This is intentional — the AI needs to freely explore the codebase to produce accurate documentation. The clone is performed in an isolated temporary directory to limit the blast radius.

---

## Stage 3: Concurrent Content Generation

The content generation stage is where the bulk of the work happens. For each page defined in `plan.json`, an AI CLI session explores the codebase and writes comprehensive markdown documentation.

### How It Works

```
Input:  plan.json (page definitions) + cloned repository
Output: Markdown files at /data/projects/{name}/cache/pages/*.md
```

### Concurrency Model

Pages are generated **concurrently** using Python's async capabilities with semaphore-limited concurrency. This dramatically reduces total generation time for projects with many documentation pages:

```python
# Conceptual model:
# Each page generation is an independent async task
# A semaphore limits how many AI CLI processes run simultaneously

async with semaphore:
    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        input=page_prompt,
        capture_output=True,
        text=True
    )
```

```
                    plan.json
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Page 1   │ │ Page 2   │ │ Page 3   │  ... (concurrent, semaphore-limited)
    │ AI CLI   │ │ AI CLI   │ │ AI CLI   │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         ▼            ▼            ▼
    page-1.md    page-2.md    page-3.md
```

Each AI CLI invocation runs with `cwd` set to the cloned repository (or `--workspace` for Cursor), giving the AI full access to explore the codebase as needed for that specific page. The AI receives a prompt that includes the page title, description, and any context from the plan about what the page should cover.

### Caching Strategy

Generated markdown files are cached at:

```
/data/projects/{project-name}/cache/pages/*.md
```

This cache serves two purposes:

1. **Resilience** — If the pipeline fails partway through, already-generated pages don't need to be regenerated
2. **Incremental updates** — When a repository changes, only affected pages need regeneration (see [Incremental Updates](#incremental-updates) below)

### Output Format

Each page is generated as a standalone markdown file containing:

- Prose explanations of concepts and architecture
- Code examples drawn from the actual repository
- Configuration snippets and usage instructions
- Cross-references to other documentation pages

> **Note:** The AI has full access to explore the repository for each page it generates. This means it can read source files, examine tests, check configuration, and follow import chains to produce accurate, codebase-specific documentation — not generic boilerplate.

---

## Stage 4: HTML Rendering with Jinja2

The final stage transforms raw markdown into a polished, interactive static HTML documentation site. This is a deterministic process — no AI is involved — that uses Jinja2 templates and bundled front-end assets.

### How It Works

```
Input:  Markdown pages (cache/pages/*.md) + plan.json + CSS/JS assets
Output: Static HTML site at /data/projects/{name}/site/
```

### Rendering Pipeline

The renderer performs these operations:

1. **Markdown-to-HTML conversion** — Using the Python `markdown` library
2. **Template rendering** — Jinja2 templates wrap HTML content with navigation, headers, and layout
3. **Asset bundling** — CSS, JavaScript, and other static assets are copied to the output directory
4. **Search index generation** — A JSON search index is built for client-side full-text search

### Site Features

The rendered HTML site includes a rich set of features out of the box:

| Feature | Implementation |
|---------|---------------|
| Sidebar navigation | Generated from `plan.json` hierarchy |
| Dark/light theme toggle | `theme-toggle.js` |
| Client-side search | `search.js` + `search-index.json` (lunr.js or similar) |
| Code syntax highlighting | `highlight.js` |
| Responsive design | Custom CSS |
| Card layouts | CSS component styles |
| Callout boxes | Note, warning, and info styled blocks |

### Output Structure

The final static site follows this directory layout:

```
/data/projects/{project-name}/site/
  index.html              # Landing page
  *.html                  # Generated documentation pages
  assets/
    style.css             # Bundled stylesheet
    search.js             # Client-side search functionality
    theme-toggle.js       # Dark/light mode toggle
    highlight.js          # Code syntax highlighting
  search-index.json       # Pre-built search index
```

### Serving and Distribution

Once rendered, the static site can be accessed in two ways:

1. **Served directly** via docsfy's built-in route:
   ```
   GET /docs/{project}/{path}
   ```

2. **Downloaded** as a `.tar.gz` archive for self-hosting:
   ```
   GET /api/projects/{name}/download
   ```

> **Tip:** The downloaded archive is a fully self-contained static site. You can host it on any static file server — GitHub Pages, Netlify, S3, nginx, or any CDN — with no docsfy dependency required.

---

## Incremental Updates

docsfy avoids regenerating documentation from scratch when a repository changes. The incremental update strategy minimizes AI usage and generation time:

1. **SHA tracking** — The last commit SHA is stored per project in SQLite
2. **Change detection** — On re-generate, the repository is fetched and the current SHA is compared against the stored SHA
3. **Plan comparison** — If the SHA has changed, the AI Planner re-runs to check if the documentation structure changed
4. **Selective regeneration** — Only pages whose content may be affected by the changes are regenerated
5. **Cache reuse** — Unaffected pages are served directly from `cache/pages/*.md`

```
Re-generate Request
       │
       ▼
  Compare SHA ──── Same? ──── No regeneration needed
       │
    Different
       │
       ▼
  Re-run Planner
       │
       ├── Plan unchanged ──── Regenerate only affected pages
       │
       └── Plan changed ──── Regenerate all pages
```

> **Note:** The incremental update strategy relies on the AI Planner's ability to determine which pages are affected by code changes. For significant architectural changes to a repository, a full regeneration may still be triggered.

---

## Pipeline Configuration Reference

All pipeline behavior is controlled through environment variables:

```bash
# .env

# AI Provider Selection
AI_PROVIDER=claude                    # Options: claude, gemini, cursor
AI_MODEL=claude-opus-4-6[1m]         # Model identifier
AI_CLI_TIMEOUT=60                     # Timeout per AI invocation (minutes)

# Claude Authentication (Option 1: API Key)
ANTHROPIC_API_KEY=sk-ant-...

# Claude Authentication (Option 2: Vertex AI)
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-project

# Gemini Authentication
GEMINI_API_KEY=...

# Cursor Authentication
CURSOR_API_KEY=...

# Logging
LOG_LEVEL=INFO
```

### Storage Paths

| Path | Purpose |
|------|---------|
| `/data/docsfy.db` | SQLite database for project metadata and status |
| `/data/projects/{name}/plan.json` | Documentation structure from AI Planner |
| `/data/projects/{name}/cache/pages/*.md` | Cached AI-generated markdown |
| `/data/projects/{name}/site/` | Final rendered static HTML site |

---

## Error Handling

If any stage in the pipeline fails, the project status in SQLite is set to `error` and the failure is logged. The pipeline does not automatically retry — the user must re-trigger generation via `POST /api/generate`.

Key failure modes by stage:

| Stage | Common Failures | Effect |
|-------|----------------|--------|
| Clone | Invalid URL, auth failure, network timeout | Pipeline aborts before AI invocation |
| Plan | AI CLI unavailable, timeout, unparseable response | No `plan.json` produced |
| Generate | Individual page timeout, AI error | Partial cache (successful pages preserved) |
| Render | Template error, disk full | No `site/` directory produced |

> **Tip:** Use the availability check (lightweight `"Hi"` prompt) before starting a full generation to catch AI CLI configuration issues early. This prevents wasting time on a clone operation only to discover the AI provider is not accessible.
