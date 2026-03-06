from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

TEST_ADMIN_KEY = "test-admin-secret-key"


@pytest.fixture
async def db_path(tmp_path: Path) -> Path:
    import docsfy.storage as storage

    db = tmp_path / "test.db"
    storage.DB_PATH = db
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    with patch.dict(os.environ, {"ADMIN_KEY": TEST_ADMIN_KEY}):
        await storage.init_db()
        yield db


async def test_init_db_creates_table(db_path: Path) -> None:
    assert db_path.exists()


async def test_save_and_get_project(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
    )
    project = await get_project("my-repo", ai_provider="claude", ai_model="opus")
    assert project is not None
    assert project["name"] == "my-repo"
    assert project["repo_url"] == "https://github.com/org/my-repo.git"
    assert project["status"] == "generating"
    assert project["ai_provider"] == "claude"
    assert project["ai_model"] == "opus"


async def test_update_project_status(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project, update_project_status

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
    )
    await update_project_status(
        "my-repo",
        "claude",
        "opus",
        status="ready",
        last_commit_sha="abc123",
        page_count=5,
    )
    project = await get_project("my-repo", ai_provider="claude", ai_model="opus")
    assert project is not None
    assert project["status"] == "ready"
    assert project["last_commit_sha"] == "abc123"
    assert project["page_count"] == 5


async def test_list_projects(db_path: Path) -> None:
    from docsfy.storage import list_projects, save_project

    await save_project(
        name="repo-a",
        repo_url="https://github.com/org/repo-a.git",
        status="ready",
        ai_provider="claude",
        ai_model="opus",
    )
    await save_project(
        name="repo-b",
        repo_url="https://github.com/org/repo-b.git",
        status="generating",
        ai_provider="gemini",
        ai_model="pro",
    )
    projects = await list_projects()
    assert len(projects) == 2


async def test_delete_project(db_path: Path) -> None:
    from docsfy.storage import delete_project, get_project, save_project

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="ready",
        ai_provider="claude",
        ai_model="opus",
    )
    deleted = await delete_project("my-repo", ai_provider="claude", ai_model="opus")
    assert deleted is True
    project = await get_project("my-repo", ai_provider="claude", ai_model="opus")
    assert project is None


async def test_delete_nonexistent_project(db_path: Path) -> None:
    from docsfy.storage import delete_project

    deleted = await delete_project("no-such-repo")
    assert deleted is False


async def test_get_nonexistent_project(db_path: Path) -> None:
    from docsfy.storage import get_project

    project = await get_project("no-such-repo")
    assert project is None


async def test_get_known_models(db_path: Path) -> None:
    from docsfy.storage import get_known_models, save_project, update_project_status

    await save_project(
        name="repo-a",
        repo_url="https://github.com/org/a.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus-4-6",
    )
    await update_project_status(
        "repo-a",
        "claude",
        "opus-4-6",
        status="ready",
    )
    await save_project(
        name="repo-b",
        repo_url="https://github.com/org/b.git",
        status="generating",
        ai_provider="claude",
        ai_model="sonnet-4-6",
    )
    await update_project_status(
        "repo-b",
        "claude",
        "sonnet-4-6",
        status="ready",
    )
    await save_project(
        name="repo-c",
        repo_url="https://github.com/org/c.git",
        status="generating",
        ai_provider="gemini",
        ai_model="gemini-2.5-pro",
    )
    await update_project_status(
        "repo-c",
        "gemini",
        "gemini-2.5-pro",
        status="ready",
    )

    models = await get_known_models()
    assert "claude" in models
    assert "opus-4-6" in models["claude"]
    assert "sonnet-4-6" in models["claude"]
    assert "gemini" in models
    assert "gemini-2.5-pro" in models["gemini"]


async def test_init_db_resets_orphaned_generating(db_path: Path) -> None:
    from docsfy.storage import get_project, init_db, save_project

    await save_project(
        name="stuck-repo",
        repo_url="https://github.com/org/stuck.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
    )

    # Simulate server restart by re-running init_db
    await init_db()

    project = await get_project("stuck-repo", ai_provider="claude", ai_model="opus")
    assert project is not None
    assert project["status"] == "error"
    assert "Server restarted" in project["error_message"]


