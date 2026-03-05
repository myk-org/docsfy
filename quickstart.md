# Quickstart

Generate your first documentation site in minutes. This guide walks you through starting the docsfy server, sending a generate request with a GitHub repository URL, and viewing the rendered documentation.

## Prerequisites

Before you begin, make sure you have:

- **Docker** and **Docker Compose** installed (recommended), _or_ **Python 3.12+** with [uv](https://docs.astral.sh/uv/) installed
- **An AI provider API key** — at least one of:
  - [Anthropic API key](https://console.anthropic.com/) for Claude
  - [Google API key](https://aistudio.google.com/) for Gemini
  - [Cursor API key](https://cursor.com/) for Cursor

## Step 1: Clone and Configure

Clone the repository and set up your environment:

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
```

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Open `.env` and configure your AI provider credentials. At minimum, set the API key for your chosen provider:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Option 1: API Key
ANTHROPIC_API_KEY=sk-ant-...

# Claude - Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=
# ANTHROPIC_VERTEX_PROJECT_ID=

# Gemini
# GEMINI_API_KEY=

# Cursor
# CURSOR_API_KEY=

# Logging
LOG_LEVEL=INFO
```

> **Tip:** The `[1m]` suffix in the model name `claude-opus-4-6[1m]` specifies a 1 million token context window — this is a valid model identifier, not a typo.

## Step 2: Start the Server

### With Docker (recommended)

```bash
docker compose up
```

This builds the container image, installs all three AI CLIs (Claude, Cursor, Gemini), and starts the server. Your generated documentation persists in the `./data` volume on the host.

```yaml
# docker-compose.yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Without Docker

```bash
uv sync
uv run docsfy
```

> **Note:** When running without Docker, you must have at least one AI CLI installed on your system. Install Claude Code with `curl -fsSL https://claude.ai/install.sh | bash`, Gemini CLI with `npm install -g @google/gemini-cli`, or Cursor Agent with `curl -fsSL https://cursor.com/install | bash`.

The server starts on **http://localhost:8000** by default. Verify it's running:

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok"}
```

## Step 3: Generate Documentation

Send a POST request to `/api/generate` with a GitHub repository URL:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/fastapi/fastapi"}'
```

The server responds immediately with a `202 Accepted` status while generation runs in the background:

```json
{"project": "fastapi", "status": "generating"}
```

The project name is derived automatically from the repository URL — `https://github.com/fastapi/fastapi` becomes `fastapi`.

> **Note:** Generation is an asynchronous process. Depending on repository size and complexity, it can take several minutes. The AI clones the repository, plans the documentation structure, then generates each page with full codebase context.

### What happens behind the scenes

1. **Clone** — The repository is shallow-cloned (`git clone --depth 1`) into a temporary directory
2. **Plan** — The AI analyzes the entire codebase and produces a documentation plan with navigation groups and page definitions
3. **Generate** — Up to 5 pages are generated concurrently, each with full repository context available to the AI
4. **Render** — Markdown pages are converted to a polished static HTML site with navigation, search, syntax highlighting, and theme support

## Step 4: Check Generation Status

Poll the status endpoint to see when generation completes:

```bash
curl http://localhost:8000/api/status
```

```json
{
  "projects": [
    {
      "name": "fastapi",
      "repo_url": "https://github.com/fastapi/fastapi",
      "status": "ready",
      "last_commit_sha": "abc123def456...",
      "last_generated": "2026-03-05T12:00:00",
      "page_count": 12
    }
  ]
}
```

The `status` field transitions through these states:

| Status | Meaning |
|---|---|
| `generating` | Documentation is being created |
| `ready` | Generation complete — docs are available to view |
| `error` | Something went wrong — check `error_message` for details |

For more detail on a specific project, use the project endpoint:

```bash
curl http://localhost:8000/api/projects/fastapi
```

## Step 5: View Your Documentation

Once the status shows `ready`, open the documentation in your browser:

```
http://localhost:8000/docs/fastapi/
```

The generated site includes:

- Sidebar navigation organized by topic groups
- Dark and light theme toggle
- Full-text client-side search
- Syntax-highlighted code blocks with copy buttons
- Previous/Next page navigation
- Table of contents for each page
- GitHub repository link with star count

### Download for self-hosting

You can also download the entire site as a portable archive to deploy on any static hosting provider:

```bash
curl -o fastapi-docs.tar.gz http://localhost:8000/api/projects/fastapi/download
tar -xzf fastapi-docs.tar.gz
```

The extracted directory contains a fully self-contained static site (HTML, CSS, JS) ready to deploy to GitHub Pages, Netlify, Vercel, or any web server. It also includes `llms.txt` and `llms-full.txt` files for LLM-friendly consumption.

## Additional Options

### Use a different AI provider

Override the default AI provider and model per request:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/repo",
    "ai_provider": "gemini",
    "ai_model": "gemini-2.0-flash-exp"
  }'
```

Supported providers: `claude`, `gemini`, `cursor`.

### Generate from a local repository

If you have a repository on disk, pass `repo_path` instead of `repo_url`:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/your/repo"}'
```

> **Warning:** Provide either `repo_url` or `repo_path`, not both. The request will be rejected if both are set.

### Force regeneration

By default, docsfy caches generated pages and skips regeneration if the repository hasn't changed (same commit SHA). To force a full regeneration and clear the cache:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/repo", "force": true}'
```

### Delete a project

Remove a project and all its generated files:

```bash
curl -X DELETE http://localhost:8000/api/projects/fastapi
```

```json
{"deleted": "fastapi"}
```

## Configuration Reference

All settings can be configured via environment variables in your `.env` file:

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `claude` | AI provider (`claude`, `gemini`, or `cursor`) |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier |
| `AI_CLI_TIMEOUT` | `60` | AI generation timeout in minutes |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATA_DIR` | `/data` | Directory for database and generated sites |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Enable auto-reload for development |

## Next Steps

- Explore the interactive API docs at **http://localhost:8000/docs** (auto-generated by FastAPI)
- Check the generated `llms.txt` file at `http://localhost:8000/docs/{project}/llms.txt` for an LLM-friendly index of the documentation
- Set `LOG_LEVEL=DEBUG` in your `.env` for detailed generation logs
