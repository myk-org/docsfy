from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def sample_plan() -> dict:
    return {
        "project_name": "test-repo",
        "tagline": "A test project",
        "navigation": [
            {
                "group": "Getting Started",
                "pages": [
                    {"slug": "introduction", "title": "Introduction", "description": "Overview"},
                    {"slug": "quickstart", "title": "Quick Start", "description": "Get started fast"},
                ],
            }
        ],
    }


async def test_run_planner(tmp_path: Path, sample_plan: dict) -> None:
    from docsfy.generator import run_planner

    with patch("docsfy.generator.call_ai_cli", return_value=(True, json.dumps(sample_plan))):
        plan = await run_planner(repo_path=tmp_path, project_name="test-repo", ai_provider="claude", ai_model="opus")

    assert plan is not None
    assert plan["project_name"] == "test-repo"
    assert len(plan["navigation"]) == 1


async def test_run_planner_ai_failure(tmp_path: Path) -> None:
    from docsfy.generator import run_planner

    with patch("docsfy.generator.call_ai_cli", return_value=(False, "AI error")):
        with pytest.raises(RuntimeError, match="AI error"):
            await run_planner(repo_path=tmp_path, project_name="test-repo", ai_provider="claude", ai_model="opus")


async def test_run_planner_bad_json(tmp_path: Path) -> None:
    from docsfy.generator import run_planner

    with patch("docsfy.generator.call_ai_cli", return_value=(True, "not json")):
        with pytest.raises(RuntimeError, match="Failed to parse"):
            await run_planner(repo_path=tmp_path, project_name="test-repo", ai_provider="claude", ai_model="opus")


async def test_generate_page(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    with patch("docsfy.generator.call_ai_cli", return_value=(True, "# Introduction\n\nWelcome!")):
        md = await generate_page(
            repo_path=tmp_path, slug="introduction", title="Introduction", description="Overview",
            cache_dir=cache_dir, ai_provider="claude", ai_model="opus",
        )

    assert "# Introduction" in md
    assert (cache_dir / "introduction.md").exists()


async def test_generate_page_uses_cache(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached = cache_dir / "introduction.md"
    cached.write_text("# Cached content")

    md = await generate_page(
        repo_path=tmp_path, slug="introduction", title="Introduction", description="Overview",
        cache_dir=cache_dir, ai_provider="claude", ai_model="opus", use_cache=True,
    )

    assert md == "# Cached content"
