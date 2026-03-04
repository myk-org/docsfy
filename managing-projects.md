# Managing Projects

docsfy organizes generated documentation into **projects**. Each project corresponds to a single GitHub repository and contains the AI-generated documentation plan, cached markdown pages, and the final rendered HTML site. This page covers how to list, inspect, and delete projects, as well as how to interpret project statuses.

## Project Overview

Every project in docsfy tracks the following metadata in a SQLite database (`/data/docsfy.db`):

| Field | Description |
|-------|-------------|
| Project name | Unique identifier derived from the repository |
| Repo URL | The GitHub repository URL (SSH or HTTPS) |
| Status | Current state: `generating`, `ready`, or `error` |
| Last generated timestamp | When documentation was last successfully built |
| Last commit SHA | The commit SHA from the most recent generation |
| Generation history and logs | Record of past generation runs |

Each project also has a corresponding directory on the filesystem:

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

## Listing All Projects

To retrieve a list of all projects and their current generation status, use the `GET /api/status` endpoint.

**Request:**

```bash
curl http://localhost:8000/api/status
```

This returns all projects with their current status (`generating`, `ready`, or `error`), giving you a dashboard-level view of every documentation site managed by your docsfy instance.

> **Tip:** Use this endpoint to monitor generation progress after submitting multiple repositories. Projects currently being built will show `generating` status.

## Viewing Project Details

To inspect a specific project's metadata, use the `GET /api/projects/{name}` endpoint.

**Request:**

```bash
curl http://localhost:8000/api/projects/my-project
```

The response includes:

- **Last generated timestamp** — when the documentation was last built
- **Last commit SHA** — the Git commit that was used for generation
- **Pages** — the list of documentation pages (derived from `plan.json`)
- **Current status** — the project's generation state

This information is especially useful for verifying whether documentation is up to date with the latest repository changes. By comparing the **last commit SHA** against the current HEAD of your repository, you can determine if a regeneration is needed.

> **Note:** The pages list reflects the structure determined by the AI Planner during generation. It includes all sections and navigation hierarchy defined in the project's `plan.json`.

## Serving and Downloading Generated Docs

Once a project reaches `ready` status, its documentation is available in two ways:

### Browsing Docs Directly

Generated documentation is served directly by the docsfy API:

```
GET /docs/{project}/{path}
```

For example, to view the index page of a project called `my-project`:

```bash
curl http://localhost:8000/docs/my-project/index.html
```

Or simply open `http://localhost:8000/docs/my-project/` in a browser to browse the full documentation site with sidebar navigation, search, and theme toggling.

### Downloading for Self-Hosting

To download the entire rendered site as a portable archive:

```bash
curl -O http://localhost:8000/api/projects/my-project/download
```

This returns a `.tar.gz` archive of the project's `site/` directory, containing all HTML files, CSS, JavaScript, and the search index. You can extract and host these files with any static file server (Nginx, Caddy, GitHub Pages, S3, etc.).

## Deleting Projects

To remove a project and all of its generated documentation, use the `DELETE /api/projects/{name}` endpoint.

**Request:**

```bash
curl -X DELETE http://localhost:8000/api/projects/my-project
```

This operation:

1. Removes the project's metadata from the SQLite database (`/data/docsfy.db`)
2. Deletes the project's entire directory from the filesystem (`/data/projects/my-project/`)

> **Warning:** Deleting a project is irreversible. All generated documentation — including cached markdown pages, the `plan.json`, and the rendered HTML site — will be permanently removed. You will need to run a full regeneration via `POST /api/generate` to recreate the project.

## Understanding Project Statuses

Every project has one of three statuses that reflects where it is in the generation lifecycle:

### `generating`

The project is currently being processed through the four-stage generation pipeline:

1. **Clone Repository** — shallow clone (`--depth 1`) of the source repo to a temporary directory
2. **AI Planner** — the AI CLI analyzes the codebase and produces a `plan.json` with the documentation structure
3. **AI Content Generator** — for each page in `plan.json`, the AI generates markdown content (pages may be generated concurrently)
4. **HTML Renderer** — markdown and `plan.json` are converted into a polished static HTML site using Jinja2 templates

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
                                                          ready / error
```

A project remains in `generating` status until the pipeline either completes successfully or encounters a failure.

> **Note:** The generation timeout is controlled by the `AI_CLI_TIMEOUT` environment variable, which defaults to `60` minutes. Long or complex repositories may require increasing this value.

### `ready`

The project's documentation has been successfully generated and is available to serve or download. A project in `ready` status has:

- A valid `plan.json` defining the documentation structure
- Cached markdown pages in `cache/pages/*.md`
- A fully rendered static HTML site in `site/`

Projects in `ready` status are served at `GET /docs/{project}/{path}`.

### `error`

The generation pipeline failed at some stage. This can happen for several reasons:

- The repository URL is invalid or inaccessible
- The AI CLI tool is not available or not properly configured
- The AI provider timed out during planning or content generation
- The AI response could not be parsed into valid JSON (despite multi-strategy extraction)
- An error occurred during HTML rendering

> **Tip:** Check the project's generation logs to diagnose the specific failure. After resolving the issue, submit a new `POST /api/generate` request to retry. The project status will transition back to `generating`.

### Status Transitions

```
                    ┌──────────────┐
  POST /api/generate│              │
  ─────────────────▶│  generating  │
                    │              │
                    └──────┬───────┘
                           │
                ┌──────────┴──────────┐
                │                     │
           success                  failure
                │                     │
                ▼                     ▼
         ┌──────────┐         ┌──────────┐
         │  ready   │         │  error   │
         └──────────┘         └──────────┘
```

Submitting a new generation request (including for an existing project) always transitions the status back to `generating`, regardless of the current state.

## Incremental Updates

docsfy supports smart incremental updates to avoid regenerating unchanged documentation. When you trigger a regeneration for an existing project:

1. The system fetches the repository and compares the current commit SHA against the stored **last commit SHA**
2. If the SHA has changed, the AI Planner reruns to check whether the documentation structure has changed
3. If the plan structure is unchanged, only pages affected by the code changes are regenerated
4. Unchanged cached markdown pages in `cache/pages/*.md` are reused

This significantly reduces generation time and AI usage for repositories with frequent, incremental changes.

```bash
# Trigger a regeneration — docsfy handles incremental logic automatically
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/owner/repo"}'
```

> **Tip:** Incremental updates are fully automatic. Simply call `POST /api/generate` with the same repository URL, and docsfy will determine what needs to be regenerated based on the commit history.

## API Reference Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository |
| `GET` | `/api/status` | List all projects with their current status |
| `GET` | `/api/projects/{name}` | Get detailed project metadata (timestamp, SHA, pages) |
| `DELETE` | `/api/projects/{name}` | Remove a project and all generated docs |
| `GET` | `/api/projects/{name}/download` | Download the rendered site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve generated documentation pages |
