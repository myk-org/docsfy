from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


def test_detect_version_pyproject_toml(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "2.1.0"\n'
    )
    assert detect_version(tmp_path) == "2.1.0"


def test_detect_version_pyproject_poetry(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "myapp"\nversion = "3.0.0"\n'
    )
    assert detect_version(tmp_path) == "3.0.0"


def test_detect_version_package_json(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "package.json").write_text('{"name": "myapp", "version": "1.5.2"}')
    assert detect_version(tmp_path) == "1.5.2"


def test_detect_version_cargo_toml(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "myapp"\nversion = "0.3.1"\n'
    )
    assert detect_version(tmp_path) == "0.3.1"


def test_detect_version_setup_cfg(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "setup.cfg").write_text("[metadata]\nname = myapp\nversion = 4.0.0\n")
    assert detect_version(tmp_path) == "4.0.0"


def test_detect_version_git_tag(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    with patch("docsfy.postprocess.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="v1.0.0\n", stderr=""
        )
        assert detect_version(tmp_path) == "v1.0.0"


def test_detect_version_git_tag_fails(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    with patch("docsfy.postprocess.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        assert detect_version(tmp_path) is None


def test_detect_version_priority_order(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "1.0.0"\n'
    )
    (tmp_path / "package.json").write_text('{"name": "myapp", "version": "2.0.0"}')
    assert detect_version(tmp_path) == "1.0.0"


def test_detect_version_none_when_no_sources(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    with patch("docsfy.postprocess.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        assert detect_version(tmp_path) is None


@pytest.mark.asyncio
async def test_validate_pages_no_issues(tmp_path: Path) -> None:
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Introduction\nThis is valid content."}
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, "[]")):
        result = await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="claude",
            ai_model="opus",
            cache_dir=tmp_path / "cache",
            project_name="test",
        )
    assert result == pages


@pytest.mark.asyncio
async def test_validate_pages_with_stale_references(tmp_path: Path) -> None:
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Introduction\nUses the old HTML reports feature."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {
                        "slug": "intro",
                        "title": "Introduction",
                        "description": "Overview of the project",
                    },
                ],
            }
        ]
    }
    stale_refs = json.dumps(
        [{"reference": "HTML reports feature", "reason": "removed in v2"}]
    )
    regen_content = "# Introduction\nUses the new React dashboard."
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, stale_refs)):
        with patch("docsfy.generator.call_ai_cli", return_value=(True, regen_content)):
            result = await validate_pages(
                pages=pages,
                repo_path=tmp_path,
                ai_provider="claude",
                ai_model="opus",
                cache_dir=tmp_path / "cache",
                project_name="test",
                plan=plan,
            )
    assert "React dashboard" in result["intro"]


@pytest.mark.asyncio
async def test_validate_pages_ai_failure_preserves_pages(tmp_path: Path) -> None:
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Introduction\nOriginal content."}
    with patch("docsfy.postprocess.call_ai_cli", return_value=(False, "AI error")):
        result = await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="claude",
            ai_model="opus",
            cache_dir=tmp_path / "cache",
            project_name="test",
        )
    assert result == pages


@pytest.mark.asyncio
async def test_add_cross_links(tmp_path: Path) -> None:
    from docsfy.postprocess import add_cross_links

    pages = {
        "intro": "# Introduction\nOverview content.",
        "config": "# Configuration\nConfig content.",
        "api": "# API Reference\nAPI content.",
    }
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {
                        "slug": "intro",
                        "title": "Introduction",
                        "description": "Overview",
                    },
                    {
                        "slug": "config",
                        "title": "Configuration",
                        "description": "Config guide",
                    },
                    {
                        "slug": "api",
                        "title": "API Reference",
                        "description": "API docs",
                    },
                ],
            }
        ]
    }
    cross_links_json = json.dumps(
        {
            "intro": ["config", "api"],
            "config": ["intro"],
            "api": ["intro", "config"],
        }
    )
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, cross_links_json)):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
        )
    assert "## Related Pages" in result["intro"]
    assert "[Configuration](config.html)" in result["intro"]
    assert "[API Reference](api.html)" in result["intro"]
    assert "## Related Pages" in result["api"]


@pytest.mark.asyncio
async def test_add_cross_links_ai_failure_preserves_pages(tmp_path: Path) -> None:
    from docsfy.postprocess import add_cross_links

    pages = {"intro": "# Introduction\nContent."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [{"slug": "intro", "title": "Intro", "description": ""}],
            }
        ]
    }
    with patch("docsfy.postprocess.call_ai_cli", return_value=(False, "AI error")):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
        )
    assert result == pages
