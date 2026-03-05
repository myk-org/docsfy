# DELETE /api/projects/{name}

Remove a project and all its generated documentation from storage.

## Endpoint

```
DELETE /api/projects/{name}
```

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The name of the project to delete |

The project name corresponds to the identifier assigned during generation via `POST /api/generate`. It is the same name used to serve docs at `/docs/{name}/` and to retrieve project details from `GET /api/projects/{name}`.

## Request

This endpoint requires no request body or query parameters.

```bash
curl -X DELETE http://localhost:8000/api/projects/my-project
```

## Response

### 200 OK

The project and all associated data were successfully removed.

```json
{
  "message": "Project 'my-project' deleted successfully"
}
```

### 404 Not Found

The specified project does not exist.

```json
{
  "detail": "Project 'my-project' not found"
}
```

## What Gets Deleted

Deleting a project removes **all** data associated with it across both storage layers.

### SQLite Database (`/data/docsfy.db`)

The project metadata record is removed, including:

- Project name and repository URL
- Generation status (`generating` / `ready` / `error`)
- Last generated timestamp
- Last commit SHA (used for incremental updates)
- Generation history and logs

### Filesystem (`/data/projects/{name}/`)

The entire project directory is removed:

```
/data/projects/{name}/
  plan.json                 # documentation structure from AI planner
  cache/
    pages/*.md              # AI-generated markdown (cached for incremental updates)
  site/                     # final rendered HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

> **Warning:** Deletion is permanent and irreversible. There is no soft-delete or recovery mechanism. If you need the generated documentation, download it first using `GET /api/projects/{name}/download` before deleting.

## Side Effects

Once a project is deleted, the following endpoints will no longer return data for it:

| Endpoint | Behavior After Deletion |
|----------|------------------------|
| `GET /docs/{name}/{path}` | Returns `404 Not Found` — static HTML is no longer served |
| `GET /api/projects/{name}` | Returns `404 Not Found` — project metadata is gone |
| `GET /api/projects/{name}/download` | Returns `404 Not Found` — no site to package |
| `GET /api/status` | The project no longer appears in the project list |

## Examples

### Delete a project with curl

```bash
curl -X DELETE http://localhost:8000/api/projects/my-project
```

### Delete a project with Python requests

```python
import requests

response = requests.delete("http://localhost:8000/api/projects/my-project")

if response.status_code == 200:
    print("Project deleted successfully")
elif response.status_code == 404:
    print("Project not found")
```

### Download before deleting

Back up the generated documentation as a `.tar.gz` archive before removing the project:

```bash
# Download the generated docs
curl -o my-project-docs.tar.gz \
  http://localhost:8000/api/projects/my-project/download

# Then delete the project
curl -X DELETE http://localhost:8000/api/projects/my-project
```

> **Tip:** Use the download-then-delete pattern when you want to self-host the generated documentation independently. The downloaded archive contains the complete static site and can be served from any web server.

## Deleting a Project That Is Currently Generating

If a project is in the `generating` state (the AI pipeline is actively running), deleting it will cancel the in-progress generation and clean up any partially written files.

You can check a project's current status before deleting:

```bash
# Check project status
curl http://localhost:8000/api/projects/my-project

# Delete if no longer needed
curl -X DELETE http://localhost:8000/api/projects/my-project
```

> **Note:** After deletion, you can re-generate documentation for the same repository by submitting a new `POST /api/generate` request. The project name will be available for reuse.

## Storage Configuration

The data directories used by docsfy are configured through the Docker volume mount. The default `docker-compose.yaml` maps a local `./data` directory:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
```

Deletion operates on files under `/data/projects/{name}/` inside the container, which maps to `./data/projects/{name}/` on the host filesystem.

## Related Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details, status, and page list |
| `GET` | `/api/projects/{name}/download` | Download the generated site as a `.tar.gz` archive |
