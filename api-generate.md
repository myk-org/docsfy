# POST /api/generate

Start documentation generation for a GitHub repository. This endpoint triggers docsfy's four-stage pipeline — clone, plan, generate, render — producing a polished static HTML documentation site from your repository's source code.

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
| `repo_url` | `string` | Yes | GitHub repository URL to generate documentation for. Supports both HTTPS and SSH formats. |

#### Supported URL Formats

```
https://github.com/owner/repo
https://github.com/owner/repo.git
git@github.com:owner/repo.git
```

> **Note:** Private repositories are supported. The service uses system git credentials configured in the container environment for authentication.

### Example Request

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/my-project"}'
```

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/generate",
    json={"repo_url": "https://github.com/owner/my-project"}
)
print(response.json())
```

## Response

### Success Response

**Status Code:** `200 OK`

The endpoint returns a JSON object with the project metadata and generation status.

```json
{
  "name": "my-project",
  "repo_url": "https://github.com/owner/my-project",
  "status": "generating"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Project name derived from the repository URL. |
| `repo_url` | `string` | The repository URL provided in the request. |
| `status` | `string` | Current generation status. One of `generating`, `ready`, or `error`. |

#### Status Values

| Status | Description |
|--------|-------------|
| `generating` | The documentation generation pipeline is currently running. |
| `ready` | Documentation has been successfully generated and is available for viewing. |
| `error` | Generation failed. Check the project details endpoint for error information. |

> **Note:** Generation is an asynchronous process. The endpoint returns immediately with a `generating` status. Use [`GET /api/status`](/api/status) or [`GET /api/projects/{name}`](/api/projects) to poll for completion.

### Error Responses

**Status Code:** `422 Unprocessable Entity`

Returned when the request body is invalid or missing required fields.

```json
{
  "detail": [
    {
      "loc": ["body", "repo_url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Status Code:** `400 Bad Request`

Returned when the repository URL is malformed or unsupported.

```json
{
  "detail": "Invalid repository URL format"
}
```

**Status Code:** `500 Internal Server Error`

Returned when the server encounters an unexpected error during request processing (e.g., AI CLI unavailable, git clone failure).

```json
{
  "detail": "Generation failed: <error message>"
}
```

## Generation Pipeline

When you call `POST /api/generate`, the service executes a four-stage pipeline:

### Stage 1: Clone Repository

The repository is shallow-cloned (`--depth 1`) to a temporary directory to minimize disk usage and clone time.

### Stage 2: AI Planner

The configured AI CLI analyzes the full repository and produces a `plan.json` file containing the documentation structure — pages, sections, and navigation hierarchy.

### Stage 3: AI Content Generator

For each page defined in `plan.json`, the AI CLI explores the codebase and generates a markdown file. Pages are generated concurrently using semaphore-limited concurrency for efficiency. Output is cached at:

```
/data/projects/{name}/cache/pages/*.md
```

### Stage 4: HTML Renderer

Markdown pages and `plan.json` are converted into a polished static HTML site using Jinja2 templates with bundled assets. The final site includes sidebar navigation, dark/light theme toggle, client-side search, and code syntax highlighting via highlight.js.

The rendered site is output to:

```
/data/projects/{name}/site/
```

> **Tip:** Once generation completes with status `ready`, view the docs at `GET /docs/{project}/` or download them as a `.tar.gz` archive via `GET /api/projects/{name}/download`.

## Incremental Updates

Calling `POST /api/generate` for a repository that has already been generated triggers an incremental update:

1. The service fetches the repository and compares the current commit SHA against the stored SHA in the database.
2. If the commit SHA has changed, the AI Planner re-evaluates whether the documentation structure has changed.
3. Only pages whose content may be affected by the changes are regenerated.
4. If the plan structure is unchanged and only specific files changed, only the relevant pages are regenerated.

This significantly reduces generation time for repositories that have already been documented.

> **Note:** If the commit SHA has not changed since the last generation, the pipeline may skip regeneration entirely.

## AI Provider Configuration

The AI provider used during generation is controlled by environment variables. The configured provider affects all stages that invoke the AI CLI (planning and content generation).

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI CLI provider. One of `claude`, `gemini`, or `cursor`. |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier passed to the AI CLI. |
| `AI_CLI_TIMEOUT` | `60` | Maximum time in minutes for each AI CLI invocation. |

The provider determines which binary and command flags are used:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

| Provider | Binary | Command Pattern |
|----------|--------|----------------|
| `claude` | `claude` | `claude --model <model> --dangerously-skip-permissions -p` |
| `gemini` | `gemini` | `gemini --model <model> --yolo` |
| `cursor` | `agent` | `agent --force --model <model> --print --workspace <path>` |

> **Warning:** Before starting generation, the service runs a lightweight availability check against the configured AI CLI. If the CLI is not installed or credentials are not configured, the generation will fail.

## Monitoring Generation Progress

After submitting a generation request, use these endpoints to track progress:

```bash
# List all projects and their statuses
curl http://localhost:8000/api/status

# Get details for a specific project
curl http://localhost:8000/api/projects/my-project
```

The project details endpoint returns metadata including the last generated timestamp, commit SHA, and list of generated pages.

## Complete Example

```bash
# 1. Start generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/my-project"}'
# Response: {"name": "my-project", "repo_url": "...", "status": "generating"}

# 2. Poll for completion
curl http://localhost:8000/api/projects/my-project
# Response includes "status": "ready" when complete

# 3. View the generated docs
# Open in browser: http://localhost:8000/docs/my-project/

# 4. Or download as a static site archive
curl -o docs.tar.gz http://localhost:8000/api/projects/my-project/download
```

## Related Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details |
| `DELETE` | `/api/projects/{name}` | Remove a project and its generated docs |
| `GET` | `/api/projects/{name}/download` | Download site as `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve generated static HTML docs |
