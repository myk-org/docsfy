from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(tmp_path: Path):
    import docsfy.storage as storage

    storage.DB_PATH = tmp_path / "test.db"
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"

    from docsfy.main import app

    await storage.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_status_endpoint_empty(client: AsyncClient) -> None:
    response = await client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["projects"] == []


async def test_generate_endpoint_invalid_url(client: AsyncClient) -> None:
    response = await client.post("/api/generate", json={"repo_url": "not-a-url"})
    assert response.status_code == 422


async def test_generate_endpoint_starts_generation(client: AsyncClient) -> None:
    with patch("docsfy.main.asyncio.create_task"):
        response = await client.post(
            "/api/generate",
            json={"repo_url": "https://github.com/org/repo.git"},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["project"] == "repo"
    assert body["status"] == "generating"


async def test_get_project_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/projects/nonexistent")
    assert response.status_code == 404


async def test_generate_endpoint_with_force(client: AsyncClient) -> None:
    with patch("docsfy.main.asyncio.create_task"):
        response = await client.post(
            "/api/generate",
            json={"repo_url": "https://github.com/org/repo.git", "force": True},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["project"] == "repo"


async def test_generate_endpoint_local_path(
    client: AsyncClient, tmp_path: Path
) -> None:
    # Create a fake git repo
    (tmp_path / "myrepo" / ".git").mkdir(parents=True)
    with patch("docsfy.main.asyncio.create_task"):
        response = await client.post(
            "/api/generate",
            json={"repo_path": str(tmp_path / "myrepo")},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["project"] == "myrepo"


async def test_delete_project_not_found(client: AsyncClient) -> None:
    response = await client.delete("/api/projects/nonexistent")
    assert response.status_code == 404
