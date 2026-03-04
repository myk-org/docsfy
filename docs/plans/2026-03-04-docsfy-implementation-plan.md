# docsfy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an AI-powered FastAPI service that generates Mintlify-quality static HTML documentation from GitHub repositories.

**Architecture:** Clone repo → AI plans doc structure → AI generates each page as markdown → Render to static HTML. FastAPI serves the docs and provides a download endpoint for self-hosting.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, aiosqlite, Jinja2, markdown, pydantic-settings, hatchling, uv

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/docsfy/__init__.py`
- Create: `.pre-commit-config.yaml` (copy from `/home/myakove/git/pr-test-oracle/.pre-commit-config.yaml`)
- Create: `.flake8` (copy from `/home/myakove/git/pr-test-oracle/.flake8`)
- Create: `tox.toml` (based on `/home/myakove/git/pr-test-oracle/tox.toml`)
- Create: `.gitleaks.toml`
- Create: `.env.example`
- Create: `Dockerfile`
- Create: `docker-compose.yaml`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "docsfy"
version = "0.1.0"
description = "AI-powered documentation generator - generates Mintlify-quality static HTML docs from GitHub repos"
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "uvicorn",
    "pydantic-settings",
    "python-simple-logger",
    "aiosqlite",
    "jinja2",
    "markdown",
    "pygments",
]

[project.scripts]
docsfy = "docsfy.main:run"

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "pytest-xdist", "httpx"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.hatch.build.targets.wheel]
packages = ["src/docsfy"]

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

**Step 2: Create `src/docsfy/__init__.py`** — empty file.

**Step 3: Copy `.pre-commit-config.yaml`** from `/home/myakove/git/pr-test-oracle/.pre-commit-config.yaml` verbatim, updating mypy `additional_dependencies` to: `[types-requests, types-PyYAML, types-colorama, types-aiofiles, pydantic]`

**Step 4: Copy `.flake8`** from `/home/myakove/git/pr-test-oracle/.flake8` verbatim.

**Step 5: Create `tox.toml`**

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

**Step 6: Create `.gitleaks.toml`**

```toml
[extend]
useDefault = true

[allowlist]
paths = [
    '''tests/.*\.py''',
]
```

**Step 7: Create `.env.example`**

```bash
# AI Configuration
AI_PROVIDER=claude
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

**Step 8: Create `Dockerfile`**

```dockerfile
# --- Stage 1: build ---
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev

# --- Stage 2: runtime ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash git curl ca-certificates gnupg && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (for Gemini CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user (OpenShift compatible)
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /data /home/appuser/.npm-global && \
    chown -R appuser:0 /data /home/appuser && \
    chmod -R g=u /data /home/appuser

USER appuser
WORKDIR /app

ENV HOME=/home/appuser \
    PATH="/home/appuser/.local/bin:/home/appuser/.npm-global/bin:${PATH}"

# Install AI CLIs (unpinned for latest)
RUN /bin/bash -o pipefail -c "curl -fsSL https://claude.ai/install.sh | bash"
RUN /bin/bash -o pipefail -c "curl -fsSL https://cursor.com/install | bash"
RUN npm config set prefix '/home/appuser/.npm-global' && \
    npm install -g @google/gemini-cli

# Copy app from builder
COPY --from=builder --chown=appuser:0 /app /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uv", "run", "--no-sync", "uvicorn", "docsfy.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 9: Create `docker-compose.yaml`**

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

**Step 10: Commit**

```bash
git add pyproject.toml src/docsfy/__init__.py .pre-commit-config.yaml .flake8 tox.toml .gitleaks.toml .env.example Dockerfile docker-compose.yaml
git commit -m "feat: project scaffolding with build config, linters, and container setup"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/docsfy/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

Create `tests/__init__.py` (empty file).

Create `tests/test_config.py`:

```python
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_default_settings() -> None:
    from docsfy.config import Settings

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
    assert settings.ai_provider == "claude"
    assert settings.ai_model == "claude-opus-4-6[1m]"
    assert settings.ai_cli_timeout == 60
    assert settings.log_level == "INFO"
    assert settings.data_dir == "/data"


def test_custom_settings() -> None:
    from docsfy.config import Settings

    env = {
        "AI_PROVIDER": "gemini",
        "AI_MODEL": "gemini-2.5-pro",
        "AI_CLI_TIMEOUT": "120",
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
    assert settings.ai_provider == "gemini"
    assert settings.ai_model == "gemini-2.5-pro"
    assert settings.ai_cli_timeout == 120
    assert settings.log_level == "DEBUG"


def test_invalid_timeout_rejected() -> None:
    from docsfy.config import Settings

    with patch.dict(os.environ, {"AI_CLI_TIMEOUT": "0"}, clear=True):
        with pytest.raises(Exception):
            Settings()
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_config.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

Create `src/docsfy/config.py`:

```python
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add configuration module with pydantic-settings"
```

---

## Task 3: Pydantic Models

**Files:**
- Create: `src/docsfy/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
from __future__ import annotations

import pytest


def test_generate_request_valid_https() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="https://github.com/org/repo.git")
    assert req.repo_url == "https://github.com/org/repo.git"


def test_generate_request_valid_ssh() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="git@github.com:org/repo.git")
    assert req.repo_url == "git@github.com:org/repo.git"