async def test_update_project_with_ai_info(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project, update_project_status

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus-4-6",
    )
    await update_project_status(
        "my-repo",
        "claude",
        "opus-4-6",
        status="ready",
        last_commit_sha="abc123",
        page_count=5,
    )
    project = await get_project("my-repo", ai_provider="claude", ai_model="opus-4-6")
    assert project is not None
    assert project["ai_provider"] == "claude"
    assert project["ai_model"] == "opus-4-6"


async def test_multiple_variants_same_repo(db_path: Path) -> None:
    from docsfy.storage import get_project, list_projects, save_project

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="claude",
        ai_model="opus",
    )
    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="gemini",
        ai_model="pro",
    )

    projects = await list_projects()
    assert len(projects) == 2

    p1 = await get_project("repo", ai_provider="claude", ai_model="opus")
    assert p1 is not None
    assert p1["ai_provider"] == "claude"

    p2 = await get_project("repo", ai_provider="gemini", ai_model="pro")
    assert p2 is not None
    assert p2["ai_provider"] == "gemini"


async def test_delete_specific_variant(db_path: Path) -> None:
    from docsfy.storage import delete_project, list_projects, save_project

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="claude",
        ai_model="opus",
    )
    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="gemini",
        ai_model="pro",
    )

    deleted = await delete_project("repo", ai_provider="claude", ai_model="opus")
    assert deleted is True

    projects = await list_projects()
    assert len(projects) == 1
    assert projects[0]["ai_provider"] == "gemini"


async def test_list_variants(db_path: Path) -> None:
    from docsfy.storage import list_variants, save_project

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="claude",
        ai_model="opus",
    )
    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="gemini",
        ai_model="pro",
    )

    variants = await list_variants("repo")
    assert len(variants) == 2


async def test_get_latest_variant(db_path: Path) -> None:
    import aiosqlite

    from docsfy.storage import (
        DB_PATH,
        get_latest_variant,
        save_project,
        update_project_status,
    )

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="claude",
        ai_model="opus",
    )
    await update_project_status(
        "repo", "claude", "opus", status="ready", last_commit_sha="abc"
    )

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="gemini",
        ai_model="pro",
    )
    await update_project_status(
        "repo", "gemini", "pro", status="ready", last_commit_sha="def"
    )

    # Manually set last_generated to ensure deterministic ordering
    # (CURRENT_TIMESTAMP may resolve to the same second for both rows)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET last_generated = '2025-01-01 00:00:00' WHERE ai_provider = 'claude'"
        )
        await db.execute(
            "UPDATE projects SET last_generated = '2025-01-02 00:00:00' WHERE ai_provider = 'gemini'"
        )
        await db.commit()

    latest = await get_latest_variant("repo")
    assert latest is not None
    # gemini has a later last_generated timestamp
    assert latest["ai_provider"] == "gemini"


# ---------------------------------------------------------------------------
# Test: session management
# ---------------------------------------------------------------------------


async def test_create_and_get_session(db_path: Path) -> None:
    from docsfy.storage import create_session, get_session

    token = await create_session("testuser", is_admin=False)
    assert token  # token is non-empty

    session = await get_session(token)
    assert session is not None
    assert session["username"] == "testuser"
    assert session["is_admin"] == 0


async def test_create_admin_session(db_path: Path) -> None:
    from docsfy.storage import create_session, get_session

    token = await create_session("admin", is_admin=True)
    session = await get_session(token)
    assert session is not None
    assert session["is_admin"] == 1


async def test_delete_session(db_path: Path) -> None:
    from docsfy.storage import create_session, delete_session, get_session

    token = await create_session("testuser")
    session = await get_session(token)
    assert session is not None

    await delete_session(token)
    session = await get_session(token)
    assert session is None


