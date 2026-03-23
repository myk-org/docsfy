from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

TEST_ADMIN_KEY = "test-admin-secret-key"


@pytest.fixture
async def _init_db(tmp_path: Path):
    """Initialize storage paths and database without creating a client."""
    import docsfy.storage as storage
    from docsfy.config import get_settings

    orig_db = storage.DB_PATH
    orig_data = storage.DATA_DIR
    orig_projects = storage.PROJECTS_DIR

    storage.DB_PATH = tmp_path / "test.db"
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"

    get_settings.cache_clear()

    try:
        with patch.dict(os.environ, {"ADMIN_KEY": TEST_ADMIN_KEY}):
            get_settings.cache_clear()
            await storage.init_db()
            yield
    finally:
        storage.DB_PATH = orig_db
        storage.DATA_DIR = orig_data
        storage.PROJECTS_DIR = orig_projects
        get_settings.cache_clear()


@pytest.fixture
async def unauthed_client(_init_db: None):
    """Client with NO auth credentials."""
    from docsfy.api.projects import _generating
    from docsfy.main import app

    _generating.clear()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        _generating.clear()


@pytest.fixture
async def admin_client(_init_db: None):
    """Client authenticated as admin via Bearer token."""
    from docsfy.api.projects import _generating
    from docsfy.main import app

    _generating.clear()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
        ) as ac:
            yield ac
    finally:
        _generating.clear()


# ---------------------------------------------------------------------------
# Test: unauthenticated API returns 401
# ---------------------------------------------------------------------------


async def test_api_returns_401_when_unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    """API requests without auth should return 401."""
    response = await unauthed_client.get("/api/status")
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


# ---------------------------------------------------------------------------
# Test: SPA routes pass through without auth (middleware lets them through)
# ---------------------------------------------------------------------------


async def test_spa_root_passes_through_without_auth(
    unauthed_client: AsyncClient,
) -> None:
    """Non-API, non-docs routes should pass through the middleware without auth check.

    The SPA catch-all serves index.html for all unmatched routes, so GET /
    returns 200 without requiring authentication.
    """
    response = await unauthed_client.get("/", follow_redirects=False)
    # SPA routes pass through middleware; catch-all serves index.html
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Test: login with admin key via JSON API
# ---------------------------------------------------------------------------


async def test_login_with_admin_key(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/login with the admin key should set a session cookie."""
    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["is_admin"] is True
    assert "docsfy_session" in response.cookies


# ---------------------------------------------------------------------------
# Test: login with user key via JSON API
# ---------------------------------------------------------------------------


async def test_login_with_user_key(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/login with a valid user key should set a session cookie."""
    from docsfy.storage import create_user

    _username, raw_key = await create_user("alice")

    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "alice", "api_key": raw_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "alice"
    assert "docsfy_session" in response.cookies


# ---------------------------------------------------------------------------
# Test: login with invalid key
# ---------------------------------------------------------------------------


async def test_login_with_invalid_key(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/login with a bad key should return 401."""
    response = await unauthed_client.post(
        "/api/auth/login",
        json={
            "username": "someone",
            "api_key": "totally-wrong",  # pragma: allowlist secret
        },
    )
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test: API Bearer auth
# ---------------------------------------------------------------------------


async def test_api_bearer_auth(admin_client: AsyncClient) -> None:
    """Requests with a valid Bearer token should succeed."""
    response = await admin_client.get("/api/status")
    assert response.status_code == 200
    assert "projects" in response.json()


async def test_api_bearer_auth_user_key(_init_db: None) -> None:
    """Requests with a valid user Bearer token should succeed."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _username, raw_key = await create_user("bob")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {raw_key}"},
    ) as ac:
        response = await ac.get("/api/status")
    assert response.status_code == 200
    _generating.clear()


# ---------------------------------------------------------------------------
# Test: user sees only own docs (via API)
# ---------------------------------------------------------------------------


