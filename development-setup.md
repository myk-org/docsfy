# Development Setup

This guide walks you through setting up a local development environment for docsfy. The project uses `uv` as its exclusive package manager, Python 3.12+, and a comprehensive suite of pre-commit hooks and testing tools to maintain code quality.

## Prerequisites

| Requirement | Minimum Version | Purpose |
|-------------|----------------|---------|
| Python | 3.12+ | Runtime |
| uv | Latest | Package management (no pip) |
| Git | 2.25+ | Version control, shallow clones |
| Node.js & npm | 18+ | Gemini CLI (optional) |

> **Warning:** docsfy uses `uv` exclusively for dependency management. Do not use `pip` or `pip install` — all dependency operations must go through `uv`.

## Installing uv

If you don't already have `uv` installed:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

After installation, ensure `uv` is available on your `PATH` by restarting your shell or sourcing your profile:

```bash
source ~/.bashrc  # or ~/.zshrc
```

## Cloning the Repository

```bash
git clone https://github.com/your-org/docsfy.git
cd docsfy
```

## Python Version

docsfy requires **Python 3.12 or later**. The project pins this requirement via the `requires-python` field in `pyproject.toml`:

```toml
[project]
requires-python = ">=3.12"
```

If you have multiple Python versions installed, `uv` will automatically select a compatible version. You can also specify one explicitly:

```bash
uv python install 3.12
```

## Installing Dependencies

Use `uv` to create a virtual environment and install all project dependencies in a single step:

```bash
uv sync
```

This command:

1. Creates a `.venv` virtual environment in the project root (if it doesn't exist)
2. Installs all project dependencies from `uv.lock`
3. Installs the project itself in editable mode

To include development dependencies:

```bash
uv sync --all-extras
```

> **Tip:** Unlike `pip`, `uv` resolves and locks dependencies deterministically via `uv.lock`. Never edit this file manually — run `uv lock` to regenerate it after changing dependencies in `pyproject.toml`.

## Build System

docsfy uses **hatchling** as its build backend:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

The source code lives under the `src/` layout:

```
src/
  docsfy/
    __init__.py
    main.py
    ...
tests/
  ...
```

## Pre-commit Hooks

The project enforces code quality through a comprehensive set of pre-commit hooks. These run automatically on every commit to catch issues before they reach code review.

### Installation

```bash
uv run pre-commit install
```

This registers the hooks with Git so they execute on `git commit`.

### Hook Suite

The `.pre-commit-config.yaml` configures the following hooks:

#### Standard Hooks

Basic file hygiene checks from the `pre-commit-hooks` repository:

```yaml
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v5.0.0
  hooks:
    - id: trailing-whitespace
    - id: end-of-file-fixer
    - id: check-yaml
    - id: check-added-large-files
    - id: check-merge-conflict
    - id: debug-statements
```

These hooks:

- Strip trailing whitespace from lines
- Ensure files end with a newline
- Validate YAML syntax
- Prevent accidentally committing large binary files
- Detect leftover merge conflict markers
- Flag `breakpoint()` and `pdb` statements left in code

#### Ruff (Lint + Format)

[Ruff](https://docs.astral.sh/ruff/) handles both linting and code formatting, replacing tools like `isort`, `black`, and many `flake8` plugins:

```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.9.9
  hooks:
    - id: ruff
      args: [--fix]
    - id: ruff-format
```

Ruff is configured in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "S",    # flake8-bandit (security)
    "A",    # flake8-builtins
    "C4",   # flake8-comprehensions
    "DTZ",  # flake8-datetimez
    "T20",  # flake8-print
    "RET",  # flake8-return
    "PTH",  # flake8-use-pathlib
]
ignore = ["S603", "S607"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]  # allow assert in tests
```

> **Note:** The `--fix` argument enables auto-fixing of safe lint violations (such as import sorting). Unsafe fixes require manual review.

#### mypy (Strict Type Checking)

[mypy](https://mypy.readthedocs.io/) enforces strict static type checking across the entire codebase:

```yaml
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.15.0
  hooks:
    - id: mypy
      additional_dependencies:
        - fastapi
        - uvicorn
        - jinja2
        - aiosqlite
```

The mypy configuration in `pyproject.toml` enables strict mode:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
```

> **Tip:** When adding new dependencies, include them in the `additional_dependencies` list for the mypy hook so that type stubs are available during pre-commit runs.

#### flake8 (Additional Linting)

[flake8](https://flake8.pycqa.org/) provides supplementary linting checks beyond what ruff covers:

```yaml
- repo: https://github.com/PyCQA/flake8
  rev: 7.1.2
  hooks:
    - id: flake8
      args: [--max-line-length=120]
```

The flake8 configuration is typically placed in `setup.cfg`:

```ini
[flake8]
max-line-length = 120
extend-ignore = E203,W503
per-file-ignores =
    tests/*:S101
```

> **Note:** Some rules overlap between ruff and flake8 by design. Ruff handles auto-fixing while flake8 serves as an independent second check.

#### gitleaks (Secret Detection)

[gitleaks](https://github.com/gitleaks/gitleaks) scans commits for accidentally committed secrets such as API keys, tokens, and passwords:

```yaml
- repo: https://github.com/gitleaks/gitleaks
  rev: v8.23.3
  hooks:
    - id: gitleaks
```

gitleaks checks every staged change against a comprehensive set of patterns for known secret formats (AWS keys, GitHub tokens, private keys, etc.).

#### detect-secrets (Secret Baseline)

[detect-secrets](https://github.com/Yelp/detect-secrets) provides a second layer of secret detection with a baseline-aware approach:

```yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets
      args: ['--baseline', '.secrets.baseline']
```

To initialize the baseline (first-time setup):

```bash
uv run detect-secrets scan > .secrets.baseline
```

When detect-secrets flags a false positive, audit and update the baseline:

```bash
uv run detect-secrets audit .secrets.baseline
```

> **Warning:** Both gitleaks and detect-secrets run on every commit. If either tool flags a potential secret, the commit will be blocked. Never use `--no-verify` to bypass these checks — instead, remove the secret and use environment variables.

### Running All Hooks Manually

To run all pre-commit hooks against the entire codebase (not just staged files):

```bash
uv run pre-commit run --all-files
```

To run a specific hook:

```bash
uv run pre-commit run ruff --all-files
uv run pre-commit run mypy --all-files
uv run pre-commit run gitleaks --all-files
```

### Updating Hook Versions

To update all hooks to their latest versions:

```bash
uv run pre-commit autoupdate
```

After updating, run the full suite to ensure compatibility:

```bash
uv run pre-commit run --all-files
```

## Testing with tox

The project uses [tox](https://tox.wiki/) as its test orchestrator, configured in `tox.ini` at the project root.

### tox Configuration

```ini
[tox]
envlist = unused, py312
isolated_build = true

[testenv]
deps =
    pytest
    pytest-cov
    pytest-asyncio
    httpx
allowlist_externals = uv
commands =
    uv run pytest tests/ -v --cov=docsfy --cov-report=term-missing {posargs}

[testenv:unused]
deps =
    vulture
commands =
    uv run vulture src/docsfy/ --min-confidence 80
```

### Test Environments

| Environment | Command | Purpose |
|-------------|---------|---------|
| `py312` | `pytest` via `uv run` | Run the full unit test suite with coverage |
| `unused` | `vulture` | Detect unused code (functions, variables, imports) |

### Running Tests

Run the full test suite:

```bash
uv run tox
```

Run only unit tests:

```bash
uv run tox -e py312
```

Run only the unused code check:

```bash
uv run tox -e unused
```

Run tests directly with pytest (faster iteration during development):

```bash
uv run pytest tests/ -v
```

Run a specific test file or test:

```bash
uv run pytest tests/test_main.py -v
uv run pytest tests/test_main.py::test_health_endpoint -v
```

Run with coverage reporting:

```bash
uv run pytest tests/ --cov=docsfy --cov-report=term-missing
```

> **Tip:** During active development, run `uv run pytest` directly for faster feedback. Use `uv run tox` before committing to ensure all environments pass.

## Environment Variables

Copy the example environment file and configure your AI provider credentials:

```bash
cp .env.example .env
```

The key variables for local development:

```bash
# AI Configuration
AI_PROVIDER=claude              # claude | gemini | cursor
AI_MODEL=claude-opus-4-6[1m]   # Model identifier
AI_CLI_TIMEOUT=60               # Timeout in minutes

# Claude - Option 1: API Key
ANTHROPIC_API_KEY=your-key-here

# Claude - Option 2: Vertex AI
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=your-project-id

# Gemini
GEMINI_API_KEY=your-key-here

# Logging
LOG_LEVEL=INFO
```

> **Warning:** Never commit `.env` files. The `.gitignore` should exclude `.env`, and both gitleaks and detect-secrets will block commits containing API keys.

## Running the Application Locally

Start the development server with auto-reload:

```bash
uv run uvicorn docsfy.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:

- **API docs (Swagger):** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health
- **Project status:** http://localhost:8000/api/status

## Docker Development

For a containerized development environment:

```bash
docker compose up --build
```

This mounts local volumes for persistent data and credential access:

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

> **Note:** The container runs as a non-root user (`appuser`) with GID 0 for OpenShift compatibility. The base image is `python:3.12-slim` with `uv` as the package manager.

## Development Workflow Summary

A typical development cycle looks like this:

```
1. Create a feature branch
   git checkout -b feature/my-feature

2. Make your changes
   (edit files in src/docsfy/ and tests/)

3. Run tests during development
   uv run pytest tests/ -v

4. Pre-commit hooks run automatically on commit
   git add .
   git commit -m "feat: add my feature"
   # → hooks run: ruff, mypy, flake8, gitleaks, detect-secrets

5. If hooks fail, fix issues and re-commit
   uv run pre-commit run --all-files   # check what needs fixing
   git add .
   git commit -m "feat: add my feature"

6. Run full tox suite before pushing
   uv run tox

7. Push and open a pull request
   git push origin feature/my-feature
```

## Troubleshooting

### Pre-commit hook fails with "mypy not found"

Ensure mypy's additional dependencies are installed. Run:

```bash
uv run pre-commit clean
uv run pre-commit install
uv run pre-commit run mypy --all-files
```

### `uv sync` fails with Python version error

Verify you have Python 3.12+ installed:

```bash
python3 --version
uv python list
```

If needed, install the correct version:

```bash
uv python install 3.12
```

### detect-secrets blocks commit with false positive

Audit the baseline and mark the finding as a false positive:

```bash
uv run detect-secrets audit .secrets.baseline
```

Then stage the updated baseline:

```bash
git add .secrets.baseline
git commit -m "chore: update secrets baseline"
```

### tox environment creation fails

Clear the tox cache and retry:

```bash
rm -rf .tox/
uv run tox
```
