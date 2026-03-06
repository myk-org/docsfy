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
    from docsfy.main import _generating, app

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
    from docsfy.main import _generating, app

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
# Test: unauthenticated redirect / 401
# ---------------------------------------------------------------------------


async def test_login_redirect_when_unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    """Browser requests to protected pages should redirect to /login."""
    response = await unauthed_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_api_returns_401_when_unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    """API requests without auth should return 401."""
    response = await unauthed_client.get("/api/status")
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


# ---------------------------------------------------------------------------
# Test: login with admin key
# ---------------------------------------------------------------------------


async def test_login_with_admin_key(unauthed_client: AsyncClient) -> None:
    """POST /login with the admin key should set a session cookie and redirect."""
    response = await unauthed_client.post(
        "/login",
        data={"username": "admin", "api_key": TEST_ADMIN_KEY},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert "docsfy_session" in response.cookies


# ---------------------------------------------------------------------------
# Test: login with user key
# ---------------------------------------------------------------------------


async def test_login_with_user_key(unauthed_client: AsyncClient) -> None:
    """POST /login with a valid user key should set a session cookie."""
    from docsfy.storage import create_user

    _username, raw_key = await create_user("alice")

    response = await unauthed_client.post(
        "/login",
        data={"username": "alice", "api_key": raw_key},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert "docsfy_session" in response.cookies


# ---------------------------------------------------------------------------
# Test: login with invalid key
# ---------------------------------------------------------------------------


async def test_login_with_invalid_key(unauthed_client: AsyncClient) -> None:
    """POST /login with a bad key should return 401 with an error message."""
    response = await unauthed_client.post(
        "/login",
        data={
            "username": "someone",
            "api_key": "totally-wrong",  # pragma: allowlist secret
        },
    )
    assert response.status_code == 401
    assert "Invalid username or API key" in response.text


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
    from docsfy.main import _generating, app
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
# Test: user sees only own docs, admin sees all
# ---------------------------------------------------------------------------


async def test_user_sees_only_own_docs(_init_db: None) -> None:
    """A non-admin user should only see projects they own."""
    from docsfy.main import _generating, app
    from docsfy.storage import create_user, save_project

    _generating.clear()

    _, alice_key = await create_user("alice-owner")
    _, bob_key = await create_user("bob-owner")

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
        response = await ac.get("/")
    assert response.status_code == 200
    assert "project-a" in response.text
    assert "project-b" not in response.text

    _generating.clear()


async def test_admin_sees_all_docs(admin_client: AsyncClient) -> None:
    """Admin should see all projects regardless of owner."""
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

    response = await admin_client.get("/")
    assert response.status_code == 200
    assert "project-x" in response.text
    assert "project-y" in response.text


# ---------------------------------------------------------------------------
# Test: logout
# ---------------------------------------------------------------------------


async def test_logout(unauthed_client: AsyncClient) -> None:
    """GET /logout should delete the session cookie and redirect to /login."""
    # First login
    response = await unauthed_client.post(
        "/login",
        data={"username": "admin", "api_key": TEST_ADMIN_KEY},
        follow_redirects=False,
    )
    assert "docsfy_session" in response.cookies

    # Now logout
    response = await unauthed_client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
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
# Test: login page is accessible without auth
# ---------------------------------------------------------------------------


async def test_login_page_accessible(unauthed_client: AsyncClient) -> None:
    """GET /login should return the login page without redirecting."""
    response = await unauthed_client.get("/login")
    assert response.status_code == 200
    assert "docsfy" in response.text
    assert "Username" in response.text
    assert "API Key" in response.text


# ---------------------------------------------------------------------------
# Test: viewer role can view but cannot generate
# ---------------------------------------------------------------------------


async def test_viewer_can_view_dashboard(_init_db: None) -> None:
    """A viewer should be able to access the dashboard (read-only)."""
    from docsfy.main import _generating, app
    from docsfy.storage import create_user

    _generating.clear()
    _, viewer_key = await create_user("viewer-user", role="viewer")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {viewer_key}"},
    ) as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    # Viewer should NOT see the generate form
    assert "Generate Documentation" not in response.text
    _generating.clear()


async def test_viewer_cannot_generate(_init_db: None) -> None:
    """A viewer should get 403 when trying to generate docs."""
    from docsfy.main import _generating, app
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
    assert "Viewers cannot perform this action" in response.json()["detail"]
    _generating.clear()


async def test_viewer_cannot_delete(_init_db: None) -> None:
    """A viewer should get 403 when trying to delete a project."""
    from docsfy.main import _generating, app
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
        response = await ac.delete("/api/projects/proj-del/claude/opus")
    assert response.status_code == 403
    _generating.clear()


# ---------------------------------------------------------------------------
# Test: admin user (not ADMIN_KEY) can see all docs
# ---------------------------------------------------------------------------


async def test_admin_user_sees_all_docs(_init_db: None) -> None:
    """A user with admin role should see all projects (like ADMIN_KEY)."""
    from docsfy.main import _generating, app
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
        response = await ac.get("/")
    assert response.status_code == 200
    assert "proj-alpha" in response.text
    assert "proj-beta" in response.text
    _generating.clear()