async def test_user_sees_only_own_docs(_init_db: None) -> None:
    """A non-admin user should only see projects they own via /api/status."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user, save_project

    _generating.clear()

    _, alice_key = await create_user("alice-owner")
    await create_user("bob-owner")

    # Alice owns project-a
    await save_project(
        name="project-a",
        repo_url="https://github.com/org/a.git",
        ai_provider="claude",
        ai_model="opus",
        owner="alice-owner",
    )
    # Bob owns project-b
    await save_project(
        name="project-b",
        repo_url="https://github.com/org/b.git",
        ai_provider="claude",
        ai_model="opus",
        owner="bob-owner",
    )

    transport = ASGITransport(app=app)

    # Alice should see only project-a
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {alice_key}"},
    ) as ac:
        response = await ac.get("/api/status")
    assert response.status_code == 200
    projects = response.json()["projects"]
    project_names = [p["name"] for p in projects]
    assert "project-a" in project_names
    assert "project-b" not in project_names

    _generating.clear()


async def test_admin_sees_all_docs(admin_client: AsyncClient) -> None:
    """Admin should see all projects regardless of owner via /api/status."""
    from docsfy.storage import save_project

    await save_project(
        name="project-x",
        repo_url="https://github.com/org/x.git",
        ai_provider="claude",
        ai_model="opus",
        owner="someone",
    )
    await save_project(
        name="project-y",
        repo_url="https://github.com/org/y.git",
        ai_provider="claude",
        ai_model="opus",
        owner="other",
    )

    response = await admin_client.get("/api/status")
    assert response.status_code == 200
    projects = response.json()["projects"]
    project_names = [p["name"] for p in projects]
    assert "project-x" in project_names
    assert "project-y" in project_names


# ---------------------------------------------------------------------------
# Test: logout via JSON API
# ---------------------------------------------------------------------------


async def test_logout(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/logout should delete the session cookie and return {ok: true}."""
    # First login to get a session cookie
    login_response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    assert "docsfy_session" in login_response.cookies
    session_cookie = login_response.cookies["docsfy_session"]

    # Now logout with the session cookie
    unauthed_client.cookies.set("docsfy_session", session_cookie)
    response = await unauthed_client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    # Cookie should be deleted (set to empty / expired)
    set_cookie = response.headers.get("set-cookie", "")
    assert "docsfy_session" in set_cookie


# ---------------------------------------------------------------------------
# Test: health endpoint is public (no auth required)
# ---------------------------------------------------------------------------


async def test_health_is_public(unauthed_client: AsyncClient) -> None:
    """The /health endpoint should be accessible without authentication."""
    response = await unauthed_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Test: /login path is accessible without auth (public path)
# ---------------------------------------------------------------------------


async def test_login_path_is_public(unauthed_client: AsyncClient) -> None:
    """GET /login should pass through middleware without auth.

    The SPA catch-all serves index.html for /login so React can render
    the login form client-side.
    """
    response = await unauthed_client.get("/login", follow_redirects=False)
    # /login is in _PUBLIC_PATHS, so middleware passes through.
    # The SPA catch-all serves index.html.
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Test: viewer role can view but cannot generate
# ---------------------------------------------------------------------------


async def test_viewer_cannot_generate(_init_db: None) -> None:
    """A viewer should get 403 when trying to generate docs."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _, viewer_key = await create_user("viewer-gen", role="viewer")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {viewer_key}"},
    ) as ac:
        response = await ac.post(
            "/api/generate",
            json={
                "repo_url": "https://github.com/org/repo",
                "project_name": "test-proj",
            },
        )
    assert response.status_code == 403
    assert "Write access required" in response.json()["detail"]
    _generating.clear()


async def test_viewer_cannot_delete(_init_db: None) -> None:
    """A viewer should get 403 when trying to delete a project."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user, save_project

    _generating.clear()
    _, viewer_key = await create_user("viewer-del", role="viewer")

    await save_project(
        name="proj-del",
        repo_url="https://github.com/org/del.git",
        ai_provider="claude",
        ai_model="opus",
        owner="viewer-del",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {viewer_key}"},
    ) as ac:
        response = await ac.delete("/api/projects/proj-del/main/claude/opus")
    assert response.status_code == 403
    _generating.clear()


# ---------------------------------------------------------------------------
# Test: admin user (not ADMIN_KEY) can see all docs
# ---------------------------------------------------------------------------


