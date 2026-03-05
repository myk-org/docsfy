# Code Quality

docsfy enforces code quality through a layered set of automated checks that run on every commit. The project uses [pre-commit](https://pre-commit.com/) as the orchestration layer, combining linting, formatting, type checking, and security scanning into a single developer workflow.

## Overview

| Tool | Version | Purpose |
|------|---------|---------|
| Ruff | v0.15.2 | Python linting and code formatting |
| Flake8 | v7.3.0 | RedHatQE M511 mutable default detection |
| mypy | v1.19.1 | Strict static type checking |
| detect-secrets | v1.5.0 | Prevent secrets from entering the codebase |
| gitleaks | v8.30.0 | Scan git history for leaked secrets |
| tox (unused-code) | — | Dead code detection via `pyutils-unusedcode` |

## Pre-commit Hooks

All checks are configured in `.pre-commit-config.yaml` and run automatically before each commit. The project also integrates with [pre-commit.ci](https://pre-commit.ci/) for continuous integration, with automatic PR auto-fix disabled:

```yaml
ci:
  autofix_prs: false
  autoupdate_commit_msg: "ci: [pre-commit.ci] pre-commit autoupdate"
```

### Standard Hooks

The first layer of pre-commit hooks catches common issues before any language-specific tooling runs:

```yaml
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v6.0.0
  hooks:
    - id: check-added-large-files
    - id: check-docstring-first
    - id: check-executables-have-shebangs
    - id: check-merge-conflict
    - id: check-symlinks
    - id: detect-private-key
    - id: mixed-line-ending
    - id: debug-statements
    - id: trailing-whitespace
      args: [--markdown-linebreak-ext=md]
    - id: end-of-file-fixer
    - id: check-ast
    - id: check-builtin-literals
    - id: check-toml
```

These hooks enforce baseline hygiene: no large binaries, no merge conflict markers, no stray `breakpoint()` or `pdb` calls, consistent line endings, and valid Python AST in every `.py` file.

### Installing Pre-commit

To set up the hooks locally:

```bash
pip install pre-commit
pre-commit install
```

To run all hooks against the entire codebase on demand:

```bash
pre-commit run --all-files
```

## Ruff — Linting and Formatting

[Ruff](https://docs.astral.sh/ruff/) serves as the primary linter and code formatter for the project. It replaces tools like isort, pyflakes, pycodestyle, and Black with a single, fast Rust-based tool.

Both the linter and formatter are registered as separate pre-commit hooks:

```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.15.2
  hooks:
    - id: ruff
    - id: ruff-format
```

The project uses ruff's default rule set with no custom configuration — there is no `[tool.ruff]` section in `pyproject.toml` and no standalone `ruff.toml` file. The defaults include pyflakes (`F`), pycodestyle (`E`, `W`), and isort (`I`) rules.

> **Tip:** Ruff can auto-fix many issues. Run `ruff check --fix .` to apply safe fixes, or `ruff format .` to reformat the codebase.

## Flake8 — M511 Mutable Default Detection

Flake8 is retained alongside ruff specifically for the [RedHatQE flake8-plugins](https://github.com/RedHatQE/flake8-plugins) package, which provides the **M511** rule. This rule detects mutable default arguments in function signatures — a common Python pitfall where a mutable object (like a list or dict) is used as a default parameter value and shared across all calls.

### Configuration

The `.flake8` configuration file restricts flake8 to only the M511 rule:

```ini
[flake8]
select=M511

exclude =
    doc,
    .tox,
    .git,
    *.yml,
    Pipfile.*,
    docs/*,
    .cache/*
```

The pre-commit hook also pulls in `flake8-mutable` as an additional dependency:

```yaml
- repo: https://github.com/PyCQA/flake8
  rev: 7.3.0
  hooks:
    - id: flake8
      args: [--config=.flake8]
      additional_dependencies:
        # Tracks main branch intentionally for latest RedHatQE flake8 plugins
        [git+https://github.com/RedHatQE/flake8-plugins.git, flake8-mutable]
```

> **Note:** The RedHatQE plugin dependency tracks the `main` branch intentionally to pick up the latest rules without waiting for a release.

### What M511 Catches

M511 flags code like this:

```python
# Bad — mutable default argument
def process_items(items: list[str] = []) -> None:
    items.append("new")  # mutates the shared default
```

The correct pattern, used throughout the docsfy codebase, is to use immutable defaults or factory functions:

```python
# Good — immutable default with Pydantic Field factory
navigation: list[NavGroup] = Field(default_factory=list)
```

## mypy — Strict Type Checking

The project enforces strict static type checking with [mypy](https://mypy.readthedocs.io/). All source code (excluding tests) must have complete, correct type annotations.

### Configuration

The mypy configuration in `pyproject.toml` enables nearly every strictness flag:

```toml
[tool.mypy]
check_untyped_defs = true
disallow_any_generics = true
disallow_incomplete_defs = true
disallow_untyped_defs = true
no_implicit_optional = true
show_error_codes = true
warn_unused_ignores = true
strict_equality = true
extra_checks = true
warn_unused_configs = true
warn_redundant_casts = true
```

Key strictness options and what they enforce:

| Option | Effect |
|--------|--------|
| `disallow_untyped_defs` | Every function must have type annotations |
| `disallow_any_generics` | Generic types (e.g., `list`, `dict`) must specify their type parameters |
| `disallow_incomplete_defs` | Partially annotated functions are rejected |
| `no_implicit_optional` | `None` defaults don't automatically make the type optional |
| `strict_equality` | Prevents comparing unrelated types with `==` |
| `extra_checks` | Enables additional miscellaneous checks |

### Pre-commit Integration

The mypy pre-commit hook excludes tests and ships with type stub packages for the project's dependencies:

```yaml
- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.19.1
  hooks:
    - id: mypy
      exclude: (tests/)
      additional_dependencies:
        [types-requests, types-PyYAML, types-colorama, types-aiofiles, pydantic, types-Markdown]
```

> **Note:** Tests are excluded from mypy checking (`exclude: (tests/)`) to allow more flexible typing in test code, where mocks and fixtures often don't carry precise types.

### Code Examples

The strict configuration shapes how all code in the project is written. Every function signature carries full type annotations, including return types:

```python
# From src/docsfy/storage.py
async def update_project_status(
    name: str,
    status: str,
    last_commit_sha: str | None = None,
    page_count: int | None = None,
    error_message: str | None = None,
    plan_json: str | None = None,
) -> None:
```

Pydantic models use modern union syntax and `Literal` types for constrained values:

```python
# From src/docsfy/models.py
from typing import Literal

class GenerateRequest(BaseModel):
    repo_url: str | None = Field(
        default=None, description="Git repository URL (HTTPS or SSH)"
    )
    ai_provider: Literal["claude", "gemini", "cursor"] | None = None
    ai_cli_timeout: int | None = Field(default=None, gt=0)
```

Return types are always explicit, including for functions that return complex structures:

```python
# From src/docsfy/storage.py
async def get_project(name: str) -> dict[str, str | int | None] | None:
    ...

async def list_projects() -> list[dict[str, str | int | None]]:
    ...
```

## Security Scanning

The project uses two complementary tools to prevent secrets from entering the repository.

### detect-secrets

[detect-secrets](https://github.com/Yelp/detect-secrets) by Yelp scans staged files for high-entropy strings, API keys, passwords, and other potential secrets before they are committed:

```yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets
```

This hook runs with default detection rules and blocks commits that contain patterns matching known secret formats.

### gitleaks

[gitleaks](https://github.com/gitleaks/gitleaks) provides an additional layer of secret scanning that inspects the full git history, not just staged changes. This catches secrets that may have been committed before `detect-secrets` was installed.

```yaml
- repo: https://github.com/gitleaks/gitleaks
  rev: v8.30.0
  hooks:
    - id: gitleaks
```

The gitleaks configuration in `.gitleaks.toml` extends the default ruleset and allowlists the test file that intentionally contains mock URL patterns:

```toml
[extend]
useDefault = true

[allowlist]
paths = [
    '''tests/test_repository\.py''',
]
```

> **Warning:** If gitleaks flags a legitimate secret that was accidentally committed, simply removing it from the current code is not enough — the secret remains in git history. Rotate the credential immediately and consider rewriting history with `git filter-repo`.

## Tox — Unused Code Detection

The project uses [tox](https://tox.wiki/) to run a dead code detection pass alongside the regular test suite. The `tox.toml` configuration defines two environments:

```toml
skipsdist = true

envlist = ["unused-code", "unittests"]

[env.unused-code]
deps = ["python-utility-scripts"]
commands = [
  [
    "pyutils-unusedcode",
  ],
]

[env.unittests]
deps = ["uv"]
commands = [
  [
    "uv",
    "run",
    "--extra",
    "dev",
    "pytest",
    "-n",
    "auto",
    "tests",
  ],
]
```

### The `unused-code` Environment

The `unused-code` environment installs [python-utility-scripts](https://github.com/RedHatQE/python-utility-scripts) and runs `pyutils-unusedcode`, which analyzes the codebase for functions, classes, imports, and variables that are defined but never referenced. This helps prevent code rot and keeps the codebase lean.

Run it with:

```bash
tox -e unused-code
```

### The `unittests` Environment

The `unittests` environment runs the full pytest suite using [uv](https://docs.astral.sh/uv/) as the package manager, with parallel execution via `pytest-xdist`:

```bash
tox -e unittests
```

To run both environments:

```bash
tox
```

> **Tip:** The `unused-code` check is fast and non-destructive. Consider running it after removing or refactoring features to catch any newly orphaned code.

## Workflow Summary

The following diagram shows when each tool runs in the development workflow:

```
git commit
  └─► pre-commit hooks
        ├─► Standard checks (whitespace, AST, merge conflicts, ...)
        ├─► Ruff lint + format
        ├─► Flake8 M511 (mutable defaults)
        ├─► detect-secrets
        ├─► gitleaks
        └─► mypy strict type checking

tox (on-demand / CI)
  ├─► unused-code (pyutils-unusedcode)
  └─► unittests (pytest -n auto)

pre-commit.ci (on push / PR)
  └─► Runs all pre-commit hooks in CI
```

All pre-commit hooks run automatically on every commit. The tox environments (`unused-code` and `unittests`) are designed to be run on demand during development or as part of a CI pipeline. The pre-commit.ci integration ensures that all hooks also run on every push and pull request.
