# Testing

## Overview

docsfy uses a layered testing strategy built on industry-standard Python tooling. The test infrastructure runs through two primary entry points:

- **Tox** orchestrates all test environments — unused-code analysis and unit tests
- **Pre-commit** enforces code quality gates on every commit — linting, formatting, type checking, and secret detection

All tooling uses **uv** as the sole package manager. pip is not used anywhere in the project.

## Prerequisites

Ensure you have the following installed:

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Python | 3.12+ | Runtime |
| uv | Latest | Package management and virtual environments |
| tox | 4.x | Test orchestration |
| pre-commit | Latest | Git hook management |

Install the development environment:

```bash
uv sync --dev
```

> **Note:** docsfy uses `hatchling` as its build system. All project metadata and tool configuration lives in `pyproject.toml`.

---

## Running the Full Test Suite with Tox

Tox is the single command to run all checks — unused-code detection and unit tests. Each environment is isolated and uses uv for dependency resolution.

### Run everything

```bash
tox
```

This executes all configured environments sequentially. A passing `tox` run is the bar for merge readiness.

### List available environments

```bash
tox list
```

Typical environments:

| Environment | Description |
|-------------|-------------|
| `unused-code` | Detects dead code via vulture |
| `tests` | Runs the unit test suite via pytest |

### Run a specific environment

```bash
# Run only unit tests
tox -e tests

# Run only unused-code checks
tox -e unused-code
```

### Tox Configuration

Tox is configured in `pyproject.toml` under the `[tool.tox]` section. A representative configuration:

```toml
[tool.tox]
legacy_tox_ini = """
[tox]
envlist = unused-code, tests
no_package = true

[testenv]
deps = uv
allowlist_externals = uv

[testenv:tests]
commands =
    uv run pytest {posargs}

[testenv:unused-code]
commands =
    uv run vulture docsfy/ tests/ --min-confidence 80
"""
```

> **Tip:** Pass extra arguments to pytest through tox using `--`:
> ```bash
> tox -e tests -- -v -k "test_health"
> ```

---

## Unit Tests via uv

For rapid iteration during development, run pytest directly through uv without the overhead of tox environment creation.

### Run all tests

```bash
uv run pytest
```

### Common pytest options

```bash
# Verbose output with test names
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_main.py

# Run a specific test function
uv run pytest tests/test_main.py::test_health_endpoint

# Run tests matching a keyword
uv run pytest -k "test_generate"

# Stop on first failure
uv run pytest -x

# Show local variables in tracebacks
uv run pytest -l

# Run with coverage report
uv run pytest --cov=docsfy --cov-report=term-missing
```

### Pytest Configuration

Pytest is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
```

| Option | Meaning |
|--------|---------|
| `testpaths` | Directories to search for tests |
| `-ra` | Show summary of all non-passing tests |
| `-q` | Quiet output — less verbose by default |

### Writing Tests

Tests live in the `tests/` directory and follow standard pytest conventions. Test files must be named `test_*.py` and test functions must be prefixed with `test_`.

Example — testing the health endpoint:

```python
import pytest
from fastapi.testclient import TestClient
from docsfy.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
```

> **Tip:** Use `conftest.py` files in the `tests/` directory for shared fixtures. Pytest automatically discovers and makes them available to all tests in the same directory and below.

---

## Unused-Code Checks

docsfy uses **vulture** to detect dead code — unused functions, variables, imports, and unreachable code paths. This prevents code rot and keeps the codebase lean.

### Run via tox

```bash
tox -e unused-code
```

### Run directly

```bash
uv run vulture docsfy/ tests/ --min-confidence 80
```

The `--min-confidence 80` flag filters out low-confidence results. Vulture uses heuristics to detect unused code, and lower confidence values produce more false positives.

### Handling False Positives

Some code is intentionally unused from vulture's perspective — framework callbacks, plugin entry points, or dynamically referenced names. Create a vulture allowlist file to suppress these:

```python
# vulture_allowlist.py
from docsfy.main import app  # noqa: F401  # used by uvicorn