async def test_admin_user_sees_all_docs(_init_db: None) -> None:
    """A user with admin role should see all projects (like ADMIN_KEY) via /api/status."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user, save_project

    _generating.clear()
    _, admin_key = await create_user("admin-user", role="admin")

    await save_project(
        name="proj-alpha",
        repo_url="https://github.com/org/alpha.git",
        ai_provider="claude",
        ai_model="opus",
        owner="someone-else",
    )
    await save_project(
        name="proj-beta",
        repo_url="https://github.com/org/beta.git",
        ai_provider="claude",
        ai_model="opus",
        owner="another-person",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {admin_key}"},
    ) as ac:
        response = await ac.get("/api/status")
    assert response.status_code == 200
    projects = response.json()["projects"]
    project_names = [p["name"] for p in projects]
    assert "proj-alpha" in project_names
    assert "proj-beta" in project_names
    _generating.clear()


# ---------------------------------------------------------------------------
# Test: session-based auth (cookie stores opaque token, not raw API key)
# ---------------------------------------------------------------------------


async def test_session_cookie_is_opaque_token(unauthed_client: AsyncClient) -> None:
    """The session cookie should NOT contain the raw API key."""
    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    assert "docsfy_session" in response.cookies
    cookie_value = response.cookies["docsfy_session"]
    # The cookie must NOT be the raw admin key
    assert cookie_value != TEST_ADMIN_KEY
    # It should be a URL-safe base64 token (from secrets.token_urlsafe)
    assert len(cookie_value) > 20


async def test_session_cookie_authenticates(unauthed_client: AsyncClient) -> None:
    """A valid session cookie should authenticate the user."""
    # Login to get session
    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    session_cookie = response.cookies["docsfy_session"]

    # Use session cookie to access protected page
    unauthed_client.cookies.set("docsfy_session", session_cookie)
    response = await unauthed_client.get("/api/status")
    assert response.status_code == 200


async def test_session_deleted_on_logout(unauthed_client: AsyncClient) -> None:
    """After logout, the session token should no longer authenticate."""
    from docsfy.storage import get_session

    # Login
    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    session_token = response.cookies["docsfy_session"]
    # Session should exist
    session = await get_session(session_token)
    assert session is not None

    # Logout
    unauthed_client.cookies.set("docsfy_session", session_token)
    await unauthed_client.post("/api/auth/logout")

    # Session should be deleted from DB
    session = await get_session(session_token)
    assert session is None


# ---------------------------------------------------------------------------
# Test: username "admin" is reserved (Fix 8)
# ---------------------------------------------------------------------------


async def test_create_user_admin_reserved(admin_client: AsyncClient) -> None:
    """Creating a user with username 'admin' should fail."""
    response = await admin_client.post(
        "/api/admin/users",
        json={"username": "admin", "role": "user"},
    )
    assert response.status_code == 400
    assert "reserved" in response.json()["detail"]


async def test_create_user_admin_case_insensitive(admin_client: AsyncClient) -> None:
    """Creating a user with username 'Admin' (any case) should fail."""
    response = await admin_client.post(
        "/api/admin/users",
        json={"username": "Admin", "role": "user"},
    )
    assert response.status_code == 400
    assert "reserved" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test: admin cannot self-delete (Fix 13)
# ---------------------------------------------------------------------------


async def test_admin_cannot_self_delete(admin_client: AsyncClient) -> None:
    """Admin should not be able to delete their own account."""
    response = await admin_client.delete("/api/admin/users/admin")
    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test: /api/status filters by owner (Fix 16)
# ---------------------------------------------------------------------------


async def test_api_status_filters_by_owner(_init_db: None) -> None:
    """Non-admin user should only see their own projects via /api/status."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user, save_project

    _generating.clear()
    _, alice_key = await create_user("alice-status")

    await save_project(
        name="alice-proj",
        repo_url="https://github.com/org/a.git",
        ai_provider="claude",
        ai_model="opus",
        owner="alice-status",
    )
    await save_project(
        name="other-proj",
        repo_url="https://github.com/org/b.git",
        ai_provider="claude",
        ai_model="opus",
        owner="someone-else",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {alice_key}"},
    ) as ac:
        response = await ac.get("/api/status")
    assert response.status_code == 200
    projects = response.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["name"] == "alice-proj"
    _generating.clear()


# ---------------------------------------------------------------------------
# Test: ownership check on project endpoints (Fix 17)
# ---------------------------------------------------------------------------


