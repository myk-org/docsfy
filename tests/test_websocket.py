from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

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
def sync_client(_init_db: None):
    """Synchronous TestClient for WebSocket testing."""
    from docsfy.api.projects import _generating
    from docsfy.api.websocket import _connections
    from docsfy.main import app

    _generating.clear()
    _connections.clear()
    try:
        # Use raise_server_exceptions=False so we can inspect WS close codes
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        _generating.clear()
        _connections.clear()


def test_websocket_rejects_unauthenticated(sync_client: TestClient) -> None:
    """WS connect without auth should be closed with code 1008 (policy violation)."""
    with pytest.raises(Exception):
        # TestClient raises an exception when the server rejects the WebSocket
        with sync_client.websocket_connect("/api/ws"):
            pass


def test_websocket_accepts_bearer_token(sync_client: TestClient) -> None:
    """WS connect with ?token=ADMIN_KEY should receive a sync message."""
    with sync_client.websocket_connect(f"/api/ws?token={TEST_ADMIN_KEY}") as ws:
        data = ws.receive_json()
        assert data["type"] == "sync"
        assert "projects" in data
        assert "available_models" in data
        assert "total_cost_usd" in data
        assert isinstance(data["total_cost_usd"], (int, float))
        assert "known_branches" in data
        # projects should be a list (possibly empty)
        assert isinstance(data["projects"], list)


def test_websocket_accepts_session_cookie(sync_client: TestClient) -> None:
    """WS connect with a valid session cookie should receive a sync message."""
    # First, login to get a session cookie
    response = sync_client.post(
        "/api/auth/login",
        json={"username": "admin", "api_key": TEST_ADMIN_KEY},
    )
    assert response.status_code == 200
    session_cookie = response.cookies.get("docsfy_session")
    assert session_cookie is not None

    # Connect to WebSocket with the session cookie
    sync_client.cookies.set("docsfy_session", session_cookie)
    with sync_client.websocket_connect("/api/ws") as ws:
        data = ws.receive_json()
        assert data["type"] == "sync"
        assert "projects" in data


def test_websocket_receives_ping(sync_client: TestClient) -> None:
    """WS connect should eventually receive a ping (heartbeat)."""
    # Patch the heartbeat interval to make the test fast
    from docsfy.api import websocket as ws_module

    original_interval = ws_module._WS_HEARTBEAT_INTERVAL
    ws_module._WS_HEARTBEAT_INTERVAL = 0.1  # 100ms for test speed
    try:
        with sync_client.websocket_connect(f"/api/ws?token={TEST_ADMIN_KEY}") as ws:
            # First message is sync
            sync_msg = ws.receive_json()
            assert sync_msg["type"] == "sync"

            # Second message should be a ping
            ping_msg = ws.receive_json()
            assert ping_msg["type"] == "ping"

            # Send pong back
            ws.send_json({"type": "pong"})
    finally:
        ws_module._WS_HEARTBEAT_INTERVAL = original_interval