def test_generate_request_extracts_project_name() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="https://github.com/org/my-repo.git")
    assert req.project_name == "my-repo"

    req2 = GenerateRequest(repo_url="https://github.com/org/my-repo")
    assert req2.project_name == "my-repo"


def test_generate_request_invalid_url() -> None:
    from docsfy.models import GenerateRequest

    with pytest.raises(Exception):
        GenerateRequest(repo_url="not-a-url")


def test_doc_page_model() -> None:
    from docsfy.models import DocPage

    page = DocPage(slug="intro", title="Introduction", description="Project overview")
    assert page.slug == "intro"


def test_doc_plan_model() -> None:
    from docsfy.models import DocPage, DocPlan, NavGroup

    plan = DocPlan(
        project_name="my-repo",
        tagline="A cool project",
        navigation=[
            NavGroup(
                group="Getting Started",
                pages=[DocPage(slug="intro", title="Introduction", description="Overview")],
            )
        ],
    )
    assert plan.project_name == "my-repo"
    assert len(plan.navigation) == 1
    assert len(plan.navigation[0].pages) == 1


def test_project_status_model() -> None:
    from docsfy.models import ProjectStatus

    status = ProjectStatus(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="ready",
    )
    assert status.name == "my-repo"
    assert status.status == "ready"
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_models.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `src/docsfy/models.py`:

```python
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class GenerateRequest(BaseModel):
    repo_url: str = Field(description="Git repository URL (HTTPS or SSH)")
    ai_provider: Literal["claude", "gemini", "cursor"] | None = None
    ai_model: str | None = None
    ai_cli_timeout: int | None = Field(default=None, gt=0)

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        https_pattern = r"^https?://[\w.\-]+/[\w.\-]+/[\w.\-]+(\.git)?$"
        ssh_pattern = r"^git@[\w.\-]+:[\w.\-]+/[\w.\-]+(\.git)?$"
        if not re.match(https_pattern, v) and not re.match(ssh_pattern, v):
            msg = f"Invalid git repository URL: '{v}'"
            raise ValueError(msg)
        return v

    @property
    def project_name(self) -> str:
        name = self.repo_url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name


class DocPage(BaseModel):
    slug: str
    title: str
    description: str = ""


class NavGroup(BaseModel):
    group: str
    pages: list[DocPage]


class DocPlan(BaseModel):
    project_name: str
    tagline: str = ""
    navigation: list[NavGroup] = Field(default_factory=list)


class ProjectStatus(BaseModel):
    name: str
    repo_url: str
    status: Literal["generating", "ready", "error"] = "generating"
    last_commit_sha: str | None = None
    last_generated: str | None = None
    error_message: str | None = None
    page_count: int = 0
```

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/models.py tests/test_models.py
git commit -m "feat: add pydantic models for requests, doc plans, and project status"
```

---

## Task 4: SQLite Storage Layer

**Files:**
- Create: `src/docsfy/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write the failing test**

Create `tests/test_storage.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
async def db_path(tmp_path: Path) -> Path:
    import docsfy.storage as storage

    db = tmp_path / "test.db"
    storage.DB_PATH = db
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    await storage.init_db()
    return db


async def test_init_db_creates_table(db_path: Path) -> None:
    assert db_path.exists()


async def test_save_and_get_project(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
    )
    project = await get_project("my-repo")
    assert project is not None
    assert project["name"] == "my-repo"
    assert project["repo_url"] == "https://github.com/org/my-repo.git"
    assert project["status"] == "generating"


async def test_update_project_status(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project, update_project_status

    await save_project(name="my-repo", repo_url="https://github.com/org/my-repo.git", status="generating")
    await update_project_status("my-repo", status="ready", last_commit_sha="abc123", page_count=5)
    project = await get_project("my-repo")
    assert project is not None
    assert project["status"] == "ready"
    assert project["last_commit_sha"] == "abc123"
    assert project["page_count"] == 5


async def test_list_projects(db_path: Path) -> None:
    from docsfy.storage import list_projects, save_project

    await save_project(name="repo-a", repo_url="https://github.com/org/repo-a.git", status="ready")
    await save_project(name="repo-b", repo_url="https://github.com/org/repo-b.git", status="generating")
    projects = await list_projects()
    assert len(projects) == 2


async def test_delete_project(db_path: Path) -> None:
    from docsfy.storage import delete_project, get_project, save_project

    await save_project(name="my-repo", repo_url="https://github.com/org/my-repo.git", status="ready")
    deleted = await delete_project("my-repo")
    assert deleted is True
    project = await get_project("my-repo")
    assert project is None


async def test_delete_nonexistent_project(db_path: Path) -> None:
    from docsfy.storage import delete_project

    deleted = await delete_project("no-such-repo")
    assert deleted is False


async def test_get_nonexistent_project(db_path: Path) -> None:
    from docsfy.storage import get_project

    project = await get_project("no-such-repo")
    assert project is None
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_storage.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `src/docsfy/storage.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

import aiosqlite

DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT PRIMARY KEY,
                repo_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'generating',
                last_commit_sha TEXT,
                last_generated TEXT,
                page_count INTEGER DEFAULT 0,
                error_message TEXT,
                plan_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def save_project(name: str, repo_url: str, status: str = "generating") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO projects (name, repo_url, status, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (name, repo_url, status),
        )
        await db.commit()


