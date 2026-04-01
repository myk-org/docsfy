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


# --- Fix 1: ai_cli_timeout and cli_flags wiring ---


@pytest.mark.asyncio
async def test_validate_pages_passes_ai_cli_timeout(tmp_path: Path) -> None:
    """validate_pages must forward ai_cli_timeout to call_ai_cli."""
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Intro\nContent."}
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, "[]")) as mock_cli:
        await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="claude",
            ai_model="opus",
            cache_dir=tmp_path / "cache",
            project_name="test",
            ai_cli_timeout=42,
        )
    mock_cli.assert_called_once()
    _, kwargs = mock_cli.call_args
    assert kwargs.get("ai_cli_timeout") == 42


@pytest.mark.asyncio
async def test_validate_pages_cursor_passes_trust_flag(tmp_path: Path) -> None:
    """validate_pages must pass cli_flags=['--trust'] when ai_provider is 'cursor'."""
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Intro\nContent."}
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, "[]")) as mock_cli:
        await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="cursor",
            ai_model="gpt-5.4",
            cache_dir=tmp_path / "cache",
            project_name="test",
        )
    mock_cli.assert_called_once()
    _, kwargs = mock_cli.call_args
    assert kwargs.get("cli_flags") == ["--trust"]


@pytest.mark.asyncio
async def test_validate_pages_non_cursor_no_trust_flag(tmp_path: Path) -> None:
    """validate_pages must NOT pass --trust when ai_provider is not 'cursor'."""
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Intro\nContent."}
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, "[]")) as mock_cli:
        await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="gemini",
            ai_model="gemini-flash",
            cache_dir=tmp_path / "cache",
            project_name="test",
        )
    mock_cli.assert_called_once()
    _, kwargs = mock_cli.call_args
    assert kwargs.get("cli_flags") is None


@pytest.mark.asyncio
async def test_validate_pages_passes_timeout_to_regen(tmp_path: Path) -> None:
    """When regenerating, ai_cli_timeout must be forwarded to _generate_full_page_content."""
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Intro\nOld content."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [{"slug": "intro", "title": "Intro", "description": "Desc"}],
            }
        ]
    }
    stale_refs = json.dumps([{"reference": "old_feature", "reason": "removed"}])
    regen_content = "# Intro\nNew content."
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, stale_refs)):
        with patch(
            "docsfy.postprocess._generate_full_page_content",
            return_value=regen_content,
        ) as mock_regen:
            await validate_pages(
                pages=pages,
                repo_path=tmp_path,
                ai_provider="claude",
                ai_model="opus",
                cache_dir=tmp_path / "cache",
                project_name="test",
                plan=plan,
                ai_cli_timeout=99,
            )
    mock_regen.assert_called_once()
    _, kwargs = mock_regen.call_args
    assert kwargs.get("ai_cli_timeout") == 99


@pytest.mark.asyncio
async def test_add_cross_links_passes_ai_cli_timeout(tmp_path: Path) -> None:
    """add_cross_links must forward ai_cli_timeout to call_ai_cli."""
    from docsfy.postprocess import add_cross_links

    pages = {"intro": "# Intro\nContent.", "api": "# API\nContent."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {"slug": "intro", "title": "Intro", "description": ""},
                    {"slug": "api", "title": "API", "description": ""},
                ],
            }
        ]
    }
    cross_links_json = json.dumps({"intro": ["api"]})
    with patch(
        "docsfy.postprocess.call_ai_cli", return_value=(True, cross_links_json)
    ) as mock_cli:
        await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
            ai_cli_timeout=77,
        )
    mock_cli.assert_called_once()
    _, kwargs = mock_cli.call_args
    assert kwargs.get("ai_cli_timeout") == 77


@pytest.mark.asyncio
async def test_add_cross_links_cursor_passes_trust_flag(tmp_path: Path) -> None:
    """add_cross_links must pass cli_flags=['--trust'] when ai_provider is 'cursor'."""
    from docsfy.postprocess import add_cross_links

    pages = {"intro": "# Intro\nContent."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [{"slug": "intro", "title": "Intro", "description": ""}],
            }
        ]
    }
    with patch(
        "docsfy.postprocess.call_ai_cli", return_value=(True, json.dumps({}))
    ) as mock_cli:
        await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="cursor",
            ai_model="gpt-5.4",
            repo_path=tmp_path,
        )
    mock_cli.assert_called_once()
    _, kwargs = mock_cli.call_args
    assert kwargs.get("cli_flags") == ["--trust"]


