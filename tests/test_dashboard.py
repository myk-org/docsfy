from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

TEST_ADMIN_KEY = "test-admin-secret-key"


@pytest.fixture
async def client(tmp_path: Path):
    import docsfy.storage as storage
    from docsfy.api.projects import _generating
    from docsfy.config import get_settings

    orig_db = storage.DB_PATH
    orig_data = storage.DATA_DIR
    orig_projects = storage.PROJECTS_DIR

    storage.DB_PATH = tmp_path / "test.db"
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    _generating.clear()

    get_settings.cache_clear()

    from docsfy.main import app

    try:
        with patch.dict(os.environ, {"ADMIN_KEY": TEST_ADMIN_KEY}):
            get_settings.cache_clear()
            await storage.init_db()
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
                headers={"Authorization": f"Bearer {TEST_ADMIN_KEY}"},
            ) as ac:
                yield ac
    finally:
        storage.DB_PATH = orig_db
        storage.DATA_DIR = orig_data
        storage.PROJECTS_DIR = orig_projects
        _generating.clear()
        get_settings.cache_clear()


async def test_root_serves_spa_index(client: AsyncClient) -> None:
    """GET / should serve the SPA index.html via the catch-all handler.

    The middleware passes SPA routes through without auth check, and the
    catch-all handler serves frontend/dist/index.html.
    """
    response = await client.get("/")
    assert response.status_code == 200


async def test_api_status_returns_projects(client: AsyncClient) -> None:
    """GET /api/status should list projects as JSON."""
    from docsfy.storage import save_project, update_project_status

    await save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )
    await update_project_status(
        "test-repo",
        "claude",
        "opus",
        status="ready",
        owner="admin",
        page_count=10,
    )

    response = await client.get("/api/status")
    assert response.status_code == 200
    projects = response.json()["projects"]
    project_names = [p["name"] for p in projects]
    assert "test-repo" in project_names


async def test_api_status_empty_state(client: AsyncClient) -> None:
    """GET /api/status with no projects should return an empty list."""
    response = await client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["projects"] == []
