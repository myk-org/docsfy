# Development Setup

## Prerequisites

Before setting up docsfy for local development, ensure the following tools are installed on your system.

### Python 3.12+

docsfy requires Python 3.12 or later. Verify your Python version:

```bash
python3 --version
```

### uv

docsfy uses [uv](https://docs.astral.sh/uv/) as its sole package manager. **Do not use pip** — all dependency management, virtual environment creation, and script execution goes through `uv`.

Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify the installation:

```bash
uv --version
```

> **Warning:** pip is not supported for this project. All commands use `uv` exclusively — from installing dependencies to running tests and the development server.

### Git

Git is required for cloning repositories (both the docsfy source and target repositories during doc generation):

```bash
git --version
```

### Node.js and npm (optional)

Only required if you plan to work with the Gemini CLI provider or modify front-end assets:

```bash
node --version
npm --version
```

---

## Cloning the Repository

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
```

---

## Installing Dependencies

docsfy uses [hatchling](https://hatch.pypa.io/) as its build system and `uv` for dependency management. Install the project with all development dependencies:

```bash
uv sync
```

This will:
- Create a virtual environment in `.venv/` (if one doesn't already exist)
- Install all runtime and development dependencies defined in `pyproject.toml`
- Install docsfy itself in editable mode

> **Tip:** You never need to manually activate the virtual environment. Use `uv run` to execute any command within the project's environment — for example, `uv run python -c "import docsfy"`.

---

## Pre-commit Hooks

docsfy enforces code quality through a comprehensive set of [pre-commit](https://pre-commit.com/) hooks. These run automatically on every commit to catch issues before they reach CI.

### Installing Pre-commit

Install pre-commit and set up the git hooks:

```bash
uv run pre-commit install
```

### Hook Overview

The `.pre-commit-config.yaml` configures the following hooks:

| Hook | Purpose |
|------|---------|
| **ruff** (lint) | Fast Python linter — catches errors, enforces style rules, and auto-fixes where possible |
| **ruff** (format) | Deterministic code formatter (replaces Black) |
| **mypy** | Static type checking in strict mode |
| **flake8** | Additional Python linting checks |
| **gitleaks** | Scans commits for accidentally committed secrets (API keys, tokens, passwords) |
| **detect-secrets** | Detects high-entropy strings and known secret patterns in staged files |
| **Standard hooks** | Trailing whitespace removal, end-of-file fixer, YAML/TOML validation, merge conflict detection |

### Running Hooks Manually

Run all hooks against every file in the repository (not just staged changes):

```bash
uv run pre-commit run --all-files
```

Run a specific hook:

```bash
uv run pre-commit run ruff --all-files
uv run pre-commit run mypy --all-files
```

> **Note:** The first run may take longer as pre-commit downloads and caches each hook's environment. Subsequent runs will be much faster.

### Ruff Configuration

Ruff handles both linting and formatting for the project. Its configuration lives in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort (import sorting)
    "UP",  # pyupgrade
]
```

Format your code manually at any time:

```bash
uv run ruff format .
uv run ruff check --fix .
```

### Mypy Configuration

Mypy runs in **strict mode** to enforce complete type annotations. Configuration is in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
```

Run type checking independently:

```bash
uv run mypy docsfy/
```

> **Tip:** If you're adding new code, ensure all functions have complete type annotations. Mypy in strict mode will reject untyped definitions.

---

## Running Tests

### With Tox

[Tox](https://tox.wiki/) is the test runner for CI-compatible test execution. docsfy's tox configuration defines environments for unit tests and code quality checks:

```bash
uv run tox
```

Run a specific tox environment:

```bash
uv run tox -e unit-tests
uv run tox -e unused-code
```

| Tox Environment | Purpose |
|----------------|---------|
| `unit-tests` | Runs the full unit test suite via pytest |
| `unused-code` | Detects dead code that can be safely removed |

> **Note:** Tox environments use `uv` internally for dependency installation, consistent with the project's uv-only policy.

### With Pytest Directly

For faster iteration during development, run pytest directly:

```bash
uv run pytest
```

Run a specific test file or test:

```bash
uv run pytest tests/test_renderer.py
uv run pytest tests/test_api.py::test_health_endpoint -v
```

---

## Running the Development Server

Start the FastAPI development server with auto-reload:

```bash
uv run uvicorn docsfy.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at `http://localhost:8000`. Key endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/status` | List all projects and their generation status |
| `POST /api/generate` | Start documentation generation for a repository |
| `GET /docs/{project}/` | Serve generated documentation |

### Environment Variables

Create a `.env` file from the example template for local configuration:

```bash
cp .env.example .env
```

The key variables for development:

```bash
# AI Configuration
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Option 1: API Key
ANTHROPIC_API_KEY=your-key-here

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

> **Warning:** Never commit your `.env` file. It is excluded via `.gitignore`, and the gitleaks pre-commit hook will block commits containing API keys or tokens.

---

## AI CLI Providers

docsfy shells out to AI CLI tools for documentation generation. You need at least one provider installed locally to test the generation pipeline.

### Claude Code (default)

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Verify installation:

```bash
claude --version
```

### Gemini CLI

```bash
npm install -g @google/gemini-cli
```

### Cursor Agent

```bash
curl -fsSL https://cursor.com/install | bash
```

> **Tip:** You only need the provider matching your `AI_PROVIDER` setting. Claude is the default.

---

## Docker Development

For a fully containerized development environment, use Docker Compose:

```bash
docker compose up --build
```

The `docker-compose.yaml` maps the local `./data` directory for persistent storage and mounts credential directories for AI provider authentication:

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

The Dockerfile uses a multi-stage build based on `python:3.12-slim` and runs as a non-root user (`appuser`) for OpenShift compatibility.

---

## Local Storage

During development, docsfy stores all generated data under the `./data` directory:

```
./data/
├── docsfy.db                      # SQLite database (project metadata)
└── projects/
    └── {project-name}/
        ├── plan.json              # Documentation structure from AI
        ├── cache/
        │   └── pages/*.md         # AI-generated markdown (cached)
        └── site/                  # Rendered static HTML
            ├── index.html
            ├── *.html
            ├── assets/
            │   ├── style.css
            │   ├── search.js
            │   ├── theme-toggle.js
            │   └── highlight.js
            └── search-index.json
```

> **Tip:** To reset all generated documentation during development, remove the `./data` directory. The SQLite database and all cached content will be recreated on the next generation request.

---

## Development Workflow Summary

A typical development cycle looks like this:

```bash
# 1. Install/sync dependencies
uv sync

# 2. Set up pre-commit hooks (one-time)
uv run pre-commit install

# 3. Create your feature branch
git checkout -b feature/my-feature

# 4. Start the dev server
uv run uvicorn docsfy.main:app --port 8000 --reload

# 5. Make your changes, then verify
uv run ruff format .
uv run ruff check --fix .
uv run mypy docsfy/
uv run pytest

# 6. Commit (pre-commit hooks run automatically)
git add -A
git commit -m "feat: add my feature"

# 7. Run the full test suite before pushing
uv run tox
```

> **Note:** If a pre-commit hook fails during `git commit`, fix the reported issues and commit again. The hooks are there to keep the codebase clean — don't bypass them with `--no-verify`.
