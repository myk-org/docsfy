# POST /api/generate

Start documentation generation for a GitHub repository. This endpoint accepts a repository URL and initiates an asynchronous four-stage pipeline that clones the repository, plans the documentation structure, generates content using AI, and renders a static HTML site.

## Endpoint

```
POST /api/generate
```

## Request

### Headers

| Header | Value | Required |
|--------|-------|----------|
| `Content-Type` | `application/json` | Yes |

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_url` | `string` | Yes | GitHub repository URL to generate documentation for |

The `repo_url` field accepts both HTTPS and SSH formats:

```json
{
  "repo_url": "https://github.com/user/repo"
}
```

```json
{
  "repo_url": "git@github.com:user/repo.git"
}
```

> **Note:** Private repositories are supported. The service uses system git credentials configured in the container environment for authentication.

### Example Request

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/octocat/Hello-World"}'
```

## Response

### Success Response

**Status Code:** `202 Accepted`

The server acknowledges the request and begins processing in the background. The response includes identifiers you can use to track progress.

```json
{
  "project_name": "Hello-World",
  "status": "generating",
  "repo_url": "https://github.com/octocat/Hello-World"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `project_name` | `string` | Derived project name used to identify the project across all API endpoints |
| `status` | `string` | Initial status of the generation request. Always `generating` on success |
| `repo_url` | `string` | The repository URL as submitted |

### Error Responses

| Status Code | Description |
|-------------|-------------|
| `422 Unprocessable Entity` | Invalid or missing `repo_url` in request body |
| `500 Internal Server Error` | Server-side failure (e.g., AI provider unavailable) |

## Generation Pipeline

Once the request is accepted, docsfy runs a four-stage pipeline asynchronously. The project status in the database tracks overall progress.

```
POST /api/generate
      │
      ▼
┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────┐
│  Clone   │───▶│  AI Planner  │───▶│ AI Content  │───▶│   HTML   │
│  Repo    │    │ (plan.json)  │    │  Generator  │    │ Renderer │
└──────────┘    └──────────────┘    └─────────────┘    └──────────┘
                                                             │
                                                             ▼
                                                     Status: "ready"
                                                     Docs served at
                                                  /docs/{project}/
```

### Stage 1: Clone Repository

A shallow clone (`--depth 1`) of the repository is created in a temporary directory. This minimizes bandwidth and disk usage while providing the full current state of the codebase.

### Stage 2: AI Planner

The configured AI CLI tool analyzes the cloned repository and produces a `plan.json` file defining the documentation structure — pages, sections, and navigation hierarchy.

### Stage 3: AI Content Generator

For each page defined in `plan.json`, the AI CLI generates markdown content. Pages are generated concurrently using semaphore-limited async execution, with the AI able to explore the entire codebase for each page. Generated markdown is cached at:

```
/data/projects/{project-name}/cache/pages/*.md
```

### Stage 4: HTML Renderer

Markdown pages and `plan.json` are converted into a polished static HTML site using Jinja2 templates with bundled CSS and JavaScript. The rendered site includes sidebar navigation, dark/light theme toggle, client-side search (lunr.js), and code syntax highlighting (highlight.js). Output is written to:

```
/data/projects/{project-name}/site/
```

> **Tip:** The AI CLI timeout defaults to 60 minutes (`AI_CLI_TIMEOUT`). For very large repositories, you may need to increase this value in your environment configuration.

## Status Tracking

Documentation generation is asynchronous. Use the following endpoints to monitor progress:

### Poll Project Status

```bash
# List all projects and their statuses
curl http://localhost:8000/api/status
```

### Get Specific Project Details

```bash
# Get details for a specific project
curl http://localhost:8000/api/projects/Hello-World
```

The response includes the current status, last generated timestamp, commit SHA, and page list.

### Status Values

| Status | Description |
|--------|-------------|
| `generating` | Pipeline is currently running. One or more stages are in progress |
| `ready` | Generation completed successfully. Documentation is available for viewing and download |
| `error` | Generation failed. Check logs for details |

### Viewing Generated Documentation

Once the status transitions to `ready`, the generated documentation is served at:

```
GET /docs/{project-name}/
```

```bash
# View generated docs in a browser
open http://localhost:8000/docs/Hello-World/
```

## Incremental Updates (Re-generation)

Calling `POST /api/generate` again with the same repository URL triggers an incremental update rather than a full regeneration:

1. The service fetches the latest state of the repository
2. Compares the current commit SHA against the previously stored SHA
3. If the repository has changed:
   - Re-runs the AI Planner to detect structural changes
   - Regenerates only pages whose content may be affected
4. If the plan structure is unchanged, only the relevant pages are regenerated

```bash
# Trigger incremental update for an existing project
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/octocat/Hello-World"}'
```

> **Note:** Incremental updates reuse cached markdown from `/data/projects/{name}/cache/pages/` to avoid unnecessary AI calls, reducing both generation time and cost.

## AI Provider Configuration

The AI provider used during generation is configured via environment variables. docsfy supports three providers:

| Provider | `AI_PROVIDER` | `AI_MODEL` (default) | Binary |
|----------|---------------|----------------------|--------|
| Claude Code | `claude` | `claude-opus-4-6[1m]` | `claude` |
| Gemini CLI | `gemini` | *(provider default)* | `gemini` |
| Cursor Agent | `cursor` | *(provider default)* | `agent` |

```bash
# .env configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60
```

> **Warning:** The service performs an availability check on the configured AI CLI before starting generation. If the AI provider binary is not installed or not authenticated, the generation will fail. Ensure your provider credentials are configured in the container environment.

### Provider Authentication

Depending on the selected provider, configure the appropriate credentials:

```bash
# Claude via API Key
ANTHROPIC_API_KEY=sk-ant-...

# Claude via Vertex AI
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-project

# Gemini
GEMINI_API_KEY=...

# Cursor
CURSOR_API_KEY=...
```

## Complete Workflow Example

```bash
# 1. Start generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/octocat/Hello-World"}'
# Response: {"project_name": "Hello-World", "status": "generating", ...}

# 2. Poll for completion
curl http://localhost:8000/api/projects/Hello-World
# Response: {"status": "generating", ...}  (still processing)
# Response: {"status": "ready", ...}       (done!)

# 3. View the generated documentation
open http://localhost:8000/docs/Hello-World/

# 4. Or download the static site for self-hosting
curl -O http://localhost:8000/api/projects/Hello-World/download
# Downloads: Hello-World.tar.gz
```

## Storage

Each generated project is stored both in the SQLite database (metadata) and on the filesystem (content):

```
/data/docsfy.db                          # SQLite: project metadata and status
/data/projects/{project-name}/
  plan.json                              # Documentation structure from AI Planner
  cache/
    pages/*.md                           # Cached AI-generated markdown
  site/                                  # Rendered static HTML site
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

## Related Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details, commit SHA, and page list |
| `DELETE` | `/api/projects/{name}` | Remove a project and all generated docs |
| `GET` | `/api/projects/{name}/download` | Download the site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve the generated static HTML documentation |
| `GET` | `/health` | Health check |
