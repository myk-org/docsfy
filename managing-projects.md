# Managing Projects

docsfy tracks every documentation site it generates as a **project**. Each project maps to a single GitHub repository and stores its generation status, metadata, and rendered output. This page covers how to list, inspect, and delete projects through the docsfy API.

## Project Metadata

Every project in docsfy maintains the following metadata in the SQLite database (`/data/docsfy.db`):

| Field | Description |
|-------|-------------|
| **name** | Unique project identifier derived from the repository |
| **repo_url** | The source GitHub repository URL |
| **status** | Current state: `generating`, `ready`, or `error` |
| **last_generated** | Timestamp of the most recent successful generation |
| **last_commit_sha** | The Git commit SHA used for the last generation |

## Listing Projects

Retrieve all projects and their current generation status with a single `GET` request.

### Endpoint

```
GET /api/status
```

### Example Request

```bash
curl http://localhost:8000/api/status
```

### Example Response

```json
[
  {
    "name": "my-project",
    "repo_url": "https://github.com/org/my-project",
    "status": "ready",
    "last_generated": "2026-03-04T14:32:00Z",
    "last_commit_sha": "a1b2c3d"
  },
  {
    "name": "another-repo",
    "repo_url": "https://github.com/org/another-repo",
    "status": "generating",
    "last_generated": null,
    "last_commit_sha": null
  }
]
```

### Project Statuses

| Status | Meaning |
|--------|---------|
| `generating` | Documentation generation is currently in progress |
| `ready` | Documentation has been generated and is available to serve or download |
| `error` | The most recent generation attempt failed |

> **Tip:** Poll `/api/status` after calling `/api/generate` to monitor when a project transitions from `generating` to `ready` or `error`.

## Viewing Project Details

Get detailed information about a specific project, including its last generated timestamp, the commit SHA it was built from, and its page structure.

### Endpoint

```
GET /api/projects/{name}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | path | The project identifier |

### Example Request

```bash
curl http://localhost:8000/api/projects/my-project
```

### Example Response

```json
{
  "name": "my-project",
  "repo_url": "https://github.com/org/my-project",
  "status": "ready",
  "last_generated": "2026-03-04T14:32:00Z",
  "last_commit_sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
}
```

### Key Fields

**`last_generated`** — The UTC timestamp of the most recent successful documentation build. This is `null` if the project has never completed generation. Use this to determine how stale a project's documentation may be.

**`last_commit_sha`** — The full Git commit SHA that the documentation was generated from. docsfy stores this value to support incremental updates — when you re-generate a project, it compares the current repository HEAD against this stored SHA to determine what has changed.

> **Note:** The `last_commit_sha` corresponds to the HEAD of the repository at the time of the shallow clone (`--depth 1`) performed during generation. It reflects the exact source state the documentation was built from.

### Incremental Updates and Commit Tracking

docsfy uses the stored commit SHA to enable efficient re-generation:

1. On a re-generate request, docsfy fetches the repository and compares the current HEAD against the stored `last_commit_sha`
2. If the SHA has changed, the AI Planner re-evaluates the documentation structure
3. Only pages affected by the changes are regenerated, reusing cached markdown for unchanged pages

Cached markdown pages are stored on the filesystem at:

```
/data/projects/{project-name}/
  plan.json             # doc structure from AI
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # final rendered HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

> **Tip:** If you want to force a full regeneration regardless of commit SHA, delete the project first and then re-generate it.

## Deleting Projects

Remove a project and all of its generated documentation from both the database and filesystem.

### Endpoint

```
DELETE /api/projects/{name}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | path | The project identifier to delete |

### Example Request

```bash
curl -X DELETE http://localhost:8000/api/projects/my-project
```

### What Gets Deleted

When you delete a project, docsfy removes:

- **Database record** — The project metadata row in `/data/docsfy.db` (name, URL, status, timestamps, commit SHA, generation history)
- **Filesystem artifacts** — The entire `/data/projects/{project-name}/` directory, including:
  - `plan.json` (the AI-generated documentation plan)
  - `cache/pages/*.md` (cached markdown content)
  - `site/` (the rendered HTML documentation)

> **Warning:** Deletion is permanent. There is no undo. If you need to preserve the generated documentation, download it first using the `/api/projects/{name}/download` endpoint, which provides the site as a `.tar.gz` archive.

### Downloading Before Deletion

To save a copy of the generated site before deleting:

```bash
# Download the site archive
curl -O http://localhost:8000/api/projects/my-project/download

# Then delete the project
curl -X DELETE http://localhost:8000/api/projects/my-project
```

The download endpoint packages the contents of `/data/projects/{project-name}/site/` into a `.tar.gz` archive suitable for self-hosting on any static file server.

## Serving Project Documentation

Once a project reaches `ready` status, its generated HTML documentation is served directly by docsfy at:

```
GET /docs/{project}/{path}
```

For example, to view the index page of a project called `my-project`:

```
http://localhost:8000/docs/my-project/index.html
```

## Storage and Persistence

All project data is stored under the `/data` volume:

| Path | Contents |
|------|----------|
| `/data/docsfy.db` | SQLite database with all project metadata |
| `/data/projects/` | Filesystem directory containing generated docs per project |

When running with Docker Compose, the `./data:/data` volume mount in the compose configuration ensures project data persists across container restarts:

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

> **Note:** If you run docsfy without a persistent volume mount, all project data will be lost when the container is removed.
