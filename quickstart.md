# Quickstart

Get docsfy running in under 5 minutes: install prerequisites, configure an AI provider, and generate your first documentation site.

## Prerequisites

Before you begin, make sure you have the following installed:

| Prerequisite | Version | Purpose |
|---|---|---|
| [Docker](https://docs.docker.com/get-docker/) | 20.10+ | Container runtime |
| [Docker Compose](https://docs.docker.com/compose/install/) | v2+ | Service orchestration |
| [Git](https://git-scm.com/) | 2.x+ | Repository cloning |

You also need credentials for at least one supported AI provider:

| Provider | What You Need |
|---|---|
| **Claude** (default) | Anthropic API key or Google Cloud Vertex AI credentials |
| **Gemini** | Google Gemini API key |
| **Cursor** | Cursor API key |

## 1. Clone the Repository

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
```

## 2. Configure Your AI Provider

Copy the example environment file and edit it with your credentials:

```bash
cp .env.example .env
```

Open `.env` in your editor and configure your chosen AI provider. The file contains settings for all three supported providers — you only need to configure one.

### Option A: Claude with API Key (Recommended)

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - API Key
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Logging
LOG_LEVEL=INFO
```

### Option B: Claude with Vertex AI

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Vertex AI
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
```

When using Vertex AI, your Google Cloud credentials are mounted into the container automatically via the Docker Compose volume mapping (`~/.config/gcloud`). Make sure you've already authenticated locally:

```bash
gcloud auth application-default login
```

### Option C: Gemini

```bash
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro

GEMINI_API_KEY=your-gemini-key-here
```

### Option D: Cursor

```bash
AI_PROVIDER=cursor

CURSOR_API_KEY=your-cursor-key-here
```

> **Tip:** You can change `AI_CLI_TIMEOUT` to increase or decrease the maximum time (in minutes) allowed for each AI CLI invocation. The default of `60` minutes is suitable for most repositories.

## 3. Start the Service

Launch docsfy with Docker Compose:

```bash
docker-compose up -d
```

This builds the container image (first run only) and starts the service. The container includes all three AI CLI tools pre-installed, so no additional setup is needed regardless of which provider you chose.

Verify the service is running:

```bash
curl http://localhost:8000/health
```

You should see a healthy response confirming the service is up.

> **Note:** The first build may take a few minutes as Docker installs system dependencies (git, Node.js, npm), the AI CLI tools (Claude Code, Gemini CLI, Cursor Agent), and Python packages.

## 4. Generate Your First Documentation Site

Send a `POST` request to start documentation generation for any GitHub repository:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo"}'
```

docsfy will:

1. **Clone** the repository (shallow clone for speed)
2. **Plan** — the AI analyzes the entire codebase and produces a `plan.json` defining pages, sections, and navigation
3. **Generate** — the AI writes markdown content for each page, exploring source code as needed
4. **Render** — markdown is converted to a polished static HTML site with sidebar navigation, dark/light theme toggle, search, and syntax highlighting

> **Warning:** Generation time depends on repository size and the AI model used. Small repositories typically complete in a few minutes; large codebases may take longer. Monitor progress with the status endpoint below.

## 5. Check Generation Status

Poll the status endpoint to monitor progress:

```bash
curl http://localhost:8000/api/status
```

Or check a specific project:

```bash
curl http://localhost:8000/api/projects/your-repo
```

The project status will be one of:

| Status | Meaning |
|---|---|
| `generating` | Documentation is being generated |
| `ready` | Generation complete — docs are available |
| `error` | Something went wrong — check logs |

## 6. View Your Documentation

Once the status shows `ready`, browse your generated docs at:

```
http://localhost:8000/docs/your-repo/
```

The generated site includes:

- **Sidebar navigation** with the full page hierarchy
- **Dark/light theme toggle** that respects your preference
- **Client-side search** across all documentation pages
- **Code syntax highlighting** powered by highlight.js
- **Responsive design** for desktop and mobile

## 7. Download for Self-Hosting (Optional)

If you want to host the generated docs on your own infrastructure (GitHub Pages, Netlify, S3, etc.), download the complete static site as a tarball:

```bash
curl -o docs.tar.gz http://localhost:8000/api/projects/your-repo/download
tar -xzf docs.tar.gz
```

The extracted `site/` directory contains pure static HTML, CSS, and JavaScript — no server required. Deploy it anywhere you serve static files.

## What's Inside the Generated Site

After generation, docsfy stores everything under `/data/projects/{project-name}/`:

```
/data/projects/your-repo/
  plan.json             # Documentation structure from AI
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # Final rendered HTML — this is what gets served
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

## Updating Documentation

When your repository changes, simply call the generate endpoint again:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/your-org/your-repo"}'
```

docsfy performs **incremental updates** automatically:

1. Compares the current commit SHA against the previously stored SHA
2. Re-runs the AI Planner only if the repository has changed
3. Regenerates only the pages affected by the changes
4. Skips regeneration entirely if the commit SHA hasn't changed

This makes subsequent runs significantly faster than the initial generation.

## Removing a Project

To delete a project and all its generated documentation:

```bash
curl -X DELETE http://localhost:8000/api/projects/your-repo
```

## Docker Compose Reference

Here is the full `docker-compose.yaml` for reference:

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

| Volume | Purpose |
|---|---|
| `./data:/data` | Persistent storage for the SQLite database and generated documentation |
| `~/.config/gcloud:ro` | Google Cloud credentials for Claude via Vertex AI (read-only) |
| `./cursor` | Cursor Agent configuration |

> **Tip:** If you're not using Vertex AI or Cursor, you can safely remove their respective volume mounts from the Compose file.

## Next Steps

- **API Reference** — explore all available endpoints and request/response schemas
- **Configuration** — fine-tune AI models, timeouts, and logging
- **Deployment** — run docsfy in production with reverse proxies and TLS
- **Incremental Updates** — set up webhooks for automatic regeneration on push