async def update_project_status(
    name: str,
    status: str,
    last_commit_sha: str | None = None,
    page_count: int | None = None,
    error_message: str | None = None,
    plan_json: str | None = None,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        values: list[str | int | None] = [status]

        if last_commit_sha is not None:
            fields.append("last_commit_sha = ?")
            values.append(last_commit_sha)
        if page_count is not None:
            fields.append("page_count = ?")
            values.append(page_count)
        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)
        if plan_json is not None:
            fields.append("plan_json = ?")
            values.append(plan_json)
        if status == "ready":
            fields.append("last_generated = CURRENT_TIMESTAMP")

        values.append(name)
        await db.execute(f"UPDATE projects SET {', '.join(fields)} WHERE name = ?", values)
        await db.commit()


async def get_project(name: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM projects WHERE name = ?", (name,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def list_projects() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT name, repo_url, status, last_commit_sha, last_generated, page_count FROM projects ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_project(name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM projects WHERE name = ?", (name,))
        await db.commit()
        return cursor.rowcount > 0


def get_project_dir(name: str) -> Path:
    return PROJECTS_DIR / name


def get_project_site_dir(name: str) -> Path:
    return PROJECTS_DIR / name / "site"


def get_project_cache_dir(name: str) -> Path:
    return PROJECTS_DIR / name / "cache" / "pages"
```

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_storage.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/storage.py tests/test_storage.py
git commit -m "feat: add SQLite storage layer for project metadata"
```

---

## Task 5: AI CLI Provider Module

**Files:**
- Create: `src/docsfy/ai_client.py`
- Create: `tests/test_ai_client.py`

**Step 1: Write the failing test**

Create `tests/test_ai_client.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_provider_config_registry() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG, VALID_AI_PROVIDERS

    assert "claude" in PROVIDER_CONFIG
    assert "gemini" in PROVIDER_CONFIG
    assert "cursor" in PROVIDER_CONFIG
    assert VALID_AI_PROVIDERS == {"claude", "gemini", "cursor"}


def test_build_claude_cmd() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG

    config = PROVIDER_CONFIG["claude"]
    cmd = config.build_cmd(config.binary, "claude-opus-4-6", None)
    assert cmd == ["claude", "--model", "claude-opus-4-6", "--dangerously-skip-permissions", "-p"]
    assert config.uses_own_cwd is False


def test_build_gemini_cmd() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG

    config = PROVIDER_CONFIG["gemini"]
    cmd = config.build_cmd(config.binary, "gemini-2.5-pro", None)
    assert cmd == ["gemini", "--model", "gemini-2.5-pro", "--yolo"]
    assert config.uses_own_cwd is False


def test_build_cursor_cmd() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG

    config = PROVIDER_CONFIG["cursor"]
    cmd = config.build_cmd(config.binary, "claude-sonnet", Path("/tmp/repo"))
    assert cmd == ["agent", "--force", "--model", "claude-sonnet", "--print", "--workspace", "/tmp/repo"]
    assert config.uses_own_cwd is True


def test_build_cursor_cmd_no_cwd() -> None:
    from docsfy.ai_client import PROVIDER_CONFIG

    config = PROVIDER_CONFIG["cursor"]
    cmd = config.build_cmd(config.binary, "claude-sonnet", None)
    assert "--workspace" not in cmd


async def test_call_ai_cli_unknown_provider() -> None:
    from docsfy.ai_client import call_ai_cli

    success, msg = await call_ai_cli("hello", ai_provider="unknown", ai_model="test")
    assert success is False
    assert "Unknown AI provider" in msg


async def test_call_ai_cli_no_model() -> None:
    from docsfy.ai_client import call_ai_cli

    success, msg = await call_ai_cli("hello", ai_provider="claude", ai_model="")
    assert success is False
    assert "No AI model" in msg


async def test_call_ai_cli_success() -> None:
    from docsfy.ai_client import call_ai_cli

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "AI response here"
    mock_result.stderr = ""

    with patch("docsfy.ai_client.asyncio.to_thread", return_value=mock_result):
        success, output = await call_ai_cli("test prompt", ai_provider="claude", ai_model="opus")
    assert success is True
    assert output == "AI response here"


async def test_call_ai_cli_nonzero_exit() -> None:
    from docsfy.ai_client import call_ai_cli

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "some error"

    with patch("docsfy.ai_client.asyncio.to_thread", return_value=mock_result):
        success, output = await call_ai_cli("test", ai_provider="claude", ai_model="opus")
    assert success is False
    assert "some error" in output


async def test_call_ai_cli_timeout() -> None:
    import subprocess

    from docsfy.ai_client import call_ai_cli

    with patch("docsfy.ai_client.asyncio.to_thread", side_effect=subprocess.TimeoutExpired("cmd", 60)):
        success, output = await call_ai_cli("test", ai_provider="claude", ai_model="opus", ai_cli_timeout=1)
    assert success is False
    assert "timed out" in output


async def test_call_ai_cli_binary_not_found() -> None:
    from docsfy.ai_client import call_ai_cli

    with patch("docsfy.ai_client.asyncio.to_thread", side_effect=FileNotFoundError()):
        success, output = await call_ai_cli("test", ai_provider="claude", ai_model="opus")
    assert success is False
    assert "not found" in output


async def test_check_ai_cli_available_success() -> None:
    from docsfy.ai_client import check_ai_cli_available

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Hello!"
    mock_result.stderr = ""

    with patch("docsfy.ai_client.asyncio.to_thread", return_value=mock_result):
        success, msg = await check_ai_cli_available("claude", "opus")
    assert success is True


async def test_check_ai_cli_available_failure() -> None:
    from docsfy.ai_client import check_ai_cli_available

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "auth error"

    with patch("docsfy.ai_client.asyncio.to_thread", return_value=mock_result):
        success, msg = await check_ai_cli_available("claude", "opus")
    assert success is False
    assert "sanity check failed" in msg
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_ai_client.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `src/docsfy/ai_client.py`:

```python
from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)


