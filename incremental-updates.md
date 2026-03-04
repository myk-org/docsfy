# Incremental Updates

docsfy avoids redundant, full-site regeneration by tracking repository state and intelligently determining which documentation pages need to be rebuilt. This page explains the three-phase incremental update mechanism: **change detection** via commit SHA tracking, **plan re-evaluation** via the AI Planner, and **selective page regeneration**.

## Overview

When a regeneration request is made for an existing project, docsfy does not blindly rebuild every page from scratch. Instead, it follows a pipeline that minimizes AI CLI invocations — the most expensive operation in the system — by comparing the current repository state against what was previously generated.

```
Re-generate request
       │
       ▼
┌──────────────┐     SHA match?     ┌──────────────────┐
│  Fetch repo  │────────────────────│  No changes —    │
│  Compare SHA │    yes             │  skip generation  │
└──────┬───────┘                    └──────────────────┘
       │ no
       ▼
┌──────────────┐    plan unchanged?  ┌──────────────────┐
│  Re-run AI   │─────────────────────│  Regenerate only │
│  Planner     │    yes              │  affected pages  │
└──────┬───────┘                     └──────────────────┘
       │ plan changed
       ▼
┌──────────────────┐
│  Full content    │
│  regeneration    │
└──────────────────┘
```

## Phase 1: Change Detection via Commit SHA Tracking

Every time docsfy generates documentation for a project, it records the **commit SHA** of the repository at the time of generation. This SHA is stored in the SQLite database alongside other project metadata.

### How SHAs Are Stored

Project metadata — including the last commit SHA — lives in the SQLite database at `/data/docsfy.db`:

```
/data/docsfy.db
  └── projects table
        ├── project name
        ├── repo URL
        ├── status (generating / ready / error)
        ├── last generated timestamp
        ├── last commit SHA          ◄── used for change detection
        └── generation history / logs
```

When a `POST /api/generate` request is made for a project that has already been generated, docsfy performs a shallow clone of the repository and compares the current `HEAD` SHA against the stored SHA:

```bash
# docsfy performs a shallow clone to minimize bandwidth
git clone --depth 1 <repo-url> <temp-dir>

# The HEAD SHA of the fresh clone is compared to the stored value
git -C <temp-dir> rev-parse HEAD
```

If the SHAs match, the repository has not changed since the last generation, and docsfy can skip the entire pipeline.

> **Note:** docsfy uses `--depth 1` shallow clones, so only the latest commit is fetched. This keeps clone operations fast while still providing the current SHA and full repository tree for AI analysis.

### Checking Project State via the API

You can inspect a project's current commit SHA and generation status through the API:

```
GET /api/projects/{name}
```

The response includes the last commit SHA and timestamp, allowing external systems (CI/CD pipelines, cron jobs) to make informed decisions about when to trigger regeneration.

## Phase 2: Plan Re-evaluation

When the commit SHA has changed, docsfy re-runs the **AI Planner** stage to determine whether the documentation structure itself needs to change.

### What the AI Planner Produces

The AI Planner analyzes the repository and outputs a `plan.json` file that defines the documentation structure — pages, sections, and navigation hierarchy:

```
/data/projects/{project-name}/
  plan.json             # doc structure from AI
  cache/
    pages/*.md          # AI-generated markdown
  site/                 # final rendered HTML
```

The AI CLI runs with its working directory set to the cloned repository, giving it full access to explore the codebase:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

| Provider | Command | CWD Handling |
|----------|---------|--------------|
| Claude | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` = repo path |
| Gemini | `gemini --model <model> --yolo` | subprocess `cwd` = repo path |
| Cursor | `agent --force --model <model> --print --workspace <path>` | `--workspace` flag |

### Comparing Plans

After the AI Planner produces a new `plan.json`, docsfy compares it against the previously stored plan. This comparison determines the scope of content regeneration:

- **Plan unchanged** — The documentation structure (pages, sections, hierarchy) is the same. Only pages affected by the code changes need regeneration.
- **Plan changed** — New pages were added, pages were removed, or the navigation hierarchy changed. A broader regeneration is required to reflect the structural changes.

> **Tip:** Keeping your repository's high-level structure stable (e.g., not frequently renaming core modules or reorganizing directory layouts) helps docsfy classify more updates as plan-unchanged, resulting in faster incremental regeneration.

## Phase 3: Selective Page Regeneration

This is where the efficiency gains are realized. Rather than regenerating every page in the documentation site, docsfy identifies which pages are affected by the repository changes and regenerates only those.

### Page Caching

Generated markdown content for each page is cached on the filesystem:

```
/data/projects/{project-name}/
  cache/
    pages/
      getting-started.md
      configuration.md
      api-reference.md
      deployment.md
      ...
