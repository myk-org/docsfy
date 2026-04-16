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
                    {
                        "slug": "introduction",
                        "title": "Introduction",
                        "description": "Overview",
                    },
                    {
                        "slug": "quickstart",
                        "title": "Quick Start",
                        "description": "Get started fast",
                    },
                ],
            }
        ],
    }


async def test_run_planner(tmp_path: Path, sample_plan: dict) -> None:
    from docsfy.generator import run_planner

    with patch(
        "docsfy.generator.call_ai_cli", return_value=(True, json.dumps(sample_plan))
    ):
        plan = await run_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
        )

    assert plan is not None
    assert plan["project_name"] == "test-repo"
    assert len(plan["navigation"]) == 1


async def test_run_planner_ai_failure(tmp_path: Path) -> None:
    from docsfy.generator import run_planner

    with patch("docsfy.generator.call_ai_cli", return_value=(False, "AI error")):
        with pytest.raises(RuntimeError, match="AI error"):
            await run_planner(
                repo_path=tmp_path,
                project_name="test-repo",
                ai_provider="claude",
                ai_model="opus",
            )


async def test_run_planner_bad_json(tmp_path: Path) -> None:
    from docsfy.generator import run_planner

    with patch("docsfy.generator.call_ai_cli", return_value=(True, "not json")):
        with pytest.raises(RuntimeError, match="Failed to parse"):
            await run_planner(
                repo_path=tmp_path,
                project_name="test-repo",
                ai_provider="claude",
                ai_model="opus",
            )


async def test_generate_page(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, "# Introduction\n\nWelcome!"),
    ):
        md = await generate_page(
            repo_path=tmp_path,
            slug="introduction",
            title="Introduction",
            description="Overview",
            cache_dir=cache_dir,
            ai_provider="claude",
            ai_model="opus",
        )

    assert "# Introduction" in md
    assert (cache_dir / "introduction.md").exists()


async def test_generate_page_applies_incremental_updates(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    existing_content = (
        "# Introduction\n\nWelcome!\n\n## Configuration\n\nOld settings.\n"
    )
    incremental_response = json.dumps(
        {
            "updates": [
                {
                    "old_text": "## Configuration\n\nOld settings.\n",
                    "new_text": "## Configuration\n\nNew settings.\n",
                }
            ]
        }
    )

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, incremental_response),
    ):
        md = await generate_page(
            repo_path=tmp_path,
            slug="introduction",
            title="Introduction",
            description="Overview",
            cache_dir=cache_dir,
            ai_provider="claude",
            ai_model="opus",
            existing_content=existing_content,
            changed_files=["src/config.py"],
            diff_content="diff --git a/src/config.py\n+new settings",
        )

    assert md == "# Introduction\n\nWelcome!\n\n## Configuration\n\nNew settings.\n"
    assert (cache_dir / "introduction.md").read_text() == md


async def test_generate_page_falls_back_to_full_generation_on_invalid_incremental_update(
    tmp_path: Path,
) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    existing_content = "# Introduction\n\nWelcome!\n"
    invalid_incremental_response = json.dumps(
        {
            "updates": [
                {
                    "old_text": "## Missing\n\nNot here.\n",
                    "new_text": "## Missing\n\nUpdated.\n",
                }
            ]
        }
    )
    full_page_response = "# Introduction\n\nRegenerated content.\n"

    with patch(
        "docsfy.generator.call_ai_cli",
        side_effect=[
            (True, invalid_incremental_response),
            (True, full_page_response),
        ],
    ) as mock_call:
        md = await generate_page(
            repo_path=tmp_path,
            slug="introduction",
            title="Introduction",
            description="Overview",
            cache_dir=cache_dir,
            ai_provider="claude",
            ai_model="opus",
            existing_content=existing_content,
            changed_files=["src/main.py"],
            diff_content="diff --git a/src/main.py\n+new line",
        )

    assert md == full_page_response.strip()
    assert mock_call.call_count == 2


async def test_generate_page_uses_cache(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached = cache_dir / "introduction.md"
    cached.write_text("# Cached content")

    md = await generate_page(
        repo_path=tmp_path,
        slug="introduction",
        title="Introduction",
        description="Overview",
        cache_dir=cache_dir,
        ai_provider="claude",
        ai_model="opus",
        use_cache=True,
    )

    assert md == "# Cached content"


async def test_run_incremental_planner(tmp_path: Path, sample_plan: dict) -> None:
    from docsfy.generator import run_incremental_planner

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, '["introduction"]'),
    ):
        result = await run_incremental_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            changed_files=["src/main.py"],
            existing_plan=sample_plan,
        )

    assert result == ["introduction"]


async def test_run_incremental_planner_preserves_empty_result(
    tmp_path: Path, sample_plan: dict
) -> None:
    from docsfy.generator import run_incremental_planner

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, "[]"),
    ):
        result = await run_incremental_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            changed_files=["src/main.py"],
            existing_plan=sample_plan,
        )

    assert result == []


async def test_run_incremental_planner_returns_all_on_non_string_items(
    tmp_path: Path, sample_plan: dict
) -> None:
    from docsfy.generator import run_incremental_planner

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, '[1, "valid", null]'),
    ):
        result = await run_incremental_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            changed_files=["src/main.py"],
            existing_plan=sample_plan,
        )

    assert result == ["all"]


async def test_run_incremental_planner_returns_all_on_mixed_all_and_slug(
    tmp_path: Path, sample_plan: dict
) -> None:
    from docsfy.generator import run_incremental_planner

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, '["all", "introduction"]'),
    ):
        result = await run_incremental_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            changed_files=["src/main.py"],
            existing_plan=sample_plan,
        )

    assert result == ["all"]


async def test_run_incremental_planner_returns_all_on_empty_slug(
    tmp_path: Path, sample_plan: dict
) -> None:
    from docsfy.generator import run_incremental_planner

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, '["   "]'),
    ):
        result = await run_incremental_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            changed_files=["src/main.py"],
            existing_plan=sample_plan,
        )

    assert result == ["all"]


async def test_run_incremental_planner_deduplicates_and_trims_slugs(
    tmp_path: Path, sample_plan: dict
) -> None:
    from docsfy.generator import run_incremental_planner

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, '[" introduction ", "introduction", "quickstart"]'),
    ):
        result = await run_incremental_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            changed_files=["src/main.py"],
            existing_plan=sample_plan,
        )

    assert result == ["introduction", "quickstart"]


async def test_run_incremental_planner_returns_all_on_failure(
    tmp_path: Path, sample_plan: dict
) -> None:
    from docsfy.generator import run_incremental_planner

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(False, "AI error"),
    ):
        result = await run_incremental_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            changed_files=["src/main.py"],
            existing_plan=sample_plan,
        )

    assert result == ["all"]


async def test_run_incremental_planner_returns_all_on_bad_json(
    tmp_path: Path, sample_plan: dict
) -> None:
    from docsfy.generator import run_incremental_planner

    with patch(
        "docsfy.generator.call_ai_cli",
        return_value=(True, "not json at all"),
    ):
        result = await run_incremental_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            changed_files=["src/main.py"],
            existing_plan=sample_plan,
        )

    assert result == ["all"]
