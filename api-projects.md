# Project Management Endpoints

The project management endpoints allow you to monitor, inspect, and clean up documentation projects managed by docsfy. These read and delete operations complement the generation endpoint by giving you full visibility into project state and lifecycle management.

## GET /api/status

Lists all tracked projects with their current generation status. This is the primary endpoint for dashboards and monitoring tools that need an overview of all documentation projects.

### Request

```
GET /api/status
```

No query parameters or request body required.

### Response

Returns HTTP `200` with a JSON object containing a `projects` array. Projects are ordered by most recently updated first.

```json
{
  "projects": [
    {
      "name": "my-repo",
      "repo_url": "https://github.com/org/my-repo.git",
      "status": "ready",
      "last_commit_sha": "abc123def456",
      "last_generated": "2025-09-15 14:30:00",
      "page_count": 12
    },
    {
      "name": "another-repo",
      "repo_url": "https://github.com/org/another-repo.git",
      "status": "generating",
      "last_commit_sha": null,
      "last_generated": null,
      "page_count": 0
    }
  ]
}
```

When no projects exist, the response contains an empty array:

```json
{
  "projects": []
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Unique project identifier, derived from the repository name |
| `repo_url` | `string` | Source repository URL or local path |
| `status` | `string` | Current state: `"generating"`, `"ready"`, or `"error"` |
| `last_commit_sha` | `string \| null` | Git commit SHA of the last processed revision. `null` if generation hasn't completed |
| `last_generated` | `string \| null` | Timestamp when documentation was last successfully generated. `null` if never completed |
| `page_count` | `integer` | Number of documentation pages generated. `0` during initial generation |

> **Note:** The `list_projects()` query in `storage.py` selects only the six fields shown above. Fields like `error_message`, `plan_json`, `created_at`, and `updated_at` are excluded from this summary view. Use `GET /api/projects/{name}` for full project details.

### Example

```bash
curl http://localhost:8000/api/status
```

### Status Values

The `status` field reflects where a project is in the generation lifecycle:

| Status | Meaning |
|--------|---------|
| `generating` | Documentation generation is in progress. The AI planner and page generator are actively working. |
| `ready` | Generation completed successfully. Documentation is available for viewing and download. |
| `error` | Generation failed. Use `GET /api/projects/{name}` to retrieve the `error_message` with details. |

These values are enforced at the storage layer as a fixed set:

```python
# src/docsfy/storage.py
VALID_STATUSES = frozenset({"generating", "ready", "error"})
```

---

## GET /api/projects/{name}

Retrieves full details for a single project, including fields not returned by the status listing such as `error_message`, `plan_json`, and timestamps.

### Request

```
GET /api/projects/{name}
```

| Parameter | Location | Type | Description |
|-----------|----------|------|-------------|
| `name` | path | `string` | Project name. Must match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$` |

### Response

Returns HTTP `200` with the complete project record:

```json
{
  "name": "my-repo",
  "repo_url": "https://github.com/org/my-repo.git",
  "status": "ready",
  "last_commit_sha": "abc123def456",
  "last_generated": "2025-09-15 14:30:00",
  "page_count": 12,
  "error_message": null,
  "plan_json": "{\"project_name\": \"my-repo\", \"tagline\": \"...\", \"navigation\": [...]}",
  "created_at": "2025-09-15 14:00:00",
  "updated_at": "2025-09-15 14:30:00"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Unique project identifier |
| `repo_url` | `string` | Source repository URL or local path |
| `status` | `string` | `"generating"`, `"ready"`, or `"error"` |
| `last_commit_sha` | `string \| null` | Git SHA of the last processed commit |
| `last_generated` | `string \| null` | Timestamp of last successful generation |
| `page_count` | `integer` | Number of generated documentation pages |
| `error_message` | `string \| null` | Error details when `status` is `"error"`. `null` otherwise |
| `plan_json` | `string \| null` | JSON-serialized documentation plan produced by the AI planner. Contains navigation structure, page slugs, titles, and descriptions |
| `created_at` | `string` | Timestamp when the project was first created |
| `updated_at` | `string` | Timestamp of the most recent update to this record |

### The Documentation Plan

When `plan_json` is present, it deserializes to a structure matching the `DocPlan` model:

```json
{
  "project_name": "my-repo",
  "tagline": "A brief description of the project",
  "navigation": [
    {
      "group": "Getting Started",
      "pages": [
        {
          "slug": "introduction",
          "title": "Introduction",
          "description": "Overview of the project"
        },
        {
          "slug": "installation",
          "title": "Installation",
          "description": "How to install and configure"
        }
      ]
    }
  ]
}
```

> **Tip:** The `plan_json` field is populated as soon as the AI planner finishes, even while individual pages are still being generated. You can use this to show users the planned documentation structure with a progress indicator before generation completes.

### Error Responses

| Status Code | Condition | Response Body |
|-------------|-----------|---------------|
| `400` | Invalid project name (fails regex validation) | `{"detail": "Invalid project name: '{name}'"}` |
| `404` | Project does not exist in the database | `{"detail": "Project '{name}' not found"}` |

### Name Validation

Project names are validated against a strict regex pattern to prevent path traversal attacks:

```python
# src/docsfy/main.py
def _validate_project_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        raise HTTPException(status_code=400, detail=f"Invalid project name: '{name}'")
    return name