```

These cached markdown files serve as the baseline. During an incremental update, pages that are **not** affected by the changes are served directly from cache, skipping the expensive AI content generation step.

### How Affected Pages Are Determined

When the plan structure is unchanged and only specific files in the repository have changed, docsfy regenerates only the relevant pages. The AI Content Generator is invoked per page — each invocation runs with `cwd` set to the cloned repository so the AI can explore the codebase as needed to produce accurate content for that specific page.

Pages can be generated concurrently using async execution with semaphore-limited concurrency:

```python
# AI CLI invocation runs in a thread pool for async compatibility
# Returns tuple[bool, str] — (success, output)
await asyncio.to_thread(subprocess.run, cmd, input=prompt, capture_output=True, text=True)
```

> **Warning:** Each page generation invokes an AI CLI subprocess. The `AI_CLI_TIMEOUT` setting (default: 60 minutes) applies per invocation. For large documentation sites, ensure your timeout is sufficient for the most complex page.

### What Triggers a Full Regeneration

Certain changes will cause docsfy to regenerate all pages rather than a subset:

| Scenario | Regeneration Scope |
|----------|--------------------|
| No SHA change | None (skipped entirely) |
| SHA changed, plan unchanged, localized file changes | Affected pages only |
| SHA changed, plan structure changed | All pages |
| First-time generation | All pages |
| Project deleted and re-created | All pages |

## Putting It All Together

The full incremental update flow integrates with the four-stage generation pipeline:

1. **Clone Repository** — Shallow clone (`--depth 1`) to a temporary directory. Compare the `HEAD` SHA against the stored SHA in SQLite.
2. **AI Planner** — If the SHA changed, re-run the AI Planner. Compare the new `plan.json` against the cached plan to determine scope.
3. **AI Content Generator** — Generate markdown only for affected pages. Unaffected pages are read from `/data/projects/{name}/cache/pages/*.md`.
4. **HTML Renderer** — Render the full site using Jinja2 templates. Even if only some pages changed, the complete static site is rebuilt from the combined set of cached and freshly generated markdown to ensure consistent navigation, search indexing, and cross-page links.

> **Note:** The HTML rendering step (Stage 4) always runs for the full site, even during incremental updates. This ensures the sidebar navigation, search index (`search-index.json`), and inter-page links remain consistent. HTML rendering is fast compared to AI content generation, so this has minimal impact on update times.

## Configuration

Incremental update behavior is controlled through environment variables and the project's stored state. There are no separate configuration options for the incremental logic itself — it is always active.

```bash
# .env — relevant settings for incremental updates

# AI provider used for both planning and content generation
AI_PROVIDER=claude

# Model used for plan evaluation and content generation
AI_MODEL=claude-opus-4-6[1m]

# Timeout per AI CLI invocation (in minutes)
# Applies to both the Planner and per-page Content Generator calls
AI_CLI_TIMEOUT=60
```

### Triggering Regeneration

To trigger an incremental update for an existing project, send the same `POST /api/generate` request with the repository URL:

```
POST /api/generate
```

docsfy automatically detects that the project already exists, performs SHA comparison, and follows the incremental update path. No special flags or parameters are needed.

To force a clean regeneration, delete the project first:

```
DELETE /api/projects/{name}
```

Then issue a new `POST /api/generate` request. This clears all cached plans and pages, forcing a full generation from scratch.

## Monitoring Updates

Use the status and project detail endpoints to monitor incremental update progress:

```
# List all projects and their current status
GET /api/status

# Get details for a specific project, including last commit SHA
GET /api/projects/{name}
```

The project status field reflects the current state:

| Status | Meaning |
|--------|---------|
| `generating` | An update (full or incremental) is in progress |
| `ready` | Documentation is up to date and available |
| `error` | The last generation attempt failed |

> **Tip:** Integrate the `/api/status` endpoint with your CI/CD pipeline to automatically trigger documentation regeneration after deployments. Compare the returned commit SHA against your deployment SHA to decide whether an update is needed before sending a `POST /api/generate` request.
