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
