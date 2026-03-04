# Storage & Database

docsfy uses a dual-storage architecture: **SQLite** for structured project metadata and the **local filesystem** for documentation artifacts — plan files, cached markdown, and rendered HTML sites. All persistent data lives under a single `/data/` root directory, making backups and container mounts straightforward.

## Storage Architecture Overview

```
/data/
├── docsfy.db                          # SQLite database (project metadata)
└── projects/
    └── {project-name}/
        ├── plan.json                  # Documentation structure from AI Planner
        ├── cache/
        │   └── pages/
        │       ├── getting-started.md # AI-generated markdown (cached)
        │       ├── api-reference.md
        │       └── ...
        └── site/                      # Final rendered HTML
            ├── index.html
            ├── getting-started.html
            ├── api-reference.html
            ├── search-index.json
            └── assets/
                ├── style.css
                ├── search.js
                ├── theme-toggle.js
                └── highlight.js
```

> **Note:** The `/data/` directory is the single mount point for all persistent storage. In Docker deployments, this is mapped to a host directory via a volume mount (see [Docker Configuration](#docker-volume-configuration)).

## SQLite Database

docsfy stores all project metadata in a single SQLite database at `/data/docsfy.db`. The database is accessed asynchronously using `aiosqlite` to avoid blocking the FastAPI event loop.

### Why SQLite?

SQLite is an ideal fit for docsfy because:

- **Zero configuration** — no external database server to set up or manage
- **Single-file storage** — the entire database is one portable file
- **Concurrent reads** — multiple API requests can query project status simultaneously
- **Lightweight** — minimal resource overhead for metadata-only workloads
- **Docker-friendly** — persists easily via a single volume mount

### What the Database Stores

The SQLite database tracks project-level metadata:

| Field | Description |
|-------|-------------|
| Project name | Unique identifier for the documentation project |
| Repository URL | The source GitHub repository (SSH or HTTPS) |
| Status | Current state: `generating`, `ready`, or `error` |
| Last generated timestamp | When documentation was last successfully built |
| Last commit SHA | The Git commit SHA from the most recent generation |
| Generation history | Logs from previous generation runs |

### Project Status Lifecycle

A project moves through the following statuses during its lifecycle:

```
POST /api/generate
       │
       v
  ┌────────────┐     success     ┌─────────┐
  │ generating │ ──────────────> │  ready   │
  └────────────┘                 └─────────┘
       │                              │
       │ failure                      │ re-generate
       v                              v
  ┌────────────┐                ┌────────────┐
  │   error    │                │ generating │
  └────────────┘                └────────────┘
```

### Querying Project Metadata

The database is the source of truth for the API status endpoints:

- **`GET /api/status`** — queries all projects and returns their current status
- **`GET /api/projects/{name}`** — returns detailed metadata for a specific project, including last generated timestamp, commit SHA, and page list
- **`DELETE /api/projects/{name}`** — removes the project record from the database *and* deletes the corresponding filesystem directory

> **Tip:** Use the `GET /api/status` endpoint to monitor the progress of documentation generation. The status field will transition from `generating` to `ready` (or `error`) when the pipeline completes.

### Commit SHA Tracking

The database stores the last commit SHA for each project to power incremental updates. When a re-generation is triggered:

1. docsfy fetches the repository and reads the current HEAD SHA
2. Compares it against the stored SHA in SQLite
3. If unchanged, the regeneration can be skipped entirely
4. If changed, the new SHA is stored after successful generation

This mechanism is described further in the [Incremental Updates](#incremental-updates) section below.

## Filesystem Storage

All documentation artifacts — plan files, cached markdown, and rendered HTML — are stored on the filesystem under `/data/projects/`. Each project gets its own isolated directory identified by name.

### Plan Files

**Location:** `/data/projects/{project-name}/plan.json`

The plan file is the output of **Stage 2: AI Planner** in the generation pipeline. It defines the entire documentation structure: pages, sections, and navigation hierarchy.

```json
{
  "pages": [
    {
      "name": "getting-started",
      "title": "Getting Started",
      "description": "Installation and initial setup guide"
    },
    {
      "name": "api-reference",
      "title": "API Reference",
      "description": "Complete API endpoint documentation"
    }
  ],
  "navigation": [
    { "title": "Getting Started", "path": "getting-started" },
    { "title": "API Reference", "path": "api-reference" }
  ]
}
```

The plan file serves multiple purposes:

- **Content generation** — Stage 3 iterates over the pages defined in the plan to generate markdown content
- **HTML rendering** — Stage 4 uses the plan to build navigation sidebars and page structure
- **Incremental updates** — on re-generation, the new plan is compared against the cached plan to determine which pages need updating

> **Note:** The `plan.json` file is generated by the AI and parsed using a multi-strategy JSON extraction approach: direct parse, brace-matching, markdown code block extraction, and regex recovery as a fallback.

### Cached Markdown Pages

**Location:** `/data/projects/{project-name}/cache/pages/*.md`

Each page defined in `plan.json` gets its own markdown file in the cache directory. These files are the raw output of **Stage 3: AI Content Generator**.

```
cache/
└── pages/
    ├── getting-started.md
    ├── api-reference.md
    ├── configuration.md
    └── deployment.md
```

Caching markdown separately from the rendered HTML provides several benefits:

- **Incremental regeneration** — only pages affected by repository changes need to be re-generated by the AI, while unchanged pages reuse their cached markdown
- **Re-rendering without AI** — if the HTML template or styles change, all pages can be re-rendered from cached markdown without re-invoking the AI CLI
- **Debugging** — the raw markdown can be inspected to verify AI output quality before rendering

> **Warning:** The cache directory should not be manually edited. Modifications will be overwritten on the next generation run. If you need to customize documentation content, consider post-processing the rendered HTML instead.

### Rendered HTML Sites

**Location:** `/data/projects/{project-name}/site/`

The site directory contains the final rendered static HTML, ready to be served or downloaded. It is the output of **Stage 4: HTML Renderer**, which converts cached markdown and the plan file into a polished documentation site using Jinja2 templates.

```
site/
├── index.html              # Landing page
├── getting-started.html    # Individual doc pages
├── api-reference.html
├── search-index.json       # Client-side search index
└── assets/
    ├── style.css           # Documentation theme styles
    ├── search.js           # Client-side search (lunr.js or similar)
    ├── theme-toggle.js     # Dark/light mode toggle
    └── highlight.js        # Code syntax highlighting
```

The rendered site includes these features:

- **Sidebar navigation** — built from the `plan.json` structure
- **Dark/light theme** — toggleable via `theme-toggle.js`
- **Client-side search** — powered by `search-index.json` and `search.js`
- **Code syntax highlighting** — via highlight.js
- **Responsive design** — works on desktop and mobile
- **Callout boxes** — note, warning, and info callouts

#### Serving the Site

The rendered HTML is served directly by the FastAPI application:

```
GET /docs/{project}/{path}
```

For example, to access the "Getting Started" page for a project called `my-app`:

```
GET /docs/my-app/getting-started.html
```

#### Downloading for Self-Hosting

The entire site can be downloaded as a `.tar.gz` archive for hosting elsewhere:

```
GET /api/projects/{name}/download
```

This packages the contents of the `site/` directory into a compressed archive that can be extracted and served by any static file server (Nginx, Apache, Cloudflare Pages, GitHub Pages, etc.).

## Incremental Updates

docsfy avoids expensive full regeneration when possible by tracking changes at both the repository and documentation structure levels.

The incremental update flow:

1. **Compare commit SHAs** — the current repository HEAD is checked against the SHA stored in SQLite from the last generation
2. **Re-run AI Planner** — if the repository has changed, Stage 2 re-analyzes the repo to produce an updated `plan.json`
3. **Compare plan structures** — the new plan is diffed against the cached `plan.json` to identify added, removed, or modified pages
4. **Selective page regeneration** — only pages whose source content may have been affected are regenerated by the AI
5. **Re-render HTML** — Stage 4 re-renders the full site from the (partially updated) cached markdown

```
Re-generate request
       │
       v
  Compare commit SHA
  (SQLite vs current)
       │
       ├── unchanged ──> skip (no-op)
       │
       └── changed
            │
            v
       Re-run AI Planner
            │
            v
       Compare plan.json
       (cached vs new)
            │
            ├── structure unchanged ──> regenerate affected pages only
            │
            └── structure changed ──> regenerate all pages
                                       │
                                       v
                                  Re-render HTML site
```

> **Tip:** Incremental updates are automatic. Simply call `POST /api/generate` with the same repository URL, and docsfy will determine the minimal set of work needed.

## Docker Volume Configuration

In Docker deployments, the `/data/` directory must be mounted as a persistent volume to survive container restarts.

From the `docker-compose.yaml`:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
      - ./cursor:/home/appuser/.config/cursor
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

| Volume Mount | Purpose |
|-------------|---------|
| `./data:/data` | Persistent storage for SQLite database and all project files |
| `~/.config/gcloud:.../:ro` | Google Cloud credentials for Vertex AI (read-only) |
| `./cursor:.../.config/cursor` | Cursor agent configuration |

> **Warning:** If the `/data` volume is not mounted, all generated documentation will be lost when the container is restarted. Always configure a persistent volume mount in production.

### File Permissions

The Docker container runs as a non-root user (`appuser`) with GID 0 for OpenShift compatibility. Ensure the host directory mapped to `/data` is writable by this user:

```bash
mkdir -p ./data
chmod 775 ./data
```

## Storage-Related API Reference

| Method | Endpoint | Storage Interaction |
|--------|----------|-------------------|
| `POST` | `/api/generate` | Creates project record in SQLite; writes `plan.json`, `cache/pages/*.md`, and `site/` to filesystem |
| `GET` | `/api/status` | Reads all project records from SQLite |
| `GET` | `/api/projects/{name}` | Reads project metadata from SQLite |
| `DELETE` | `/api/projects/{name}` | Deletes project record from SQLite; removes `/data/projects/{name}/` directory |
| `GET` | `/api/projects/{name}/download` | Reads `site/` directory; returns as `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serves static files from `site/` directory |

## Backup and Recovery

Because docsfy uses SQLite and the filesystem, backups are straightforward:

### Full Backup

Back up the entire `/data/` directory to capture both the database and all project files:

```bash
tar -czf docsfy-backup-$(date +%Y%m%d).tar.gz /data/
```

### Database-Only Backup

To back up just the project metadata:

```bash
sqlite3 /data/docsfy.db ".backup /backups/docsfy-$(date +%Y%m%d).db"
```

### Recovery

Restore from a full backup:

```bash
tar -xzf docsfy-backup-20260304.tar.gz -C /
```

> **Tip:** Since cached markdown and rendered HTML can always be regenerated from the source repository, a database-only backup is sufficient for disaster recovery — though regeneration will consume AI API credits.
