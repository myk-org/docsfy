from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(tmp_path: Path):
    import docsfy.storage as storage
    from docsfy.main import _generating

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
        storage.DB_PATH = orig_db
        storage.DATA_DIR = orig_data
        storage.PROJECTS_DIR = orig_projects
        _generating.clear()


async def test_dashboard_returns_html(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "docsfy" in response.text


async def test_dashboard_shows_projects(client: AsyncClient) -> None:
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
        page_count=10,
    )

    response = await client.get("/")
    assert response.status_code == 200
    assert "test-repo" in response.text


async def test_dashboard_shows_generate_form(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "Generate" in response.text


async def test_dashboard_empty_state(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "docsfy" in response.text
    # No project cards should be present
    assert "project-card" not in response.text or "No projects" in response.text