@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable[[str, str, Path | None], list[str]]
    uses_own_cwd: bool = False


def _build_claude_cmd(binary: str, model: str, _cwd: Path | None) -> list[str]:
    return [binary, "--model", model, "--dangerously-skip-permissions", "-p"]


def _build_gemini_cmd(binary: str, model: str, _cwd: Path | None) -> list[str]:
    return [binary, "--model", model, "--yolo"]


def _build_cursor_cmd(binary: str, model: str, cwd: Path | None) -> list[str]:
    cmd = [binary, "--force", "--model", model, "--print"]
    if cwd:
        cmd.extend(["--workspace", str(cwd)])
    return cmd


PROVIDER_CONFIG: dict[str, ProviderConfig] = {
    "claude": ProviderConfig(binary="claude", build_cmd=_build_claude_cmd),
    "gemini": ProviderConfig(binary="gemini", build_cmd=_build_gemini_cmd),
    "cursor": ProviderConfig(binary="agent", uses_own_cwd=True, build_cmd=_build_cursor_cmd),
}
VALID_AI_PROVIDERS = set(PROVIDER_CONFIG.keys())


def _get_ai_cli_timeout() -> int:
    raw = os.getenv("AI_CLI_TIMEOUT", "60")
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError
        return value
    except (ValueError, TypeError):
        logger.warning(f"Invalid AI_CLI_TIMEOUT={raw}; defaulting to 60")
        return 60


AI_CLI_TIMEOUT = _get_ai_cli_timeout()


async def call_ai_cli(
    prompt: str,
    cwd: Path | None = None,
    ai_provider: str = "",
    ai_model: str = "",
    ai_cli_timeout: int | None = None,
) -> tuple[bool, str]:
    config = PROVIDER_CONFIG.get(ai_provider)
    if not config:
        return (False, f"Unknown AI provider: '{ai_provider}'. Valid: {', '.join(sorted(VALID_AI_PROVIDERS))}")

    if not ai_model:
        return (False, "No AI model configured. Set AI_MODEL environment variable.")

    provider_info = f"{ai_provider.upper()} ({ai_model})"
    cmd = config.build_cmd(config.binary, ai_model, cwd)
    subprocess_cwd = None if config.uses_own_cwd else cwd
    effective_timeout = ai_cli_timeout or AI_CLI_TIMEOUT
    timeout = effective_timeout * 60

    logger.info(f"Calling {provider_info} CLI")

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            cwd=subprocess_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=prompt,
        )
    except subprocess.TimeoutExpired:
        return (False, f"{provider_info} CLI error: timed out after {effective_timeout} minutes")
    except FileNotFoundError:
        return (False, f"{provider_info} CLI error: '{config.binary}' not found in PATH")

    if result.returncode != 0:
        error_detail = result.stderr or result.stdout or "unknown error (no output)"
        return False, f"{provider_info} CLI error: {error_detail}"

    logger.debug(f"{provider_info} CLI response length: {len(result.stdout)} chars")
    return True, result.stdout


async def check_ai_cli_available(ai_provider: str, ai_model: str) -> tuple[bool, str]:
    config = PROVIDER_CONFIG.get(ai_provider)
    if not config:
        return (False, f"Unknown AI provider: '{ai_provider}'")
    if not ai_model:
        return (False, "No AI model configured")

    provider_info = f"{ai_provider.upper()} ({ai_model})"
    sanity_cmd = config.build_cmd(config.binary, ai_model, None)

    try:
        sanity_result = await asyncio.to_thread(
            subprocess.run, sanity_cmd, cwd=None, capture_output=True, text=True, timeout=60, input="Hi",
        )
        if sanity_result.returncode != 0:
            error_detail = sanity_result.stderr or sanity_result.stdout or "unknown"
            return False, f"{provider_info} sanity check failed: {error_detail}"
    except subprocess.TimeoutExpired:
        return False, f"{provider_info} sanity check timed out"
    except FileNotFoundError:
        return False, f"{provider_info}: '{config.binary}' not found in PATH"

    return True, ""
```

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_ai_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/ai_client.py tests/test_ai_client.py
git commit -m "feat: add AI CLI provider module with claude, gemini, and cursor support"
```

---

## Task 6: JSON Response Parser

**Files:**
- Create: `src/docsfy/json_parser.py`
- Create: `tests/test_json_parser.py`

**Step 1: Write the failing test**

Create `tests/test_json_parser.py`:

