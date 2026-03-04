# Generating Documentation

docsfy generates polished, static HTML documentation sites from GitHub repositories using AI. This page covers how to submit a repository for documentation generation, monitor progress, and understand the pipeline that transforms your codebase into a documentation site.

## Submitting a Repository

To generate documentation for a repository, send a `POST` request to the `/api/generate` endpoint with the repository URL.

### Request

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo"}'
```

The endpoint accepts both HTTPS and SSH repository URLs:

```bash
# HTTPS (public or private)
{"repo_url": "https://github.com/your-org/your-repo"}

# SSH (requires system git credentials)
{"repo_url": "git@github.com:your-org/your-repo.git"}
```

> **Note:** Private repositories are supported. docsfy uses system git credentials configured in the container for authentication. See the [deployment configuration](#private-repository-access) section for setting up credentials.

### Response

A successful request returns the project status with generation details:

```json
{
  "name": "your-repo",
  "repo_url": "https://github.com/your-org/your-repo",
  "status": "generating"
}
```

The `status` field will be `generating` while the pipeline is running. Once complete, it transitions to `ready` or `error`.

### Re-generating Documentation

Submitting the same repository URL again triggers an **incremental update**. docsfy tracks the last commit SHA per project and only regenerates what changed:

1. The repository is fetched and the current commit SHA is compared against the stored SHA
2. If the commit has changed, the AI Planner re-evaluates whether the documentation structure needs updating
3. Only pages affected by code changes are regenerated
4. If the plan structure is unchanged, only relevant pages are rebuilt

This makes re-generation significantly faster than a full build.

```bash
# Re-generate after pushing new commits
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo"}'
```

## Monitoring Generation Status

### List All Projects

Use `GET /api/status` to see all projects and their current generation state:

```bash
curl http://localhost:8000/api/status
```

Each project reports one of three statuses:

| Status | Description |
|--------|-------------|
| `generating` | The pipeline is actively running |
| `ready` | Documentation has been generated successfully and is available to view |
| `error` | Generation failed; check project details for logs |

### Get Project Details

For detailed information about a specific project, use `GET /api/projects/{name}`:

```bash
curl http://localhost:8000/api/projects/your-repo
```

This returns extended metadata including:

- Last generated timestamp
- Last commit SHA processed
- List of generated pages
- Generation history and logs

### Polling for Completion

Since generation is asynchronous, poll the status endpoint to detect when documentation is ready:

```bash
#!/bin/bash
PROJECT="your-repo"

while true; do
  STATUS=$(curl -s "http://localhost:8000/api/projects/$PROJECT" | jq -r '.status')
  
  case "$STATUS" in
    "ready")
      echo "Documentation is ready!"
      echo "View at: http://localhost:8000/docs/$PROJECT/"
      break
      ;;
    "error")
      echo "Generation failed. Check project details for logs."
      break
      ;;
    "generating")
      echo "Still generating..."
      sleep 30
      ;;
  esac
done
```

> **Tip:** Generation time varies depending on repository size and the AI provider used. The default `AI_CLI_TIMEOUT` is 60 minutes, which covers most repositories.

## The Four-Stage Pipeline

Every generation request passes through four sequential stages. Understanding these stages helps with debugging failures and tuning performance.

```
POST /api/generate
       |
       v
  +---------+     +--------------+     +------------+     +----------+
  |  Clone  | --> |  AI Planner  | --> | AI Content | --> |   HTML   |
  |  Repo   |     |  (plan.json) |     | Generator  |     | Renderer |
  +---------+     +--------------+     +------------+     +----------+
                                                                |
                                                                v
                                                          Static site
                                                     /data/projects/{name}/site/
```

### Stage 1: Clone Repository

The first stage creates a shallow clone of the target repository.

- Performs a `git clone --depth 1` to a temporary directory, downloading only the latest commit
- Supports both SSH and HTTPS URLs
- Uses system git credentials for private repository access

A shallow clone minimizes bandwidth and disk usage since docsfy only needs the current state of the codebase to generate documentation.

> **Warning:** If the clone fails (invalid URL, authentication error, network issue), the entire pipeline aborts and the project status is set to `error`.

### Stage 2: AI Planner

The planner stage analyzes the entire repository to design the documentation structure.

The AI CLI is invoked with its working directory set to the cloned repository, giving the AI full access to explore every file. It receives a prompt instructing it to analyze the codebase and produce a documentation plan.

**Output:** A `plan.json` file containing the page hierarchy, sections, and navigation structure:

```
/data/projects/{project-name}/
  plan.json             # Documentation structure from AI
