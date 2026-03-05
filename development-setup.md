# Development Setup

This guide walks you through setting up a local development environment for docsfy, including dependency management with uv, running the application in DEBUG mode, and an overview of the project's development tooling.

## Prerequisites

- **Python 3.12+** &mdash; docsfy requires Python 3.12 or later
- **uv** &mdash; fast Python package manager used for dependency management
- **git** &mdash; required at runtime for repository cloning operations
- **An AI CLI** &mdash; at least one of Claude Code CLI, Cursor Agent CLI, or Gemini CLI installed and authenticated

### Installing uv

If you don't already have uv installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify the installation:

```bash
uv --version
```

> **Tip:** uv replaces pip, pip-tools, and virtualenv in one tool. It is significantly faster than pip and handles virtual environment creation automatically.

## Cloning the Repository

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
```

## Installing Dependencies

### All Dependencies (Recommended for Development)

Use `uv sync` with the `dev` extra to install both production and development dependencies in a single step:

```bash
uv sync --extra dev
```

This installs everything defined in `pyproject.toml`:

**Production dependencies:**

| Package | Purpose |
|---|---|
| `ai-cli-runner` | Wraps AI CLI tools (Claude, Gemini, Cursor) |
| `fastapi` | Web framework for the API |
| `uvicorn` | ASGI server |
| `pydantic-settings` | Settings management with environment variable loading |
| `python-simple-logger` | Structured logging |
| `aiosqlite` | Async SQLite database driver |
| `jinja2` | HTML template engine |
| `markdown` | Markdown-to-HTML conversion |
| `pygments` | Syntax highlighting for code blocks |

**Dev dependencies** (from `[project.optional-dependencies]`):

| Package | Purpose |
|---|---|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `pytest-xdist` | Parallel test execution |
| `httpx` | Async HTTP client for API testing |

### Production Only

To install without dev dependencies (e.g., for container builds):

```bash
uv sync --frozen --no-dev
```

The `--frozen` flag ensures the exact versions from `uv.lock` are used without updating the lock file.

## Environment Configuration

docsfy uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) to load configuration from environment variables and `.env` files. Copy the example environment file to get started:

```bash
cp .env.example .env
```

Then edit `.env` with your AI provider credentials. Here is the full set of options:

```bash
# AI Configuration
AI_PROVIDER=claude
# [1m] = 1 million token context window, this is a valid model identifier
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60

# Claude - Option 1: API Key
# ANTHROPIC_API_KEY=

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

The `Settings` class in `src/docsfy/config.py` defines defaults and loads values automatically:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: str = "claude"
    ai_model: str = "claude-opus-4-6[1m]"
    ai_cli_timeout: int = Field(default=60, gt=0)
    log_level: str = "INFO"
    data_dir: str = "/data"
```

> **Note:** For local development, you will likely want to set `DATA_DIR` to a local path (e.g., `DATA_DIR=./data`) instead of the container default `/data`. The application stores its SQLite database and generated documentation under this directory.

## Running Locally

### Using the CLI Entry Point

The project defines a console script entry point `docsfy` in `pyproject.toml`:

```toml
[project.scripts]
docsfy = "docsfy.main:run"
```

Run it with uv:

```bash
uv run docsfy
```

The server starts on `http://0.0.0.0:8000` by default.

### DEBUG Mode (Hot Reload)

Set the `DEBUG` environment variable to `true` to enable uvicorn's auto-reload, which automatically restarts the server when source files change:

```bash
DEBUG=true uv run docsfy
```

This is driven by the `run()` function in `src/docsfy/main.py`:

```python
def run() -> None:
    import uvicorn

    reload = os.getenv("DEBUG", "").lower() == "true"
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
```

You can also customize the host and port:

```bash
DEBUG=true HOST=127.0.0.1 PORT=9000 uv run docsfy
```

### Running uvicorn Directly

If you prefer to pass uvicorn options directly:

```bash
uv run uvicorn docsfy.main:app --reload --host 127.0.0.1 --port 8000
```

### Verifying the Server

Once running, check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok"}
```

The interactive API documentation is available at `http://localhost:8000/docs` (Swagger UI, auto-generated by FastAPI).

## Running with Docker

For a containerized setup without installing Python locally:

```bash
cp .env.example .env
# Edit .env with your credentials

docker compose up
```

The `docker-compose.yaml` maps port 8000, mounts a `./data` volume for persistence, and reads your `.env` file:

```yaml
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

> **Warning:** The Docker image includes Claude, Cursor, and Gemini CLIs. You still need to provide valid API credentials via the `.env` file for the chosen provider.

## Project Tooling Overview

### Testing

Tests live in the `tests/` directory and use pytest with async support. The pytest configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

Run the full test suite:

```bash
uv run pytest
```

Run tests in parallel using pytest-xdist:

```bash
uv run pytest -n auto
```

Run a specific test file:

```bash
uv run pytest tests/test_main.py
```

Run with verbose output:

```bash
uv run pytest -v
```

> **Tip:** Tests use `tmp_path` fixtures and override the `storage` module globals to create isolated SQLite databases per test, so you don't need a running server or pre-existing data directory.

### Tox

The project includes a `tox.toml` for standardized test automation with two environments:

```toml
envlist = ["unused-code", "unittests"]