async def test_non_owner_cannot_access_project(_init_db: None) -> None:
    """Non-admin user should not see projects owned by others."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user, save_project

    _generating.clear()
    _, bob_key = await create_user("bob-noowner")

    await save_project(
        name="secret-proj",
        repo_url="https://github.com/org/secret.git",
        ai_provider="claude",
        ai_model="opus",
        owner="alice-owner2",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {bob_key}"},
    ) as ac:
        # GET /api/projects/{name} - returns 404 to avoid leaking existence
        response = await ac.get("/api/projects/secret-proj")
        assert response.status_code == 404

        # GET /api/projects/{name}/{branch}/{provider}/{model}
        response = await ac.get("/api/projects/secret-proj/main/claude/opus")
        assert response.status_code == 404

    _generating.clear()


# ---------------------------------------------------------------------------
# Test: repo_path requires admin (Fix 9)
# ---------------------------------------------------------------------------


async def test_non_admin_cannot_use_repo_path(_init_db: None, tmp_path: Path) -> None:
    """Non-admin users should get 403 when using repo_path."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _, user_key = await create_user("repo-path-user")

    # Create a fake git repo so Pydantic validation passes
    repo_dir = tmp_path / "fakerepo"
    (repo_dir / ".git").mkdir(parents=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {user_key}"},
    ) as ac:
        response = await ac.post(
            "/api/generate",
            json={"repo_path": str(repo_dir)},
        )
    assert response.status_code == 403
    assert "admin privileges" in response.json()["detail"]
    _generating.clear()


# ---------------------------------------------------------------------------
# Test: SameSite=strict and secure flags on cookie (Fix 4+5)
# ---------------------------------------------------------------------------


async def test_login_cookie_has_samesite_strict(
    unauthed_client: AsyncClient,
) -> None:
    """Login cookie should have SameSite=strict."""
    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    set_cookie = response.headers.get("set-cookie", "")
    assert "samesite=strict" in set_cookie.lower()


# ---------------------------------------------------------------------------
# Test: viewer sees assigned projects
# ---------------------------------------------------------------------------


async def test_viewer_sees_assigned_projects(_init_db: None) -> None:
    """A viewer with granted access should see assigned projects."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user, grant_project_access, save_project

    _generating.clear()
    _, viewer_key = await create_user("viewer-assigned", role="viewer")

    # Create a project owned by someone else
    await save_project(
        name="assigned-proj",
        repo_url="https://github.com/org/assigned.git",
        ai_provider="claude",
        ai_model="opus",
        owner="other-owner",
    )

    # Grant viewer access to the project (scoped by project owner)
    await grant_project_access(
        "assigned-proj", "viewer-assigned", project_owner="other-owner"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {viewer_key}"},
    ) as ac:
        response = await ac.get("/api/status")
    assert response.status_code == 200
    projects = response.json()["projects"]
    project_names = [p["name"] for p in projects]
    assert "assigned-proj" in project_names
    _generating.clear()


# ---------------------------------------------------------------------------
# Test: user rotates own key via /api/auth/rotate-key
# ---------------------------------------------------------------------------


async def test_user_rotates_own_key(_init_db: None) -> None:
    """A user can rotate their own API key, invalidating the old one."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    username, key = await create_user("rotatetest", role="user")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login via JSON API
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "rotatetest", "api_key": key},
        )
        cookie = resp.cookies.get("docsfy_session")

        # Rotate via new endpoint
        ac.cookies.set("docsfy_session", cookie)
        resp = await ac.post(
            "/api/auth/rotate-key",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "new_api_key" in data
        assert data["new_api_key"] != key

        # Old key should no longer work for login
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "rotatetest", "api_key": key},
        )
        assert resp.status_code == 401  # login should fail

    _generating.clear()


# ---------------------------------------------------------------------------
# Test: admin rotates user key
# ---------------------------------------------------------------------------


async def test_admin_rotates_user_key(admin_client: AsyncClient) -> None:
    """Admin can rotate another user's API key."""
    from docsfy.storage import create_user

    await create_user("target", role="user")

    resp = await admin_client.post("/api/admin/users/target/rotate-key", json={})
    assert resp.status_code == 200
    assert "new_api_key" in resp.json()


