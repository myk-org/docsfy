from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
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
                name TEXT NOT NULL,
                ai_provider TEXT NOT NULL DEFAULT '',
                ai_model TEXT NOT NULL DEFAULT '',
                repo_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'generating',
                current_stage TEXT,
                last_commit_sha TEXT,
                last_generated TEXT,
                page_count INTEGER DEFAULT 0,
                error_message TEXT,
                plan_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (name, ai_provider, ai_model)
            )
        """)

        # Migration: convert old single-PK table to composite PK
        cursor = await db.execute("PRAGMA table_info(projects)")
        columns = await cursor.fetchall()
        col_names = [c[1] for c in columns]

        # Check if ai_provider is already NOT NULL (new schema) or nullable (old schema)
        # If 'ai_provider' column doesn't exist or is nullable, we need to migrate
        needs_migration = "ai_provider" not in col_names
        if not needs_migration:
            # Check if it's the old schema where ai_provider was added as nullable
            for col in columns:
                if col[1] == "ai_provider" and col[3] == 0:  # notnull=0 means nullable
                    needs_migration = True
                    break

        if needs_migration:
            logger.info("Migrating database to composite PK schema")

            # Check which columns exist in the old table
            cursor = await db.execute("PRAGMA table_info(projects)")
            old_columns = {row[1] for row in await cursor.fetchall()}

            await db.execute("""
                CREATE TABLE IF NOT EXISTS projects_new (
                    name TEXT NOT NULL,
                    ai_provider TEXT NOT NULL DEFAULT '',
                    ai_model TEXT NOT NULL DEFAULT '',
                    repo_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'generating',
                    current_stage TEXT,
                    last_commit_sha TEXT,
                    last_generated TEXT,
                    page_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    plan_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (name, ai_provider, ai_model)
                )
            """)

            # Build SELECT with safe defaults for missing columns
            select_cols = []
            select_cols.append("name")
            select_cols.append(
                "COALESCE(ai_provider, '') AS ai_provider"
                if "ai_provider" in old_columns
                else "'' AS ai_provider"
            )
            select_cols.append(
                "COALESCE(ai_model, '') AS ai_model"
                if "ai_model" in old_columns
                else "'' AS ai_model"
            )
            select_cols.append("repo_url")
            select_cols.append("status")
            select_cols.append(
                "current_stage"
                if "current_stage" in old_columns
                else "NULL AS current_stage"
            )
            select_cols.append("last_commit_sha")
            select_cols.append("last_generated")
            select_cols.append("page_count")
            select_cols.append("error_message")
            select_cols.append("plan_json")
            select_cols.append("created_at")
            select_cols.append("updated_at")

            await db.execute(f"""
                INSERT OR IGNORE INTO projects_new
                    (name, ai_provider, ai_model, repo_url, status, current_stage,
                     last_commit_sha, last_generated, page_count, error_message,
                     plan_json, created_at, updated_at)
                SELECT {", ".join(select_cols)}
                FROM projects
            """)
            await db.execute("DROP TABLE projects")
            await db.execute("ALTER TABLE projects_new RENAME TO projects")
            logger.info("Database migration complete")

        # Migration: add owner column
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN owner TEXT DEFAULT ''")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                logger.error(f"Migration failed: {exc}")
                raise

        # Reset orphaned "generating" projects from previous server run
        cursor = await db.execute(
            "UPDATE projects SET status = 'error', error_message = 'Server restarted during generation', current_stage = NULL WHERE status = 'generating'"
        )
        if cursor.rowcount > 0:
            logger.info(
                f"Reset {cursor.rowcount} orphaned generating project(s) to error status"
            )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                api_key_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: add role column for existing DBs
        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
            )
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                logger.error(f"Migration failed: {exc}")
                raise

        await db.execute("""
            CREATE TABLE IF NOT EXISTS project_access (
                project_name TEXT NOT NULL,
                username TEXT NOT NULL,
                PRIMARY KEY (project_name, username)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        """)

        await db.commit()


async def save_project(
    name: str,
    repo_url: str,
    status: str = "generating",
    ai_provider: str = "",
    ai_model: str = "",
    owner: str = "",
) -> None:
    if status not in VALID_STATUSES:
        msg = f"Invalid project status: '{status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"
        raise ValueError(msg)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO projects (name, ai_provider, ai_model, repo_url, status, owner, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(name, ai_provider, ai_model) DO UPDATE SET
               repo_url = excluded.repo_url,
               status = excluded.status,
               owner = excluded.owner,
               error_message = NULL,
               current_stage = NULL,
               updated_at = CURRENT_TIMESTAMP""",
            (name, ai_provider, ai_model, repo_url, status, owner),
        )
        await db.commit()