[env.unused-code]
deps = ["python-utility-scripts"]
commands = [["pyutils-unusedcode"]]

[env.unittests]
deps = ["uv"]
commands = [["uv", "run", "--extra", "dev", "pytest", "-n", "auto", "tests"]]
```

Run all tox environments:

```bash
tox
```

Run a specific environment:

```bash
tox -e unittests
tox -e unused-code
```

- **`unittests`** &mdash; Runs the full test suite in parallel via pytest-xdist
- **`unused-code`** &mdash; Scans for dead/unused code using `pyutils-unusedcode`

### Pre-commit Hooks

The project uses [pre-commit](https://pre-commit.com/) to enforce code quality on every commit. Install the hooks after cloning:

```bash
uv run pre-commit install
```

Run all hooks manually against the entire codebase:

```bash
uv run pre-commit run --all-files
```

The configured hooks (from `.pre-commit-config.yaml`):

| Hook | Version | Purpose |
|---|---|---|
| **pre-commit-hooks** | v6.0.0 | File hygiene checks (large files, merge conflicts, trailing whitespace, EOF fixer, AST validation, TOML syntax) |
| **flake8** | 7.3.0 | Linting with RedHatQE M511 plugin (mutable default arguments) |
| **detect-secrets** | v1.5.0 | Prevents accidental secret commits |
| **ruff** | v0.15.2 | Fast linting and code formatting |
| **gitleaks** | v8.30.0 | Git history secret scanning |
| **mypy** | v1.19.1 | Static type checking (excludes `tests/`) |

### Type Checking

mypy is configured with strict settings in `pyproject.toml`:

```toml
[tool.mypy]
check_untyped_defs = true
disallow_any_generics = true
disallow_incomplete_defs = true
disallow_untyped_defs = true
no_implicit_optional = true
show_error_codes = true
strict_equality = true
extra_checks = true
```

Run mypy standalone:

```bash
uv run mypy src/docsfy
```

> **Note:** The pre-commit mypy hook excludes `tests/` from type checking. Only production source code under `src/docsfy/` is checked.

### Linting and Formatting

[Ruff](https://docs.astral.sh/ruff/) handles both linting and formatting. It runs automatically via pre-commit, but you can also invoke it directly:

```bash
# Lint
uv run ruff check src/ tests/

# Lint and auto-fix
uv run ruff check --fix src/ tests/

# Format
uv run ruff format src/ tests/
```

## Project Structure

```
docsfy/
├── .env.example                # Environment variable template
├── .flake8                     # Flake8 config (M511 plugin only)
├── .gitleaks.toml              # Secret scanning config
├── .pre-commit-config.yaml     # Pre-commit hooks
├── Dockerfile                  # Multi-stage production build
├── docker-compose.yaml         # Local container orchestration
├── pyproject.toml              # Project metadata, deps, and tool config
├── tox.toml                    # Tox test automation
├── uv.lock                    # Pinned dependency versions
├── src/
│   └── docsfy/
│       ├── __init__.py
│       ├── main.py             # FastAPI app and CLI entry point
│       ├── config.py           # Settings (pydantic-settings)
│       ├── ai_client.py        # AI CLI runner wrapper
│       ├── generator.py        # Documentation generation logic
│       ├── json_parser.py      # AI response JSON parser
│       ├── models.py           # Pydantic request/response models
│       ├── prompts.py          # AI prompt templates
│       ├── renderer.py         # HTML/Markdown rendering
│       ├── repository.py       # Git repository operations
│       ├── storage.py          # SQLite database layer
│       ├── static/             # CSS and JavaScript assets
│       └── templates/          # Jinja2 HTML templates
└── tests/
    ├── test_ai_client.py
    ├── test_config.py
    ├── test_generator.py
    ├── test_integration.py
    ├── test_json_parser.py
    ├── test_main.py
    ├── test_models.py
    ├── test_prompts.py
    ├── test_renderer.py
    ├── test_repository.py
    └── test_storage.py
```

## Quick Reference

| Task | Command |
|---|---|
| Install all deps | `uv sync --extra dev` |
| Run dev server (hot reload) | `DEBUG=true uv run docsfy` |
| Run production server | `uv run docsfy` |
| Run tests | `uv run pytest` |
| Run tests in parallel | `uv run pytest -n auto` |
| Run tox | `tox` |
| Install pre-commit hooks | `uv run pre-commit install` |
| Run all pre-commit checks | `uv run pre-commit run --all-files` |
| Type check | `uv run mypy src/docsfy` |
| Lint | `uv run ruff check src/ tests/` |
| Format | `uv run ruff format src/ tests/` |
| Docker startup | `docker compose up` |
| Health check | `curl http://localhost:8000/health` |
