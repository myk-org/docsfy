# Generating Documentation

This guide covers the complete workflow for generating documentation with docsfy: submitting a repository, monitoring the generation pipeline, and accessing the finished documentation site.

## Overview

Documentation generation is a four-stage pipeline that clones your repository, uses AI to plan and write documentation, then renders it into a polished static HTML site. The entire process is triggered by a single API call.

```
POST /api/generate
       │
       ▼
 ┌───────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │  Clone     │───▶│  AI Planner  │───▶│  AI Content  │───▶│    HTML      │
 │  Repo      │    │ (plan.json)  │    │  Generator   │    │  Renderer    │
 └───────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                  │
                                                                  ▼
                                                          Static HTML site
                                                     /data/projects/{name}/site/
```

## Submitting a Repository

### Endpoint

```
POST /api/generate
```

### Request Body

Send a JSON payload with the URL of the GitHub repository you want to document:

```json
{
  "repo_url": "https://github.com/user/repository"
}
```

SSH URLs are also supported:

```json
{
  "repo_url": "git@github.com:user/repository.git"
}
```

### Example: cURL

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repository"}'
```

### Example: Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/generate",
    json={"repo_url": "https://github.com/user/repository"}
)
print(response.json())
```

> **Note:** For private repositories, docsfy uses the system git credentials configured in the container environment. Ensure the container has appropriate SSH keys or credential helpers configured.

### What Happens After Submission

Once you submit a request, the project status is set to `generating` and the four-stage pipeline begins:

1. **Clone Repository** — A shallow clone (`--depth 1`) is performed to a temporary directory, keeping only the latest commit to minimize disk usage and clone time.

2. **AI Planner** — The AI CLI runs with its working directory set to the cloned repository. It analyzes the codebase structure and produces a `plan.json` file that defines the pages, sections, and navigation hierarchy for the documentation site.

3. **AI Content Generator** — For each page defined in `plan.json`, the AI CLI runs again with full access to the repository. Pages can be generated concurrently using semaphore-limited concurrency. Generated markdown is cached at `/data/projects/{name}/cache/pages/*.md`.

4. **HTML Renderer** — Markdown pages and `plan.json` are converted into a static HTML site using Jinja2 templates with bundled CSS and JavaScript. The final output is written to `/data/projects/{name}/site/`.

> **Tip:** The AI CLI availability is verified before generation starts with a lightweight test prompt. If the configured provider is unavailable, the request fails fast rather than partway through the pipeline.

## Monitoring Progress

### Project Status Values

Each project has one of three statuses:

| Status | Description |
|--------|-------------|
| `generating` | The documentation pipeline is currently running |
| `ready` | Generation completed successfully; documentation is available |
| `error` | Generation failed; check logs for details |

### List All Projects

To check the status of all projects at once:

```
GET /api/status
```

```bash
curl http://localhost:8000/api/status
```

This returns a list of all projects with their current generation status, allowing you to see at a glance which projects are in progress, complete, or have errors.

### Get Project Details

For detailed information about a specific project:

```
GET /api/projects/{name}
```

```bash
curl http://localhost:8000/api/projects/my-project
```

The response includes:

- Current generation status
- Last generated timestamp
- Last commit SHA
- List of documentation pages

### Polling for Completion

Since generation runs asynchronously, poll the status endpoint to detect when your documentation is ready:

```python
import time
import requests

project_name = "my-project"

while True:
    response = requests.get(f"http://localhost:8000/api/projects/{project_name}")
    data = response.json()

    if data["status"] == "ready":
        print("Documentation is ready!")
        break
    elif data["status"] == "error":
        print("Generation failed.")
        break

    time.sleep(10)  # check every 10 seconds
```

> **Note:** Generation time depends on repository size and the configured AI provider. The default AI CLI timeout is 60 minutes per invocation, so large repositories with many pages may take significant time to complete.

### Health Check

Verify the docsfy service itself is running:

```
GET /health
```

```bash
curl http://localhost:8000/health
```

## Accessing Generated Documentation

