# docsfy

AI-powered documentation generator that creates Mintlify-quality static HTML docs from GitHub repositories using Claude Code, Gemini CLI, or Cursor Agent CLI.

## Features

- Generates polished static HTML documentation from any GitHub repository
- AI-powered content generation using Claude Code, Gemini CLI, or Cursor Agent CLI
- Dark/light theme with system preference detection
- Client-side search with Cmd+K / Ctrl+K modal
- "On this page" table of contents with scroll spy
- Prev/Next page navigation
- Code syntax highlighting with copy buttons and language labels
- Callout boxes (Note, Warning, Tip)
- `llms.txt` and `llms-full.txt` generation for LLM-friendly documentation
- GitHub star count badge
- Incremental updates -- only regenerates when the repository commit SHA changes
- Force regeneration option to bypass cache
- Download generated docs as `tar.gz` for self-hosting anywhere
- Containerized with all AI CLIs pre-installed (Claude Code, Gemini, Cursor)

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
cp .env.example .env
# Edit .env with your AI provider credentials (see Configuration below)
docker compose up --build
```

Generate documentation for a repository:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/fastapi/fastapi"}'
```

Browse the generated docs at `http://localhost:8000/docs/fastapi/`.

### Local Development

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
uv sync --extra dev
cp .env.example .env
# Edit .env with your AI provider credentials
uv run docsfy
```

The server starts on `http://localhost:8000`.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/generate` | Start documentation generation |
| `GET` | `/api/status` | List all projects and their statuses |
| `GET` | `/api/projects/{name}` | Get details for a specific project |
| `DELETE` | `/api/projects/{name}` | Delete a project and its generated files |
| `GET` | `/api/projects/{name}/download` | Download generated docs as `tar.gz` |
| `GET` | `/docs/{project}/{path}` | Serve generated documentation pages |
| `GET` | `/health` | Health check |

### POST /api/generate

Start asynchronous documentation generation for a GitHub repository. Returns immediately with status `202 Accepted`.

**Request:**

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/psf/requests",
    "ai_provider": "claude",
    "ai_model": "claude-opus-4-6[1m]",
    "ai_cli_timeout": 120,
    "force": false
  }'
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo_url` | string | No* | -- | Git repository URL (HTTPS or SSH) |
| `repo_path` | string | No* | -- | Local git repository path |
| `ai_provider` | string | No | From `.env` | `claude`, `gemini`, or `cursor` |
| `ai_model` | string | No | From `.env` | Model identifier for the chosen provider |
| `ai_cli_timeout` | integer | No | From `.env` | Timeout in seconds for each AI CLI call |
| `force` | boolean | No | `false` | Force full regeneration, ignoring cache |

*Exactly one of `repo_url` or `repo_path` must be provided.

**Response (202):**

```json
{
  "project": "requests",
  "status": "generating"
}
```

#### Local Repositories

You can also generate documentation from a local git repository:

```bash
# Generate docs from a local git repository
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/local/repo"}'
```

**Note:** When using Docker, the local path must be mounted as a volume so the container can access it.

### GET /api/status

List all projects with their current statuses.

```bash
curl http://localhost:8000/api/status
```

**Response:**

```json
{
  "projects": [
    {
      "name": "requests",
      "repo_url": "https://github.com/psf/requests",
      "status": "ready",
      "last_commit_sha": "a1b2c3d4",
      "page_count": 12
    }
  ]
}
```

### GET /api/projects/{name}

Get details for a specific project.

```bash
curl http://localhost:8000/api/projects/requests
```

**Response:**

```json
{
  "name": "requests",
  "repo_url": "https://github.com/psf/requests",
  "status": "ready",
  "last_commit_sha": "a1b2c3d4e5f6",
  "last_generated": "2026-03-04T12:00:00",
  "error_message": null,
  "page_count": 12
}
```

### DELETE /api/projects/{name}

Delete a project and all its generated files.

```bash
curl -X DELETE http://localhost:8000/api/projects/requests
```

**Response:**

```json
{
  "deleted": "requests"
}
```

### GET /api/projects/{name}/download

Download the generated documentation site as a `tar.gz` archive. The project must have `status: "ready"`.

```bash
curl -o requests-docs.tar.gz http://localhost:8000/api/projects/requests/download
```

Extract and serve locally:

```bash
tar xzf requests-docs.tar.gz
cd requests
python -m http.server 3000
```

### GET /docs/{project}/{path}

Serves the generated HTML documentation. Browse directly in your browser:

```
http://localhost:8000/docs/requests/
http://localhost:8000/docs/requests/quickstart.html
```

### GET /health

Health check endpoint.

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "ok"
}
```

## Configuration

