# Serving Documentation

Once docsfy has generated documentation for a repository, the built-in static file server makes it immediately available for browsing. This page covers how to access your generated documentation, navigate the site structure, switch between dark and light themes, and use client-side search to find content.

## Accessing Generated Documentation

Every project's documentation is served at a predictable URL path based on the project name:

```
GET /docs/{project}/{path}
```

For example, if you generated documentation for a project called `my-api`, the documentation is available at:

```
http://localhost:8000/docs/my-api/
```

The root path (`/docs/my-api/`) serves `index.html`, which is the landing page for the project's documentation. Individual pages are accessible as HTML files under the same base path:

```
http://localhost:8000/docs/my-api/              # Landing page (index.html)
http://localhost:8000/docs/my-api/getting-started.html
http://localhost:8000/docs/my-api/configuration.html
http://localhost:8000/docs/my-api/api-reference.html
```

> **Note:** Documentation is only available after the generation pipeline has completed all four stages (clone, plan, generate content, render HTML). Check the project status via `GET /api/projects/{name}` — the status must be `ready`.

### Verifying a Project Is Ready

Before attempting to browse documentation, confirm the project has finished generating:

```bash
curl http://localhost:8000/api/projects/my-api
```

A successful response includes the project status:

```json
{
  "name": "my-api",
  "status": "ready",
  "repo_url": "https://github.com/org/my-api",
  "last_generated": "2026-03-04T14:30:00Z",
  "last_commit_sha": "a1b2c3d..."
}
```

You can also list all projects and their statuses:

```bash
curl http://localhost:8000/api/status
```

> **Warning:** If the project status is `generating`, the documentation site may be incomplete or unavailable. If the status is `error`, generation failed and no documentation will be served.

## How the Static File Server Works

The FastAPI server maps the `/docs/{project}/{path}` route to files stored on the filesystem under `/data/projects/{project-name}/site/`. The rendered site directory has the following structure:

