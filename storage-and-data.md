# Storage & Data

docsfy uses a dual-storage architecture: **SQLite** for project metadata and **the filesystem** for generated documentation artifacts. Both live under the `/data` directory, making backups and container volume mounts straightforward.

```
/data/
├── docsfy.db              # SQLite database (metadata)
└── projects/              # Filesystem (generated docs)
    ├── my-api/
    ├── frontend-sdk/
    └── ...
```

> **Note:** The entire `/data` directory is mounted as a Docker volume, so all project data persists across container restarts.

## Volume Configuration

The `docker-compose.yaml` maps a local `./data` directory into the container at `/data`:

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

The `/data` volume holds both the SQLite database and all generated project files. The other volume mounts (`gcloud`, `cursor`) provide AI provider credentials and are read-only where possible.

---

## SQLite Database

### Location

```
/data/docsfy.db
```

docsfy uses SQLite via `aiosqlite` for async-compatible database operations within the FastAPI application. SQLite was chosen for its zero-configuration setup, single-file portability, and suitability for the single-writer workload that docsfy produces.

### Schema

The database stores project metadata — not the documentation content itself. It tracks:

| Field | Description |
|-------|-------------|
| **Project name** | Unique identifier derived from the repository |
| **Repository URL** | The source GitHub repo (SSH or HTTPS) |
| **Status** | Current generation state |
| **Last generated timestamp** | When documentation was last built |
| **Last commit SHA** | The Git commit the docs were generated from |
| **Generation history** | Log of past generation runs |

### Project Status Values

A project transitions through three statuses during its lifecycle:

| Status | Meaning |
|--------|---------|
| `generating` | Pipeline is actively running (clone, plan, generate, render) |
| `ready` | Documentation has been generated and is available for serving |
| `error` | Generation failed — check generation logs for details |

### Database Operations

The API endpoints map directly to CRUD operations on the database:

| Endpoint | Operation | Description |
|----------|-----------|-------------|
| `POST /api/generate` | **Create / Update** | Inserts a new project record or updates an existing one; sets status to `generating` |
| `GET /api/status` | **Read** | Lists all projects with their current status |
| `GET /api/projects/{name}` | **Read** | Returns full project details including last commit SHA and page list |
| `DELETE /api/projects/{name}` | **Delete** | Removes the project record *and* its filesystem artifacts |

> **Warning:** `DELETE /api/projects/{name}` removes both the database record and the entire project directory under `/data/projects/{name}/`. This action is irreversible.

---

## Filesystem Storage

### Directory Structure

Each project gets its own directory under `/data/projects/`. The directory name matches the project name stored in SQLite.

```
/data/projects/{project-name}/
├── plan.json                # Documentation structure from AI planning stage
├── cache/
│   └── pages/
│       ├── getting-started.md
│       ├── installation.md
│       ├── api-reference.md
│       └── ...              # One markdown file per documentation page
└── site/                    # Final rendered static HTML site
    ├── index.html
    ├── getting-started.html
    ├── installation.html
    ├── api-reference.html
    ├── assets/
    │   ├── style.css        # Theme styles (dark/light mode)
    │   ├── search.js        # Client-side search logic
    │   ├── theme-toggle.js  # Dark/light theme switcher
    │   └── highlight.js     # Code syntax highlighting
    └── search-index.json    # Pre-built search index
```

### The Three Layers

The filesystem stores three distinct layers of data, each produced by a different pipeline stage:

#### 1. `plan.json` — Documentation Blueprint

Created by the **AI Planner** stage. Contains the documentation structure: pages, sections, navigation hierarchy, and ordering. This file drives both content generation and HTML rendering.

The AI CLI runs with `cwd` set to the cloned repository, giving it full access to explore the codebase and determine what documentation pages to create.

#### 2. `cache/pages/*.md` — Generated Markdown

Created by the **AI Content Generator** stage. One markdown file per page defined in `plan.json`. These files are cached to support incremental updates — if a page doesn't need regeneration, its cached markdown is reused.

Pages can be generated concurrently using async execution with semaphore-limited concurrency:

```python
# Pages generated via AI CLI subprocess calls
# Async execution via asyncio.to_thread(subprocess.run, ...)
# Returns tuple[bool, str] (success, output)
```

#### 3. `site/` — Rendered HTML

Created by the **HTML Renderer** stage. The final static site built from `plan.json` + cached markdown using Jinja2 templates and bundled CSS/JS assets.

