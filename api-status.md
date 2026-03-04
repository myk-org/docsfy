# GET /api/status

List all tracked projects with their current generation status, last generated timestamp, and commit SHA.

## Overview

The `GET /api/status` endpoint returns a summary of every project registered in docsfy. Use it to monitor generation progress, check which projects are up to date, and identify failed builds at a glance.

## Request

```
GET /api/status
```

No request body or query parameters are required.

### Example Request

```bash
curl http://localhost:8000/api/status
```

## Response

Returns a JSON array of project objects. Each object contains the metadata stored in the SQLite database at `/data/docsfy.db`.

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Unique project identifier |
| `repo_url` | `string` | GitHub repository URL (HTTPS or SSH) |
| `status` | `string` | Current generation status: `generating`, `ready`, or `error` |
| `last_generated` | `string \| null` | ISO 8601 timestamp of the last successful generation, or `null` if never completed |
| `last_commit_sha` | `string \| null` | The commit SHA from the most recent generation run, or `null` if never generated |

### Status Values

| Status | Meaning |
|--------|---------|
| `generating` | A generation pipeline is currently running for this project |
| `ready` | Documentation was generated successfully and is available for serving or download |
| `error` | The most recent generation attempt failed |

### Example Response

```json
[
  {
    "name": "my-api",
    "repo_url": "https://github.com/acme/my-api.git",
    "status": "ready",
    "last_generated": "2026-03-04T14:32:10Z",
    "last_commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
  },
  {
    "name": "frontend-sdk",
    "repo_url": "https://github.com/acme/frontend-sdk.git",
    "status": "generating",
    "last_generated": null,
    "last_commit_sha": null
  },
  {
    "name": "infra-tools",
    "repo_url": "https://github.com/acme/infra-tools.git",
    "status": "error",
    "last_generated": "2026-03-03T09:15:44Z",
    "last_commit_sha": "f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5"
  }
]
```

An empty array (`[]`) is returned when no projects have been registered.

## How Project Status Is Tracked

Project metadata is persisted in a SQLite database at `/data/docsfy.db`. The status field is updated at each stage of the generation pipeline:

1. **`POST /api/generate`** is called with a repository URL — a new project record is created (or an existing one is updated) with status `generating`.
2. The four-stage pipeline runs: clone, AI planner, AI content generator, and HTML renderer.
3. On success the status is set to `ready`, `last_generated` is set to the current timestamp, and `last_commit_sha` is set to the HEAD commit of the cloned repository.
4. On failure the status is set to `error`. The previous `last_generated` and `last_commit_sha` values are preserved so you can identify the last known good state.

> **Note:** The `last_commit_sha` is captured from a shallow clone (`--depth 1`) of the repository. It reflects the HEAD commit at the time of generation, not the full history.

## Incremental Updates and Commit SHA

The `last_commit_sha` field plays a key role in docsfy's incremental update mechanism, as described in the [design document](https://github.com/docsfy/docsfy):

1. When `POST /api/generate` is called for an existing project, docsfy fetches the repo and compares the current HEAD SHA against the stored `last_commit_sha`.
2. If the SHA has changed, the AI Planner re-evaluates the documentation structure.
3. Only pages affected by the changes are regenerated — unchanged pages use their cached markdown from `/data/projects/{name}/cache/pages/`.
4. The `last_commit_sha` is updated to the new HEAD after a successful run.

> **Tip:** Compare the `last_commit_sha` from this endpoint against the latest commit in your repository to determine whether your docs are up to date before triggering a regeneration.

## Usage Patterns

### Polling for Generation Completion

After triggering a generation with `POST /api/generate`, poll the status endpoint to detect when the build finishes:

```bash
while true; do
  STATUS=$(curl -s http://localhost:8000/api/status | \
    jq -r '.[] | select(.name == "my-api") | .status')

  if [ "$STATUS" = "ready" ]; then
    echo "Documentation is ready."
    break
  elif [ "$STATUS" = "error" ]; then
    echo "Generation failed."
    break
  fi

  sleep 10
done
```

### Checking All Projects Programmatically

```python
import httpx

response = httpx.get("http://localhost:8000/api/status")
projects = response.json()

for project in projects:
    print(f"{project['name']}: {project['status']}")
    if project["last_generated"]:
        print(f"  Last generated: {project['last_generated']}")
        print(f"  Commit SHA:     {project['last_commit_sha']}")
```

### Filtering by Status

Find all projects in an error state:

```bash
curl -s http://localhost:8000/api/status | \
  jq '[.[] | select(.status == "error")]'
```

## Related Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository |
| `GET` | `/api/projects/{name}` | Get detailed project information including page list |
| `DELETE` | `/api/projects/{name}` | Remove a project and its generated docs |
| `GET` | `/api/projects/{name}/download` | Download the generated site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve the generated static HTML documentation |

> **Note:** For detailed information about a specific project — including the full list of generated pages — use `GET /api/projects/{name}` instead.

## Storage Reference

The status endpoint reads from the SQLite database. The corresponding generated files live on the filesystem:

```
/data/docsfy.db                          # SQLite metadata (source for this endpoint)
/data/projects/{name}/
  plan.json                              # Documentation structure from AI planner
  cache/pages/*.md                       # Cached markdown (for incremental updates)
  site/                                  # Rendered static HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

> **Warning:** Do not modify `docsfy.db` or the files under `/data/projects/` directly. Use the API endpoints to manage projects. Direct modifications may cause inconsistencies between the database and filesystem.
