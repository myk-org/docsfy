from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
async def db_path(tmp_path: Path) -> Path:
    import docsfy.storage as storage

    db = tmp_path / "test.db"
    storage.DB_PATH = db
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    await storage.init_db()
    return db


async def test_init_db_creates_table(db_path: Path) -> None:
    assert db_path.exists()


async def test_save_and_get_project(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
    )
    project = await get_project("my-repo")
    assert project is not None
    assert project["name"] == "my-repo"
    assert project["repo_url"] == "https://github.com/org/my-repo.git"
    assert project["status"] == "generating"


async def test_update_project_status(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project, update_project_status

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
    )
    await update_project_status(
        "my-repo", status="ready", last_commit_sha="abc123", page_count=5
    )
    project = await get_project("my-repo")
    assert project is not None
    assert project["status"] == "ready"
    assert project["last_commit_sha"] == "abc123"
    assert project["page_count"] == 5


async def test_list_projects(db_path: Path) -> None:
    from docsfy.storage import list_projects, save_project

    await save_project(
        name="repo-a", repo_url="https://github.com/org/repo-a.git", status="ready"
    )
    await save_project(
        name="repo-b", repo_url="https://github.com/org/repo-b.git", status="generating"
    )
    projects = await list_projects()
    assert len(projects) == 2


async def test_delete_project(db_path: Path) -> None:
    from docsfy.storage import delete_project, get_project, save_project

    await save_project(
        name="my-repo", repo_url="https://github.com/org/my-repo.git", status="ready"
    )
    deleted = await delete_project("my-repo")
    assert deleted is True
    project = await get_project("my-repo")
    assert project is None


async def test_delete_nonexistent_project(db_path: Path) -> None:
    from docsfy.storage import delete_project

    deleted = await delete_project("no-such-repo")
    assert deleted is False


async def test_get_nonexistent_project(db_path: Path) -> None:
    from docsfy.storage import get_project

    project = await get_project("no-such-repo")
    assert project is None


async def test_get_known_models(db_path: Path) -> None:
    from docsfy.storage import get_known_models, save_project, update_project_status

    await save_project(
        name="repo-a", repo_url="https://github.com/org/a.git", status="generating"
    )
    await update_project_status(
        "repo-a", status="ready", ai_provider="claude", ai_model="opus-4-6"
    )
    await save_project(
        name="repo-b", repo_url="https://github.com/org/b.git", status="generating"
    )
    await update_project_status(
        "repo-b", status="ready", ai_provider="claude", ai_model="sonnet-4-6"
    )
    await save_project(
        name="repo-c", repo_url="https://github.com/org/c.git", status="generating"
    )
    await update_project_status(
        "repo-c", status="ready", ai_provider="gemini", ai_model="gemini-2.5-pro"
    )

    models = await get_known_models()
    assert "claude" in models
    assert "opus-4-6" in models["claude"]
    assert "sonnet-4-6" in models["claude"]
    assert "gemini" in models
    assert "gemini-2.5-pro" in models["gemini"]


async def test_update_project_with_ai_info(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project, update_project_status

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
    )
    await update_project_status(
        "my-repo",
        status="ready",
        last_commit_sha="abc123",
        page_count=5,
        ai_provider="claude",
        ai_model="opus-4-6",
    )
    project = await get_project("my-repo")
    assert project is not None
    assert project["ai_provider"] == "claude"
    assert project["ai_model"] == "opus-4-6"
