from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(tmp_path: Path):
    import docsfy.storage as storage
    from docsfy.main import _generating

    # Save originals
    orig_db = storage.DB_PATH
    orig_data = storage.DATA_DIR
    orig_projects = storage.PROJECTS_DIR

    storage.DB_PATH = tmp_path / "test.db"
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    _generating.clear()

    from docsfy.main import app

    try:
        await storage.init_db()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        # Restore originals
        storage.DB_PATH = orig_db
        storage.DATA_DIR = orig_data
        storage.PROJECTS_DIR = orig_projects
        _generating.clear()


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
    with patch("docsfy.main.asyncio.create_task") as mock_task:
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
    response = await client.get("/api/projects/nonexistent")
    assert response.status_code == 404


async def test_generate_endpoint_with_force(client: AsyncClient) -> None:
    with patch("docsfy.main.asyncio.create_task") as mock_task:
        mock_task.side_effect = lambda coro: coro.close()
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
    with patch("docsfy.main.asyncio.create_task") as mock_task:
        mock_task.side_effect = lambda coro: coro.close()
        response = await client.post(
            "/api/generate",
            json={"repo_path": str(tmp_path / "myrepo")},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["project"] == "myrepo"


async def test_abort_no_active_generation(client: AsyncClient) -> None:
    response = await client.post("/api/projects/nonexistent/abort")
    assert response.status_code == 404


async def test_delete_project_not_found(client: AsyncClient) -> None:
    response = await client.delete("/api/projects/nonexistent")
    assert response.status_code == 404


async def test_generate_duplicate_variant(client: AsyncClient) -> None:
    """Test that generating the same variant twice returns 409."""
    from docsfy.main import _generating

    _generating["repo/claude/opus"] = asyncio.create_task(asyncio.sleep(100))
    try:
        response = await client.post(
            "/api/generate",
            json={
                "repo_url": "https://github.com/org/repo.git",
                "ai_provider": "claude",
                "ai_model": "opus",
            },
        )
        assert response.status_code == 409
    finally:
        task = _generating.pop("repo/claude/opus", None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def test_variant_specific_endpoints(client: AsyncClient) -> None:
    """Test variant-specific get, delete, and download endpoints."""
    from docsfy.storage import save_project, update_project_status

    await save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
    )
    await update_project_status(
        "test-repo",
        "claude",
        "opus",
        status="ready",
        page_count=5,
    )

    # Get variant details
    response = await client.get("/api/projects/test-repo/claude/opus")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-repo"
    assert data["ai_provider"] == "claude"
    assert data["ai_model"] == "opus"

    # Get nonexistent variant
    response = await client.get("/api/projects/test-repo/gemini/flash")
    assert response.status_code == 404

    # Delete nonexistent variant
    response = await client.delete("/api/projects/test-repo/gemini/flash")
    assert response.status_code == 404

    # Delete existing variant
    response = await client.delete("/api/projects/test-repo/claude/opus")
    assert response.status_code == 200
    assert response.json()["deleted"] == "test-repo/claude/opus"


async def test_get_project_returns_variants(client: AsyncClient) -> None:
    """Test that GET /api/projects/{name} returns all variants."""
    from docsfy.storage import save_project, update_project_status

    await save_project(
        name="multi-repo",
        repo_url="https://github.com/org/multi-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
    )
    await update_project_status(
        "multi-repo",
        "claude",
        "opus",
        status="ready",
        page_count=5,
    )
    await save_project(
        name="multi-repo",
        repo_url="https://github.com/org/multi-repo.git",
        status="generating",
        ai_provider="gemini",
        ai_model="pro",
    )
    await update_project_status(
        "multi-repo",
        "gemini",
        "pro",
        status="ready",
        page_count=3,
    )

    response = await client.get("/api/projects/multi-repo")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "multi-repo"
    assert len(data["variants"]) == 2


async def test_abort_variant_endpoint(client: AsyncClient) -> None:
    """Test variant-specific abort endpoint returns 404 when no active gen."""
    response = await client.post("/api/projects/repo/claude/opus/abort")
    assert response.status_code == 404
