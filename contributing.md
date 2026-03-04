# Contributing

## Prerequisites

Before contributing to docsfy, ensure you have the following installed:

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — the project's sole package manager (pip is not used)
- **git**
- **[pre-commit](https://pre-commit.com/)**

Install uv if you don't already have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setting Up the Development Environment

1. **Clone the repository:**

   ```bash
   git clone git@github.com:your-org/docsfy.git
   cd docsfy
   ```

2. **Install dependencies with uv:**

   ```bash
   uv sync --all-extras
   ```

   > **Note:** docsfy uses `uv` exclusively for dependency management. Do not use `pip install` — all dependencies and virtual environments are managed through `uv`.

3. **Install pre-commit hooks:**

   ```bash
   uv run pre-commit install
   ```

   This registers the hooks so they run automatically on every `git commit`.

## Development Workflow

### Branch Strategy

1. Create a feature branch from `main`:

   ```bash
   git checkout -b feature/my-feature main
   ```

2. Make your changes, ensuring all pre-commit hooks pass.
3. Write or update tests for your changes.
4. Push your branch and open a pull request against `main`.

### Build System

docsfy uses **hatchling** as its build backend. The project metadata and build configuration live in `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "docsfy"
requires-python = ">=3.12"
```

### Running the Application Locally

Start the FastAPI development server:

```bash
uv run uvicorn docsfy.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use Docker Compose:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
```

```bash
docker compose up --build
```

## Code Style Conventions

docsfy enforces consistent code quality through automated tooling. All style checks run as pre-commit hooks and in CI.

### Ruff (Linting and Formatting)

[Ruff](https://docs.astral.sh/ruff/) handles both linting and code formatting, replacing tools like black, isort, and most flake8 rules. It is configured in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.format]
skip-magic-trailing-comma = true
```

Run ruff manually:

```bash
# Check for lint violations
uv run ruff check .

# Auto-fix lint violations where possible
uv run ruff check --fix .

# Check formatting
uv run ruff format --check .

# Apply formatting
uv run ruff format .
```

### Mypy (Static Type Checking)

docsfy uses **mypy in strict mode** to enforce thorough type annotations. Configuration is in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

Run mypy manually:

```bash
uv run mypy docsfy/
```

> **Tip:** All function signatures must include type annotations. Mypy strict mode rejects untyped definitions, so every function parameter and return type needs an explicit annotation.

### Flake8

Flake8 provides additional lint coverage for patterns not caught by ruff. It is configured via a `.flake8` file:

```ini
[flake8]
max-line-length = 120
extend-ignore = E203, W503
```

Run flake8 manually:

```bash
uv run flake8 docsfy/
```

### General Style Guidelines

- **Line length:** 120 characters maximum.
- **Python version:** Use Python 3.12+ features freely (type unions with `|`, `match` statements, etc.).
- **Type hints:** Required on all public and private functions (enforced by mypy strict).
- **Imports:** Sorted and grouped automatically by ruff.
- **Docstrings:** Use them for public APIs; keep internal helpers self-documenting with clear names.

## Pre-commit Hooks

Pre-commit hooks run automatically before every commit to catch issues early. The project uses the following hooks, configured in `.pre-commit-config.yaml`:

### Hook Overview

| Hook | Purpose |
|------|---------|
| **ruff** (lint) | Catches code quality issues, import ordering, unused imports |
| **ruff** (format) | Enforces consistent code formatting |
| **mypy** | Static type checking in strict mode |
| **flake8** | Supplementary linting rules |
| **gitleaks** | Scans for accidentally committed secrets (API keys, tokens, passwords) |
| **detect-secrets** | Additional secret detection layer |
| **standard hooks** | Trailing whitespace, end-of-file fixer, YAML validation, large file checks |

### Configuration

The `.pre-commit-config.yaml` follows this structure:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        additional_dependencies: [fastapi, uvicorn, aiosqlite, jinja2]

  - repo: https://github.com/PyCQA/flake8
    rev: "7.1.0"
    hooks:
      - id: flake8

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.0
    hooks:
      - id: gitleaks

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
```

### Running Hooks Manually

Run all hooks against every file (not just staged changes):

```bash
uv run pre-commit run --all-files
```

Run a specific hook:

```bash
# Run only ruff linting
uv run pre-commit run ruff --all-files

# Run only mypy
uv run pre-commit run mypy --all-files

# Run only gitleaks
uv run pre-commit run gitleaks --all-files
```

> **Warning:** Never bypass pre-commit hooks with `git commit --no-verify`. If a hook is failing, fix the underlying issue rather than skipping the check. If you believe a hook produces a false positive, open an issue to discuss updating the configuration.

### Handling Secret Detection (gitleaks / detect-secrets)

If gitleaks or detect-secrets flags a false positive:

1. Verify the flagged string is not actually a secret.
2. Add an inline comment to suppress the finding:

   ```python
   EXAMPLE_PLACEHOLDER = "not-a-real-key"  # gitleaks:allow
   ```

3. Or add the pattern to `.gitleaksignore` for gitleaks.

> **Warning:** Never commit real secrets, API keys, or credentials to the repository. Use environment variables and `.env` files (which are gitignored) for sensitive configuration. See the `.env.example` file for the expected variables.

## Running the Test Suite with Tox

[Tox](https://tox.wiki/) orchestrates all testing and quality checks in isolated environments. It is the single entry point for running the full validation suite.

### Tox Configuration

Tox is configured in `tox.ini` (or in `pyproject.toml` under `[tool.tox]`), and uses `uv` as the package manager for creating virtual environments:

```ini
[tox]
envlist = lint, type, unused, tests

[testenv:lint]
description = Run ruff linting and formatting checks
deps = ruff
commands =
    ruff check .
    ruff format --check .

[testenv:type]
description = Run mypy strict type checking
deps =
    mypy
    fastapi
    uvicorn
    aiosqlite
    jinja2
commands =
    mypy docsfy/

[testenv:unused]
description = Check for unused code (vulture)
deps = vulture
commands =
    vulture docsfy/

[testenv:tests]
description = Run unit tests with pytest
deps =
    pytest
    pytest-asyncio
    pytest-cov
    httpx
commands =
    pytest tests/ -v --cov=docsfy --cov-report=term-missing
```

### Running Tests

Run the full tox suite:

```bash
uv run tox
```

Run a specific tox environment:

```bash
# Run only unit tests
uv run tox -e tests

# Run only linting
uv run tox -e lint

# Run only type checking
uv run tox -e type

# Run unused-code detection
uv run tox -e unused
```

### Running pytest Directly

For faster iteration during development, run pytest directly without tox:

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_renderer.py -v

# Run a specific test function
uv run pytest tests/test_renderer.py::test_markdown_to_html -v

# Run with coverage reporting
uv run pytest tests/ -v --cov=docsfy --cov-report=term-missing

# Run only tests matching a keyword
uv run pytest tests/ -v -k "planner"
```

### Writing Tests

- Place test files under `tests/` with the `test_` prefix.
- Use `pytest-asyncio` for testing async FastAPI endpoints and pipeline stages.
- Use `httpx.AsyncClient` with FastAPI's `TestClient` for API integration tests:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from docsfy.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
```

> **Tip:** Run `uv run pytest tests/ -v` frequently during development. The full `uv run tox` suite should pass before you push a branch or open a pull request.

## Continuous Integration

All pre-commit hooks and tox environments run in CI on every pull request. A PR cannot be merged unless:

1. All pre-commit hooks pass (ruff, mypy, flake8, gitleaks, detect-secrets).
2. All tox environments pass (lint, type checking, unused-code detection, unit tests).
3. The code has been reviewed and approved.

## Project Structure

Understanding the project layout helps you place new code correctly:

```
docsfy/
├── docsfy/                  # Application source code
│   ├── main.py              # FastAPI app and endpoint definitions
│   ├── pipeline/            # Generation pipeline stages
│   ├── providers/           # AI CLI provider integrations
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, and bundled assets
├── tests/                   # Test suite
├── docs/                    # Documentation and design documents
│   └── plans/
├── pyproject.toml           # Project metadata, dependencies, tool config
├── tox.ini                  # Tox test environments
├── .pre-commit-config.yaml  # Pre-commit hook definitions
├── .flake8                  # Flake8 configuration
├── Dockerfile               # Container build
├── docker-compose.yaml      # Local development with Docker
└── .env.example             # Template for environment variables
```

## Summary Checklist

Before submitting a pull request, verify the following:

- [ ] `uv run pre-commit run --all-files` passes with no errors
- [ ] `uv run tox` passes all environments
- [ ] New code includes type annotations (mypy strict)
- [ ] New features or bug fixes include corresponding tests
- [ ] No secrets or credentials are committed (gitleaks/detect-secrets pass)
- [ ] Commit messages are descriptive and follow conventional style
