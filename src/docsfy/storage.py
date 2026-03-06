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

MIN_KEY_LENGTH = 16

SESSION_TTL_SECONDS = 28800  # 8 hours
SESSION_TTL_HOURS = SESSION_TTL_SECONDS // 3600


def validate_api_key(key: str) -> None:
    """Validate API key meets minimum requirements."""
    if len(key) < MIN_KEY_LENGTH:
        msg = f"API key must be at least {MIN_KEY_LENGTH} characters long"
        raise ValueError(msg)


_UNSET: object = object()

# Module-level paths are set at import time from env vars.
# Tests override these globals directly for isolation.
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"


async def init_db(data_dir: str = "") -> None:
    """Initialize the database and run migrations.

    Fix 11: Accept an optional data_dir to centralise storage path
    configuration and avoid split-brain between config.py and module globals.
    """
    global DB_PATH, DATA_DIR, PROJECTS_DIR
    if data_dir:
        DB_PATH = Path(data_dir) / "docsfy.db"
        DATA_DIR = Path(data_dir)
        PROJECTS_DIR = DATA_DIR / "projects"

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT NOT NULL,
                ai_provider TEXT NOT NULL DEFAULT '',
                ai_model TEXT NOT NULL DEFAULT '',
                owner TEXT NOT NULL DEFAULT '',
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
                PRIMARY KEY (name, ai_provider, ai_model, owner)
            )
        """)

        # Migration: convert old 3-column PK table to 4-column PK (with owner)
        cursor = await db.execute("PRAGMA table_info(projects)")
        columns = await cursor.fetchall()
        col_names = [c[1] for c in columns]

        needs_pk_migration = False

        # Detect old schema: owner not in columns, or owner is nullable
        if "owner" not in col_names:
            needs_pk_migration = True
        elif "ai_provider" not in col_names:
            needs_pk_migration = True
        else:
            # Check if ai_provider is nullable (old schema)
            for col in columns:
                if col[1] == "ai_provider" and col[3] == 0:  # notnull=0 means nullable
                    needs_pk_migration = True
                    break

        # Also detect when owner exists but is NOT part of the PK
        # by checking if a 3-column PK table was already created
        if not needs_pk_migration and "owner" in col_names:
            # Check the table_info for whether owner has pk index > 0
            owner_is_pk = False
            for col in columns:
                if col[1] == "owner" and col[5] > 0:  # pk column index
                    owner_is_pk = True
                    break
            if not owner_is_pk:
                needs_pk_migration = True

        if needs_pk_migration:
            logger.info(
                "Migrating database to 4-column PK schema (name, ai_provider, ai_model, owner)"
            )

            # Check which columns exist in the old table
            cursor = await db.execute("PRAGMA table_info(projects)")
            old_columns = {row[1] for row in await cursor.fetchall()}

            await db.execute("DROP TABLE IF EXISTS projects_new")
            await db.execute("""
                CREATE TABLE projects_new (
                    name TEXT NOT NULL,
                    ai_provider TEXT NOT NULL DEFAULT '',
                    ai_model TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
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
                    PRIMARY KEY (name, ai_provider, ai_model, owner)
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
            select_cols.append(
                "COALESCE(owner, '') AS owner"
                if "owner" in old_columns
                else "'' AS owner"
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
                    (name, ai_provider, ai_model, owner, repo_url, status, current_stage,
                     last_commit_sha, last_generated, page_count, error_message,
                     plan_json, created_at, updated_at)
                SELECT {", ".join(select_cols)}
                FROM projects
            """)
            await db.execute("DROP TABLE projects")
            await db.execute("ALTER TABLE projects_new RENAME TO projects")
            logger.info("Database migration to 4-column PK complete")

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
                api_key_hash TEXT NOT NULL UNIQUE,
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
                logger.exception("Migration failed while adding column")
                raise

        # Migration: add UNIQUE constraint on api_key_hash (Fix 7)
        # Check if existing table lacks the UNIQUE constraint by inspecting index
        cursor = await db.execute("PRAGMA index_list(users)")
        indexes = await cursor.fetchall()
        has_unique_key_index = False
        for idx in indexes:
            if idx[2]:  # unique=1
                cursor2 = await db.execute(f"PRAGMA index_info({idx[1]})")
                idx_cols = await cursor2.fetchall()
                for ic in idx_cols:
                    if ic[2] == "api_key_hash":
                        has_unique_key_index = True
                        break
            if has_unique_key_index:
                break

        if not has_unique_key_index:
            try:
                await db.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_api_key_hash ON users (api_key_hash)"
                )
            except sqlite3.OperationalError as exc:
                if "unique" not in str(exc).lower():
                    logger.exception("Migration failed while adding unique index")
                    raise

        await db.execute("""
            CREATE TABLE IF NOT EXISTS project_access (
                project_name TEXT NOT NULL,
                project_owner TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL,
                PRIMARY KEY (project_name, project_owner, username)
            )
        """)

        # Migration: add project_owner column to project_access
        try:
            await db.execute(
                "ALTER TABLE project_access ADD COLUMN project_owner TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                logger.exception("Migration failed while adding column")
                raise

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
            """INSERT INTO projects (name, ai_provider, ai_model, owner, repo_url, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(name, ai_provider, ai_model, owner) DO UPDATE SET
               repo_url = excluded.repo_url,
               status = excluded.status,
               error_message = NULL,
               current_stage = NULL,
               updated_at = CURRENT_TIMESTAMP""",
            (name, ai_provider, ai_model, owner, repo_url, status),
        )
        await db.commit()


async def update_project_status(
    name: str,
    ai_provider: str,
    ai_model: str,
    status: str,
    owner: str = "",
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
        where = "WHERE name = ? AND ai_provider = ? AND ai_model = ?"
        if owner:
            where += " AND owner = ?"
            values.append(owner)
        # Fields list is built from hardcoded column names only (no user input)
        await db.execute(
            f"UPDATE projects SET {', '.join(fields)} {where}",
            values,
        )
        await db.commit()


async def get_project(
    name: str,
    ai_provider: str = "",
    ai_model: str = "",
    owner: str | None = None,
) -> dict[str, str | int | None] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = (
            "SELECT * FROM projects WHERE name = ? AND ai_provider = ? AND ai_model = ?"
        )
        params: list[str] = [name, ai_provider, ai_model]
        if owner is not None:
            query += " AND owner = ?"
            params.append(owner)
        query += " ORDER BY CASE WHEN owner = '' THEN 1 ELSE 0 END"
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_projects(
    owner: str | None = None,
    accessible: list[tuple[str, str]] | None = None,
) -> list[dict[str, str | int | None]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if owner and accessible and len(accessible) > 0:
            # Build OR conditions for each (name, owner) pair
            conditions = ["(owner = ?)"]
            params: list[str] = [owner]
            for proj_name, proj_owner in accessible:
                conditions.append("(name = ? AND owner = ?)")
                params.extend([proj_name, proj_owner])
            query = f"SELECT * FROM projects WHERE {' OR '.join(conditions)} ORDER BY updated_at DESC"
            cursor = await db.execute(query, params)
        elif owner:
            cursor = await db.execute(
                "SELECT * FROM projects WHERE owner = ? ORDER BY updated_at DESC",
                (owner,),
            )
        else:
            cursor = await db.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def grant_project_access(
    project_name: str, username: str, project_owner: str = ""
) -> None:
    """Grant a user access to all variants of a project."""
    if not project_owner:
        msg = "project_owner is required for access grants"
        raise ValueError(msg)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO project_access (project_name, project_owner, username) VALUES (?, ?, ?)",
            (project_name, project_owner, username),
        )
        await db.commit()


async def revoke_project_access(
    project_name: str, username: str, project_owner: str = ""
) -> None:
    """Revoke a user's access to a project."""
    async with aiosqlite.connect(DB_PATH) as db:
        if project_owner:
            await db.execute(
                "DELETE FROM project_access WHERE project_name = ? AND project_owner = ? AND username = ?",
                (project_name, project_owner, username),
            )
        else:
            await db.execute(
                "DELETE FROM project_access WHERE project_name = ? AND username = ?",
                (project_name, username),
            )
        await db.commit()


async def get_project_access(project_name: str, project_owner: str = "") -> list[str]:
    """Get list of usernames with access to a project."""
    async with aiosqlite.connect(DB_PATH) as db:
        if project_owner:
            cursor = await db.execute(
                "SELECT username FROM project_access WHERE project_name = ? AND project_owner = ? ORDER BY username",
                (project_name, project_owner),
            )
        else:
            cursor = await db.execute(
                "SELECT username FROM project_access WHERE project_name = ? ORDER BY username",
                (project_name,),
            )
        return [row[0] for row in await cursor.fetchall()]


async def get_user_accessible_projects(username: str) -> list[tuple[str, str]]:
    """Get list of (project_name, project_owner) tuples a user has been granted access to."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT project_name, project_owner FROM project_access WHERE username = ? ORDER BY project_name",
            (username,),
        )
        return [(row[0], row[1]) for row in await cursor.fetchall()]


async def delete_project(
    name: str, ai_provider: str = "", ai_model: str = "", owner: str = ""
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        query = (
            "DELETE FROM projects WHERE name = ? AND ai_provider = ? AND ai_model = ?"
        )
        params: list[str] = [name, ai_provider, ai_model]
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        cursor = await db.execute(query, params)

        # Clean up project_access if no more variants remain for this name+owner
        if cursor.rowcount > 0 and owner:
            remaining = await db.execute(
                "SELECT COUNT(*) FROM projects WHERE name = ? AND owner = ?",
                (name, owner),
            )
            row = await remaining.fetchone()
            if row and row[0] == 0:
                await db.execute(
                    "DELETE FROM project_access WHERE project_name = ? AND project_owner = ?",
                    (name, owner),
                )

        await db.commit()
        return cursor.rowcount > 0


def _validate_name(name: str) -> str:
    """Validate project name to prevent path traversal."""
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        msg = f"Invalid project name: '{name}'"
        raise ValueError(msg)
    return name


def _validate_owner(owner: str) -> str:
    """Validate owner segment to prevent path traversal."""
    if not owner:
        return "_default"
    if "/" in owner or "\\" in owner or ".." in owner or owner.startswith("."):
        msg = f"Invalid owner: '{owner}'"
        raise ValueError(msg)
    return owner


def get_project_dir(
    name: str, ai_provider: str = "", ai_model: str = "", owner: str = ""
) -> Path:
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
    safe_owner = _validate_owner(owner)
    return PROJECTS_DIR / safe_owner / _validate_name(name) / ai_provider / ai_model


def get_project_site_dir(
    name: str, ai_provider: str = "", ai_model: str = "", owner: str = ""
) -> Path:
    return get_project_dir(name, ai_provider, ai_model, owner) / "site"


def get_project_cache_dir(
    name: str, ai_provider: str = "", ai_model: str = "", owner: str = ""
) -> Path:
    return get_project_dir(name, ai_provider, ai_model, owner) / "cache" / "pages"


async def list_variants(
    name: str, owner: str | None = None
) -> list[dict[str, str | int | None]]:
    """List all variants for a repo."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if owner:
            cursor = await db.execute(
                "SELECT * FROM projects WHERE name = ? AND owner = ? ORDER BY updated_at DESC",
                (name, owner),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM projects WHERE name = ? ORDER BY updated_at DESC",
                (name,),
            )
        return [dict(row) for row in await cursor.fetchall()]


async def get_latest_variant(
    name: str, owner: str | None = None
) -> dict[str, str | int | None] | None:
    """Get the most recently generated ready variant for a repo."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if owner:
            cursor = await db.execute(
                "SELECT * FROM projects WHERE name = ? AND owner = ? AND status = 'ready' ORDER BY last_generated DESC LIMIT 1",
                (name, owner),
            )
        else:
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


def hash_api_key(key: str, hmac_secret: str = "") -> str:
    """Hash an API key with HMAC-SHA256 for storage.

    Uses ADMIN_KEY as the HMAC secret so that even if the source is read,
    keys cannot be cracked without the environment secret.
    """
    secret = hmac_secret or os.getenv("ADMIN_KEY", "")
    if not secret:
        msg = "ADMIN_KEY environment variable is required for key hashing"
        raise RuntimeError(msg)
    return hmac.new(secret.encode(), key.encode(), hashlib.sha256).hexdigest()


def generate_api_key() -> str:
    """Generate a random API key."""
    return f"docsfy_{secrets.token_urlsafe(32)}"


VALID_ROLES = frozenset({"admin", "user", "viewer"})


async def create_user(username: str, role: str = "user") -> tuple[str, str]:
    """Create a user and return (username, raw_api_key)."""
    if username.lower() == "admin":
        msg = "Username 'admin' is reserved"
        raise ValueError(msg)
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,49}$", username):
        msg = f"Invalid username: '{username}'. Must be 2-50 alphanumeric characters, dots, hyphens, underscores."
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
    """Delete a user by username, invalidating all their sessions and cleaning up ACLs."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE username = ?", (username,))
        # Fix 4: Clean up ACL entries on user deletion
        await db.execute("DELETE FROM project_access WHERE username = ?", (username,))
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


def _hash_session_token(token: str) -> str:
    """Hash a session token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    username: str, is_admin: bool = False, ttl_hours: int = SESSION_TTL_HOURS
) -> str:
    """Create an opaque session token."""
    token = secrets.token_urlsafe(32)
    token_hash = _hash_session_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (token, username, is_admin, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, username, 1 if is_admin else 0, expires_str),
        )
        await db.commit()
    return token


async def get_session(token: str) -> dict[str, str | int | None] | None:
    """Look up a session. Returns None if expired or not found."""
    token_hash = _hash_session_token(token)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token_hash,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_session(token: str) -> None:
    """Delete a session (logout)."""
    token_hash = _hash_session_token(token)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token_hash,))
        await db.commit()


async def rotate_user_key(username: str, custom_key: str | None = None) -> str:
    """Generate or set a new API key for a user. Returns the raw new key."""
    if custom_key:
        validate_api_key(custom_key)
        raw_key = custom_key
    else:
        raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET api_key_hash = ? WHERE username = ?",
            (key_hash, username),
        )
        if cursor.rowcount == 0:
            msg = f"User '{username}' not found"
            raise ValueError(msg)
        # Invalidate all existing sessions for this user
        await db.execute("DELETE FROM sessions WHERE username = ?", (username,))
        await db.commit()
    return raw_key


async def cleanup_expired_sessions() -> None:
    """Remove expired sessions.

    NOTE: This is called during application startup (lifespan) only.
    Expired sessions accumulate between restarts but are harmless since
    get_session() filters by expires_at. For long-running deployments,
    consider calling this periodically (e.g., via a background task).
    TODO: Add periodic cleanup for long-running instances.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
        await db.commit()