All configuration is done through environment variables. Copy `.env.example` to `.env` and edit as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI provider to use: `claude`, `gemini`, or `cursor` |
| `AI_MODEL` | `claude-opus-4-6[1m]` | Model identifier for the chosen provider |
| `AI_CLI_TIMEOUT` | `60` | Timeout in seconds for each AI CLI invocation |
| `ANTHROPIC_API_KEY` | -- | API key for Claude (Option 1) |
| `CLAUDE_CODE_USE_VERTEX` | -- | Set to `1` to use Claude via Vertex AI (Option 2) |
| `CLOUD_ML_REGION` | -- | Google Cloud region for Vertex AI |
| `ANTHROPIC_VERTEX_PROJECT_ID` | -- | Google Cloud project ID for Vertex AI |
| `GEMINI_API_KEY` | -- | API key for Gemini |
| `CURSOR_API_KEY` | -- | API key for Cursor |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DATA_DIR` | `/data` | Directory for generated docs and database |
| `DEBUG` | -- | Set to `true` to enable uvicorn auto-reload |

## AI Provider Setup

### Claude Code (default)

**Option 1 -- API Key:**

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
ANTHROPIC_API_KEY=sk-ant-...
```

**Option 2 -- Vertex AI:**

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

### Gemini CLI

```bash
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=AIza...
```

### Cursor Agent CLI

```bash
AI_PROVIDER=cursor
CURSOR_API_KEY=cur-...
```

## Force Regeneration

By default, docsfy skips regeneration if the repository HEAD commit SHA has not changed since the last run. Use the `force` flag to bypass this check and regenerate all pages from scratch:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/psf/requests",
    "force": true
  }'
```

When `force` is `true`:
- The page cache for the project is cleared
- All pages are regenerated by the AI provider
- The commit SHA is updated to the current HEAD

## llms.txt

Each generated documentation site includes two LLM-friendly files:

- **`llms.txt`** -- A structured index of all documentation pages with titles, slugs, and descriptions. Follows the [llms.txt specification](https://llmstxt.org/) for LLM-optimized discovery.

- **`llms-full.txt`** -- The full text content of all documentation pages concatenated into a single file, suitable for feeding an entire project's docs into an LLM context window.

Access them at:

```
http://localhost:8000/docs/{project}/llms.txt
http://localhost:8000/docs/{project}/llms-full.txt
```

## How It Works

1. **Clone** -- docsfy clones the target repository into a temporary directory.
2. **Plan** -- An AI provider analyzes the repository and produces a documentation plan (navigation structure, page titles, descriptions).
3. **Generate** -- Each documentation page is generated in parallel (up to 5 concurrent pages) by the AI provider, which reads the source code and writes markdown.
4. **Render** -- Markdown pages are converted to static HTML with syntax highlighting, search index, table of contents, and navigation.
5. **Serve** -- The generated site is served via FastAPI and can be browsed or downloaded.

## Deploy to GitHub Pages

You can host your generated docs on GitHub Pages for free.

### 1. Download the generated docs

```bash
curl -o docs.tar.gz http://localhost:8000/api/projects/YOUR_PROJECT/download
tar -xzf docs.tar.gz
```

### 2. GitHub Actions (Recommended)

Add this workflow to your repository at `.github/workflows/docs.yml`:

```yaml
name: Generate & Deploy Docs

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  docs:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - name: Generate docs
        run: |
          # Start docsfy
          docker compose up -d
          # Wait for healthy
          until curl -sf http://localhost:8000/health; do sleep 5; done
          # Generate docs for this repo
          curl -X POST http://localhost:8000/api/generate \
            -H "Content-Type: application/json" \
            -d "{\"repo_url\": \"https://github.com/${{ github.repository }}\"}"
          # Wait for completion
          while true; do
            STATUS=$(curl -s http://localhost:8000/api/projects/$(basename ${{ github.repository }}) | jq -r .status)
            [ "$STATUS" = "ready" ] && break
            [ "$STATUS" = "error" ] && exit 1
            sleep 30
          done
          # Download
          curl -o docs.tar.gz http://localhost:8000/api/projects/$(basename ${{ github.repository }})/download
          tar -xzf docs.tar.gz
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: $(basename ${{ github.repository }})
      - uses: actions/deploy-pages@v4
        id: deployment
```

### 3. Manual deployment

```bash
# Download and extract docs
curl -o docs.tar.gz http://localhost:8000/api/projects/my-project/download
tar -xzf docs.tar.gz

# Push to gh-pages branch
cd my-project
git init
git checkout -b gh-pages
git add -A
git commit -m "docs: update documentation"
git remote add origin git@github.com:org/repo.git
git push -f origin gh-pages
```

Then enable GitHub Pages in your repo settings -> Pages -> Source: **Deploy from a branch** -> Branch: `gh-pages` / `/ (root)`.

Your docs will be available at `https://org.github.io/repo/`.

## Development

### Running Tests

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

The project uses ruff (format + lint), flake8, mypy, detect-secrets, and gitleaks.

### Type Checking

```bash
uvx mypy src/docsfy/
```

## License

Apache-2.0
