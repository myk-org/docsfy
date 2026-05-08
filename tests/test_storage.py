from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

TEST_ADMIN_KEY = "test-admin-secret-key"


@pytest.fixture
async def db_path(tmp_path: Path) -> Path:
    import docsfy.storage as storage

    # Save original globals to restore after test
    orig_db_path = storage.DB_PATH
    orig_data_dir = storage.DATA_DIR
    orig_projects_dir = storage.PROJECTS_DIR

    db = tmp_path / "test.db"
    storage.DB_PATH = db
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    with patch.dict(os.environ, {"ADMIN_KEY": TEST_ADMIN_KEY}):
        await storage.init_db()
        yield db

    # Restore original globals
    storage.DB_PATH = orig_db_path
    storage.DATA_DIR = orig_data_dir
    storage.PROJECTS_DIR = orig_projects_dir


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
        owner="testuser",
    )
    project = await get_project(
        "my-repo", ai_provider="claude", ai_model="opus", owner="testuser"
    )
    assert project is not None
    assert project["name"] == "my-repo"
    assert project["repo_url"] == "https://github.com/org/my-repo.git"
    assert project["status"] == "generating"
    assert project["ai_provider"] == "claude"
    assert project["ai_model"] == "opus"
    assert project["owner"] == "testuser"


async def test_update_project_status(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project, update_project_status

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="testuser",
    )
    await update_project_status(
        "my-repo",
        "claude",
        "opus",
        status="ready",
        owner="testuser",
        last_commit_sha="abc123",
        page_count=5,
    )
    project = await get_project(
        "my-repo", ai_provider="claude", ai_model="opus", owner="testuser"
    )
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
        owner="testuser",
    )
    await save_project(
        name="repo-b",
        repo_url="https://github.com/org/repo-b.git",
        status="generating",
        ai_provider="gemini",
        ai_model="pro",
        owner="testuser",
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
        owner="testuser",
    )
    deleted = await delete_project(
        "my-repo", ai_provider="claude", ai_model="opus", owner="testuser"
    )
    assert deleted is True
    project = await get_project(
        "my-repo", ai_provider="claude", ai_model="opus", owner="testuser"
    )
    assert project is None


async def test_delete_nonexistent_project(db_path: Path) -> None:
    from docsfy.storage import delete_project

    deleted = await delete_project("no-such-repo")
    assert deleted is False


async def test_get_nonexistent_project(db_path: Path) -> None:
    from docsfy.storage import get_project

    project = await get_project("no-such-repo")
    assert project is None


async def test_init_db_resets_orphaned_generating(db_path: Path) -> None:
    from docsfy.storage import get_project, init_db, save_project

    await save_project(
        name="stuck-repo",
        repo_url="https://github.com/org/stuck.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="testuser",
    )

    # Simulate server restart by re-running init_db
    await init_db()

    project = await get_project(
        "stuck-repo", ai_provider="claude", ai_model="opus", owner="testuser"
    )
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
        owner="testuser",
    )
    await update_project_status(
        "my-repo",
        "claude",
        "opus-4-6",
        status="ready",
        owner="testuser",
        last_commit_sha="abc123",
        page_count=5,
    )
    project = await get_project(
        "my-repo", ai_provider="claude", ai_model="opus-4-6", owner="testuser"
    )
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
        owner="testuser",
    )
    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="gemini",
        ai_model="pro",
        owner="testuser",
    )

    projects = await list_projects()
    assert len(projects) == 2

    p1 = await get_project(
        "repo", ai_provider="claude", ai_model="opus", owner="testuser"
    )
    assert p1 is not None
    assert p1["ai_provider"] == "claude"

    p2 = await get_project(
        "repo", ai_provider="gemini", ai_model="pro", owner="testuser"
    )
    assert p2 is not None
    assert p2["ai_provider"] == "gemini"