```python
from __future__ import annotations

import json


def test_parse_direct_json() -> None:
    from docsfy.json_parser import parse_json_response

    data = {"project_name": "test", "navigation": []}
    result = parse_json_response(json.dumps(data))
    assert result == data


def test_parse_json_with_surrounding_text() -> None:
    from docsfy.json_parser import parse_json_response

    raw = 'Here is the plan:\n{"project_name": "test", "navigation": []}\nDone!'
    result = parse_json_response(raw)
    assert result is not None
    assert result["project_name"] == "test"


def test_parse_json_from_code_block() -> None:
    from docsfy.json_parser import parse_json_response

    raw = '```json\n{"project_name": "test", "navigation": []}\n```'
    result = parse_json_response(raw)
    assert result is not None
    assert result["project_name"] == "test"


def test_parse_json_nested_braces() -> None:
    from docsfy.json_parser import parse_json_response

    data = {"project_name": "test", "meta": {"key": "value"}, "navigation": []}
    raw = f"Some text before {json.dumps(data)} some text after"
    result = parse_json_response(raw)
    assert result is not None
    assert result["meta"]["key"] == "value"


def test_parse_json_returns_none_for_garbage() -> None:
    from docsfy.json_parser import parse_json_response

    result = parse_json_response("this is not json at all")
    assert result is None


def test_parse_json_empty_string() -> None:
    from docsfy.json_parser import parse_json_response

    result = parse_json_response("")
    assert result is None


def test_parse_json_with_escaped_quotes() -> None:
    from docsfy.json_parser import parse_json_response

    raw = '{"project_name": "test \\"quoted\\" name", "navigation": []}'
    result = parse_json_response(raw)
    assert result is not None
    assert "quoted" in result["project_name"]
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_json_parser.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `src/docsfy/json_parser.py`:

```python
from __future__ import annotations

import json
import re

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)


def parse_json_response(raw_text: str) -> dict | None:
    text = raw_text.strip()
    if not text:
        return None

    # Strategy 1: Direct parse
    if text.startswith("{"):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 2: Brace matching
    result = _extract_json_by_braces(text)
    if result is not None:
        return result

    # Strategy 3: Markdown code blocks
    result = _extract_json_from_code_blocks(text)
    if result is not None:
        return result

    logger.warning("Failed to parse AI response as JSON")
    return None


