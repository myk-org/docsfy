from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

TEST_ADMIN_KEY = "test-admin-secret-key"


@pytest.fixture
async def client(tmp_path: Path):
    import docsfy.storage as storage
    from docsfy.config import get_settings
    from docsfy.main import _generating

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
    response = await client.delete("/api/projects/nonexistent?owner=someuser")
    assert response.status_code == 404


async def test_delete_project_admin_requires_owner(client: AsyncClient) -> None:
    """Admin must provide ?owner= when deleting a project."""
    response = await client.delete("/api/projects/anyproject")
    assert response.status_code == 400
    assert "owner" in response.json()["detail"].lower()


async def test_generate_duplicate_variant(client: AsyncClient) -> None:
    """Test that generating the same variant twice returns 409."""
    from docsfy.main import _generating

    # gen_key format: "owner/name/branch/provider/model"
    _generating["admin/repo/main/claude/opus"] = asyncio.create_task(asyncio.sleep(100))
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
        task = _generating.pop("admin/repo/main/claude/opus", None)
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
        owner="admin",
    )
    await update_project_status(
        "test-repo",
        "claude",
        "opus",
        status="ready",
        owner="admin",
        page_count=5,
    )

    # Get variant details
    response = await client.get("/api/projects/test-repo/main/claude/opus")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-repo"
    assert data["ai_provider"] == "claude"
    assert data["ai_model"] == "opus"

    # Get nonexistent variant
    response = await client.get("/api/projects/test-repo/main/gemini/flash")
    assert response.status_code == 404

    # Delete nonexistent variant
    response = await client.delete(
        "/api/projects/test-repo/main/gemini/flash?owner=admin"
    )
    assert response.status_code == 404

    # Delete existing variant
    response = await client.delete(
        "/api/projects/test-repo/main/claude/opus?owner=admin"
    )
    assert response.status_code == 200
    assert response.json()["deleted"] == "test-repo/main/claude/opus"


