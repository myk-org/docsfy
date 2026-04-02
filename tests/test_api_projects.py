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

    # Save originals
    orig_db = storage.DB_PATH
    orig_data = storage.DATA_DIR
    orig_projects = storage.PROJECTS_DIR

    storage.DB_PATH = tmp_path / "test.db"
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    _generating.clear()

    # Clear cached settings so ADMIN_KEY is picked up
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
        # Restore originals
        storage.DB_PATH = orig_db
        storage.DATA_DIR = orig_data
        storage.PROJECTS_DIR = orig_projects
        _generating.clear()
        get_settings.cache_clear()


async def test_list_projects_empty(client: AsyncClient) -> None:
    """GET /api/projects returns empty list with known_models and known_branches."""
    response = await client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["projects"] == []
    assert "known_models" in data
    assert "known_branches" in data


async def test_generate_invalid_url(client: AsyncClient) -> None:
    """POST /api/generate rejects invalid URLs (422)."""
    response = await client.post("/api/generate", json={"repo_url": "not-a-url"})
    assert response.status_code == 422


async def test_generate_starts(client: AsyncClient) -> None:
    """POST /api/generate starts generation (mock create_task), returns 202."""
    with patch("docsfy.api.projects.asyncio.create_task") as mock_task:
        mock_task.side_effect = lambda coro: coro.close()
        response = await client.post(
            "/api/generate",
            json={"repo_url": "https://github.com/org/repo.git"},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["project"] == "repo"
    assert body["status"] == "generating"


async def test_get_project_not_found(client: AsyncClient) -> None:
    """GET /api/projects/nonexistent returns 404."""
    response = await client.get("/api/projects/nonexistent")
    assert response.status_code == 404


async def test_get_models_returns_valid_structure(client: AsyncClient) -> None:
    """GET /api/models returns providers, defaults, and known_models."""
    response = await client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "default_provider" in data
    assert "default_model" in data
    assert "known_models" in data
    assert isinstance(data["providers"], list)
    assert isinstance(data["known_models"], dict)


async def test_get_models_includes_valid_providers(client: AsyncClient) -> None:
    """GET /api/models providers list matches VALID_PROVIDERS."""
    from docsfy.models import VALID_PROVIDERS

    response = await client.get("/api/models")
    data = response.json()
    assert data["providers"] == list(VALID_PROVIDERS)


async def test_get_models_no_auth_required() -> None:
    """GET /api/models works without authentication."""
    import docsfy.storage as storage
    from docsfy.config import get_settings

    # Use a temporary path to avoid interfering with other tests
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        orig_db = storage.DB_PATH
        orig_data = storage.DATA_DIR
        orig_projects = storage.PROJECTS_DIR

        storage.DB_PATH = tmp_path / "test.db"
        storage.DATA_DIR = tmp_path
        storage.PROJECTS_DIR = tmp_path / "projects"

        get_settings.cache_clear()

        from docsfy.main import app

        try:
            with patch.dict(os.environ, {"ADMIN_KEY": TEST_ADMIN_KEY}):
                get_settings.cache_clear()
                await storage.init_db()
                transport = ASGITransport(app=app)
                # No Authorization header -- unauthenticated request
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as ac:
                    response = await ac.get("/api/models")
                    assert response.status_code == 200
                    data = response.json()
                    assert "providers" in data
        finally:
            storage.DB_PATH = orig_db
            storage.DATA_DIR = orig_data
            storage.PROJECTS_DIR = orig_projects
            get_settings.cache_clear()