def _extract_json_by_braces(text: str) -> dict | None:
    first_brace = text.find("{")
    if first_brace == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    end_pos = -1

    for i in range(first_brace, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            if in_string:
                escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end_pos = i
                break

    if end_pos == -1:
        return None

    json_str = text[first_brace : end_pos + 1]
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json_from_code_blocks(text: str) -> dict | None:
    blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    for block_content in blocks:
        block_content = block_content.strip()
        if not block_content or "{" not in block_content:
            continue
        try:
            return json.loads(block_content)
        except (json.JSONDecodeError, ValueError):
            pass
        result = _extract_json_by_braces(block_content)
        if result is not None:
            return result
    return None
```

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_json_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/json_parser.py tests/test_json_parser.py
git commit -m "feat: add multi-strategy JSON response parser for AI CLI output"
```

---

## Task 7: Repository Cloning

**Files:**
- Create: `src/docsfy/repository.py`
- Create: `tests/test_repository.py`

**Step 1: Write the failing test**

Create `tests/test_repository.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def test_extract_repo_name_https() -> None:
    from docsfy.repository import extract_repo_name

    assert extract_repo_name("https://github.com/org/my-repo.git") == "my-repo"
    assert extract_repo_name("https://github.com/org/my-repo") == "my-repo"


def test_extract_repo_name_ssh() -> None:
    from docsfy.repository import extract_repo_name

    assert extract_repo_name("git@github.com:org/my-repo.git") == "my-repo"


def test_clone_repo_success(tmp_path: Path) -> None:
    from docsfy.repository import clone_repo

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="abc123def\n", stderr=""),
        ]
        repo_path, sha = clone_repo("https://github.com/org/repo.git", tmp_path)

    assert repo_path == tmp_path / "repo"
    assert sha == "abc123def"


def test_clone_repo_failure(tmp_path: Path) -> None:
    import pytest

    from docsfy.repository import clone_repo

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: repo not found")
        with pytest.raises(RuntimeError, match="Clone failed"):
            clone_repo("https://github.com/org/bad-repo.git", tmp_path)
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_repository.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `src/docsfy/repository.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from simple_logger.logger import get_logger

logger = get_logger(name=__name__)


def extract_repo_name(repo_url: str) -> str:
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    if ":" in name:
        name = name.split(":")[-1].split("/")[-1]
    return name


def clone_repo(repo_url: str, base_dir: Path) -> tuple[Path, str]:
    repo_name = extract_repo_name(repo_url)
    repo_path = base_dir / repo_name

    logger.info(f"Cloning {repo_url} to {repo_path}")

    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = f"Clone failed: {result.stderr or result.stdout}"
        raise RuntimeError(msg)

    sha_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    commit_sha = sha_result.stdout.strip()

    logger.info(f"Cloned {repo_name} at commit {commit_sha[:8]}")
    return repo_path, commit_sha
```

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_repository.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/repository.py tests/test_repository.py
git commit -m "feat: add repository cloning with shallow clone support"
```

---

## Task 8: AI Prompt Templates

**Files:**
- Create: `src/docsfy/prompts.py`
- Create: `tests/test_prompts.py`

**Step 1: Write the failing test**

Create `tests/test_prompts.py`:

```python
from __future__ import annotations


def test_build_planner_prompt() -> None:
    from docsfy.prompts import build_planner_prompt

    prompt = build_planner_prompt("my-repo")
    assert "my-repo" in prompt
    assert "JSON" in prompt
    assert "project_name" in prompt
    assert "navigation" in prompt


def test_build_page_prompt() -> None:
    from docsfy.prompts import build_page_prompt

    prompt = build_page_prompt(
        project_name="my-repo",
        page_title="Installation",
        page_description="How to install the project",
    )
    assert "my-repo" in prompt
    assert "Installation" in prompt
    assert "markdown" in prompt.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_prompts.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `src/docsfy/prompts.py`:

```python
from __future__ import annotations

PLAN_SCHEMA = """{
  "project_name": "string - project name",
  "tagline": "string - one-line project description",
  "navigation": [
    {
      "group": "string - section group name",
      "pages": [
        {
          "slug": "string - URL-friendly page identifier",
          "title": "string - human-readable page title",
          "description": "string - brief description of what this page covers"
        }
      ]
    }
  ]
}"""


def build_planner_prompt(project_name: str) -> str:
    return f"""You are a technical documentation planner. Explore this repository thoroughly.
Read the README, source code, configuration files, tests, and any existing documentation.
Understand what this project does, how it works, and who uses it.

Then create a documentation plan as a JSON object. The plan should cover:
- Introduction and overview
- Installation / getting started
- Configuration (if applicable)
- Usage guides for key features
- API reference (if the project has an API)
- Any other sections that would help users understand and use this project

Project name: {project_name}

CRITICAL: Your response must be ONLY a valid JSON object. No text before or after. No markdown code blocks.

Output format:
{PLAN_SCHEMA}"""


def build_page_prompt(project_name: str, page_title: str, page_description: str) -> str:
    return f"""You are a technical documentation writer. Explore this repository to write
the "{page_title}" page for the {project_name} documentation.

Page description: {page_description}

Explore the codebase as needed. Read source files, configs, tests, and existing docs
to write comprehensive, accurate documentation.

Write in markdown format. Include:
- Clear explanations
- Code examples from the actual codebase (not made up)
- Configuration snippets where relevant

Use these callout formats for special content:
- Notes: > **Note:** text
- Warnings: > **Warning:** text
- Tips: > **Tip:** text

Output ONLY the markdown content for this page. No wrapping, no explanation."""
```

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_prompts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/prompts.py tests/test_prompts.py
git commit -m "feat: add AI prompt templates for planner and page generation"
```

---

## Task 9: Documentation Generator (Orchestrator)

**Files:**
- Create: `src/docsfy/generator.py`
- Create: `tests/test_generator.py`

**Step 1: Write the failing test**

Create `tests/test_generator.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def sample_plan() -> dict:
    return {
        "project_name": "test-repo",
        "tagline": "A test project",
        "navigation": [
            {
                "group": "Getting Started",
                "pages": [
                    {"slug": "introduction", "title": "Introduction", "description": "Overview"},
                    {"slug": "quickstart", "title": "Quick Start", "description": "Get started fast"},
                ],
            }
        ],
    }


async def test_run_planner(tmp_path: Path, sample_plan: dict) -> None:
    from docsfy.generator import run_planner

    with patch("docsfy.generator.call_ai_cli", return_value=(True, json.dumps(sample_plan))):
        plan = await run_planner(repo_path=tmp_path, project_name="test-repo", ai_provider="claude", ai_model="opus")

    assert plan is not None
    assert plan["project_name"] == "test-repo"
    assert len(plan["navigation"]) == 1


async def test_run_planner_ai_failure(tmp_path: Path) -> None:
    from docsfy.generator import run_planner

    with patch("docsfy.generator.call_ai_cli", return_value=(False, "AI error")):
        with pytest.raises(RuntimeError, match="AI error"):
            await run_planner(repo_path=tmp_path, project_name="test-repo", ai_provider="claude", ai_model="opus")


async def test_run_planner_bad_json(tmp_path: Path) -> None:
    from docsfy.generator import run_planner

    with patch("docsfy.generator.call_ai_cli", return_value=(True, "not json")):
        with pytest.raises(RuntimeError, match="Failed to parse"):
            await run_planner(repo_path=tmp_path, project_name="test-repo", ai_provider="claude", ai_model="opus")


async def test_generate_page(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    with patch("docsfy.generator.call_ai_cli", return_value=(True, "# Introduction\n\nWelcome!")):
        md = await generate_page(
            repo_path=tmp_path, slug="introduction", title="Introduction", description="Overview",
            cache_dir=cache_dir, ai_provider="claude", ai_model="opus",
        )

    assert "# Introduction" in md
    assert (cache_dir / "introduction.md").exists()


async def test_generate_page_uses_cache(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached = cache_dir / "introduction.md"
    cached.write_text("# Cached content")

    md = await generate_page(
        repo_path=tmp_path, slug="introduction", title="Introduction", description="Overview",
        cache_dir=cache_dir, ai_provider="claude", ai_model="opus", use_cache=True,
    )

    assert md == "# Cached content"
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_generator.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `src/docsfy/generator.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path

from simple_logger.logger import get_logger

from docsfy.ai_client import call_ai_cli
from docsfy.json_parser import parse_json_response
from docsfy.prompts import build_page_prompt, build_planner_prompt

logger = get_logger(name=__name__)

MAX_CONCURRENT_PAGES = 5


async def run_planner(
    repo_path: Path, project_name: str, ai_provider: str, ai_model: str, ai_cli_timeout: int | None = None,
) -> dict:
    prompt = build_planner_prompt(project_name)
    success, output = await call_ai_cli(
        prompt=prompt, cwd=repo_path, ai_provider=ai_provider, ai_model=ai_model, ai_cli_timeout=ai_cli_timeout,
    )
    if not success:
        msg = f"Planner failed: {output}"
        raise RuntimeError(msg)

    plan = parse_json_response(output)
    if plan is None:
        msg = "Failed to parse planner output as JSON"
        raise RuntimeError(msg)

    logger.info(f"Plan generated: {len(plan.get('navigation', []))} groups")
    return plan


async def generate_page(
    repo_path: Path, slug: str, title: str, description: str, cache_dir: Path,
    ai_provider: str, ai_model: str, ai_cli_timeout: int | None = None, use_cache: bool = False,
) -> str:
    cache_file = cache_dir / f"{slug}.md"
    if use_cache and cache_file.exists():
        logger.debug(f"Using cached page: {slug}")
        return cache_file.read_text()

    prompt = build_page_prompt(project_name=repo_path.name, page_title=title, page_description=description)
    success, output = await call_ai_cli(
        prompt=prompt, cwd=repo_path, ai_provider=ai_provider, ai_model=ai_model, ai_cli_timeout=ai_cli_timeout,
    )
    if not success:
        logger.warning(f"Failed to generate page '{slug}': {output}")
        output = f"# {title}\n\n*Documentation generation failed. Please re-run.*"

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(output)
    logger.info(f"Generated page: {slug} ({len(output)} chars)")
    return output


async def generate_all_pages(
    repo_path: Path, plan: dict, cache_dir: Path, ai_provider: str, ai_model: str,
    ai_cli_timeout: int | None = None, use_cache: bool = False,
) -> dict[str, str]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)
    pages: dict[str, str] = {}

    async def _gen(slug: str, title: str, description: str) -> tuple[str, str]:
        async with semaphore:
            md = await generate_page(
                repo_path=repo_path, slug=slug, title=title, description=description,
                cache_dir=cache_dir, ai_provider=ai_provider, ai_model=ai_model,
                ai_cli_timeout=ai_cli_timeout, use_cache=use_cache,
            )
            return slug, md

    tasks = []
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            tasks.append(_gen(page["slug"], page["title"], page.get("description", "")))

    results = await asyncio.gather(*tasks)
    for slug, md in results:
        pages[slug] = md

    logger.info(f"Generated {len(pages)} pages total")
    return pages
