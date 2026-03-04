# Quickstart

Get docsfy running locally, generate documentation for your first GitHub repository, and browse the results — all in under ten minutes.

## Prerequisites

Before you begin, make sure you have the following installed on your machine:

- **Docker** (v20.10+) and **Docker Compose** (v2+)
- **Git**
- An API key for at least one supported AI provider:

| Provider | Required Credential |
|----------|-------------------|
| Claude (default) | `ANTHROPIC_API_KEY` or Vertex AI credentials |
| Gemini | `GEMINI_API_KEY` |
| Cursor | `CURSOR_API_KEY` |

> **Note:** docsfy uses AI CLI tools under the hood to analyze your repository and generate documentation. You need valid credentials for whichever provider you choose.

## Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
```

## Step 2: Configure Environment Variables

Create a `.env` file in the project root. Start from the provided example:

```bash
cp .env.example .env
```

Open `.env` and configure your AI provider credentials. The simplest setup uses Claude with an API key:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Option 1: API Key
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Logging
LOG_LEVEL=INFO
```

> **Tip:** If you're using Google Cloud, you can authenticate Claude via Vertex AI instead of an API key:
>
> ```bash
> AI_PROVIDER=claude
> CLAUDE_CODE_USE_VERTEX=1
> CLOUD_ML_REGION=us-east5
> ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
> ```

### Using a Different Provider

To use Gemini or Cursor instead of Claude, set `AI_PROVIDER` and the corresponding API key:

```bash
# Gemini
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key

# Cursor
AI_PROVIDER=cursor
CURSOR_API_KEY=your-cursor-key
```

## Step 3: Create the Data Directory

docsfy persists all generated documentation and its SQLite database to a `data/` volume. Create it before starting the service:

```bash
mkdir -p data
```

This directory will contain:

```
data/
├── docsfy.db              # SQLite database (project metadata, status, history)
└── projects/              # Generated documentation per project
    └── {project-name}/
        ├── plan.json      # Documentation structure from AI planner
        ├── cache/
        │   └── pages/*.md # AI-generated markdown (cached for incremental updates)
        └── site/          # Final rendered static HTML
            ├── index.html
            ├── *.html
            └── assets/
```

## Step 4: Start docsfy with Docker Compose

Build and start the service:

```bash
docker compose up --build
```

The `docker-compose.yaml` defines the service as follows:

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

> **Note:** The `~/.config/gcloud` volume mount is only needed if you're authenticating Claude via Vertex AI. The `./cursor` mount is only needed for the Cursor provider. Both can be safely removed if unused.

Wait for the container to finish building and report a healthy status. You can verify the service is running:

```bash
curl http://localhost:8000/health
```

## Step 5: Generate Documentation for a Repository

With the service running, trigger documentation generation by sending a `POST` request with a GitHub repository URL:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/psf/requests"}'
```

This kicks off the four-stage generation pipeline:

1. **Clone** — Shallow-clones the repository (`--depth 1`)
2. **Plan** — The AI analyzes the codebase and produces a `plan.json` defining pages, sections, and navigation
3. **Generate** — The AI writes markdown content for each page (runs concurrently with semaphore-limited parallelism)
4. **Render** — Markdown is converted to polished static HTML using Jinja2 templates with sidebar navigation, dark/light theme, client-side search, and syntax highlighting

> **Warning:** Generation can take several minutes depending on repository size and AI provider response times. The default timeout is 60 minutes, configurable via the `AI_CLI_TIMEOUT` environment variable.

## Step 6: Check Generation Status

Monitor the progress of your documentation build:

```bash
curl http://localhost:8000/api/status
```

This returns a list of all projects and their current status (`generating`, `ready`, or `error`).

For details on a specific project:

```bash
curl http://localhost:8000/api/projects/requests
```

This shows the last generated timestamp, commit SHA, page list, and generation history.

## Step 7: View the Generated Documentation

Once the status shows `ready`, open your browser and navigate to:

```
http://localhost:8000/docs/requests/
```

You'll see a fully rendered documentation site with:

- **Sidebar navigation** with sections and pages
- **Dark/light theme** toggle
- **Client-side search** across all pages
- **Syntax-highlighted** code blocks
- **Responsive design** for mobile and desktop
- **Callout boxes** for notes, warnings, and info

## Downloading Documentation for Self-Hosting

If you want to host the generated docs on your own infrastructure (GitHub Pages, Netlify, S3, etc.), download the static site as a `.tar.gz` archive:

```bash
curl -O http://localhost:8000/api/projects/requests/download
```

Extract and serve with any static file server:

```bash
tar -xzf requests.tar.gz
cd requests/site
python -m http.server 3000
```

## Regenerating After Repository Changes

docsfy supports **incremental updates**. When you regenerate documentation for a repository that has already been built, it:

1. Fetches the latest code and compares the commit SHA against the previous build
2. Re-runs the AI planner to detect structural changes
3. Regenerates only the pages affected by code changes

Simply call the generate endpoint again:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/psf/requests"}'
```

> **Tip:** This is significantly faster than a full rebuild since unchanged pages are served from the markdown cache at `/data/projects/{name}/cache/pages/`.

## Removing a Project

To delete a project and all its generated documentation:

```bash
curl -X DELETE http://localhost:8000/api/projects/requests
```

## Running in the Background

For long-running or production use, start the service in detached mode:

```bash
docker compose up --build -d
```

View logs:

```bash
docker compose logs -f docsfy
```

Stop the service:

```bash
docker compose down
```

> **Note:** Generated documentation persists in the `./data` volume and survives container restarts. You won't lose your builds when stopping or restarting the service.

## API Reference (Quick Summary)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate` | Start documentation generation for a repo URL |
| `GET` | `/api/status` | List all projects and their generation status |
| `GET` | `/api/projects/{name}` | Get project details |
| `DELETE` | `/api/projects/{name}` | Remove a project and its docs |
| `GET` | `/api/projects/{name}/download` | Download static site as `.tar.gz` |
| `GET` | `/docs/{project}/{path}` | Serve generated documentation |
| `GET` | `/health` | Health check |

## Troubleshooting

### Container fails to start

Verify your `.env` file exists and contains valid credentials. Check the logs for specific errors:

```bash
docker compose logs docsfy
```

### Generation fails with timeout

Large repositories may exceed the default 60-minute timeout. Increase it in your `.env`:

```bash
AI_CLI_TIMEOUT=120
```

### Private repository access

docsfy uses system git credentials for cloning. To access private repositories, ensure your git SSH keys or HTTPS credentials are available inside the container. You may need to add an additional volume mount for your SSH keys:

```yaml
volumes:
  - ~/.ssh:/home/appuser/.ssh:ro
```

### Health check fails

Ensure port 8000 is not already in use on your host machine:

```bash
lsof -i :8000
```