async def update_project_status(
    name: str,
    ai_provider: str,
    ai_model: str,
    status: str,
    last_commit_sha: str | None = None,
    page_count: int | None = None,
    error_message: str | None = None,
    plan_json: str | None = None,
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
        if status == "ready":
            fields.append("last_generated = CURRENT_TIMESTAMP")
        values.append(name)
        values.append(ai_provider)
        values.append(ai_model)
        # Fields list is built from hardcoded column names only (no user input)
        await db.execute(
            f"UPDATE projects SET {', '.join(fields)} WHERE name = ? AND ai_provider = ? AND ai_model = ?",
            values,
        )
        await db.commit()


async def get_project(
    name: str,
    ai_provider: str = "",
    ai_model: str = "",
) -> dict[str, str | int | None] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM projects WHERE name = ? AND ai_provider = ? AND ai_model = ?",
            (name, ai_provider, ai_model),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_projects(
    owner: str | None = None,
    accessible_names: list[str] | None = None,
) -> list[dict[str, str | int | None]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if owner and accessible_names:
            # Show owned + assigned projects
            placeholders = ",".join("?" * len(accessible_names))
            cursor = await db.execute(
                f"SELECT * FROM projects WHERE owner = ? OR name IN ({placeholders}) ORDER BY updated_at DESC",
                [owner] + accessible_names,
            )
        elif owner:
            cursor = await db.execute(
                "SELECT * FROM projects WHERE owner = ? ORDER BY updated_at DESC",
                (owner,),
            )
        else:
            cursor = await db.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def grant_project_access(project_name: str, username: str) -> None:
    """Grant a user access to all variants of a project."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO project_access (project_name, username) VALUES (?, ?)",
            (project_name, username),
        )
        await db.commit()


async def revoke_project_access(project_name: str, username: str) -> None:
    """Revoke a user's access to a project."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM project_access WHERE project_name = ? AND username = ?",
            (project_name, username),
        )
        await db.commit()


async def get_project_access(project_name: str) -> list[str]:
    """Get list of usernames with access to a project."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT username FROM project_access WHERE project_name = ? ORDER BY username",
            (project_name,),
        )
        return [row[0] for row in await cursor.fetchall()]


async def get_user_accessible_projects(username: str) -> list[str]:
    """Get list of project names a user has been granted access to."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT project_name FROM project_access WHERE username = ? ORDER BY project_name",
            (username,),
        )
        return [row[0] for row in await cursor.fetchall()]


async def delete_project(name: str, ai_provider: str = "", ai_model: str = "") -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM projects WHERE name = ? AND ai_provider = ? AND ai_model = ?",
            (name, ai_provider, ai_model),
        )
        await db.commit()
        return cursor.rowcount > 0


def _validate_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        msg = f"Invalid project name: '{name}'"
        raise ValueError(msg)
    return name


def get_project_dir(name: str, ai_provider: str = "", ai_model: str = "") -> Path:
    if not ai_provider or not ai_model:
        msg = "ai_provider and ai_model are required for project directory paths"
        raise ValueError(msg)
    # Sanitize path segments to prevent traversal
    for segment_name, segment in [("ai_provider", ai_provider), ("ai_model", ai_model)]:
        if (
            "/" in segment
            or "\\" in segment
            or ".." in segment
            or segment.startswith(".")
        ):
            msg = f"Invalid {segment_name}: '{segment}'"
            raise ValueError(msg)
    return PROJECTS_DIR / _validate_name(name) / ai_provider / ai_model


