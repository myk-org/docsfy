# GET /api/status

List all projects and their current documentation generation status.

## Endpoint

```
GET /api/status
```

This endpoint returns every project registered in docsfy along with its generation state. Use it to build dashboards, poll for completion after triggering a build, or enumerate available documentation sites.

## Response

Returns a JSON array of project objects. Each object contains the project name, repository URL, and its current generation status.

### Status Values

| Status | Description |
|--------|-------------|
| `generating` | The documentation pipeline is actively running for this project |
| `ready` | Documentation has been successfully generated and is available to serve |
| `error` | An error occurred during one of the generation stages |

### Response Schema

```json
[
  {
    "name": "string",
    "repo_url": "string",
    "status": "generating | ready | error"
  }
]
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Unique project identifier, derived from the repository name |
| `repo_url` | `string` | The GitHub repository URL submitted via `POST /api/generate` |
| `status` | `string` | One of `generating`, `ready`, or `error` |

## Examples

### Request

```bash
curl http://localhost:8000/api/status
```

### Response — Multiple Projects

```json
[
  {
    "name": "my-api",
    "repo_url": "https://github.com/acme/my-api",
    "status": "ready"
  },
  {
    "name": "frontend-sdk",
    "repo_url": "https://github.com/acme/frontend-sdk",
    "status": "generating"
  },
  {
    "name": "legacy-service",
    "repo_url": "https://github.com/acme/legacy-service",
    "status": "error"
  }
]
```

### Response — No Projects

When no projects have been submitted yet, the endpoint returns an empty array:

```json
[]
```

## Status Lifecycle

A project's status follows the generation pipeline defined in the docsfy architecture:

```
POST /api/generate
        |
        v
  [generating] ──────────────────────────────────┐
        |                                         |
   Clone Repo                                     |
        |                                         |
   AI Planner (plan.json)                    On failure
        |                                         |
   AI Content Generator (markdown pages)          |
        |                                         |
   HTML Renderer (static site)                    |
        |                                         v
    [ready]                                   [error]
```

1. When a generation is triggered via `POST /api/generate`, the project status is set to `generating`.
2. The pipeline runs four sequential stages: clone, plan, content generation, and HTML rendering.
3. On successful completion of all stages, the status transitions to `ready`.
4. If any stage fails, the status transitions to `error`.

> **Note:** Re-submitting a project that already exists triggers an incremental update. The status returns to `generating` while docsfy compares the current commit SHA against the stored SHA and regenerates only affected pages.

## Storage

Project status metadata is stored in the SQLite database at `/data/docsfy.db`. The database tracks:

- Project name and repository URL
- Current status (`generating`, `ready`, `error`)
- Last generated timestamp and commit SHA
- Generation history and logs

```
/data/docsfy.db          # SQLite metadata store
/data/projects/{name}/   # Generated documentation files
```

> **Tip:** Mount `/data` as a persistent volume in your container deployment to preserve project state across restarts. The `docker-compose.yaml` maps this to `./data:/data` by default.

## Polling for Completion

After triggering a build with `POST /api/generate`, you can poll `GET /api/status` to check when generation finishes:

```bash
# Start generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/acme/my-api"}'

# Poll until status changes from "generating"
while true; do
  STATUS=$(curl -s http://localhost:8000/api/status | \
    python3 -c "
import sys, json
projects = json.load(sys.stdin)
for p in projects:
    if p['name'] == 'my-api':
        print(p['status'])
        break
")
  echo "Status: $STATUS"
  if [ "$STATUS" != "generating" ]; then
    break
  fi
  sleep 10
done
```

> **Warning:** Documentation generation involves AI CLI calls that can take several minutes per page. The `AI_CLI_TIMEOUT` environment variable (default: `60` minutes) controls the maximum time allowed for each AI invocation. Avoid polling too aggressively.

## Related Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository |
| `GET` | `/api/projects/{name}` | Get detailed project info (last generated timestamp, commit SHA, pages) |
| `DELETE` | `/api/projects/{name}` | Remove a project and its generated docs |
| `GET` | `/api/projects/{name}/download` | Download the generated site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve the generated static HTML documentation |

Use `GET /api/status` to discover project names, then query `GET /api/projects/{name}` for full details including page lists and generation timestamps.