# FastAPI event handlers are called by the framework
startup_event  # unused-function
shutdown_event  # unused-function
```

Then include the allowlist in the vulture invocation:

```bash
uv run vulture docsfy/ tests/ vulture_allowlist.py --min-confidence 80
```

> **Warning:** Do not suppress vulture findings without understanding why the code appears unused. Legitimate dead code should be removed, not allowlisted.

---

## Quality Gates (Pre-commit)

Pre-commit hooks run automatically before each `git commit`, enforcing code quality standards. docsfy uses the following hooks:

| Hook | Purpose |
|------|---------|
| **ruff** | Linting and auto-formatting (replaces black + isort + many flake8 plugins) |
| **mypy** | Static type checking in strict mode |
| **flake8** | Additional linting rules complementing ruff |
| **gitleaks** | Scans for hardcoded secrets, API keys, and credentials |
| **detect-secrets** | Baseline-aware secret detection |
| **Standard hooks** | Trailing whitespace, end-of-file fixer, YAML/TOML validation, merge conflict markers |

### Setup

Install the pre-commit hooks into your local git repository:

```bash
pre-commit install
```

### Run against all files

Pre-commit normally only checks staged files. To run all hooks against every file in the repository:

```bash
pre-commit run --all-files
```

### Run a specific hook

```bash
# Run only ruff
pre-commit run ruff --all-files

# Run only mypy
pre-commit run mypy --all-files

# Run only flake8
pre-commit run flake8 --all-files
```

### Pre-commit Configuration

Hooks are defined in `.pre-commit-config.yaml` at the repository root. A representative configuration:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.0
    hooks:
      - id: mypy
        additional_dependencies: [fastapi, pydantic]

  - repo: https://github.com/PyCQA/flake8
    rev: 7.1.0
    hooks:
      - id: flake8

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.22.0
    hooks:
      - id: gitleaks

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
```

---

## Tool Configuration Reference

All Python tool configuration is centralized in `pyproject.toml`.

### Ruff

```toml
[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP", "B", "SIM", "RUF"]

[tool.ruff.format]
quote-style = "double"
```

| Rule Set | Description |
|----------|-------------|
| `E`, `W` | pycodestyle errors and warnings |
| `F` | pyflakes |
| `I` | isort (import sorting) |
| `UP` | pyupgrade (modern Python syntax) |
| `B` | flake8-bugbear (common pitfalls) |
| `SIM` | flake8-simplify |
| `RUF` | Ruff-specific rules |

### Mypy

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

> **Note:** Mypy runs in **strict mode**, which means all functions must have type annotations, and `Any` types are flagged. This catches type errors early and keeps the codebase fully typed.

### Flake8

Flake8 configuration lives in a separate `.flake8` file (it does not support `pyproject.toml`):

```ini
[flake8]
max-line-length = 120
extend-ignore = E203, W503
```

---

## Development Workflow

A typical development cycle looks like this:

```
1. Write code + tests
2. Run unit tests          →  uv run pytest
3. Run unused-code check   →  uv run vulture docsfy/ tests/ --min-confidence 80
4. Run full tox suite      →  tox
5. Commit (pre-commit runs automatically)
6. Fix any hook failures, re-commit
```

### Quick feedback loop

During active development, use `uv run pytest` directly for fast iteration:

```bash
# Watch mode with pytest-watch (if installed)
uv run ptw -- -x -q

# Or manually re-run on changes
uv run pytest -x -q tests/test_main.py
```

### Before opening a PR

Always run the full tox suite and pre-commit against all files:

```bash
tox && pre-commit run --all-files
```

> **Warning:** Do not skip pre-commit hooks with `--no-verify`. If a hook fails, fix the underlying issue rather than bypassing the check.

---

## Troubleshooting

### Tox cannot find uv

Ensure `uv` is installed and available on your `PATH`:

```bash
which uv
uv --version
```

If uv is installed but tox cannot find it, add `allowlist_externals = uv` to the relevant `[testenv]` section.

### Mypy reports missing stubs

Install the required type stubs as additional dependencies in the mypy pre-commit hook or add them to your dev dependencies:

```bash
uv add --dev types-requests types-pyyaml
```

### Vulture reports false positives for FastAPI routes

FastAPI route handlers are called by the framework, not directly in your code. Add them to the vulture allowlist file rather than suppressing the check entirely.

### Pre-commit hooks are slow

Pre-commit caches hook environments. If hooks are unusually slow, clear and rebuild the cache:

```bash
pre-commit clean
pre-commit install
pre-commit run --all-files
```