```

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_generator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/generator.py tests/test_generator.py
git commit -m "feat: add documentation generator with planner and concurrent page generation"
```

---

## Task 10: HTML Renderer

**Files:**
- Create: `src/docsfy/renderer.py`
- Create: `src/docsfy/templates/page.html`
- Create: `src/docsfy/templates/index.html`
- Create: `src/docsfy/static/style.css`
- Create: `src/docsfy/static/theme.js`
- Create: `src/docsfy/static/search.js`
- Create: `tests/test_renderer.py`

This is the largest task. The HTML template and CSS create the Mintlify-level polish. Reference the site at https://myk-org-github-webhook-server.mintlify.app/introduction for design inspiration.

**Step 1: Write the failing test**

Create `tests/test_renderer.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_render_page_to_html() -> None:
    from docsfy.renderer import render_page

    html = render_page(
        markdown_content="# Hello\n\nThis is a test.",
        page_title="Hello", project_name="test-repo", tagline="A test project",
        navigation=[{"group": "Docs", "pages": [{"slug": "hello", "title": "Hello"}]}],
        current_slug="hello",
    )
    assert "<html" in html
    assert "Hello" in html
    assert "test-repo" in html
    assert "This is a test." in html


def test_render_site(tmp_path: Path) -> None:
    from docsfy.renderer import render_site

    plan = {
        "project_name": "test-repo", "tagline": "A test project",
        "navigation": [
            {"group": "Getting Started", "pages": [
                {"slug": "introduction", "title": "Introduction", "description": "Overview"},
            ]},
        ],
    }
    pages = {"introduction": "# Introduction\n\nWelcome to test-repo."}
    output_dir = tmp_path / "site"

    render_site(plan=plan, pages=pages, output_dir=output_dir)

    assert (output_dir / "index.html").exists()
    assert (output_dir / "introduction.html").exists()
    assert (output_dir / "assets" / "style.css").exists()
    index_html = (output_dir / "index.html").read_text()
    assert "test-repo" in index_html
    page_html = (output_dir / "introduction.html").read_text()
    assert "Welcome to test-repo" in page_html


def test_search_index_generated(tmp_path: Path) -> None:
    from docsfy.renderer import render_site

    plan = {
        "project_name": "test-repo", "tagline": "Test",
        "navigation": [{"group": "Docs", "pages": [{"slug": "intro", "title": "Intro", "description": ""}]}],
    }
    pages = {"intro": "# Intro\n\nSome searchable content here."}
    output_dir = tmp_path / "site"

    render_site(plan=plan, pages=pages, output_dir=output_dir)
    assert (output_dir / "search-index.json").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_renderer.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create the renderer module, Jinja2 HTML templates (page.html, index.html), and static assets (style.css, theme.js, search.js). The templates should include:
- Sidebar navigation with group headers and page links
- Dark/light theme toggle button
- Search input with client-side filtering
- Responsive layout (mobile-friendly)
- Code syntax highlighting via Pygments CSS classes
- Callout box styling for Note/Warning/Tip blockquotes
- Card grid on index page for navigation groups
- Active page highlighting in sidebar

The `render_site()` function converts markdown to HTML via the `markdown` library with extensions (fenced_code, codehilite, tables, toc), renders each page into the template, copies static assets, and builds a search index JSON.

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_renderer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/renderer.py src/docsfy/templates/ src/docsfy/static/ tests/test_renderer.py
git commit -m "feat: add HTML renderer with Jinja2 templates, dark/light theme, and search"
```