async def test_delete_specific_variant(db_path: Path) -> None:
    from docsfy.storage import delete_project, list_projects, save_project

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="claude",
        ai_model="opus",
        owner="testuser",
    )
    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="gemini",
        ai_model="pro",
        owner="testuser",
    )

    deleted = await delete_project(
        "repo", ai_provider="claude", ai_model="opus", owner="testuser"
    )
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
        owner="testuser",
    )
    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="gemini",
        ai_model="pro",
        owner="testuser",
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
        owner="testuser",
    )
    await update_project_status(
        "repo",
        "claude",
        "opus",
        status="ready",
        owner="testuser",
        last_commit_sha="abc",
    )

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        ai_provider="gemini",
        ai_model="pro",
        owner="testuser",
    )
    await update_project_status(
        "repo", "gemini", "pro", status="ready", owner="testuser", last_commit_sha="def"
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
# Test: per-user scoping -- two users can have same project name
# ---------------------------------------------------------------------------


async def test_per_user_scoping(db_path: Path) -> None:
    from docsfy.storage import get_project, list_projects, save_project

    await save_project(
        name="shared-name",
        repo_url="https://github.com/alice/repo.git",
        ai_provider="claude",
        ai_model="opus",
        owner="alice",
    )
    await save_project(
        name="shared-name",
        repo_url="https://github.com/bob/repo.git",
        ai_provider="claude",
        ai_model="opus",
        owner="bob",
    )

    # Both exist
    all_projects = await list_projects()
    assert len(all_projects) == 2

    # Each owner sees only their own
    alice_proj = await get_project(
        "shared-name", ai_provider="claude", ai_model="opus", owner="alice"
    )
    assert alice_proj is not None
    assert alice_proj["repo_url"] == "https://github.com/alice/repo.git"

    bob_proj = await get_project(
        "shared-name", ai_provider="claude", ai_model="opus", owner="bob"
    )
    assert bob_proj is not None
    assert bob_proj["repo_url"] == "https://github.com/bob/repo.git"

    # Filtered list by owner
    alice_list = await list_projects(owner="alice")
    assert len(alice_list) == 1
    assert alice_list[0]["owner"] == "alice"


# ---------------------------------------------------------------------------
# Test: delete_project cleans up project_access
# ---------------------------------------------------------------------------


async def test_delete_project_cleans_up_access(db_path: Path) -> None:
    from docsfy.storage import (
        delete_project,
        get_project_access,
        grant_project_access,
        save_project,
    )

    await save_project(
        name="cleanup-proj",
        repo_url="https://github.com/org/repo.git",
        ai_provider="claude",
        ai_model="opus",
        owner="testuser",
    )
    await grant_project_access("cleanup-proj", "alice", project_owner="testuser")

    # Delete the only variant
    await delete_project(
        "cleanup-proj", ai_provider="claude", ai_model="opus", owner="testuser"
    )

    # Access entries should be cleaned up
    users = await get_project_access("cleanup-proj", project_owner="testuser")
    assert len(users) == 0


# ---------------------------------------------------------------------------
# Test: delete_user cleans up project_access
# ---------------------------------------------------------------------------


async def test_delete_user_cleans_up_access(db_path: Path) -> None:
    from docsfy.storage import (
        create_user,
        delete_user,
        get_project_access,
        grant_project_access,
        save_project,
    )

    await create_user("cleanup-user")
    await save_project(
        name="some-proj",
        repo_url="https://github.com/org/repo.git",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )
    await grant_project_access("some-proj", "cleanup-user", project_owner="admin")

    await delete_user("cleanup-user")

    users = await get_project_access("some-proj", project_owner="admin")
    assert "cleanup-user" not in users


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

    from docsfy.storage import DB_PATH, _hash_session_token, get_session

    # Directly insert a session with a past expiration
    # Tokens are stored as hashes, so hash the token before inserting
    token = "expired-test-token"
    token_hash = _hash_session_token(token)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions (token, username, is_admin, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, "testuser", 0, "2020-01-01T00:00:00"),
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

    await grant_project_access("my-repo", "alice", project_owner="testowner")
    await grant_project_access("my-repo", "bob", project_owner="testowner")

    users = await get_project_access("my-repo", project_owner="testowner")
    assert "alice" in users
    assert "bob" in users


async def test_revoke_project_access(db_path: Path) -> None:
    from docsfy.storage import (
        get_project_access,
        grant_project_access,
        revoke_project_access,
    )

    await grant_project_access("my-repo", "alice", project_owner="testowner")
    await revoke_project_access("my-repo", "alice", project_owner="testowner")

    users = await get_project_access("my-repo", project_owner="testowner")
    assert "alice" not in users


async def test_get_user_accessible_projects(db_path: Path) -> None:
    from docsfy.storage import get_user_accessible_projects, grant_project_access

    await grant_project_access("repo-a", "alice", project_owner="owner1")
    await grant_project_access("repo-b", "alice", project_owner="owner2")

    projects = await get_user_accessible_projects("alice")
    assert ("repo-a", "owner1") in projects
    assert ("repo-b", "owner2") in projects


# ---------------------------------------------------------------------------
# Test: get_project_dir includes owner in path
# ---------------------------------------------------------------------------


async def test_list_projects_with_accessible_tuples(db_path: Path) -> None:
    """list_projects with accessible (name, owner) tuples should not expose other owners' same-name projects."""
    from docsfy.storage import list_projects, save_project

    # Alice and Bob both have a project named "shared-name"
    await save_project(
        name="shared-name",
        repo_url="https://github.com/alice/repo.git",
        ai_provider="claude",
        ai_model="opus",
        owner="alice",
    )
    await save_project(
        name="shared-name",
        repo_url="https://github.com/bob/repo.git",
        ai_provider="claude",
        ai_model="opus",
        owner="bob",
    )
    # Charlie has access to alice's project, but NOT bob's
    accessible: list[tuple[str, str]] = [("shared-name", "alice")]
    projects = await list_projects(owner="charlie", accessible=accessible)

    # Charlie should see only alice's project (not bob's)
    assert len(projects) == 1
    assert projects[0]["owner"] == "alice"


async def test_get_project_dir_includes_owner(db_path: Path) -> None:
    from docsfy.storage import get_project_dir

    path = get_project_dir("my-repo", "claude", "opus", "alice")
    assert "alice" in str(path)
    assert path.parts[-5:] == ("alice", "my-repo", "main", "claude", "opus")


async def test_get_project_dir_default_owner(db_path: Path) -> None:
    from docsfy.storage import get_project_dir

    path = get_project_dir("my-repo", "claude", "opus", "")
    assert "_default" in str(path)


# ---------------------------------------------------------------------------
# Test: init_db with data_dir parameter (Fix 11)
# ---------------------------------------------------------------------------


async def test_save_and_get_project_with_branch(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="testuser",
        branch="v2.0",
    )
    project = await get_project(
        "my-repo",
        ai_provider="claude",
        ai_model="opus",
        owner="testuser",
        branch="v2.0",
    )
    assert project is not None
    assert project["branch"] == "v2.0"


async def test_same_repo_different_branches(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        status="ready",
        ai_provider="claude",
        ai_model="opus",
        owner="user",
        branch="main",
    )
    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="user",
        branch="v2.0",
    )
    main_proj = await get_project(
        "repo", ai_provider="claude", ai_model="opus", owner="user", branch="main"
    )
    v2 = await get_project(
        "repo", ai_provider="claude", ai_model="opus", owner="user", branch="v2.0"
    )
    assert main_proj is not None
    assert v2 is not None
    assert main_proj["status"] == "ready"
    assert v2["status"] == "generating"


