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
# Test: POST /api/auth/login with admin creds returns JSON + session cookie
# ---------------------------------------------------------------------------


async def test_login_admin_json(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/login with admin creds returns JSON {username, role, is_admin} + session cookie."""
    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert data["is_admin"] is True
    assert "docsfy_session" in response.cookies


# ---------------------------------------------------------------------------
# Test: POST /api/auth/login with user creds returns JSON + session cookie
# ---------------------------------------------------------------------------


async def test_login_user_json(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/login with valid user key returns JSON user info."""
    from docsfy.storage import create_user

    _username, raw_key = await create_user("alice")

    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "alice", "api_key": raw_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "alice"
    assert data["role"] == "user"
    assert data["is_admin"] is False
    assert "docsfy_session" in response.cookies


# ---------------------------------------------------------------------------
# Test: POST /api/auth/login with invalid creds returns 401
# ---------------------------------------------------------------------------


async def test_login_invalid_creds(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/login with wrong creds returns 401."""
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
# Test: POST /api/auth/logout clears session, returns {ok: true}
# ---------------------------------------------------------------------------


async def test_logout(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/logout clears session and returns {ok: true}."""
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
# Test: GET /api/auth/me returns current user info for admin Bearer token
# ---------------------------------------------------------------------------


async def test_me_endpoint(admin_client: AsyncClient) -> None:
    """GET /api/auth/me returns {username, role, is_admin} for admin Bearer token."""
    response = await admin_client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert data["is_admin"] is True


# ---------------------------------------------------------------------------
# Test: GET /api/auth/me returns 401 when unauthenticated
# ---------------------------------------------------------------------------


async def test_me_unauthenticated(unauthed_client: AsyncClient) -> None:
    """GET /api/auth/me returns 401 when not authenticated."""
    response = await unauthed_client.get("/api/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test: POST /api/auth/rotate-key rejects ADMIN_KEY users with 400
# ---------------------------------------------------------------------------


async def test_rotate_key_admin_key_user_rejected(
    admin_client: AsyncClient,
) -> None:
    """ADMIN_KEY users should get 400 when trying to rotate their own key."""
    response = await admin_client.post("/api/auth/rotate-key", json={})
    assert response.status_code == 400
    assert "ADMIN_KEY" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test: POST /api/auth/rotate-key works for DB users
# ---------------------------------------------------------------------------


async def test_rotate_key_db_user(_init_db: None) -> None:
    """A DB user can rotate their own API key via the new auth router endpoint."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _username, key = await create_user("rotateuser", role="user")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login via new API endpoint
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "rotateuser", "api_key": key},
        )
        cookie = resp.cookies.get("docsfy_session")

        # Rotate
        ac.cookies.set("docsfy_session", cookie)
        resp = await ac.post(
            "/api/auth/rotate-key",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "new_api_key" in data
        assert data["username"] == "rotateuser"
        assert data["new_api_key"] != key
        # Cache-Control header should be set
        assert resp.headers.get("cache-control") == "no-store"

    _generating.clear()


# ---------------------------------------------------------------------------
# Test: POST /api/auth/login is accessible without auth (public path)
# ---------------------------------------------------------------------------


async def test_login_is_public_path(unauthed_client: AsyncClient) -> None:
    """POST /api/auth/login should be accessible without authentication."""
    # Sending invalid creds should return 401, not redirect to /login
    response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "nobody", "api_key": "bad"},  # pragma: allowlist secret
    )
    assert response.status_code == 401
    # It should be a JSON response, not a redirect
    assert response.json()["detail"] == "Invalid username or password"


# ---------------------------------------------------------------------------
# Test: POST /api/auth/login with DB admin user returns is_admin=True
# ---------------------------------------------------------------------------


async def test_login_db_admin_user(_init_db: None) -> None:
    """A DB user created with role='admin' should get is_admin=True on login."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _username, key = await create_user("dbadmin", role="admin")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "dbadmin", "api_key": key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_admin"] is True
        assert data["role"] == "admin"

    _generating.clear()


# ---------------------------------------------------------------------------
# Test: POST /api/auth/rotate-key rejects a short custom key with 400
# ---------------------------------------------------------------------------


async def test_me_via_session_cookie(unauthed_client: AsyncClient) -> None:
    """GET /api/auth/me returns user info when authenticated via session cookie."""
    # Login to obtain a session cookie
    login_response = await unauthed_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    assert login_response.status_code == 200
    session_cookie = login_response.cookies["docsfy_session"]

    # Use the session cookie (no Bearer token) to call /api/auth/me
    unauthed_client.cookies.set("docsfy_session", session_cookie)
    response = await unauthed_client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
    assert data["is_admin"] is True


# ---------------------------------------------------------------------------
# Test: POST /api/auth/rotate-key rejects a short custom key with 400
# ---------------------------------------------------------------------------


async def test_rotate_key_short_custom_key(_init_db: None) -> None:
    """Rotating to a custom key that is too short should return 400."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _username, key = await create_user("shortkeyuser")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "shortkeyuser", "api_key": key},
        )
        cookie = resp.cookies.get("docsfy_session")

        ac.cookies.set("docsfy_session", cookie)
        resp = await ac.post(
            "/api/auth/rotate-key",
            json={"new_key": "short"},
        )
        assert resp.status_code == 400

    _generating.clear()


# ---------------------------------------------------------------------------
# Test: POST /api/auth/rotate-key accepts a valid custom key
# ---------------------------------------------------------------------------


async def test_rotate_key_valid_custom_key(_init_db: None) -> None:
    """Rotating to a valid custom key (16+ chars) should succeed."""
    from docsfy.api.projects import _generating
    from docsfy.main import app
    from docsfy.storage import create_user

    _generating.clear()
    _username, key = await create_user("validkeyuser")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "validkeyuser", "api_key": key},
        )
        cookie = resp.cookies.get("docsfy_session")

        ac.cookies.set("docsfy_session", cookie)
        resp = await ac.post(
            "/api/auth/rotate-key",
            json={"new_key": "a-valid-key-that-is-long-enough"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "new_api_key" in data

    _generating.clear()
