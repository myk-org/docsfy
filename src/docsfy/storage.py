from __future__ import annotations

import os
import re
from pathlib import Path

import aiosqlite
from simple_logger.logger import get_logger

logger = get_logger(name=__name__)

VALID_STATUSES = frozenset({"generating", "ready", "error", "aborted"})

_UNSET: object = object()

# Module-level paths are set at import time from env vars.
# Tests override these globals directly for isolation.
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
                current_stage TEXT,
                last_commit_sha TEXT,
                last_generated TEXT,
                page_count INTEGER DEFAULT 0,
                error_message TEXT,
                plan_json TEXT,
                ai_provider TEXT,
                ai_model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migrate old databases: add columns if they don't exist
        import sqlite3

        for column in ["ai_provider TEXT", "ai_model TEXT", "current_stage TEXT"]:
            try:
                await db.execute(f"ALTER TABLE projects ADD COLUMN {column}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" in str(exc).lower():
                    continue
                logger.error(f"Migration failed while adding '{column}': {exc}")
                raise

        # Reset orphaned "generating" projects from previous server run
        cursor = await db.execute(
            "UPDATE projects SET status = 'error', error_message = 'Server restarted during generation', current_stage = NULL WHERE status = 'generating'"
        )
        if cursor.rowcount > 0:
            logger.info(
                f"Reset {cursor.rowcount} orphaned generating project(s) to error status"
            )

        await db.commit()


async def save_project(name: str, repo_url: str, status: str = "generating") -> None:
    if status not in VALID_STATUSES:
        msg = f"Invalid project status: '{status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"
        raise ValueError(msg)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO projects (name, repo_url, status, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(name) DO UPDATE SET
               repo_url = excluded.repo_url,
               status = excluded.status,
               current_stage = NULL,
               error_message = NULL,
               updated_at = CURRENT_TIMESTAMP""",
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
    ai_provider: str | None = None,
    ai_model: str | None = None,
    current_stage: str | None | object = _UNSET,
) -> None:
    if status not in VALID_STATUSES:
        msg = f"Invalid project status: '{status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"
        raise ValueError(msg)
    async with aiosqlite.connect(DB_PATH) as db:
        fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        values: list[str | int | None] = [status]
        if current_stage is not _UNSET:
            fields.append("current_stage = ?")
            values.append(current_stage)  # type: ignore[arg-type]
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
        if ai_provider is not None:
            fields.append("ai_provider = ?")
            values.append(ai_provider)
        if ai_model is not None:
            fields.append("ai_model = ?")
            values.append(ai_model)
        if status == "ready":
            fields.append("last_generated = CURRENT_TIMESTAMP")
        values.append(name)
        # Fields list is built from hardcoded column names only (no user input)
        await db.execute(
            f"UPDATE projects SET {', '.join(fields)} WHERE name = ?", values
        )
        await db.commit()


async def get_project(name: str) -> dict[str, str | int | None] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM projects WHERE name = ?", (name,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def list_projects() -> list[dict[str, str | int | None]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT name, repo_url, status, current_stage, last_commit_sha, last_generated, page_count, error_message, plan_json, ai_provider, ai_model FROM projects ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_project(name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM projects WHERE name = ?", (name,))
        await db.commit()
        return cursor.rowcount > 0


def _validate_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        msg = f"Invalid project name: '{name}'"
        raise ValueError(msg)
    return name


def get_project_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name)


def get_project_site_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "site"


def get_project_cache_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "cache" / "pages"


async def get_known_models() -> dict[str, list[str]]:
    """Get distinct ai_model values per ai_provider from completed projects."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT DISTINCT ai_provider, ai_model FROM projects WHERE ai_provider IS NOT NULL AND ai_model IS NOT NULL AND status = 'ready' ORDER BY ai_provider, ai_model"
        )
        rows = await cursor.fetchall()
        models: dict[str, list[str]] = {}
        for provider, model in rows:
            if provider not in models:
                models[provider] = []
            if model not in models[provider]:
                models[provider].append(model)
        return models
