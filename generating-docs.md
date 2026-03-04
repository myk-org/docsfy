# Generating Documentation

This guide covers how to trigger documentation generation for a GitHub repository, monitor its progress through the pipeline, and access the finished site.

## Prerequisites

Before generating documentation, ensure docsfy is running and your AI provider is configured. See the [Configuration](configuration.md) page for details on setting up your `.env` file.

Verify the service is healthy:

```bash
curl http://localhost:8000/health
```

## Triggering Generation

### Start a Generation Request

To generate documentation for a repository, send a `POST` request to the `/api/generate` endpoint with the repository URL:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo.git"}'
```

Both HTTPS and SSH URLs are supported:

```bash
# HTTPS (public or private with token)
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo.git"}'

# SSH (private repos using system git credentials)
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "git@github.com:your-org/your-repo.git"}'
```

> **Note:** Private repositories require valid git credentials on the host system. When running in Docker, mount your SSH keys or configure git credential helpers appropriately.

### What Happens During Generation

The generation pipeline runs four sequential stages:

```
Clone Repository ──> AI Planner ──> AI Content Generator ──> HTML Renderer
                    (plan.json)     (concurrent pages)       (static site)
```

**Stage 1: Clone Repository** — Performs a shallow clone (`--depth 1`) of the repository to a temporary directory. This keeps the clone fast and lightweight regardless of repository history.

**Stage 2: AI Planner** — The configured AI CLI explores the entire cloned repository and produces a `plan.json` file defining the documentation structure — pages, sections, and navigation hierarchy.

**Stage 3: AI Content Generator** — For each page defined in `plan.json`, the AI CLI runs with full access to the cloned repository. Pages are generated concurrently using async execution with semaphore-limited concurrency. Each page is output as a Markdown file and cached for incremental updates.

**Stage 4: HTML Renderer** — Converts the Markdown pages and `plan.json` into a polished static HTML site using Jinja2 templates with bundled CSS/JS assets. The finished site includes sidebar navigation, dark/light theme toggle, client-side search, and code syntax highlighting.

> **Tip:** Page generation in Stage 3 runs concurrently, so repositories with many documentation pages benefit from parallelism. The semaphore prevents overwhelming system resources.

## Monitoring Progress

### List All Projects

Check the status of all projects with the `/api/status` endpoint:

```bash
curl http://localhost:8000/api/status
```

This returns a list of all projects and their current generation status.

### Get Project Details

For detailed information about a specific project, use the `/api/projects/{name}` endpoint:

```bash
curl http://localhost:8000/api/projects/your-repo
```

The response includes:

| Field | Description |
|-------|-------------|
| Project name | Derived from the repository name |
| Status | `generating`, `ready`, or `error` |
| Last generated | Timestamp of the most recent generation |
| Last commit SHA | The commit SHA that was used for generation |
| Pages | List of generated documentation pages |
| Generation history | Log of past generation runs |

### Project Status Values

| Status | Meaning |
|--------|---------|
| `generating` | The pipeline is currently running |
| `ready` | Documentation has been generated and is available |
| `error` | Generation failed — check the logs for details |

> **Warning:** Generation can take several minutes depending on repository size and the configured `AI_CLI_TIMEOUT` (default: 60 minutes). Large repositories with many pages will take longer due to multiple AI CLI invocations.

## Accessing Generated Documentation

### Browse in the Browser

Once a project's status is `ready`, the generated documentation is served directly by docsfy:

```
http://localhost:8000/docs/{project-name}/
```

For example, if you generated docs for a repository named `my-api`:

```
http://localhost:8000/docs/my-api/
```

The static site includes:

- Sidebar navigation based on the AI-generated plan
- Dark/light theme toggle
- Client-side search powered by a generated `search-index.json`
- Syntax-highlighted code blocks via highlight.js
- Responsive design for mobile and desktop

### Download for Self-Hosting

To download the entire static site as a `.tar.gz` archive:

```bash
curl -O http://localhost:8000/api/projects/your-repo/download
```

This gives you a portable archive you can host on any static file server — GitHub Pages, Netlify, S3, Nginx, or anywhere else that serves HTML.

```bash
# Extract and serve locally
tar -xzf your-repo.tar.gz
cd your-repo/site
python -m http.server 3000
```

## Regenerating Documentation

### Incremental Updates

When you re-trigger generation for a repository that has already been generated, docsfy performs an incremental update:

1. The repository is fetched and the current commit SHA is compared against the stored SHA
2. If the repository has changed, the AI Planner re-runs to check if the documentation structure has changed
3. Only pages whose content may be affected are regenerated
4. If the plan structure is unchanged and only specific files changed, only the relevant pages are regenerated

```bash
# Re-trigger generation — docsfy handles incrementality automatically
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo.git"}'
```

> **Tip:** Incremental updates are significantly faster than full regeneration since cached Markdown files at `/data/projects/{name}/cache/pages/*.md` are reused when possible.

### Force Full Regeneration

To start fresh, delete the project first, then regenerate:

```bash
# Delete existing project
curl -X DELETE http://localhost:8000/api/projects/your-repo

# Generate from scratch
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo.git"}'
```

> **Warning:** Deleting a project removes all generated documentation, cached Markdown files, and metadata. This action cannot be undone.

## Storage Layout

Understanding where docsfy stores files helps with debugging and backups:

```
/data/
├── docsfy.db                              # SQLite metadata database
└── projects/
    └── {project-name}/
        ├── plan.json                      # Documentation structure from AI
        ├── cache/
        │   └── pages/
        │       ├── getting-started.md     # Cached AI-generated markdown
        │       ├── api-reference.md
        │       └── *.md
        └── site/                          # Final rendered HTML output
            ├── index.html
            ├── getting-started.html
            ├── api-reference.html
            ├── assets/
            │   ├── style.css
            │   ├── search.js
            │   ├── theme-toggle.js
            │   └── highlight.js
            └── search-index.json
```

When running with Docker, the `/data` directory is persisted via a volume mount as defined in the `docker-compose.yaml`:

```yaml
volumes:
  - ./data:/data
```

## API Reference Summary

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository URL |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details, history, and logs |
| `DELETE` | `/api/projects/{name}` | Remove a project and all its generated docs |
| `GET` | `/api/projects/{name}/download` | Download the static site as a `.tar.gz` archive |
| `GET` | `/docs/{project}/{path}` | Serve generated static HTML documentation |
| `GET` | `/health` | Health check endpoint |

## Troubleshooting

### Generation Stuck in `generating` Status

Check that the AI CLI is available and properly configured. docsfy performs an availability check before starting generation by sending a lightweight prompt. Verify your AI provider is reachable:

```bash
# For Claude
claude --model claude-opus-4-6 --dangerously-skip-permissions -p "Hi"

# For Gemini
gemini --model gemini-2.5-pro --yolo "Hi"

# For Cursor
agent --force --model claude-opus-4-6 --print --workspace /tmp "Hi"
```

### Generation Fails with `error` Status

Retrieve the project details to inspect the logs:

```bash
curl http://localhost:8000/api/projects/your-repo
```

Common causes include:

- **AI CLI not installed** — Ensure the AI CLI binary is on the system PATH
- **Invalid credentials** — Check that your API keys or Vertex AI credentials are configured in `.env`
- **Timeout** — Increase `AI_CLI_TIMEOUT` in your `.env` file (default is 60 minutes)
- **Repository access denied** — Verify git credentials for private repositories

### No Pages Generated

If the AI Planner produces an empty or invalid `plan.json`, the content generator has nothing to work with. This can happen with very small repositories or those with minimal code. Check the plan file at `/data/projects/{name}/plan.json` to inspect the generated structure.
