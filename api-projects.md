# GET /api/projects/{name}

Retrieve detailed information about a documentation project, including its current status, the last generation timestamp, the commit SHA that was used, and a full listing of generated pages.

## Endpoint

```
GET /api/projects/{name}
```

## Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | Yes | The unique project name assigned during generation. This corresponds to the directory name under `/data/projects/`. |

## Response

### 200 OK

Returns the full project details including metadata from the SQLite database and the page listing derived from the project's `plan.json`.

```json
{
  "name": "my-project",
  "repo_url": "https://github.com/example/my-project",
  "status": "ready",
  "last_generated": "2026-03-04T18:32:01Z",
  "last_commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
  "pages": [
    "index.md",
    "getting-started.md",
    "configuration.md",
    "api-reference.md"
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | The unique project identifier. |
| `repo_url` | `string` | The GitHub repository URL (HTTPS or SSH) that this project was generated from. |
| `status` | `string` | Current project state. One of `generating`, `ready`, or `error`. |
| `last_generated` | `string` (ISO 8601) | Timestamp of the most recent documentation generation run. |
| `last_commit_sha` | `string` | The full 40-character Git commit SHA from the repository at the time of the last generation. Used for [incremental updates](#incremental-updates-and-commit-tracking). |
| `pages` | `array[string]` | List of documentation page filenames derived from the project's `plan.json`. These correspond to cached markdown files under `cache/pages/`. |

### Project Status Values

| Status | Meaning |
|--------|---------|
| `generating` | Documentation generation is currently in progress. The pipeline is running through clone, plan, content, and render stages. |
| `ready` | Generation completed successfully. The static site is available for serving or download. |
| `error` | The most recent generation attempt failed. Check generation logs for details. |

### 404 Not Found

Returned when no project exists with the given name.

```json
{
  "detail": "Project not found: my-project"
}
```

## Examples

### Retrieve a project with completed documentation

```bash
curl http://localhost:8000/api/projects/my-project
```

```json
{
  "name": "my-project",
  "repo_url": "https://github.com/example/my-project",
  "status": "ready",
  "last_generated": "2026-03-04T18:32:01Z",
  "last_commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
  "pages": [
    "index.md",
    "getting-started.md",
    "configuration.md",
    "api-reference.md"
  ]
}
```

### Check a project that is currently generating

```bash
curl http://localhost:8000/api/projects/new-project
```

```json
{
  "name": "new-project",
  "repo_url": "https://github.com/example/new-project",
  "status": "generating",
  "last_generated": null,
  "last_commit_sha": "f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5",
  "pages": []
}
```

> **Note:** While a project is in `generating` status, `last_generated` may be `null` if this is the first generation run. The `pages` array will be empty until the AI Planner and Content Generator stages complete.

### Query a project that failed generation

```bash
curl http://localhost:8000/api/projects/broken-project
```

```json
{
  "name": "broken-project",
  "repo_url": "https://github.com/example/broken-project",
  "status": "error",
  "last_generated": "2026-03-04T12:01:44Z",
  "last_commit_sha": "d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3",
  "pages": []
}
```

> **Tip:** If a project is in `error` status, you can re-trigger generation by calling `POST /api/generate` with the same repository URL. The pipeline will re-clone and attempt a full generation.

## Incremental Updates and Commit Tracking

The `last_commit_sha` field plays a key role in the incremental update system. When you trigger a re-generation for an existing project via `POST /api/generate`:

1. docsfy fetches the repository and compares the current HEAD SHA against the stored `last_commit_sha`.
2. If the SHA has changed, the AI Planner re-evaluates whether the documentation structure needs updating.
3. Only pages affected by the changes are regenerated, keeping previously cached markdown pages intact.
4. The `last_commit_sha` is updated to reflect the new HEAD after generation completes.

This makes `GET /api/projects/{name}` useful for CI/CD integrations that need to determine whether documentation is current with the latest commit.

## Storage Layout

The data returned by this endpoint is assembled from two sources:

**SQLite database** (`/data/docsfy.db`) stores the project metadata — name, repo URL, status, timestamps, and commit SHA.

**Filesystem** (`/data/projects/{name}/`) holds the generated artifacts:

```
/data/projects/{name}/
  plan.json             # Documentation structure from AI (source for pages listing)
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # Final rendered HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

The `pages` array in the response is derived from the `plan.json` file, which is produced by the AI Planner stage and defines the full navigation hierarchy and page structure of the generated documentation site.

## Related Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository URL. |
| `GET` | `/api/status` | List all projects and their generation status. |
| `DELETE` | `/api/projects/{name}` | Remove a project and all its generated documentation. |
| `GET` | `/api/projects/{name}/download` | Download the generated static site as a `.tar.gz` archive. |
| `GET` | `/docs/{project}/{path}` | Serve the generated HTML documentation directly. |

> **Warning:** Calling `DELETE /api/projects/{name}` permanently removes the project metadata from the database and deletes all generated files from disk, including cached markdown pages. This action cannot be undone.