```

Valid names: `my-repo`, `project_123`, `docs.v2`

Invalid names: `.hidden`, `../etc/passwd`, `path/traversal`, `-leading-dash`

### Examples

**Fetch a completed project:**

```bash
curl http://localhost:8000/api/projects/my-repo
```

**Check why a project failed:**

```bash
curl http://localhost:8000/api/projects/my-repo | jq '.error_message'
```

**Poll for generation completion:**

```bash
# Check status until generation finishes
while true; do
  STATUS=$(curl -s http://localhost:8000/api/projects/my-repo | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" != "generating" ] && break
  sleep 5
done
```

---

## DELETE /api/projects/{name}

Removes a project from the database and deletes all generated files from disk, including the rendered HTML site, cached markdown pages, and the documentation plan.

### Request

```
DELETE /api/projects/{name}
```

| Parameter | Location | Type | Description |
|-----------|----------|------|-------------|
| `name` | path | `string` | Project name. Must match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$` |

### Response

Returns HTTP `200` on successful deletion:

```json
{
  "deleted": "my-repo"
}
```

### What Gets Deleted

The delete operation performs two steps:

1. **Database record** — the project row is removed from the `projects` table in SQLite
2. **Project directory** — the entire directory tree at `{DATA_DIR}/projects/{name}/` is removed, including:

```
{DATA_DIR}/projects/{name}/
├── plan.json              # Documentation structure plan
├── cache/
│   └── pages/
│       ├── introduction.md
│       └── ...            # Cached AI-generated markdown
└── site/
    ├── index.html
    ├── *.html             # Rendered HTML pages
    ├── assets/
    │   ├── style.css
    │   ├── search.js
    │   └── ...
    └── search-index.json
```

The implementation from `main.py`:

```python
# src/docsfy/main.py
@app.delete("/api/projects/{name}")
async def delete_project_endpoint(name: str) -> dict[str, str]:
    name = _validate_project_name(name)
    deleted = await delete_project(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    project_dir = get_project_dir(name)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return {"deleted": name}
```

> **Warning:** This operation is irreversible. All generated documentation, cached pages, and the AI-produced plan will be permanently deleted. To regenerate, you must submit a new `POST /api/generate` request.

### Error Responses

| Status Code | Condition | Response Body |
|-------------|-----------|---------------|
| `400` | Invalid project name (fails regex validation) | `{"detail": "Invalid project name: '{name}'"}` |
| `404` | Project does not exist in the database | `{"detail": "Project '{name}' not found"}` |

### Examples

**Delete a project:**

```bash
curl -X DELETE http://localhost:8000/api/projects/my-repo
```

**Delete and confirm removal:**

```bash
curl -X DELETE http://localhost:8000/api/projects/my-repo

# Verify it's gone
curl http://localhost:8000/api/projects/my-repo
# Returns: {"detail": "Project 'my-repo' not found"} with HTTP 404
```

---

## Database Schema

All project management endpoints operate on the `projects` table in SQLite. The database is stored at `{DATA_DIR}/docsfy.db` (default: `/data/docsfy.db`) and is initialized automatically on application startup.

```sql
-- src/docsfy/storage.py
CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'generating',
    last_commit_sha TEXT,
    last_generated TEXT,
    page_count INTEGER DEFAULT 0,
    error_message TEXT,
    plan_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

The `DATA_DIR` is configurable via environment variable:

```python
# src/docsfy/storage.py
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
```

---

## Common Patterns

### Monitoring a Generation Workflow

Combine the project management endpoints to track a project from generation through completion:

```bash
# 1. Start generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/my-repo.git"}'
# Response: {"project": "my-repo", "status": "generating"}

# 2. Monitor progress via project details
curl http://localhost:8000/api/projects/my-repo
# Shows page_count incrementing as pages are generated

# 3. List all projects to see overall status
curl http://localhost:8000/api/status

# 4. Once status is "ready", view the generated docs
# at http://localhost:8000/docs/my-repo/index.html
```

### Cleanup Workflow

```bash
# List all projects
PROJECTS=$(curl -s http://localhost:8000/api/status | jq -r '.projects[].name')

# Delete projects in error state
for name in $PROJECTS; do
  STATUS=$(curl -s "http://localhost:8000/api/projects/$name" | jq -r '.status')
  if [ "$STATUS" = "error" ]; then
    echo "Deleting failed project: $name"
    curl -X DELETE "http://localhost:8000/api/projects/$name"
  fi
done
```

> **Note:** These endpoints have no authentication or rate limiting. In production deployments, consider placing a reverse proxy with authentication in front of the docsfy service, especially for the `DELETE` endpoint.
