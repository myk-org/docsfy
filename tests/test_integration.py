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


async def test_full_flow_mock(client: AsyncClient, tmp_path: Path) -> None:
    """Test the full generate -> status -> download flow with mocked AI."""
    import docsfy.storage as storage

    sample_plan = {
        "project_name": "test-repo",
        "tagline": "A test project",
        "navigation": [
            {
                "group": "Getting Started",
                "pages": [
                    {
                        "slug": "introduction",
                        "title": "Introduction",
                        "description": "Overview",
                    },
                ],
            }
        ],
    }

    with (
        patch("docsfy.main.check_ai_cli_available", return_value=(True, "")),
        patch("docsfy.main.clone_repo", return_value=(tmp_path / "repo", "abc123")),
        patch("docsfy.main.run_planner", return_value=sample_plan),
        patch(
            "docsfy.main.generate_all_pages",
            return_value={"introduction": "# Intro\n\nWelcome!"},
        ),
    ):
        from docsfy.main import _run_generation

        await storage.save_project(
            name="test-repo",
            repo_url="https://github.com/org/test-repo.git",
            status="generating",
        )

        await _run_generation(
            repo_url="https://github.com/org/test-repo.git",
            repo_path=None,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            ai_cli_timeout=60,
        )

    # Check status
    response = await client.get("/api/status")
    assert response.status_code == 200
    projects = response.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["name"] == "test-repo"
    assert projects[0]["status"] == "ready"

    # Check project details
    response = await client.get("/api/projects/test-repo")
    assert response.status_code == 200
    assert response.json()["last_commit_sha"] == "abc123"

    # Check docs are served
    response = await client.get("/docs/test-repo/index.html")
    assert response.status_code == 200
    assert "test-repo" in response.text

    response = await client.get("/docs/test-repo/introduction.html")
    assert response.status_code == 200
    assert "Welcome!" in response.text

    # Download
    response = await client.get("/api/projects/test-repo/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/gzip"

    # Delete
    response = await client.delete("/api/projects/test-repo")
    assert response.status_code == 200

    response = await client.get("/api/projects/test-repo")
    assert response.status_code == 404
