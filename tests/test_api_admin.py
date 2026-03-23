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
# Test: GET /api/admin/users returns empty list initially
# ---------------------------------------------------------------------------


async def test_list_users_empty(admin_client: AsyncClient) -> None:
    """GET /api/admin/users returns an empty list when no users have been created."""
    response = await admin_client.get("/api/admin/users")
    assert response.status_code == 200
    data = response.json()
    assert data == {"users": []}


# ---------------------------------------------------------------------------
# Test: POST /api/admin/users creates a user and returns api_key
# ---------------------------------------------------------------------------


async def test_create_user(admin_client: AsyncClient) -> None:
    """POST /api/admin/users creates a user and returns an api_key starting with 'docsfy_'."""
    response = await admin_client.post(
        "/api/admin/users",
        json={"username": "testuser", "role": "user"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "user"
    assert data["api_key"].startswith("docsfy_")
    assert response.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# Test: POST /api/admin/users rejects empty username
# ---------------------------------------------------------------------------


async def test_create_user_empty_username(admin_client: AsyncClient) -> None:
    """POST /api/admin/users with empty username returns 400."""
    response = await admin_client.post(
        "/api/admin/users",
        json={"username": "", "role": "user"},
    )
    assert response.status_code == 400
    assert "Username is required" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test: DELETE /api/admin/users/{username} deletes a user
# ---------------------------------------------------------------------------


async def test_delete_user(admin_client: AsyncClient) -> None:
    """Create a user then delete it; DELETE returns 200 with {deleted: username}."""
    # Create user first
    create_resp = await admin_client.post(
        "/api/admin/users",
        json={"username": "todelete"},
    )
    assert create_resp.status_code == 200

    # Delete the user
    delete_resp = await admin_client.delete("/api/admin/users/todelete")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"deleted": "todelete"}

    # Verify user is gone
    list_resp = await admin_client.get("/api/admin/users")
    usernames = [u["username"] for u in list_resp.json()["users"]]
    assert "todelete" not in usernames


# ---------------------------------------------------------------------------
# Test: DELETE /api/admin/users/{username} rejects self-delete
# ---------------------------------------------------------------------------


async def test_delete_self_rejected(admin_client: AsyncClient) -> None:
    """DELETE own admin account returns 400."""
    response = await admin_client.delete("/api/admin/users/admin")
    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]
