# GET /api/status & Project Details

## Overview

docsfy provides a set of REST endpoints for managing and inspecting documentation projects. You can list all projects with their current generation status, retrieve detailed information about a specific project, and delete projects you no longer need.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details (last generated, commit SHA, pages) |
| `DELETE` | `/api/projects/{name}` | Remove a project and its generated docs |

---

## List All Projects

```
GET /api/status
```

Returns a list of every project tracked by docsfy along with its current generation status. Use this endpoint to build dashboards, monitor generation progress, or check whether a project's documentation is ready to serve.

### Example Request

```bash
curl http://localhost:8000/api/status
```

### Example Response

```json
{
  "projects": [
    {
      "name": "my-api",
      "repo_url": "https://github.com/acme/my-api.git",
      "status": "ready",
      "last_generated": "2026-03-04T14:22:31Z",
      "last_commit_sha": "a1b2c3d4e5f6789012345678abcdef0123456789"
    },
    {
      "name": "frontend-app",
      "repo_url": "https://github.com/acme/frontend-app.git",
      "status": "generating",
      "last_generated": null,
      "last_commit_sha": null
    },
    {
      "name": "data-pipeline",
      "repo_url": "https://github.com/acme/data-pipeline.git",
      "status": "error",
      "last_generated": "2026-03-03T09:15:00Z",
      "last_commit_sha": "f0e1d2c3b4a5968778695a4b3c2d1e0f12345678"
    }
  ]
}
```

### Project Status Values

Each project has one of three possible status values:

| Status | Description |
|--------|-------------|
| `generating` | The four-stage generation pipeline (clone, plan, content, render) is currently running. |
| `ready` | Documentation has been successfully generated and is available to serve or download. |
| `error` | The most recent generation attempt failed. Previous successful builds, if any, may still be available. |

> **Tip:** Poll this endpoint to track generation progress after calling `POST /api/generate`. A project transitions from `generating` to either `ready` or `error` once the pipeline completes.

---

## Get Project Details

```
GET /api/projects/{name}
```

Returns detailed information about a specific project, including the last generated timestamp, the commit SHA used for generation, and the full page list from the documentation plan.

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The project name (derived from the repository name during generation) |

### Example Request

```bash
curl http://localhost:8000/api/projects/my-api
```

### Example Response

```json
{
  "name": "my-api",
  "repo_url": "https://github.com/acme/my-api.git",
  "status": "ready",
  "last_generated": "2026-03-04T14:22:31Z",
  "last_commit_sha": "a1b2c3d4e5f6789012345678abcdef0123456789",
  "pages": [
    {
      "title": "Getting Started",
      "slug": "getting-started",
      "section": "Introduction"
    },
    {
      "title": "Authentication",
      "slug": "authentication",
      "section": "Guides"
    },
    {
      "title": "API Reference",
      "slug": "api-reference",
      "section": "Reference"
    }
  ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Project identifier |
| `repo_url` | string | Source repository URL (HTTPS or SSH) |
| `status` | string | Current status: `generating`, `ready`, or `error` |
| `last_generated` | string \| null | ISO 8601 timestamp of the last successful generation, or `null` if never generated |
| `last_commit_sha` | string \| null | Full 40-character SHA of the commit used in the last generation, or `null` if never generated |
| `pages` | array | List of documentation pages from `plan.json`, including title, slug, and section |

> **Note:** The `pages` field reflects the documentation plan created by the AI Planner (Stage 2 of the generation pipeline). It is sourced from the `plan.json` file stored at `/data/projects/{name}/plan.json`.

### How Data Is Stored

Project metadata is persisted in two locations:

- **SQLite database** (`/data/docsfy.db`) — stores the project name, repo URL, status, last generated timestamp, last commit SHA, and generation history/logs.
- **Filesystem** (`/data/projects/{name}/`) — stores the generated plan, cached markdown pages, and rendered HTML site.

```
/data/projects/{name}/
  plan.json             # documentation structure from AI Planner
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # final rendered static HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

### Incremental Updates and Commit Tracking

The `last_commit_sha` field is central to docsfy's incremental update strategy:

1. Each project's last commit SHA is stored in SQLite after generation.
2. When `POST /api/generate` is called for an existing project, docsfy fetches the repo and compares the current HEAD SHA against the stored SHA.
3. If the SHA has changed, the AI Planner re-evaluates the documentation structure.
4. Only pages affected by the changes are regenerated — unchanged pages are served from the cache at `/data/projects/{name}/cache/pages/`.

> **Tip:** Compare the `last_commit_sha` from this endpoint against your repository's current HEAD to determine whether the documentation is up to date before triggering a regeneration.

### Error Response

If the project does not exist, the endpoint returns a 404:

```json
{
  "detail": "Project not found"
}
```

---

## Delete a Project

```
DELETE /api/projects/{name}
```

Permanently removes a project and all of its generated documentation, including cached markdown, rendered HTML, and database metadata.

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | The project name to delete |

### Example Request

```bash
curl -X DELETE http://localhost:8000/api/projects/my-api
```

### Example Response

```json
{
  "detail": "Project 'my-api' deleted"
}
```

> **Warning:** This action is irreversible. Deleting a project removes both the database record from `/data/docsfy.db` and the entire project directory at `/data/projects/{name}/`, including the `plan.json`, all cached markdown pages, and the rendered static site. You will need to run `POST /api/generate` again to recreate the documentation.

### What Gets Deleted

| Resource | Location | Description |
|----------|----------|-------------|
| Database record | `/data/docsfy.db` | Project metadata, status, generation history and logs |
| Documentation plan | `/data/projects/{name}/plan.json` | AI-generated page structure |
| Cached pages | `/data/projects/{name}/cache/pages/*.md` | Markdown content from the AI Content Generator |
| Rendered site | `/data/projects/{name}/site/` | Static HTML, CSS, JS, and search index |

### Error Response

If the project does not exist:

```json
{
  "detail": "Project not found"
}
```

---

## Common Workflow

A typical workflow combining these endpoints with the generation endpoint:

```bash
# 1. Start generating documentation for a repository
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/acme/my-api.git"}'

# 2. Check generation status across all projects
curl http://localhost:8000/api/status

# 3. Once status is "ready", inspect the project details
curl http://localhost:8000/api/projects/my-api

# 4. View the generated docs in your browser
#    http://localhost:8000/docs/my-api/

# 5. Download the static site for self-hosting
curl -O http://localhost:8000/api/projects/my-api/download

# 6. When no longer needed, delete the project
curl -X DELETE http://localhost:8000/api/projects/my-api
```

> **Note:** The docsfy server runs on port `8000` by default, as configured in the Docker entrypoint: `uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000`