async def test_get_project_returns_variants(client: AsyncClient) -> None:
    """Test that GET /api/projects/{name} returns all variants."""
    from docsfy.storage import save_project, update_project_status

    await save_project(
        name="multi-repo",
        repo_url="https://github.com/org/multi-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )
    await update_project_status(
        "multi-repo",
        "claude",
        "opus",
        status="ready",
        owner="admin",
        page_count=5,
    )
    await save_project(
        name="multi-repo",
        repo_url="https://github.com/org/multi-repo.git",
        status="generating",
        ai_provider="gemini",
        ai_model="pro",
        owner="admin",
    )
    await update_project_status(
        "multi-repo",
        "gemini",
        "pro",
        status="ready",
        owner="admin",
        page_count=3,
    )

    response = await client.get("/api/projects/multi-repo")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "multi-repo"
    assert len(data["variants"]) == 2


async def test_abort_variant_endpoint(client: AsyncClient) -> None:
    """Test variant-specific abort endpoint returns 404 when no active gen."""
    response = await client.post("/api/projects/repo/main/claude/opus/abort")
    assert response.status_code == 404


async def test_reject_private_url_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that SSRF protection rejects DNS names resolving to private IPs."""
    import socket

    from docsfy.main import _reject_private_url

    def mock_getaddrinfo(
        host: str, port: object, *args: object, **kwargs: object
    ) -> list[
        tuple[socket.AddressFamily, socket.SocketKind, int, str, tuple[str, int]]
    ]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("192.168.1.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    with pytest.raises(HTTPException) as exc_info:
        await _reject_private_url("https://evil.com/org/repo")
    assert exc_info.value.status_code == 400


async def test_generate_rejects_private_url(client: AsyncClient) -> None:
    """Test that SSRF protection rejects private/localhost URLs."""
    response = await client.post(
        "/api/generate",
        json={"repo_url": "https://localhost/org/repo.git"},
    )
    # Should be rejected by URL validation (either Pydantic or SSRF check)
    assert response.status_code in (400, 422)


async def test_generate_from_path_falls_back_to_full_regeneration_when_diff_fails(
    client: AsyncClient, tmp_path: Path
) -> None:
    import docsfy.storage as storage
    from docsfy.main import _generate_from_path
    from docsfy.storage import get_project_dir

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
                    }
                ],
            }
        ],
    }

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    get_project_dir("test-repo", "claude", "opus", "admin").mkdir(
        parents=True, exist_ok=True
    )

    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )
    await storage.update_project_status(
        "test-repo",
        "claude",
        "opus",
        status="ready",
        owner="admin",
        last_commit_sha="abc123",
        plan_json=json.dumps(sample_plan),
    )

    with (
        patch("docsfy.main.deepen_clone_for_diff", return_value=True),
        patch("docsfy.main.get_diff", return_value=None),
        patch("docsfy.main.run_planner", return_value=sample_plan) as mock_run_planner,
        patch(
            "docsfy.main.generate_all_pages",
            return_value={"introduction": "# Intro\n\nWelcome!"},
        ) as mock_generate_all_pages,
        patch("docsfy.main.render_site") as mock_render_site,
    ):
        await _generate_from_path(
            repo_dir=repo_dir,
            commit_sha="def456",
            source_url="https://github.com/org/test-repo.git",
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            ai_cli_timeout=60,
            force=False,
            owner="admin",
        )

    project = await storage.get_project(
        "test-repo", ai_provider="claude", ai_model="opus", owner="admin"
    )
    assert project is not None
    assert mock_run_planner.called
    assert mock_generate_all_pages.called
    assert mock_render_site.called
    assert project["status"] == "ready"
    assert project["last_commit_sha"] == "def456"


async def test_generate_from_path_reuses_existing_plan_for_incremental_updates(
    client: AsyncClient, tmp_path: Path
) -> None:
    import docsfy.storage as storage
    from docsfy.main import _generate_from_path
    from docsfy.storage import get_project_cache_dir, get_project_dir

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
                    {
                        "slug": "quickstart",
                        "title": "Quick Start",
                        "description": "Fast start",
                    },
                ],
            }
        ],
    }

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    get_project_dir("test-repo", "claude", "opus", "admin").mkdir(
        parents=True, exist_ok=True
    )
    cache_dir = get_project_cache_dir("test-repo", "claude", "opus", "admin")
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "introduction.md").write_text("# Introduction\n\nOld intro\n")
    (cache_dir / "quickstart.md").write_text("# Quick Start\n\nCached quickstart\n")

    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )
    await storage.update_project_status(
        "test-repo",
        "claude",
        "opus",
        status="ready",
        owner="admin",
        last_commit_sha="abc123",
        plan_json=json.dumps(sample_plan),
    )

    with (
        patch("docsfy.main.deepen_clone_for_diff", return_value=True),
        patch(
            "docsfy.main.get_diff",
            return_value=(["src/intro.py"], "diff --git a/src/intro.py\n+new intro"),
        ),
        patch(
            "docsfy.main.run_incremental_planner",
            return_value=["introduction"],
        ) as mock_incremental_planner,
        patch(
            "docsfy.main.run_planner",
            side_effect=AssertionError("full planner should not run"),
        ) as mock_run_planner,
        patch(
            "docsfy.main.generate_all_pages",
            return_value={
                "introduction": "# Introduction\n\nNew intro\n",
                "quickstart": "# Quick Start\n\nCached quickstart\n",
            },
        ) as mock_generate_all_pages,
        patch("docsfy.main.render_site"),
    ):
        await _generate_from_path(
            repo_dir=repo_dir,
            commit_sha="def456",
            source_url="https://github.com/org/test-repo.git",
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            ai_cli_timeout=60,
            force=False,
            owner="admin",
        )

    project = await storage.get_project(
        "test-repo", ai_provider="claude", ai_model="opus", owner="admin"
    )
    assert project is not None
    assert mock_incremental_planner.called
    assert not mock_run_planner.called
    assert mock_generate_all_pages.call_args.kwargs["use_cache"] is True
    assert mock_generate_all_pages.call_args.kwargs["existing_pages"] == {
        "introduction": "# Introduction\n\nOld intro\n"
    }
    assert project["status"] == "ready"
    assert project["last_commit_sha"] == "def456"


async def test_generate_from_path_clears_stale_cache_for_full_regeneration(
    client: AsyncClient, tmp_path: Path
) -> None:
    import docsfy.storage as storage
    from docsfy.main import _generate_from_path
    from docsfy.storage import get_project_cache_dir, get_project_dir

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
                    }
                ],
            }
        ],
    }

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    get_project_dir("test-repo", "claude", "opus", "admin").mkdir(
        parents=True, exist_ok=True
    )
    cache_dir = get_project_cache_dir("test-repo", "claude", "opus", "admin")
    cache_dir.mkdir(parents=True, exist_ok=True)
    stale_cache_file = cache_dir / "stale.md"
    stale_cache_file.write_text("# Stale\n\nOld output\n")

    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )
    await storage.update_project_status(
        "test-repo",
        "claude",
        "opus",
        status="ready",
        owner="admin",
        last_commit_sha="abc123",
    )

    recorded_calls: list[dict[str, object]] = []
    real_update_project_status = storage.update_project_status

    async def record_update_project_status(*args: object, **kwargs: object) -> None:
        recorded_calls.append({"args": args, "kwargs": dict(kwargs)})
        await real_update_project_status(*args, **kwargs)

    with (
        patch("docsfy.main.deepen_clone_for_diff", return_value=True),
        patch(
            "docsfy.main.get_diff",
            return_value=(["src/intro.py"], "diff --git a/src/intro.py\n+new intro"),
        ),
        patch("docsfy.main.run_planner", return_value=sample_plan),
        patch(
            "docsfy.main.generate_all_pages",
            return_value={"introduction": "# Introduction\n\nNew intro\n"},
        ),
        patch("docsfy.main.render_site"),
        patch(
            "docsfy.main.update_project_status",
            side_effect=record_update_project_status,
        ),
    ):
        await _generate_from_path(
            repo_dir=repo_dir,
            commit_sha="def456",
            source_url="https://github.com/org/test-repo.git",
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            ai_cli_timeout=60,
            force=False,
            owner="admin",
        )

    generating_pages_call = next(
        call
        for call in recorded_calls
        if call["kwargs"].get("current_stage") == "generating_pages"
    )
    assert generating_pages_call["kwargs"]["page_count"] == 0
    assert not stale_cache_file.exists()


async def test_generate_from_path_cross_provider_same_commit_reuses_existing_artifacts(
    client: AsyncClient, tmp_path: Path
) -> None:
    import docsfy.storage as storage
    from docsfy.main import _generate_from_path
    from docsfy.storage import get_project, get_project_cache_dir, get_project_site_dir

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
                    }
                ],
            }
        ],
    }

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    old_cache_dir = get_project_cache_dir("test-repo", "gemini", "flash", "admin")
    old_cache_dir.mkdir(parents=True, exist_ok=True)
    (old_cache_dir / "introduction.md").write_text("# Introduction\n\nGemini intro\n")

    old_site_dir = get_project_site_dir("test-repo", "gemini", "flash", "admin")
    old_site_dir.mkdir(parents=True, exist_ok=True)
    (old_site_dir / "index.html").write_text("<html>Gemini docs</html>")

    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="ready",
        ai_provider="gemini",
        ai_model="flash",
        owner="admin",
    )
    await storage.update_project_status(
        "test-repo",
        "gemini",
        "flash",
        status="ready",
        owner="admin",
        last_commit_sha="abc123",
        page_count=1,
        plan_json=json.dumps(sample_plan),
    )
    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )

    with (
        patch("docsfy.main.run_planner") as mock_run_planner,
        patch("docsfy.main.generate_all_pages") as mock_generate_all_pages,
        patch("docsfy.main.render_site") as mock_render_site,
    ):
        await _generate_from_path(
            repo_dir=repo_dir,
            commit_sha="abc123",
            source_url="https://github.com/org/test-repo.git",
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            ai_cli_timeout=60,
            force=False,
            owner="admin",
        )

    new_variant = await get_project(
        "test-repo", ai_provider="claude", ai_model="opus", owner="admin"
    )
    old_variant = await get_project(
        "test-repo", ai_provider="gemini", ai_model="flash", owner="admin"
    )
    new_cache_dir = get_project_cache_dir("test-repo", "claude", "opus", "admin")
    new_site_dir = get_project_site_dir("test-repo", "claude", "opus", "admin")

    assert new_variant is not None
    assert new_variant["status"] == "ready"
    assert new_variant["last_commit_sha"] == "abc123"
    assert new_variant["page_count"] == 1
    assert json.loads(str(new_variant["plan_json"])) == sample_plan
    assert (
        new_cache_dir / "introduction.md"
    ).read_text() == "# Introduction\n\nGemini intro\n"
    assert (new_site_dir / "index.html").read_text() == "<html>Gemini docs</html>"
    assert old_variant is None
    assert not old_cache_dir.exists()
    assert not old_site_dir.exists()
    assert not mock_run_planner.called
    assert not mock_generate_all_pages.called
    assert not mock_render_site.called


async def test_generate_from_path_cross_provider_reuses_unchanged_cached_pages(
    client: AsyncClient, tmp_path: Path
) -> None:
    import docsfy.storage as storage
    from docsfy.main import _generate_from_path
    from docsfy.storage import get_project, get_project_cache_dir, get_project_dir

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
                    {
                        "slug": "quickstart",
                        "title": "Quick Start",
                        "description": "Fast start",
                    },
                ],
            }
        ],
    }

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    get_project_dir("test-repo", "gemini", "flash", "admin").mkdir(
        parents=True, exist_ok=True
    )
    old_cache_dir = get_project_cache_dir("test-repo", "gemini", "flash", "admin")
    old_cache_dir.mkdir(parents=True, exist_ok=True)
    (old_cache_dir / "introduction.md").write_text("# Introduction\n\nOld intro\n")
    (old_cache_dir / "quickstart.md").write_text("# Quick Start\n\nCached quickstart\n")

    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="ready",
        ai_provider="gemini",
        ai_model="flash",
        owner="admin",
    )
    await storage.update_project_status(
        "test-repo",
        "gemini",
        "flash",
        status="ready",
        owner="admin",
        last_commit_sha="abc123",
        plan_json=json.dumps(sample_plan),
    )
    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )

    async def fake_generate_all_pages(
        *args: object, **kwargs: object
    ) -> dict[str, str]:
        cache_dir = kwargs["cache_dir"]
        assert isinstance(cache_dir, Path)
        assert kwargs["use_cache"] is True
        assert kwargs["existing_pages"] == {
            "introduction": "# Introduction\n\nOld intro\n"
        }
        assert not (cache_dir / "introduction.md").exists()
        assert (cache_dir / "quickstart.md").read_text() == (
            "# Quick Start\n\nCached quickstart\n"
        )
        return {
            "introduction": "# Introduction\n\nNew intro\n",
            "quickstart": "# Quick Start\n\nCached quickstart\n",
        }

    with (
        patch("docsfy.main.deepen_clone_for_diff", return_value=True),
        patch(
            "docsfy.main.get_diff",
            return_value=(["src/intro.py"], "diff --git a/src/intro.py\n+new intro"),
        ),
        patch(
            "docsfy.main.run_incremental_planner",
            return_value=["introduction"],
        ) as mock_incremental_planner,
        patch(
            "docsfy.main.run_planner",
            side_effect=AssertionError("full planner should not run"),
        ) as mock_run_planner,
        patch("docsfy.main.generate_all_pages", side_effect=fake_generate_all_pages),
        patch("docsfy.main.render_site"),
    ):
        await _generate_from_path(
            repo_dir=repo_dir,
            commit_sha="def456",
            source_url="https://github.com/org/test-repo.git",
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            ai_cli_timeout=60,
            force=False,
            owner="admin",
        )

    new_variant = await get_project(
        "test-repo", ai_provider="claude", ai_model="opus", owner="admin"
    )
    old_variant = await get_project(
        "test-repo", ai_provider="gemini", ai_model="flash", owner="admin"
    )
    new_cache_dir = get_project_cache_dir("test-repo", "claude", "opus", "admin")

    assert new_variant is not None
    assert new_variant["status"] == "ready"
    assert new_variant["last_commit_sha"] == "def456"
    assert (new_cache_dir / "quickstart.md").read_text() == (
        "# Quick Start\n\nCached quickstart\n"
    )
    assert old_variant is None
    assert not old_cache_dir.exists()
    assert mock_incremental_planner.called
    assert not mock_run_planner.called


async def test_force_generation_does_not_replace_existing_variant(
    client: AsyncClient, tmp_path: Path
) -> None:
    """force=True should do full generation without cross-provider reuse."""
    import docsfy.storage as storage
    from docsfy.main import _generate_from_path
    from docsfy.storage import (
        get_project,
        get_project_cache_dir,
        get_project_dir,
        get_project_site_dir,
    )

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
                    }
                ],
            }
        ],
    }

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Setup: save a ready variant with provider A (gemini/flash)
    get_project_dir("test-repo", "gemini", "flash", "admin").mkdir(
        parents=True, exist_ok=True
    )
    old_cache_dir = get_project_cache_dir("test-repo", "gemini", "flash", "admin")
    old_cache_dir.mkdir(parents=True, exist_ok=True)
    (old_cache_dir / "introduction.md").write_text("# Introduction\n\nGemini intro\n")
    (old_cache_dir / "stale.md").write_text("# Stale\n\nShould not leak\n")

    old_site_dir = get_project_site_dir("test-repo", "gemini", "flash", "admin")
    old_site_dir.mkdir(parents=True, exist_ok=True)
    (old_site_dir / "index.html").write_text("<html>Gemini site</html>")

    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="ready",
        ai_provider="gemini",
        ai_model="flash",
        owner="admin",
    )
    await storage.update_project_status(
        "test-repo",
        "gemini",
        "flash",
        status="ready",
        owner="admin",
        last_commit_sha="abc123",
        page_count=1,
        plan_json=json.dumps(sample_plan),
    )

    # Create the new variant record (provider B: claude/opus)
    await storage.save_project(
        name="test-repo",
        repo_url="https://github.com/org/test-repo.git",
        status="generating",
        ai_provider="claude",
        ai_model="opus",
        owner="admin",
    )
    get_project_dir("test-repo", "claude", "opus", "admin").mkdir(
        parents=True, exist_ok=True
    )

    with (
        patch("docsfy.main.run_planner", return_value=sample_plan) as mock_run_planner,
        patch(
            "docsfy.main.generate_all_pages",
            return_value={"introduction": "# Introduction\n\nClaude intro\n"},
        ) as mock_generate_all_pages,
        patch("docsfy.main.render_site"),
    ):
        # Call _generate_from_path with force=True and provider B
        await _generate_from_path(
            repo_dir=repo_dir,
            commit_sha="abc123",
            source_url="https://github.com/org/test-repo.git",
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            ai_cli_timeout=60,
            force=True,
            owner="admin",
        )

    # Verify: provider A variant still exists (not deleted)
    old_variant = await get_project(
        "test-repo", ai_provider="gemini", ai_model="flash", owner="admin"
    )
    assert old_variant is not None, "force=True must not delete the existing variant"
    assert old_variant["status"] == "ready"
    assert old_variant["last_commit_sha"] == "abc123"
    assert old_cache_dir.exists(), "force=True must not remove existing variant cache"

    # Verify: provider B variant was generated from scratch (no cross-provider reuse)
    new_variant = await get_project(
        "test-repo", ai_provider="claude", ai_model="opus", owner="admin"
    )
    assert new_variant is not None
    assert new_variant["status"] == "ready"
    assert mock_run_planner.called, "force=True should run the full planner"
    assert mock_generate_all_pages.called, (
        "force=True should generate pages from scratch"
    )

    # Verify stale artifacts from the old variant did NOT leak into the new variant
    new_cache_dir = get_project_cache_dir("test-repo", "claude", "opus", "admin")
    new_site_dir = get_project_site_dir("test-repo", "claude", "opus", "admin")
    assert not (new_cache_dir / "stale.md").exists(), (
        "stale cache artifact from old variant must not appear in new variant"
    )
    assert not (new_site_dir / "index.html").exists(), (
        "site artifact from old variant must not appear in new variant"
    )
