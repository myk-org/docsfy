# Code Quality

docsfy enforces code quality through a layered system of automated checks that run before every commit. The toolchain — adopted from the [pr-test-oracle](https://github.com/pr-test-oracle) project — combines linting, formatting, type checking, and secret detection into a single pre-commit workflow.

## Overview

| Tool | Purpose |
|------|---------|
| [Pre-commit](#pre-commit-hooks) | Git hook framework that orchestrates all checks |
| [Ruff](#ruff-linting-and-formatting) | Fast Python linter and formatter (replaces black, isort, and most flake8 rules) |
| [Mypy](#mypy-strict-type-checking) | Static type checker in strict mode |
| [Flake8](#flake8) | Supplementary linting for rules not covered by ruff |
| [Gitleaks](#gitleaks) | Scans commits for hardcoded secrets and credentials |
| [detect-secrets](#detect-secrets) | Baseline-aware secret detection to prevent new secrets from entering the codebase |

## Pre-commit Hooks

[Pre-commit](https://pre-commit.com/) is the entry point for all code quality checks. It intercepts `git commit` and runs every configured hook against staged files. If any hook fails, the commit is blocked until the issue is fixed.

### Installation

Pre-commit is installed as a development dependency via `uv`:

```bash
uv sync --dev
```

Then activate the hooks in your local repository:

```bash
uv run pre-commit install
```

### Configuration

The `.pre-commit-config.yaml` file defines all hooks and their versions:

```yaml
repos:
  # Standard pre-commit hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: debug-statements
      - id: check-merge-conflict

  # Ruff - linting and formatting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.7
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # Mypy - strict type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        additional_dependencies: [fastapi, uvicorn, jinja2, aiosqlite]
        args: [--strict]

  # Flake8 - supplementary linting
  - repo: https://github.com/PyCQA/flake8
    rev: 7.1.2
    hooks:
      - id: flake8

  # Gitleaks - secret scanning
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.22.1
    hooks:
      - id: gitleaks

  # detect-secrets - baseline secret detection
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### Running Hooks Manually

Run all hooks against every file (not just staged changes):

```bash
uv run pre-commit run --all-files
```

Run a specific hook:

```bash
uv run pre-commit run ruff --all-files
uv run pre-commit run mypy --all-files
```

> **Tip:** Run `pre-commit run --all-files` after pulling changes or updating hook versions to catch issues early before your next commit.

## Ruff Linting and Formatting

[Ruff](https://docs.astral.sh/ruff/) is an extremely fast Python linter and formatter written in Rust. It replaces black, isort, pycodestyle, pyflakes, and many flake8 plugins in a single tool.

docsfy uses ruff for two purposes via separate pre-commit hooks:

- **`ruff`** — linting with auto-fix enabled (`--fix`)
- **`ruff-format`** — code formatting (consistent style enforcement)

### Configuration

Ruff is configured in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "SIM",    # flake8-simplify
    "RUF",    # ruff-specific rules
]

[tool.ruff.lint.isort]
known-first-party = ["docsfy"]
```

### What Ruff Checks

| Rule Set | Code | What It Catches |
|----------|------|----------------|
| pycodestyle | `E`, `W` | Style violations (whitespace, indentation, line length) |
| pyflakes | `F` | Unused imports, undefined names, redefined variables |
| isort | `I` | Import ordering and grouping |
| pep8-naming | `N` | Naming convention violations |
| pyupgrade | `UP` | Code that can use newer Python 3.12+ syntax |
| flake8-bugbear | `B` | Common bugs and design problems |
| flake8-simplify | `SIM` | Code that can be simplified |
| ruff-specific | `RUF` | Ruff's own additional checks |

### Auto-fix Behavior

The `--fix` flag in the pre-commit hook means ruff will automatically fix issues where safe to do so. For example:

```python
# Before: ruff auto-fixes unused import (F401)
import os
import sys

def get_version():
    return sys.version

# After: ruff removes the unused `os` import
import sys

def get_version():
    return sys.version
```

Import ordering is also handled automatically:

```python
# Before: unordered imports (I001)
from docsfy.renderer import render_html
import asyncio
from fastapi import FastAPI
import os

# After: ruff reorders into standard/third-party/first-party groups
import asyncio
import os

from fastapi import FastAPI

from docsfy.renderer import render_html
```

> **Note:** Ruff's formatter (`ruff-format`) runs as a separate hook after the linter. This ensures that any auto-fixed code is also properly formatted.

## Mypy Strict Type Checking

[Mypy](https://mypy-lang.org/) performs static type analysis to catch type errors before runtime. docsfy runs mypy in **strict mode**, which enables all optional type-checking flags for maximum safety.

### Configuration

Mypy is configured in `pyproject.toml`:

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

### What Strict Mode Enforces

Strict mode is the combination of several flags that together require comprehensive type annotations:

- **`disallow_untyped_defs`** — Every function must have type annotations for all parameters and the return type
- **`disallow_incomplete_defs`** — Partial annotations (e.g., annotating some but not all parameters) are rejected
- **`no_implicit_optional`** — `None` defaults don't automatically make a parameter `Optional`; you must write `str | None` explicitly
- **`warn_return_any`** — Functions typed as returning a specific type but actually returning `Any` trigger a warning

### Examples

Functions must have complete type annotations:

```python
# Passes mypy --strict
async def generate_docs(repo_url: str, project_name: str) -> tuple[bool, str]:
    """Generate documentation for a repository."""
    ...

# Fails mypy --strict: missing parameter and return type annotations
async def generate_docs(repo_url, project_name):
    ...
```

Optional parameters must be explicitly annotated:

```python
# Passes mypy --strict
def get_provider(name: str | None = None) -> ProviderConfig:
    ...

# Fails mypy --strict: implicit Optional is not allowed
def get_provider(name: str = None) -> ProviderConfig:
    ...
```

> **Warning:** The pre-commit mypy hook lists `additional_dependencies` (fastapi, uvicorn, jinja2, aiosqlite) so that mypy can resolve third-party type stubs. If you add a new dependency to the project, you may need to add it here as well for type checking to pass.

## Flake8

[Flake8](https://flake8.pycqa.org/) provides supplementary linting that catches issues outside ruff's rule set. While ruff covers most of flake8's core rules, flake8 is retained for its plugin ecosystem and as a secondary verification layer.

### Configuration

Flake8 is configured in `pyproject.toml` (via the `[tool.flake8]` section if using `pyproject-flake8`) or in a `.flake8` file:

```ini
[flake8]
max-line-length = 120
extend-ignore = E203, W503
per-file-ignores =
    __init__.py:F401
```

| Setting | Value | Reason |
|---------|-------|--------|
| `max-line-length` | `120` | Matches ruff's `line-length` setting |
| `extend-ignore: E203` | — | Conflicts with formatting around slice notation |
| `extend-ignore: W503` | — | Deprecated rule about line breaks before binary operators |
| `per-file-ignores: __init__.py:F401` | — | Allows unused imports in `__init__.py` (re-exports) |

> **Note:** The `max-line-length` setting should always match ruff's `line-length` in `pyproject.toml` to avoid conflicting results between the two tools.

## Gitleaks

[Gitleaks](https://gitleaks.io/) is a SAST (Static Application Security Testing) tool that scans git commits for hardcoded secrets such as API keys, tokens, passwords, and private keys.

### How It Works

The gitleaks pre-commit hook scans the contents of staged files before each commit. If a potential secret is detected, the commit is blocked with a report identifying the file, line, and type of secret found.

### Configuration

Gitleaks uses its built-in rules by default. A custom `.gitleaks.toml` can be added to fine-tune detection:

```toml
[allowlist]
description = "Global allowlist"
paths = [
    '''\.secrets\.baseline$''',
    '''\.env\.example$''',
]
```

### Example Output

When gitleaks detects a secret, you'll see output like:

```
Finding:  ANTHROPIC_API_KEY=sk-ant-api03-real-key-here
RuleID:   generic-api-key
Entropy:  4.2
File:     .env
Line:     2
Commit:   (staged)
```

> **Warning:** Never commit `.env` files or any file containing real API keys. Use `.env.example` with placeholder values instead. The project's `.gitignore` should exclude `.env` and other sensitive files.

### Handling False Positives

If gitleaks flags a false positive (e.g., a test fixture or documentation example), you can suppress it inline:

```python
# gitleaks:allow
EXAMPLE_KEY = "sk-ant-api03-placeholder-not-real"
```

## detect-secrets

[detect-secrets](https://github.com/Yelp/detect-secrets) takes a baseline-aware approach to secret detection. Rather than scanning all files every time, it maintains a `.secrets.baseline` file that tracks known findings, and only alerts on **new** secrets introduced after the baseline was established.

### How It Works

1. A `.secrets.baseline` file is generated and committed to the repository
2. On each commit, detect-secrets compares staged files against the baseline
3. Only new secrets (not present in the baseline) trigger a failure
4. Known false positives are tracked in the baseline and ignored

### Generating the Baseline

Create the initial baseline:

```bash
uv run detect-secrets scan > .secrets.baseline
```

### Auditing the Baseline

After generating or updating the baseline, audit it to mark findings as true or false positives:

```bash
uv run detect-secrets audit .secrets.baseline
```

This launches an interactive session where each finding is presented for review. Findings marked as false positives are ignored in future scans.

### Updating the Baseline

When new files are added or existing secrets are rotated, update the baseline:

```bash
uv run detect-secrets scan --baseline .secrets.baseline
```

> **Tip:** Run `detect-secrets audit .secrets.baseline` after every baseline update to ensure new findings are properly classified.

## Running All Checks

### Via Pre-commit

The standard way to run all code quality checks:

```bash
# Run against staged files only (happens automatically on commit)
uv run pre-commit run

# Run against all files in the repository
uv run pre-commit run --all-files
```

### Via Tox

Tox provides an additional layer for running checks in isolated environments:

```bash
# Run all tox environments (tests + quality checks)
uv run tox

# Run a specific environment
uv run tox -e lint
```

## Troubleshooting

### Pre-commit Hook Fails on Commit

If a hook fails, read the error output to identify which tool flagged the issue. Common scenarios:

| Tool | Common Failure | Resolution |
|------|---------------|------------|
| ruff | `F401 unused import` | Remove the unused import or add `# noqa: F401` if intentional |
| ruff-format | File reformatted | Stage the reformatted file and commit again |
| mypy | `Missing return type` | Add type annotations to the function signature |
| flake8 | `E501 line too long` | Break the line or check that `max-line-length` matches ruff |
| gitleaks | Secret detected | Remove the secret, use environment variables instead |
| detect-secrets | New secret found | Remove it, or update the baseline if it's a false positive |

### Skipping Hooks (Emergency Only)

In rare cases where you need to bypass pre-commit hooks:

```bash
git commit --no-verify -m "emergency fix: description"
```

> **Warning:** Use `--no-verify` sparingly and only in genuine emergencies. All skipped checks should be run manually afterwards with `pre-commit run --all-files` to ensure no issues are left unresolved.

### Updating Hook Versions

Keep pre-commit hooks up to date:

```bash
uv run pre-commit autoupdate
```

This updates the `rev` field for each repo in `.pre-commit-config.yaml` to the latest available tag.