async def test_delete_project_with_branch(db_path: Path) -> None:
    from docsfy.storage import delete_project, get_project, save_project

    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        status="ready",
        ai_provider="claude",
        ai_model="opus",
        owner="user",
        branch="main",
    )
    await save_project(
        name="repo",
        repo_url="https://github.com/org/repo.git",
        status="ready",
        ai_provider="claude",
        ai_model="opus",
        owner="user",
        branch="v2.0",
    )
    result = await delete_project(
        "repo", ai_provider="claude", ai_model="opus", owner="user", branch="v2.0"
    )
    assert result is True
    project = await get_project(
        "repo", ai_provider="claude", ai_model="opus", owner="user", branch="v2.0"
    )
    assert project is None
    # Verify the main branch row still exists
    main = await get_project(
        "repo", ai_provider="claude", ai_model="opus", owner="user", branch="main"
    )
    assert main is not None


async def test_get_project_dir_with_branch(db_path: Path) -> None:
    from docsfy.storage import PROJECTS_DIR, get_project_dir

    result = get_project_dir(
        "my-repo", ai_provider="claude", ai_model="opus", owner="user", branch="main"
    )
    assert result == PROJECTS_DIR / "user" / "my-repo" / "main" / "claude" / "opus"


async def test_migration_adds_branch_default(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project

    await save_project(
        name="old-repo",
        repo_url="https://github.com/org/old.git",
        status="ready",
        ai_provider="claude",
        ai_model="opus",
        owner="user",
    )
    project = await get_project(
        "old-repo", ai_provider="claude", ai_model="opus", owner="user"
    )
    assert project is not None
    assert project["branch"] == "main"


# ---------------------------------------------------------------------------
# Test: init_db with data_dir parameter (Fix 11)
# ---------------------------------------------------------------------------


async def test_init_db_with_data_dir(tmp_path: Path) -> None:
    import docsfy.storage as storage

    # Save original globals to restore after test
    orig_db_path = storage.DB_PATH
    orig_data_dir = storage.DATA_DIR
    orig_projects_dir = storage.PROJECTS_DIR

    custom_dir = tmp_path / "custom_data"
    custom_dir.mkdir()

    try:
        with patch.dict(os.environ, {"ADMIN_KEY": TEST_ADMIN_KEY}):
            await storage.init_db(data_dir=str(custom_dir))

        assert storage.DB_PATH == custom_dir / "docsfy.db"
        assert storage.DATA_DIR == custom_dir
        assert storage.PROJECTS_DIR == custom_dir / "projects"
        assert storage.DB_PATH.exists()
    finally:
        # Restore original globals so other tests are not affected
        storage.DB_PATH = orig_db_path
        storage.DATA_DIR = orig_data_dir
        storage.PROJECTS_DIR = orig_projects_dir


async def test_get_known_branches(db_path: Path) -> None:
    from docsfy.storage import get_known_branches, save_project, update_project_status

    await save_project(
        name="repo1",
        repo_url="https://github.com/org/repo1.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="user",
        branch="main",
    )
    await update_project_status(
        "repo1", "claude", "opus", status="ready", owner="user", branch="main"
    )
    await save_project(
        name="repo1",
        repo_url="https://github.com/org/repo1.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="user",
        branch="v2.0",
    )
    await update_project_status(
        "repo1", "claude", "opus", status="ready", owner="user", branch="v2.0"
    )
    # This one is still generating, should not appear
    await save_project(
        name="repo1",
        repo_url="https://github.com/org/repo1.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="user",
        branch="dev",
    )

    branches = await get_known_branches()
    assert "repo1" in branches
    assert "main" in branches["repo1"]
    assert "v2.0" in branches["repo1"]
    assert "dev" not in branches["repo1"]


async def test_set_generation_cost(tmp_path: Path) -> None:
    """set_generation_cost sets total_cost_usd on a variant."""
    import docsfy.storage as storage

    orig_db = storage.DB_PATH
    orig_projects = storage.PROJECTS_DIR
    orig_data = storage.DATA_DIR
    try:
        storage.DB_PATH = tmp_path / "test.db"
        storage.PROJECTS_DIR = tmp_path / "projects"
        await storage.init_db(data_dir=str(tmp_path))

        await storage.save_project(
            name="cost-test",
            repo_url="https://github.com/test/repo",
            ai_provider="cursor",
            ai_model="gpt-5",
            owner="user1",
        )
        await storage.update_project_status(
            "cost-test",
            "cursor",
            "gpt-5",
            status="ready",
            owner="user1",
        )
        await storage.set_generation_cost(
            "cost-test",
            "cursor",
            "gpt-5",
            cost_usd=1.23,
            owner="user1",
        )

        project = await storage.get_project(
            "cost-test",
            ai_provider="cursor",
            ai_model="gpt-5",
            owner="user1",
        )
        assert project is not None
        assert project["total_cost_usd"] == 1.23
    finally:
        storage.DB_PATH = orig_db
        storage.PROJECTS_DIR = orig_projects
        storage.DATA_DIR = orig_data


async def test_get_total_cost(tmp_path: Path) -> None:
    """get_total_cost sums total_cost_usd across all variants."""
    import docsfy.storage as storage

    orig_db = storage.DB_PATH
    orig_projects = storage.PROJECTS_DIR
    orig_data = storage.DATA_DIR
    try:
        storage.DB_PATH = tmp_path / "test.db"
        storage.PROJECTS_DIR = tmp_path / "projects"
        await storage.init_db(data_dir=str(tmp_path))

        # Empty DB
        total = await storage.get_total_cost()
        assert total == 0.0

        # Add two variants with costs
        for i, cost in enumerate([0.50, 1.75]):
            await storage.save_project(
                name=f"proj-{i}",
                repo_url="https://github.com/test/repo",
                ai_provider="cursor",
                ai_model="gpt-5",
                owner="user1",
            )
            await storage.update_project_status(
                f"proj-{i}",
                "cursor",
                "gpt-5",
                status="ready",
                owner="user1",
            )
            await storage.set_generation_cost(
                f"proj-{i}",
                "cursor",
                "gpt-5",
                cost_usd=cost,
                owner="user1",
            )

        total = await storage.get_total_cost()
        assert total == pytest.approx(2.25)
    finally:
        storage.DB_PATH = orig_db
        storage.PROJECTS_DIR = orig_projects
        storage.DATA_DIR = orig_data


async def test_get_total_cost_owner_scoped(tmp_path: Path) -> None:
    """get_total_cost(owner=...) only sums that owner's costs."""
    import docsfy.storage as storage

    orig_db = storage.DB_PATH
    orig_data = storage.DATA_DIR
    orig_projects = storage.PROJECTS_DIR
    try:
        storage.DB_PATH = tmp_path / "test.db"
        storage.PROJECTS_DIR = tmp_path / "projects"
        await storage.init_db(data_dir=str(tmp_path))

        # Two owners with different costs
        for owner, cost in [("alice", 1.00), ("bob", 2.50)]:
            await storage.save_project(
                name=f"proj-{owner}",
                repo_url="https://github.com/test/repo",
                ai_provider="cursor",
                ai_model="gpt-5",
                owner=owner,
            )
            await storage.set_generation_cost(
                f"proj-{owner}",
                "cursor",
                "gpt-5",
                cost_usd=cost,
                owner=owner,
            )

        assert await storage.get_total_cost(owner="alice") == pytest.approx(1.00)
        assert await storage.get_total_cost(owner="bob") == pytest.approx(2.50)
        assert await storage.get_total_cost() == pytest.approx(3.50)
    finally:
        storage.DB_PATH = orig_db
        storage.DATA_DIR = orig_data
        storage.PROJECTS_DIR = orig_projects


async def test_save_project_resets_cost(tmp_path: Path) -> None:
    """save_project resets total_cost_usd to NULL for a new generation."""
    import docsfy.storage as storage

    orig_db = storage.DB_PATH
    orig_projects = storage.PROJECTS_DIR
    orig_data = storage.DATA_DIR
    try:
        storage.DB_PATH = tmp_path / "test.db"
        storage.PROJECTS_DIR = tmp_path / "projects"
        await storage.init_db(data_dir=str(tmp_path))

        await storage.save_project(
            name="reset-test",
            repo_url="https://github.com/test/repo",
            ai_provider="cursor",
            ai_model="gpt-5",
            owner="user1",
        )
        await storage.set_generation_cost(
            "reset-test",
            "cursor",
            "gpt-5",
            cost_usd=5.00,
            owner="user1",
        )
        # Re-save (new generation) should reset cost
        await storage.save_project(
            name="reset-test",
            repo_url="https://github.com/test/repo",
            ai_provider="cursor",
            ai_model="gpt-5",
            owner="user1",
        )
        project = await storage.get_project(
            "reset-test",
            ai_provider="cursor",
            ai_model="gpt-5",
            owner="user1",
        )
        assert project is not None
        assert project["total_cost_usd"] is None
    finally:
        storage.DB_PATH = orig_db
        storage.PROJECTS_DIR = orig_projects
        storage.DATA_DIR = orig_data