Once a project's status is `ready`, you can access the documentation in two ways.

### Serve Directly from docsfy

Browse the generated documentation site through the built-in static file server:

```
GET /docs/{project}/{path}
```

Open your browser to:

```
http://localhost:8000/docs/my-project/
```

The served site includes:

- Sidebar navigation generated from `plan.json`
- Dark/light theme toggle
- Client-side search powered by lunr.js
- Code syntax highlighting via highlight.js
- Responsive design with card layouts and callout boxes

### Download for Self-Hosting

Download the entire documentation site as a `.tar.gz` archive:

```
GET /api/projects/{name}/download
```

```bash
curl -o my-project-docs.tar.gz \
  http://localhost:8000/api/projects/my-project/download
```

The archive contains a fully self-contained static site that you can deploy to any static hosting provider (GitHub Pages, Netlify, S3, Nginx, etc.) without any dependency on docsfy.

The downloaded site structure mirrors the internal storage layout:

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

## Regenerating Documentation

To regenerate documentation after your repository has been updated, submit the same repository URL again:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repository"}'
```

docsfy uses incremental updates to minimize redundant work:

1. The current commit SHA is compared against the previously stored SHA
2. If the repository has changed, the AI Planner re-evaluates the documentation structure
3. Only pages whose content may be affected by the changes are regenerated
4. If the plan structure is unchanged, only pages related to modified files are rebuilt

> **Tip:** Incremental regeneration can be significantly faster than a full generation, especially for large repositories where only a few files have changed.

## Deleting a Project

To remove a project and all its generated documentation:

```
DELETE /api/projects/{name}
```

```bash
curl -X DELETE http://localhost:8000/api/projects/my-project
```

> **Warning:** This permanently deletes the project metadata from the database and all generated files from disk. This action cannot be undone.

## Configuration

The generation pipeline behavior is controlled through environment variables. These are typically set in your `.env` file or passed to the container:

### AI Provider

```bash
# Choose the AI provider: claude, gemini, or cursor
AI_PROVIDER=claude

# Model to use for generation
AI_MODEL=claude-opus-4-6[1m]

# Maximum time (in minutes) for each AI CLI invocation
AI_CLI_TIMEOUT=60
```

The three supported providers each use different CLI tools:

| Provider | CLI Binary | CWD Handling |
|----------|-----------|--------------|
| `claude` | `claude` | subprocess `cwd` set to repo path |
| `gemini` | `gemini` | subprocess `cwd` set to repo path |
| `cursor` | `agent` | `--workspace` flag pointing to repo path |

### Authentication

Configure credentials for your chosen AI provider:

```bash
# Claude - Option 1: API Key
ANTHROPIC_API_KEY=sk-ant-...

# Claude - Option 2: Vertex AI
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-central1
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project

# Gemini
GEMINI_API_KEY=...

# Cursor
CURSOR_API_KEY=...
```

> **Note:** Only one AI provider needs to be configured. Set `AI_PROVIDER` to match whichever provider you have credentials for.

### Docker Compose

A typical deployment uses Docker Compose with persistent storage:

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

The `/data` volume is essential — it persists the SQLite database and all generated documentation across container restarts.

## Error Handling

When generation fails, the project status is set to `error`. Common failure scenarios include:

| Cause | Resolution |
|-------|-----------|
| AI CLI not available | Verify the provider binary is installed and the correct `AI_PROVIDER` is set |
| Authentication failure | Check that API keys or cloud credentials are correctly configured |
| Timeout | Increase `AI_CLI_TIMEOUT` for very large repositories |
| Invalid repository URL | Verify the URL is a valid GitHub repository accessible from the container |
| Private repo access denied | Ensure system git credentials (SSH keys or credential helpers) are configured in the container |

The AI CLI's JSON response parsing uses a multi-strategy extraction approach to handle varied output formats:

1. Direct JSON parse
2. Brace-matching for the outermost JSON object
3. Markdown code block extraction
4. Fallback with regex recovery

This makes the pipeline resilient to minor formatting variations in AI output.
