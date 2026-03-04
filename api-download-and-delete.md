# Download & Delete

Once docsfy has generated your documentation site, you can download the complete static site as a portable archive or remove a project entirely when it is no longer needed.

## Download a Project

### `GET /api/projects/{name}/download`

Retrieves the generated documentation site as a `.tar.gz` archive. This allows you to host your docs anywhere — on a CDN, a static file server, or any hosting provider of your choice.

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | Yes | The project name as it appears in `/api/status` |

### Response

| Status Code | Content-Type | Description |
|-------------|--------------|-------------|
| `200` | `application/gzip` | The `.tar.gz` archive containing the full static site |
| `404` | `application/json` | Project not found |

### Example Request

```bash
curl -o my-project-docs.tar.gz \
  http://localhost:8000/api/projects/my-project/download
```

### Extracting the Archive

The archive contains the complete static site from the project's `site/` directory:

```bash
# Extract the downloaded archive
tar -xzf my-project-docs.tar.gz

# Preview the site locally
cd site/
python -m http.server 3000
```

### Archive Contents

The downloaded archive mirrors the generated site structure stored at `/data/projects/{project-name}/site/`:

```
site/
  index.html
  *.html
  assets/
    style.css
    search.js
    theme-toggle.js
    highlight.js
  search-index.json
```

| File / Directory | Description |
|------------------|-------------|
| `index.html` | Landing page for the documentation site |
| `*.html` | Individual documentation pages generated from the AI content pipeline |
| `assets/style.css` | Theme styles with dark/light mode support |
| `assets/search.js` | Client-side search powered by lunr.js |
| `assets/theme-toggle.js` | Dark/light theme switcher |
| `assets/highlight.js` | Code syntax highlighting |
| `search-index.json` | Pre-built search index for client-side search |

> **Tip:** The downloaded site is fully self-contained — no external dependencies or API calls are needed. You can serve it with any static file server (Nginx, Apache, Caddy, GitHub Pages, S3, etc.).

### Self-Hosting Examples

**Nginx:**

```nginx
server {
    listen 80;
    server_name docs.example.com;

    root /var/www/my-project-docs/site;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

**Docker (with Nginx):**

```bash
docker run -d -p 8080:80 \
  -v $(pwd)/site:/usr/share/nginx/html:ro \
  nginx:alpine
```

> **Note:** The download endpoint is only available for projects with a `ready` status. Projects that are still `generating` or in an `error` state cannot be downloaded. Check the project status first with `GET /api/projects/{name}`.

---

## Delete a Project

### `DELETE /api/projects/{name}`

Permanently removes a project and all of its associated data, including generated documentation, cached content, and database records.

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | Yes | The project name to delete |

### Response

| Status Code | Content-Type | Description |
|-------------|--------------|-------------|
| `200` | `application/json` | Project successfully deleted |
| `404` | `application/json` | Project not found |

### Example Request

```bash
curl -X DELETE http://localhost:8000/api/projects/my-project
```

### What Gets Deleted

Deleting a project removes **all** associated data from both the database and the filesystem.

**SQLite database** (`/data/docsfy.db`):

- Project name and repository URL
- Status information (`generating` / `ready` / `error`)
- Last generated timestamp and last commit SHA
- Generation history and logs

**Filesystem** (`/data/projects/{project-name}/`):

```
/data/projects/{project-name}/    <-- entire directory removed
  plan.json                       # documentation structure from AI planner
  cache/
    pages/*.md                    # cached AI-generated markdown pages
  site/                           # rendered HTML site
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

> **Warning:** This action is irreversible. All generated documentation, cached markdown pages, and the AI-generated plan will be permanently deleted. If you want to keep a copy of the generated site, use the [download endpoint](#download-a-project) before deleting.

### Verifying Deletion

After deleting a project, you can confirm it has been removed by listing all projects:

```bash
# List remaining projects
curl http://localhost:8000/api/status
```

The deleted project should no longer appear in the response.

---

## Common Workflows

### Download Then Delete

If you want to archive a project's documentation before cleaning it up:

```bash
PROJECT="my-project"

# 1. Download the generated site
curl -o "${PROJECT}-docs.tar.gz" \
  "http://localhost:8000/api/projects/${PROJECT}/download"

# 2. Verify the archive is valid
tar -tzf "${PROJECT}-docs.tar.gz" > /dev/null && echo "Archive OK"

# 3. Delete the project from docsfy
curl -X DELETE "http://localhost:8000/api/projects/${PROJECT}"
```

### Regenerate a Project

To regenerate documentation from scratch (e.g., after major repository changes), delete the existing project and trigger a new generation:

```bash
PROJECT="my-project"
REPO_URL="https://github.com/org/my-project"

# 1. Delete the existing project
curl -X DELETE "http://localhost:8000/api/projects/${PROJECT}"

# 2. Start a fresh generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d "{\"repo_url\": \"${REPO_URL}\"}"
```

> **Tip:** For minor repository updates, you don't need to delete and recreate. docsfy supports incremental updates — it tracks the last commit SHA and only regenerates pages affected by changes. Simply call `POST /api/generate` again with the same repository URL.