def get_project_site_dir(name: str, ai_provider: str = "", ai_model: str = "") -> Path:
    return get_project_dir(name, ai_provider, ai_model) / "site"


def get_project_cache_dir(name: str, ai_provider: str = "", ai_model: str = "") -> Path:
    return get_project_dir(name, ai_provider, ai_model) / "cache" / "pages"


async def list_variants(name: str) -> list[dict[str, str | int | None]]:
    """List all variants for a repo."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM projects WHERE name = ? ORDER BY updated_at DESC",
            (name,),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def get_latest_variant(name: str) -> dict[str, str | int | None] | None:
    """Get the most recently generated ready variant for a repo."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM projects WHERE name = ? AND status = 'ready' ORDER BY last_generated DESC LIMIT 1",
            (name,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_known_models() -> dict[str, list[str]]:
    """Get distinct ai_model values per ai_provider from completed projects."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT DISTINCT ai_provider, ai_model FROM projects WHERE ai_provider != '' AND ai_model != '' AND status = 'ready' ORDER BY ai_provider, ai_model"
        )
        rows = await cursor.fetchall()
        models: dict[str, list[str]] = {}
        for provider, model in rows:
            if provider not in models:
                models[provider] = []
            if model not in models[provider]:
                models[provider].append(model)
        return models


def hash_api_key(key: str) -> str:
    """Hash an API key with HMAC-SHA256 for storage.

    Uses a fixed prefix as the HMAC key. The API keys themselves are random
    and high-entropy, so a simple HMAC prevents rainbow table attacks.
    """
    return hmac.new(b"docsfy-api-key-hmac", key.encode(), hashlib.sha256).hexdigest()


def generate_api_key() -> str:
    """Generate a random API key."""
    return f"docsfy_{secrets.token_urlsafe(32)}"


VALID_ROLES = frozenset({"admin", "user", "viewer"})


async def create_user(username: str, role: str = "user") -> tuple[str, str]:
    """Create a user and return (username, raw_api_key)."""
    if username.lower() == "admin":
        msg = "Username 'admin' is reserved"
        raise ValueError(msg)
    if role not in VALID_ROLES:
        msg = f"Invalid role: '{role}'. Must be admin, user, or viewer."
        raise ValueError(msg)
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (username, api_key_hash, role) VALUES (?, ?, ?)",
            (username, key_hash, role),
        )
        await db.commit()
    return username, raw_key


async def get_user_by_key(api_key: str) -> dict[str, str | int | None] | None:
    """Look up a user by their raw API key."""
    key_hash = hash_api_key(api_key)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE api_key_hash = ?", (key_hash,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_user(username: str) -> bool:
    """Delete a user by username."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM users WHERE username = ?", (username,))
        await db.commit()
        return cursor.rowcount > 0


async def list_users() -> list[dict[str, str | int | None]]:
    """List all users (without key hashes)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY created_at DESC"
        )
        return [dict(row) for row in await cursor.fetchall()]


async def get_user_by_username(username: str) -> dict[str, str | int | None] | None:
    """Look up a user by username."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_session(
    username: str, is_admin: bool = False, ttl_hours: int = 8
) -> str:
    """Create an opaque session token."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (token, username, is_admin, expires_at) VALUES (?, ?, ?, ?)",
            (token, username, 1 if is_admin else 0, expires_at.isoformat()),
        )
        await db.commit()
    return token


async def get_session(token: str) -> dict[str, str | int | None] | None:
    """Look up a session. Returns None if expired or not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_session(token: str) -> None:
    """Delete a session (logout)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()


async def cleanup_expired_sessions() -> None:
    """Remove expired sessions."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
        await db.commit()
