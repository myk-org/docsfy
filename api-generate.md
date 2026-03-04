# POST /api/generate

Start documentation generation for a GitHub repository. This endpoint accepts a repository URL, clones the repository, and runs the full AI-powered generation pipeline to produce a polished static documentation site.

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
| `repo_url` | `string` | Yes | GitHub repository URL (HTTPS or SSH format) |

### Supported Repository URL Formats

docsfy supports both HTTPS and SSH URL formats for public and private repositories.

**HTTPS URLs:**

```json
{
  "repo_url": "https://github.com/owner/repo-name"
}
```

**SSH URLs:**

```json
{
  "repo_url": "git@github.com:owner/repo-name.git"
}
```

> **Note:** Private repositories require valid git credentials configured on the host system. When running in Docker, mount your SSH keys or configure credential helpers in the container. See [Container and Deployment](#authentication-for-private-repositories) for details.

## Response

### Success Response

**Status:** `200 OK`

The endpoint returns the project name and its current generation status. Generation runs asynchronously through a four-stage pipeline in the background.

```json
{
  "project": "repo-name",
  "status": "generating",
  "repo_url": "https://github.com/owner/repo-name"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `project` | `string` | Derived project name used to identify the generated docs |
| `status` | `string` | Current generation status: `generating`, `ready`, or `error` |
| `repo_url` | `string` | The repository URL as submitted |

### Error Responses

| Status Code | Description |
|-------------|-------------|
| `422` | Invalid or missing `repo_url` in request body |
| `500` | Internal server error (clone failure, AI CLI unavailable, etc.) |

## Generation Pipeline

When a request is accepted, the generation pipeline runs four sequential stages:

```
Clone Repository → AI Planner → AI Content Generator → HTML Renderer
```

### Stage 1: Clone Repository

The repository is shallow-cloned (`--depth 1`) to a temporary directory. This minimizes bandwidth and disk usage while still providing the AI with full access to the current state of the codebase.

### Stage 2: AI Planner

The configured AI CLI analyzes the repository and produces a `plan.json` file containing the documentation structure — pages, sections, and navigation hierarchy.

### Stage 3: AI Content Generator

For each page defined in `plan.json`, the AI CLI explores the codebase and generates markdown content. Pages are generated concurrently using async execution with semaphore-limited concurrency. Output is cached at:

```
/data/projects/{project-name}/cache/pages/*.md
```

### Stage 4: HTML Renderer

Markdown pages and `plan.json` are converted into a polished static HTML site using Jinja2 templates with bundled CSS/JS assets. The rendered site includes sidebar navigation, dark/light theme toggle, client-side search, code syntax highlighting, and responsive design. Output is written to:

```
/data/projects/{project-name}/site/
```

> **Tip:** Once generation completes with status `ready`, the docs are immediately available at `GET /docs/{project}/` or can be downloaded as a `.tar.gz` archive via `GET /api/projects/{project}/download`.

## Tracking Generation Status

Generation runs asynchronously. Poll the status endpoint to check progress:

```bash
curl http://localhost:8000/api/status
```

Or check a specific project:

```bash
curl http://localhost:8000/api/projects/repo-name
```

Project status transitions follow this lifecycle:

```
generating → ready
generating → error
```

| Status | Description |
|--------|-------------|
| `generating` | Pipeline is currently running |
| `ready` | Generation completed successfully; docs are served |
| `error` | Generation failed; check project details for error logs |

## Incremental Updates

Calling `POST /api/generate` for a repository that has already been generated triggers an incremental update:

1. The current commit SHA is compared against the stored SHA from the previous generation
2. If the repository has changed, the AI Planner re-evaluates the documentation structure
3. Only pages whose content may be affected by the changes are regenerated
4. If the plan structure is unchanged and only specific files changed, only relevant pages are regenerated

> **Note:** If the repository has not changed since the last generation (same commit SHA), the pipeline may skip regeneration entirely and return the existing documentation.

## AI Provider Configuration

The AI provider used for generation is configured via environment variables, not per-request. The following providers are supported:

| Provider | Binary | Environment Variable for API Key |
|----------|--------|----------------------------------|
| Claude (default) | `claude` | `ANTHROPIC_API_KEY` or Vertex AI credentials |
| Gemini | `gemini` | `GEMINI_API_KEY` |
| Cursor | `agent` | `CURSOR_API_KEY` |

### Default Settings

| Setting | Environment Variable | Default |
|---------|---------------------|---------|
| AI Provider | `AI_PROVIDER` | `claude` |
| AI Model | `AI_MODEL` | `claude-opus-4-6[1m]` |
| CLI Timeout | `AI_CLI_TIMEOUT` | `60` (minutes) |

Example `.env` configuration:

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60
ANTHROPIC_API_KEY=sk-ant-...
```

> **Warning:** The `AI_CLI_TIMEOUT` value is in minutes. Large repositories with many pages may require increasing this value beyond the default of 60 minutes.

## Authentication for Private Repositories

Private repository access relies on the system git credentials available to the docsfy process.

### Docker Deployment

Mount your SSH keys or Google Cloud credentials into the container via `docker-compose.yaml`:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.ssh:/home/appuser/.ssh:ro
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

> **Warning:** Ensure SSH keys mounted into the container have appropriate file permissions (`600`) and that the `known_hosts` file includes `github.com`.

## Examples

### Generate docs for a public repository (HTTPS)

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/my-project"}'
```

### Generate docs for a private repository (SSH)

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "git@github.com:owner/private-project.git"}'
```

### Full workflow: generate and poll until ready

```bash
# Start generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/my-project"}'

# Poll for completion
while true; do
  STATUS=$(curl -s http://localhost:8000/api/projects/my-project | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ]; then
    break
  fi
  sleep 10
done

# View the generated docs
open http://localhost:8000/docs/my-project/
```

### Trigger an incremental update

Re-submitting the same repository URL after upstream changes triggers an incremental update — only affected pages are regenerated:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/my-project"}'
```

## Storage Layout

After successful generation, the project artifacts are stored as follows:

```
/data/projects/{project-name}/
  plan.json             # Documentation structure from AI Planner
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # Final rendered static HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

Project metadata (name, repo URL, status, last commit SHA, generation history) is stored in the SQLite database at `/data/docsfy.db`.

## Related Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details including last commit SHA and page list |
| `DELETE` | `/api/projects/{name}` | Remove a project and all its generated docs |
| `GET` | `/api/projects/{name}/download` | Download the generated site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve the generated static HTML documentation |