async def test_expired_session_not_returned(db_path: Path) -> None:
    import aiosqlite

    from docsfy.storage import DB_PATH, get_session

    # Directly insert a session with a past expiration
    token = "expired-test-token"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (token, username, is_admin, expires_at) VALUES (?, ?, ?, ?)",
            (token, "testuser", 0, "2020-01-01T00:00:00"),
        )
        await db.commit()

    # Session should not be found since it's expired
    session = await get_session(token)
    assert session is None


async def test_get_nonexistent_session(db_path: Path) -> None:
    from docsfy.storage import get_session

    session = await get_session("nonexistent-token")
    assert session is None


async def test_cleanup_expired_sessions(db_path: Path) -> None:
    import aiosqlite

    from docsfy.storage import (
        DB_PATH,
        _hash_session_token,
        cleanup_expired_sessions,
        create_session,
    )

    # Directly insert a session with a past expiration
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (token, username, is_admin, expires_at) VALUES (?, ?, ?, ?)",
            ("expired-token", "expired-user", 0, "2020-01-01T00:00:00"),
        )
        await db.commit()

    # Create a valid session
    valid_token = await create_session("valid-user", ttl_hours=8)

    await cleanup_expired_sessions()

    # Check that only the valid session remains
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM sessions")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1

        # Session tokens are stored as hashes
        token_hash = _hash_session_token(valid_token)
        cursor = await db.execute(
            "SELECT username FROM sessions WHERE token = ?", (token_hash,)
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "valid-user"


# ---------------------------------------------------------------------------
# Test: HMAC-based key hashing
# ---------------------------------------------------------------------------


async def test_hash_api_key_is_hmac(db_path: Path) -> None:
    """hash_api_key should use HMAC, not plain SHA-256."""
    import hashlib

    from docsfy.storage import hash_api_key

    key = "test-key-12345"
    hmac_hash = hash_api_key(key)
    plain_sha256 = hashlib.sha256(key.encode()).hexdigest()
    # HMAC hash should differ from plain SHA-256
    assert hmac_hash != plain_sha256


# ---------------------------------------------------------------------------
# Test: username 'admin' is reserved
# ---------------------------------------------------------------------------


async def test_create_user_rejects_admin_username(db_path: Path) -> None:
    from docsfy.storage import create_user

    with pytest.raises(ValueError, match="reserved"):
        await create_user("admin")

    with pytest.raises(ValueError, match="reserved"):
        await create_user("Admin")

    with pytest.raises(ValueError, match="reserved"):
        await create_user("ADMIN")


# ---------------------------------------------------------------------------
# Test: get_user_by_username
# ---------------------------------------------------------------------------


async def test_get_user_by_username(db_path: Path) -> None:
    from docsfy.storage import create_user, get_user_by_username

    await create_user("lookup-user")
    user = await get_user_by_username("lookup-user")
    assert user is not None
    assert user["username"] == "lookup-user"

    missing = await get_user_by_username("nonexistent")
    assert missing is None


# ---------------------------------------------------------------------------
# Test: project access management
# ---------------------------------------------------------------------------


async def test_grant_and_get_project_access(db_path: Path) -> None:
    from docsfy.storage import get_project_access, grant_project_access

    await grant_project_access("my-repo", "alice")
    await grant_project_access("my-repo", "bob")

    users = await get_project_access("my-repo")
    assert "alice" in users
    assert "bob" in users


async def test_revoke_project_access(db_path: Path) -> None:
    from docsfy.storage import (
        get_project_access,
        grant_project_access,
        revoke_project_access,
    )

    await grant_project_access("my-repo", "alice")
    await revoke_project_access("my-repo", "alice")

    users = await get_project_access("my-repo")
    assert "alice" not in users


async def test_get_user_accessible_projects(db_path: Path) -> None:
    from docsfy.storage import get_user_accessible_projects, grant_project_access

    await grant_project_access("repo-a", "alice")
    await grant_project_access("repo-b", "alice")

    projects = await get_user_accessible_projects("alice")
    assert "repo-a" in projects
    assert "repo-b" in projects