This is what gets served at `GET /docs/{project}/{path}` and packaged for download at `GET /api/projects/{name}/download` (as a `.tar.gz` archive).

> **Tip:** You can download any project's static site as a tar.gz archive via the `/api/projects/{name}/download` endpoint and host it anywhere — no docsfy server required.

---

## How Data Flows Through the Pipeline

The generation pipeline produces data in four sequential stages. Each stage writes to a specific part of the storage hierarchy:

```
POST /api/generate (repo URL)
        │
        ▼
┌─────────────────┐
│  Stage 1: Clone │──▶ Temporary directory (cleaned up after pipeline)
│  Repository     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Stage 2: AI    │──▶ /data/projects/{name}/plan.json
│  Planner        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Stage 3: AI    │──▶ /data/projects/{name}/cache/pages/*.md
│  Content Gen    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Stage 4: HTML  │──▶ /data/projects/{name}/site/
│  Renderer       │
└─────────────────┘
         │
         ▼
  SQLite status ──▶ "ready"
```

At each stage, the project's status in SQLite is `generating`. Once the pipeline completes successfully, the status is updated to `ready`. If any stage fails, the status is set to `error`.

---

## Incremental Updates

docsfy avoids regenerating entire documentation sites by tracking changes at the Git commit level. The incremental update strategy ties together both storage systems:

1. **SHA comparison** — The last commit SHA is stored in SQLite. On re-generation, docsfy fetches the repository and compares the current HEAD SHA against the stored SHA.

2. **Plan diffing** — If the SHA has changed, the AI Planner runs again to check whether the documentation structure has changed.

3. **Selective regeneration** — Only pages whose content may be affected by the code changes are regenerated. Unchanged pages reuse their cached markdown from `cache/pages/`.

4. **Skip entirely** — If the plan structure is unchanged and no relevant files changed, regeneration is skipped altogether.

```
Re-generate request
        │
        ▼
  Compare HEAD SHA with stored SHA
        │
   ┌────┴────┐
   │ Same    │ Different
   │         ▼
   │    Re-run AI Planner
   │         │
   │    ┌────┴────┐
   │    │ Plan    │ Plan
   │    │ same    │ changed
   │    │         ▼
   │    │    Regenerate affected pages
   │    ▼
   │    Regenerate only changed pages
   ▼
  Skip (no-op)
```

> **Note:** The cached markdown files in `cache/pages/` are the key to incremental updates. Deleting this directory forces a full regeneration of all pages on the next run.

---

## Relationship Between SQLite and Filesystem

The two storage systems serve complementary purposes:

| Concern | SQLite (`docsfy.db`) | Filesystem (`projects/`) |
|---------|---------------------|-------------------------|
| **What it stores** | Metadata about projects | Actual documentation content |
| **Query patterns** | List projects, check status, get commit SHA | Serve HTML, download archives |
| **Size** | Small (KB) | Large (MB per project) |
| **Access pattern** | Random read/write | Sequential write, random read |
| **Backup strategy** | Copy single file | Copy directory tree |

The project name acts as the join key between the two systems: the `name` column in SQLite corresponds to the directory name under `/data/projects/`.

---

## Serving Generated Documentation

The rendered HTML in `site/` is served directly by FastAPI as static files:

| Endpoint | Source |
|----------|--------|
| `GET /docs/{project}/{path}` | `/data/projects/{project}/site/{path}` |
| `GET /api/projects/{name}/download` | `/data/projects/{name}/site/` packaged as `.tar.gz` |

The static site includes all assets (CSS, JS, search index) needed to run independently. Downloaded archives can be deployed to any static hosting provider without modification.

---

## Backup and Recovery

Since all data lives under `/data`, backup is straightforward:

```bash
# Full backup — captures both database and all project files
cp -r /data /backup/docsfy-$(date +%Y%m%d)

# Database-only backup
cp /data/docsfy.db /backup/docsfy-db-$(date +%Y%m%d).db

# Single project backup
tar czf my-project-backup.tar.gz /data/projects/my-project/
```

> **Tip:** Since SQLite is a single file, you can also use `sqlite3 /data/docsfy.db ".backup /backup/docsfy.db"` for a safe online backup that handles write-ahead log (WAL) files correctly.

To restore, stop the container, replace the `/data` directory (or specific files), and restart:

```bash
docker compose down
cp -r /backup/docsfy-20260304/ ./data
docker compose up -d
```

> **Warning:** Always stop the docsfy container before restoring the SQLite database to avoid corruption from concurrent writes.