@pytest.mark.asyncio
async def test_add_cross_links_non_cursor_no_trust_flag(tmp_path: Path) -> None:
    """add_cross_links must NOT pass --trust when ai_provider is not 'cursor'."""
    from docsfy.postprocess import add_cross_links

    pages = {"intro": "# Intro\nContent."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [{"slug": "intro", "title": "Intro", "description": ""}],
            }
        ]
    }
    with patch(
        "docsfy.postprocess.call_ai_cli", return_value=(True, json.dumps({}))
    ) as mock_cli:
        await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="gemini",
            ai_model="gemini-flash",
            repo_path=tmp_path,
        )
    mock_cli.assert_called_once()
    _, kwargs = mock_cli.call_args
    assert kwargs.get("cli_flags") is None


# --- Fix 2: Guard against empty exclusions ---


@pytest.mark.asyncio
async def test_validate_single_page_empty_exclusions_returns_original(
    tmp_path: Path,
) -> None:
    """When AI returns stale refs but none have usable reference strings,
    _validate_single_page must return the original content without regenerating."""
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Intro\nOriginal content."}
    # AI returns objects without a 'reference' key → exclusions is empty after filtering
    stale_refs_no_reference = json.dumps([{"reason": "removed"}, {"other": "field"}])
    with patch(
        "docsfy.postprocess.call_ai_cli", return_value=(True, stale_refs_no_reference)
    ):
        with patch("docsfy.postprocess._generate_full_page_content") as mock_regen:
            result = await validate_pages(
                pages=pages,
                repo_path=tmp_path,
                ai_provider="claude",
                ai_model="opus",
                cache_dir=tmp_path / "cache",
                project_name="test",
            )
    # Must NOT have called regen
    mock_regen.assert_not_called()
    # Must return original content unchanged
    assert result == pages


# --- Fix 3: project_name parameter for structured logging in add_cross_links ---


@pytest.mark.asyncio
async def test_add_cross_links_accepts_project_name_parameter(
    tmp_path: Path,
) -> None:
    """add_cross_links must accept project_name parameter."""
    from docsfy.postprocess import add_cross_links

    pages = {"intro": "# Intro\nContent."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [{"slug": "intro", "title": "Intro", "description": ""}],
            }
        ]
    }
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, json.dumps({}))):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
            project_name="my-project",
        )
    assert result == pages


@pytest.mark.asyncio
async def test_add_cross_links_ai_failure_includes_project_name_in_log(
    tmp_path: Path,
) -> None:
    """When AI call fails, add_cross_links must log with [project_name] prefix."""
    from docsfy.postprocess import add_cross_links

    pages = {"intro": "# Intro\nContent."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [{"slug": "intro", "title": "Intro", "description": ""}],
            }
        ]
    }
    with patch("docsfy.postprocess.call_ai_cli", return_value=(False, "AI error")):
        with patch("docsfy.postprocess.logger") as mock_logger:
            result = await add_cross_links(
                pages=pages,
                plan=plan,
                ai_provider="claude",
                ai_model="opus",
                repo_path=tmp_path,
                project_name="my-project",
            )
    # Should have logged with [my-project] prefix
    mock_logger.warning.assert_called_once()
    log_msg = mock_logger.warning.call_args[0][0]
    assert "[my-project]" in log_msg
    assert result == pages


@pytest.mark.asyncio
async def test_add_cross_links_parse_failure_includes_project_name_in_log(
    tmp_path: Path,
) -> None:
    """When parsing cross-links fails, add_cross_links must log with [project_name] prefix."""
    from docsfy.postprocess import add_cross_links

    pages = {"intro": "# Intro\nContent."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [{"slug": "intro", "title": "Intro", "description": ""}],
            }
        ]
    }
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, "invalid json")):
        with patch("docsfy.postprocess.logger") as mock_logger:
            result = await add_cross_links(
                pages=pages,
                plan=plan,
                ai_provider="claude",
                ai_model="opus",
                repo_path=tmp_path,
                project_name="my-project",
            )
    # Should have logged with [my-project] prefix
    mock_logger.warning.assert_called_once()
    log_msg = mock_logger.warning.call_args[0][0]
    assert "[my-project]" in log_msg
    assert result == pages
