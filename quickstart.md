# Quickstart

Get docsfy running locally and generate your first AI-powered documentation site in minutes.

## Prerequisites

Before you begin, make sure you have the following installed on your machine:

- **Docker** (v20.10 or later) and **Docker Compose** (v2.0 or later)
- **Git** for cloning the docsfy repository
- An **API key** for at least one supported AI provider:
  - [Anthropic API key](https://console.anthropic.com/) for Claude
  - [Google AI API key](https://ai.google.dev/) for Gemini
  - [Cursor API key](https://cursor.com/) for Cursor Agent

> **Note:** docsfy uses AI CLI tools (Claude Code, Gemini CLI, or Cursor Agent) under the hood. The Docker image installs these automatically — you only need to provide the appropriate API credentials.

## Step 1: Clone the Repository

```bash
git clone https://github.com/myakove/docsfy.git
cd docsfy
```

## Step 2: Configure Environment Variables

Create a `.env` file from the provided example:

```bash
cp .env.example .env
```

Open `.env` in your editor and configure your AI provider credentials. At minimum, you need to set the provider and supply one set of API credentials:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Logging
LOG_LEVEL=INFO
```

Then uncomment and fill in the credentials for your chosen provider.

### Option A: Claude with API Key

```bash
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

### Option B: Claude with Vertex AI

```bash
AI_PROVIDER=claude
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
```

> **Note:** When using Vertex AI, the Docker Compose configuration mounts your local GCP credentials into the container at `~/.config/gcloud`. Make sure you have authenticated with `gcloud auth application-default login` before starting the service.

### Option C: Gemini

```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
```

### Option D: Cursor

```bash
AI_PROVIDER=cursor
CURSOR_API_KEY=your-cursor-api-key
```

> **Tip:** Start with Claude (`AI_PROVIDER=claude`) for the best results. It is the default provider and uses the `claude-opus-4-6[1m]` model, which produces high-quality documentation structure and content.

## Step 3: Start docsfy with Docker Compose

Build and launch the service:

```bash
docker compose up --build
```

Docker will:

1. Build the image from `python:3.12-slim` using a multi-stage build
2. Install system dependencies (git, curl, Node.js, npm)
3. Install AI CLI tools (Claude Code, Gemini CLI, Cursor Agent)
4. Install Python dependencies with `uv`
5. Start the FastAPI server on port **8000**

Wait for the health check to pass. You should see output indicating the server is ready:

```
docsfy-docsfy-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Verify the service is healthy:

```bash
curl http://localhost:8000/health
```

> **Tip:** Run in detached mode with `docker compose up --build -d` to free up your terminal. View logs anytime with `docker compose logs -f`.

## Step 4: Generate Your First Documentation Site

Trigger documentation generation for any GitHub repository by sending a POST request to the `/api/generate` endpoint:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/pallets/flask"}'
```

This kicks off the four-stage generation pipeline:

| Stage | What happens |
|-------|-------------|
| **Clone** | Shallow-clones the repository (`--depth 1`) to a temporary directory |
| **AI Planner** | AI analyzes the entire codebase and produces a `plan.json` with page structure, sections, and navigation |
| **AI Content Generator** | For each page in the plan, AI explores the repo and writes markdown content (pages run concurrently) |
| **HTML Renderer** | Converts markdown + plan into a polished static HTML site with Jinja2 templates |

> **Warning:** Generation can take several minutes depending on the size of the repository and your AI provider's response time. The `AI_CLI_TIMEOUT` setting (default: 60 minutes) controls how long each AI invocation is allowed to run.

## Step 5: Monitor Generation Progress

Check the status of all projects:

```bash
curl http://localhost:8000/api/status
```

The response lists each project and its current status — `generating`, `ready`, or `error`.

To get detailed information about a specific project:

```bash
curl http://localhost:8000/api/projects/flask
```

This returns metadata including the last generated timestamp, commit SHA, and list of generated pages.

## Step 6: View Your Documentation

Once generation is complete (status: `ready`), open your browser and navigate to:

```
http://localhost:8000/docs/flask/
```

The generated site includes:

- **Sidebar navigation** — auto-generated from the documentation structure
- **Dark/light theme toggle** — click to switch between themes
- **Full-text search** — client-side search powered by lunr.js across all pages
- **Syntax highlighting** — code blocks highlighted with highlight.js
- **Callout boxes** — info, note, and warning callouts for important content
- **Responsive design** — works on desktop and mobile

## Step 7: Download for Self-Hosting (Optional)

If you want to host the documentation site elsewhere (GitHub Pages, Netlify, S3, etc.), download the static HTML as a `.tar.gz` archive:

```bash
curl -O http://localhost:8000/api/projects/flask/download
```

Extract and serve with any static file server:

```bash
tar -xzf flask.tar.gz
cd flask/site
python -m http.server 3000
```

The site is fully self-contained — no server-side dependencies required.

## Docker Compose Volume Mounts

The `docker-compose.yaml` mounts three volumes:

```yaml
volumes:
  - ./data:/data                                        # Project data and SQLite database
  - ~/.config/gcloud:/home/appuser/.config/gcloud:ro    # GCP credentials (for Vertex AI)
  - ./cursor:/home/appuser/.config/cursor               # Cursor configuration
```

| Mount | Purpose |
|-------|---------|
| `./data:/data` | Persists generated documentation, cached markdown, and the SQLite database (`docsfy.db`) across container restarts |
| `~/.config/gcloud` | Read-only mount of GCP credentials for Claude via Vertex AI |
| `./cursor` | Cursor Agent configuration directory |

> **Note:** The `./data` directory is created automatically. It stores all project data in the following structure:
>
> ```
> data/
> ├── docsfy.db                    # SQLite metadata database
> └── projects/
>     └── flask/
>         ├── plan.json            # Documentation structure from AI
>         ├── cache/
>         │   └── pages/*.md       # Cached markdown (for incremental updates)
>         └── site/                # Final rendered HTML site
>             ├── index.html
>             ├── *.html
>             ├── search-index.json
>             └── assets/
>                 ├── style.css
>                 ├── search.js
>                 ├── theme-toggle.js
>                 └── highlight.js
> ```

## Regenerating Documentation

When a repository is updated, docsfy supports incremental regeneration. Send the same POST request again:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/pallets/flask"}'
```

docsfy compares the current commit SHA against the previously stored one. If changes are detected, it:

1. Re-runs the AI Planner to check for structural changes
2. Regenerates only the affected pages (or all pages if the structure changed)
3. Re-renders the HTML site

This saves significant time and API costs compared to a full regeneration.

## Removing a Project

To delete a project and all its generated documentation:

```bash
curl -X DELETE http://localhost:8000/api/projects/flask
```

## API Reference Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repository |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details and metadata |
| `DELETE` | `/api/projects/{name}` | Remove a project and its documentation |
| `GET` | `/api/projects/{name}/download` | Download the static site as `.tar.gz` |
| `GET` | `/docs/{project}/{path}` | Serve generated documentation pages |
| `GET` | `/health` | Health check endpoint |

## Troubleshooting

### Container fails to start

Check the logs for errors:

```bash
docker compose logs docsfy
```

Common causes:

- Missing or invalid `.env` file — ensure the file exists and has valid syntax
- Port 8000 already in use — stop the conflicting service or change the port mapping in `docker-compose.yaml`

### Generation fails with `error` status

Check the project details for error information:

```bash
curl http://localhost:8000/api/projects/<project-name>
```

Common causes:

- **Invalid API key** — verify your AI provider credentials in `.env`
- **Repository not accessible** — ensure the repo URL is correct and publicly accessible (or that git credentials are configured for private repos)
- **AI CLI timeout** — for very large repositories, increase `AI_CLI_TIMEOUT` in `.env`

### Health check fails

```bash
curl -v http://localhost:8000/health
```

If the health endpoint does not respond, the FastAPI server may not have started. Check the container logs for Python errors or missing dependencies.

> **Tip:** Set `LOG_LEVEL=DEBUG` in your `.env` file for more detailed output when troubleshooting.