```
/data/projects/{project-name}/
  plan.json              # Documentation structure from AI planner
  cache/
    pages/*.md           # AI-generated markdown (cached for incremental updates)
  site/                  # Final rendered HTML (served by the file server)
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

When a request arrives at `/docs/my-api/getting-started.html`, the server reads and returns the file at `/data/projects/my-api/site/getting-started.html`. Static assets (CSS, JavaScript, images) under the `assets/` directory are also served through this same mechanism.

### Docker Volume Mapping

When running docsfy with Docker Compose, the `/data` directory is mapped to a local `./data` volume, making generated sites persistent across container restarts:

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

> **Tip:** You can inspect the generated site files directly on disk at `./data/projects/{project-name}/site/` for debugging or to copy them to another web server.

## Downloading Documentation for Self-Hosting

If you prefer to host documentation on your own infrastructure (Nginx, GitHub Pages, S3, etc.), you can download the entire rendered site as a `.tar.gz` archive:

```bash
curl -O http://localhost:8000/api/projects/my-api/download
```

This downloads the contents of `/data/projects/my-api/site/` as a compressed archive that can be extracted and served by any static file server.

## Navigation

The documentation site features a **sidebar navigation** that reflects the hierarchical structure defined during the AI planning stage. The navigation is generated from `plan.json`, which the AI Planner (Stage 2 of the pipeline) creates after analyzing the repository.

### How Navigation Is Built

1. The AI Planner analyzes the repository and produces `plan.json`, containing pages, sections, and the navigation hierarchy.
2. The HTML Renderer (Stage 4) uses **Jinja2 templates** to render each page with a consistent sidebar navigation derived from this plan.
3. Every page includes the full sidebar, so navigation is available without any server-side rendering at browse time.

### Navigation Features

The rendered documentation includes:

- **Sidebar navigation** — A persistent side panel listing all pages organized by sections and sub-sections. The current page is highlighted for context.
- **Responsive design** — The sidebar collapses on smaller screens and can be toggled with a menu button, ensuring usability on mobile devices and tablets.
- **Card layouts** — The landing page and section index pages may use card-based layouts to provide visual entry points into different areas of the documentation.
- **Callout boxes** — Content pages support note, warning, and info callout styles to highlight important information.

### Page Structure

Each generated HTML page includes:

| Element | Description |
|---------|-------------|
| Sidebar | Hierarchical navigation of all documentation pages |
| Main content area | The rendered documentation for the current page |
| Theme toggle | Switch between dark and light appearance |
| Search | Client-side full-text search across all pages |
| Code blocks | Syntax-highlighted code examples via highlight.js |

## Dark/Light Theme Toggle

Every generated documentation site includes a theme toggle that lets readers switch between dark and light color schemes. The toggle is implemented entirely on the client side — no server round-trips required.

### How It Works

The theme system consists of two bundled assets:

- **`assets/style.css`** — Contains CSS custom properties (variables) for both light and dark themes. The active theme is determined by a class or data attribute on the document root.
- **`assets/theme-toggle.js`** — Client-side JavaScript that handles the toggle interaction, applies the selected theme, and persists the user's preference.

When a user clicks the theme toggle:

1. `theme-toggle.js` switches the active theme class on the `<html>` or `<body>` element.
2. CSS custom properties update all colors — backgrounds, text, borders, code blocks, navigation — in a single cascade.
3. The user's preference is saved to `localStorage`, so it persists across page loads and browsing sessions.

> **Tip:** The theme toggle respects the user's system preference on first visit. If the operating system is set to dark mode, the documentation loads in dark mode by default.

### Theme Scope

The theme applies consistently across all visual elements:

- Page backgrounds and text colors
- Sidebar navigation styling
- Code syntax highlighting (highlight.js adapts to the active theme)
- Search overlay and results
- Callout boxes (note, warning, info)
- Links, borders, and interactive elements

## Client-Side Search

Generated documentation sites include a full-text search feature that runs entirely in the browser. There is no server-side search endpoint — all indexing and querying happens on the client.

### Search Architecture

The search system has two components:

| Component | File | Purpose |
|-----------|------|---------|
| Search index | `search-index.json` | Pre-built index containing the searchable content of every page |
| Search script | `assets/search.js` | Client-side JavaScript that loads the index and handles queries |

The search implementation uses **lunr.js** (or a similar lightweight client-side search library) to provide fast, full-text search without requiring a backend.

### How Search Works

1. **Index generation** — During the HTML rendering stage (Stage 4), the renderer builds `search-index.json` from the content of all generated pages. This index includes page titles, section headings, and body text.

2. **Index loading** — When a user opens any documentation page, `search.js` fetches `search-index.json` and loads it into memory. The index is typically small enough to load instantly for most project sizes.

3. **Query execution** — As the user types a search query, the script queries the in-memory index and displays matching results in real time. Results include page titles and relevant content snippets.

4. **Navigation** — Clicking a search result navigates directly to the matching page, with the relevant section scrolled into view where possible.

### Using Search

The search input is accessible from any page in the documentation. To search:

1. Click the search input field or use a keyboard shortcut (if configured).
2. Type your query — results appear as you type.
3. Click a result to navigate to that page.

> **Note:** Search operates on the pre-built index, so it only includes content that was present when the documentation was last generated. If you regenerate documentation after repository changes, the search index is rebuilt automatically.

### Search Index Contents

The `search-index.json` file is stored alongside the HTML pages at:

```
/data/projects/{project-name}/site/search-index.json
```

It is also accessible via the documentation URL:

```
http://localhost:8000/docs/my-api/search-index.json
```

## Code Syntax Highlighting

All code blocks in the generated documentation are syntax-highlighted using **highlight.js**, which is bundled as `assets/highlight.js`. The highlighting:

- Supports a wide range of programming languages automatically
- Adapts to the active theme (dark or light) for readable code in any color scheme
- Requires no configuration — language detection is automatic based on code content and any language hints in the source markdown

## Putting It All Together

Here is a typical workflow for generating and serving documentation:

```bash
# 1. Start the docsfy server
docker compose up -d

# 2. Verify the server is healthy
curl http://localhost:8000/health

# 3. Generate documentation for a repository
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/my-api"}'

# 4. Check generation status
curl http://localhost:8000/api/status

# 5. Browse documentation once status is "ready"
# Open in browser: http://localhost:8000/docs/my-api/

# 6. Optionally download for self-hosting
curl -o my-api-docs.tar.gz \
  http://localhost:8000/api/projects/my-api/download
```

## Incremental Updates

When a repository changes, you don't need to regenerate the entire documentation site. docsfy tracks the last commit SHA per project in its SQLite database. On re-generation:

1. The repository is fetched and the current commit SHA is compared against the stored SHA.
2. If changes are detected, the AI Planner re-evaluates whether the documentation structure needs updating.
3. Only pages affected by the changes are regenerated.
4. The search index (`search-index.json`) is rebuilt to reflect the updated content.

This means the served documentation at `/docs/{project}/` is automatically updated in place — no restart or redeployment needed.

> **Tip:** Regenerate documentation for a project by calling `POST /api/generate` again with the same repository URL. docsfy will detect it as an existing project and perform an incremental update.