---

## Task 11: FastAPI Application

**Files:**
- Create: `src/docsfy/main.py`
- Create: `tests/test_main.py`

**Step 1: Write the failing test**

Create `tests/test_main.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(tmp_path: Path):
    import docsfy.storage as storage

    storage.DB_PATH = tmp_path / "test.db"
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"

    from docsfy.main import app

    await storage.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_status_endpoint_empty(client: AsyncClient) -> None:
    response = await client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["projects"] == []


async def test_generate_endpoint_invalid_url(client: AsyncClient) -> None:
    response = await client.post("/api/generate", json={"repo_url": "not-a-url"})
    assert response.status_code == 422


async def test_generate_endpoint_starts_generation(client: AsyncClient) -> None:
    with patch("docsfy.main.asyncio.create_task"):
        response = await client.post("/api/generate", json={"repo_url": "https://github.com/org/repo.git"})
    assert response.status_code == 202
    body = response.json()
    assert body["project"] == "repo"
    assert body["status"] == "generating"


async def test_get_project_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/projects/nonexistent")
    assert response.status_code == 404


async def test_delete_project_not_found(client: AsyncClient) -> None:
    response = await client.delete("/api/projects/nonexistent")
    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_main.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `src/docsfy/main.py` with:
- FastAPI app with lifespan (calls `init_db()` on startup)
- `GET /health` - returns `{"status": "ok"}`
- `GET /api/status` - lists all projects from DB
- `POST /api/generate` (202) - validates `GenerateRequest`, saves project to DB, starts `_run_generation()` as background task via `asyncio.create_task()`
- `GET /api/projects/{name}` - returns project details or 404
- `DELETE /api/projects/{name}` - deletes project from DB and filesystem or 404
- `GET /api/projects/{name}/download` - creates tar.gz of site dir and streams it
- `GET /docs/{project}/{path:path}` - serves static files from project's site dir with path traversal protection
- `run()` function for CLI entry point using `uvicorn.run()`

The `_run_generation()` background task:
1. Checks AI CLI availability
2. Clones repo to tempdir
3. Checks if already up-to-date (same commit SHA)
4. Runs AI planner
5. Generates all pages
6. Renders HTML site
7. Saves plan.json to project dir
8. Updates DB status to "ready" (or "error" on exception)

**Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/docsfy/main.py tests/test_main.py
git commit -m "feat: add FastAPI application with all API endpoints"
```

---

## Task 12: Integration Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write the integration test**

Create `tests/test_integration.py` that tests the full flow with mocked AI:
1. Call `_run_generation()` with mocked `check_ai_cli_available`, `clone_repo`, `run_planner`, `generate_all_pages`
2. Verify project status is "ready" via `GET /api/status`
3. Verify project details via `GET /api/projects/{name}`
4. Verify docs are served via `GET /docs/{project}/index.html`
5. Verify download works via `GET /api/projects/{name}/download`
6. Verify delete works via `DELETE /api/projects/{name}`

**Step 2: Run all tests**

Run: `uv run --extra dev pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for full generate-serve-download flow"
```

---

## Task 13: Final Verification

**Step 1: Run full test suite**

```bash
uv run --extra dev pytest tests/ -v --tb=short
```
Expected: ALL PASS

**Step 2: Run pre-commit hooks**

```bash
pre-commit install
pre-commit run --all-files
```
Expected: ALL PASS (fix any issues that arise)

**Step 3: Verify project structure**

```bash
find src/docsfy -type f | sort
```

Expected:
```
src/docsfy/__init__.py
src/docsfy/ai_client.py
src/docsfy/config.py
src/docsfy/generator.py
src/docsfy/json_parser.py
src/docsfy/main.py
src/docsfy/models.py
src/docsfy/prompts.py
src/docsfy/renderer.py
src/docsfy/repository.py
src/docsfy/static/search.js
src/docsfy/static/style.css
src/docsfy/static/theme.js
src/docsfy/storage.py
src/docsfy/templates/index.html
src/docsfy/templates/page.html
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```