# ---------------------------------------------------------------------------
# Test: admin rotate key for non-existent user returns 404
# ---------------------------------------------------------------------------


async def test_admin_rotates_nonexistent_user_key(
    admin_client: AsyncClient,
) -> None:
    """Admin rotating key for a non-existent user should return 404."""
    resp = await admin_client.post("/api/admin/users/no-such-user/rotate-key", json={})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: viewer can rotate own key
# ---------------------------------------------------------------------------


async def test_viewer_can_rotate_key(_init_db: None) -> None:
    """A viewer should be able to rotate their own key (change password)."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _, viewer_key = await create_user("viewer-rotate", role="viewer")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login first
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "viewer-rotate", "api_key": viewer_key},
        )
        cookie = resp.cookies.get("docsfy_session")

        # Rotate should succeed
        ac.cookies.set("docsfy_session", cookie)
        resp = await ac.post(
            "/api/auth/rotate-key",
            json={},
        )
    assert resp.status_code == 200
    assert "new_api_key" in resp.json()
    _generating.clear()


# ---------------------------------------------------------------------------
# Test: ADMIN_KEY user cannot rotate key
# ---------------------------------------------------------------------------


async def test_admin_key_user_cannot_rotate_own_key(
    admin_client: AsyncClient,
) -> None:
    """ADMIN_KEY users should get 400 when trying to rotate their own key."""
    resp = await admin_client.post("/api/auth/rotate-key", json={})
    assert resp.status_code == 400
    assert "ADMIN_KEY" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test: user rotates with custom key
# ---------------------------------------------------------------------------


async def test_user_rotates_with_custom_key(_init_db: None) -> None:
    """A user can set a custom password when rotating their key."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _username, key = await create_user("customkey", role="user")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "customkey", "api_key": key},
        )
        cookie = resp.cookies.get("docsfy_session")

        custom = "my-very-secure-custom-password-123"
        ac.cookies.set("docsfy_session", cookie)
        resp = await ac.post(
            "/api/auth/rotate-key",
            json={"new_key": custom},
        )
        assert resp.status_code == 200
        assert resp.json()["new_api_key"] == custom

        # Can login with custom key
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "customkey", "api_key": custom},
        )
        assert resp.status_code == 200

    _generating.clear()


# ---------------------------------------------------------------------------
# Test: reject short custom key
# ---------------------------------------------------------------------------


async def test_reject_short_custom_key(_init_db: None) -> None:
    """A custom key shorter than 16 characters should be rejected."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _username, key = await create_user("shortkey", role="user")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "shortkey", "api_key": key},
        )
        cookie = resp.cookies.get("docsfy_session")

        ac.cookies.set("docsfy_session", cookie)
        resp = await ac.post(
            "/api/auth/rotate-key",
            json={"new_key": "short"},
        )
        assert resp.status_code == 400
        assert "16 characters" in resp.json()["detail"]

    _generating.clear()


# ---------------------------------------------------------------------------
# Test: admin sets custom key for user
# ---------------------------------------------------------------------------


async def test_admin_sets_custom_key_for_user(admin_client: AsyncClient) -> None:
    """Admin can set a custom password for a user."""
    from docsfy.storage import create_user, get_user_by_key

    await create_user("admin-custom-target", role="user")

    custom = "admin-chosen-password-long"
    resp = await admin_client.post(
        "/api/admin/users/admin-custom-target/rotate-key",
        json={"new_key": custom},
    )
    assert resp.status_code == 200
    assert resp.json()["new_api_key"] == custom

    # Verify the custom key works
    user = await get_user_by_key(custom)
    assert user is not None
    assert user["username"] == "admin-custom-target"


# ---------------------------------------------------------------------------
# Test: admin rejects short custom key for user
# ---------------------------------------------------------------------------


async def test_admin_rejects_short_custom_key(admin_client: AsyncClient) -> None:
    """Admin setting a short custom key should be rejected."""
    from docsfy.storage import create_user

    await create_user("admin-short-target", role="user")

    resp = await admin_client.post(
        "/api/admin/users/admin-short-target/rotate-key",
        json={"new_key": "tooshort"},
    )
    assert resp.status_code == 400
    assert "16 characters" in resp.json()["detail"]