```

The plan defines what pages to create, how they relate to each other, and how the sidebar navigation should be organized. This plan drives Stage 3.

The AI CLI invocation follows the provider pattern defined in the codebase:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

Prompts are passed to the AI CLI via stdin:

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

For async execution, this is wrapped with:

```python
asyncio.to_thread(subprocess.run, ...)
```

> **Note:** Before starting generation, docsfy performs an availability check by sending a lightweight "Hi" prompt to the configured AI provider. This fails fast if the provider is misconfigured or unreachable.

### Stage 3: AI Content Generator

With the plan established, this stage generates the actual documentation content for each page.

For every page defined in `plan.json`, the AI CLI is invoked again with the cloned repository as its working directory. The AI explores the codebase as needed to write accurate, detailed documentation for each page's topic.

Key characteristics:

- **Concurrent generation** — Pages are generated in parallel using async execution with semaphore-limited concurrency, preventing resource exhaustion while maximizing throughput
- **Per-page caching** — Each generated page is cached as a Markdown file for use in incremental updates

**Output:** Markdown files cached in the project directory:

```
/data/projects/{project-name}/
  cache/
    pages/*.md          # AI-generated markdown per page
```

#### JSON Response Parsing

AI CLI output containing JSON (such as structured content) is extracted using a multi-strategy parser:

1. **Direct JSON parse** — Attempt to parse the entire output as JSON
2. **Brace-matching** — Find the outermost JSON object by matching braces
3. **Markdown code block extraction** — Extract JSON from fenced code blocks
4. **Regex recovery** — Fallback pattern matching for malformed output

This layered approach ensures reliable JSON extraction regardless of how different AI providers format their responses.

### Stage 4: HTML Renderer

The final stage converts the Markdown content and `plan.json` navigation structure into a polished static HTML site.

The renderer uses **Jinja2 templates** with bundled CSS and JavaScript assets to produce a site with:

- Sidebar navigation (derived from `plan.json`)
- Dark and light theme toggle
- Client-side search (powered by lunr.js)
- Code syntax highlighting (powered by highlight.js)
- Card layouts and callout boxes (note, warning, info)
- Responsive design for mobile and desktop

**Output:** A complete static site:

```
/data/projects/{project-name}/
  site/
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

Once rendering completes, the project status is set to `ready` and the site is immediately available at `GET /docs/{project}/{path}`.

## Accessing Generated Documentation

### Browse Online

Once generation completes, documentation is served directly by docsfy:

```
http://localhost:8000/docs/your-repo/
```

### Download for Self-Hosting

To download the generated site as a `.tar.gz` archive for hosting elsewhere:

```bash
curl -O http://localhost:8000/api/projects/your-repo/download
```

The archive contains the complete static site from `/data/projects/{name}/site/` — extract it and serve with any static file server (Nginx, Apache, GitHub Pages, S3, etc.).

### Remove a Project

To delete a project and all its generated documentation:

```bash
curl -X DELETE http://localhost:8000/api/projects/your-repo
```

> **Warning:** This permanently removes the project metadata from the database and all generated files from disk. This action cannot be undone.

## Configuration

### AI Provider Settings

Generation behavior is controlled through environment variables. Configure these in your `.env` file or pass them directly to the container.

```bash
# AI Configuration
AI_PROVIDER=claude          # Options: claude, gemini, cursor
AI_MODEL=claude-opus-4-6[1m]  # Model to use for the configured provider
AI_CLI_TIMEOUT=60           # Timeout in minutes per AI CLI invocation
```

The following providers and their CLI commands are supported:

| Provider | Binary | Command Pattern | CWD Handling |
|----------|--------|-----------------|--------------|
| Claude | `claude` | `claude --model <model> --dangerously-skip-permissions -p` | subprocess `cwd` set to repo path |
| Gemini | `gemini` | `gemini --model <model> --yolo` | subprocess `cwd` set to repo path |
| Cursor | `agent` | `agent --force --model <model> --print --workspace <path>` | Uses `--workspace` flag |

### Provider Authentication

Each AI provider requires its own authentication credentials:

```bash
# Claude - Option 1: Direct API Key
ANTHROPIC_API_KEY=sk-ant-...

# Claude - Option 2: Google Cloud Vertex AI
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project

# Gemini
GEMINI_API_KEY=...

# Cursor
CURSOR_API_KEY=...
```

> **Tip:** Only configure credentials for the provider specified in `AI_PROVIDER`. Unused provider credentials are ignored.

### Private Repository Access

For private repositories, mount your git credentials into the container. The `docker-compose.yaml` includes volume mounts for common credential locations:

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

For SSH-based git access, mount your SSH keys into the container and ensure they are readable by the `appuser` user.

### Storage

All generated data is persisted under the `/data` volume:

| Path | Purpose |
|------|---------|
| `/data/docsfy.db` | SQLite database storing project metadata, status, commit SHAs, and generation history |
| `/data/projects/{name}/plan.json` | Documentation structure from the AI Planner |
| `/data/projects/{name}/cache/pages/*.md` | Cached Markdown files for incremental updates |
| `/data/projects/{name}/site/` | Final rendered HTML site |

> **Note:** Mount `/data` as a persistent volume to retain generated documentation across container restarts.

## Health Check

Verify the service is running and ready to accept requests:

```bash
curl http://localhost:8000/health
```

The Docker health check is preconfigured to probe this endpoint every 30 seconds with a 10-second timeout and 3 retries.

## Troubleshooting

### Generation stuck in `generating` status

The AI CLI has a configurable timeout (default: 60 minutes). For very large repositories, increase `AI_CLI_TIMEOUT`:

```bash
AI_CLI_TIMEOUT=120  # 2 hours
```

### Generation fails immediately

Check that the configured AI provider is available by verifying:

1. The AI CLI binary is installed in the container (`claude`, `gemini`, or `agent`)
2. The correct authentication credentials are set
3. The provider service is reachable from the container

docsfy performs an availability check before starting the pipeline — review the project details (`GET /api/projects/{name}`) for error logs.

### Clone failures

- Verify the repository URL is correct and accessible
- For private repos, ensure git credentials are properly mounted
- For SSH URLs, confirm SSH keys are available to the `appuser` inside the container
