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


def test_detect_version_invalid_package_json(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "package.json").write_text("not valid json {{{")
    with patch("docsfy.postprocess.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        assert detect_version(tmp_path) is None


def test_detect_version_invalid_toml(tmp_path: Path) -> None:
    from docsfy.postprocess import detect_version

    (tmp_path / "pyproject.toml").write_text("not valid toml [[[")
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
    with (
        patch("docsfy.postprocess.call_ai_cli", return_value=(True, stale_refs)),
        patch(
            "docsfy.postprocess.generate_full_page_content",
            return_value=regen_content,
        ),
    ):
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
    assert "cli_flags" not in kwargs or kwargs["cli_flags"] is None


@pytest.mark.asyncio
async def test_validate_pages_passes_timeout_to_regen(tmp_path: Path) -> None:
    """When regenerating, ai_cli_timeout must be forwarded to generate_full_page_content."""
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
    with (
        patch("docsfy.postprocess.call_ai_cli", return_value=(True, stale_refs)),
        patch(
            "docsfy.postprocess.generate_full_page_content",
            return_value=regen_content,
        ) as mock_regen,
    ):
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
    assert "cli_flags" not in kwargs or kwargs["cli_flags"] is None


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
    with (
        patch(
            "docsfy.postprocess.call_ai_cli",
            return_value=(True, stale_refs_no_reference),
        ),
        patch("docsfy.postprocess.generate_full_page_content") as mock_regen,
    ):
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
    with (
        patch("docsfy.postprocess.call_ai_cli", return_value=(False, "AI error")),
        patch("docsfy.postprocess.logger") as mock_logger,
    ):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
            project_name="my-project",
        )
    # Should have logged with [my-project] prefix
    assert any(
        "[my-project]" in str(call) for call in mock_logger.warning.call_args_list
    )
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
    with (
        patch("docsfy.postprocess.call_ai_cli", return_value=(True, "invalid json")),
        patch("docsfy.postprocess.logger") as mock_logger,
    ):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
            project_name="my-project",
        )
    # Should have logged with [my-project] prefix
    assert any(
        "[my-project]" in str(call) for call in mock_logger.warning.call_args_list
    )
    assert result == pages


# --- Fix 4: Separate parse failure from empty results in validation ---


@pytest.mark.asyncio
async def test_validate_single_page_parse_failure_logs_warning(
    tmp_path: Path,
) -> None:
    """When parse_json_array_response returns None (invalid JSON),
    _validate_single_page must log a warning mentioning 'invalid JSON'."""
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Intro\nContent."}
    with (
        patch(
            "docsfy.postprocess.call_ai_cli",
            return_value=(True, "not valid json at all"),
        ),
        patch("docsfy.postprocess.logger") as mock_logger,
    ):
        result = await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="claude",
            ai_model="opus",
            cache_dir=tmp_path / "cache",
            project_name="test",
        )
    assert result == pages
    # Must have logged a warning about invalid JSON
    assert any(
        "invalid JSON" in str(call) for call in mock_logger.warning.call_args_list
    )


@pytest.mark.asyncio
async def test_validate_single_page_empty_list_no_warning(
    tmp_path: Path,
) -> None:
    """When parse_json_array_response returns [] (empty list, no issues),
    _validate_single_page must NOT log any warning."""
    from docsfy.postprocess import validate_pages

    pages = {"intro": "# Intro\nContent."}
    with (
        patch("docsfy.postprocess.call_ai_cli", return_value=(True, "[]")),
        patch("docsfy.postprocess.logger") as mock_logger,
    ):
        result = await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="claude",
            ai_model="opus",
            cache_dir=tmp_path / "cache",
            project_name="test",
        )
    assert result == pages
    # Must NOT have logged any warnings
    mock_logger.warning.assert_not_called()


# --- Fix 5: add_cross_links fail-soft on AI exceptions and non-dict JSON ---


@pytest.mark.asyncio
async def test_add_cross_links_ai_exception_returns_pages_unchanged(
    tmp_path: Path,
) -> None:
    """When call_ai_cli raises an exception, add_cross_links must catch it
    and return pages unchanged."""
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
        "docsfy.postprocess.call_ai_cli",
        side_effect=RuntimeError("AI backend crashed"),
    ):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
            project_name="test-project",
        )
    assert result == pages


@pytest.mark.asyncio
async def test_add_cross_links_non_dict_json_returns_pages_unchanged(
    tmp_path: Path,
) -> None:
    """When AI returns valid JSON that is not a dict (e.g. a list),
    add_cross_links must return pages unchanged and log a warning."""
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
    # Mock parse_json_response to return a list (non-dict) directly,
    # so we test the isinstance(cross_links, dict) guard, not parse failure
    with (
        patch("docsfy.postprocess.call_ai_cli", return_value=(True, '["intro"]')),
        patch("docsfy.postprocess.parse_json_response", return_value=["intro"]),
        patch("docsfy.postprocess.logger") as mock_logger,
    ):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
            project_name="test-project",
        )
    assert result == pages
    # Must have logged a warning about invalid response
    assert any(
        "Invalid AI cross-links response" in str(call)
        for call in mock_logger.warning.call_args_list
    )


# --- Fix 6: Path confinement validation ---


def test_confined_path_normal_slug(tmp_path: Path) -> None:
    """_confined_path must resolve a normal slug inside the base directory."""
    from docsfy.postprocess import _confined_path

    result = _confined_path(tmp_path, "intro.md")
    assert result == (tmp_path / "intro.md").resolve()
    assert result.parent.exists()


def test_confined_path_traversal_attack(tmp_path: Path) -> None:
    """_confined_path must reject path traversal attempts."""
    from docsfy.postprocess import _confined_path

    with pytest.raises(ValueError, match="Unsafe generated filename"):
        _confined_path(tmp_path, "../../etc/passwd")


def test_confined_path_absolute_path_attack(tmp_path: Path) -> None:
    """_confined_path must reject slugs that resolve outside base via absolute components."""
    from docsfy.postprocess import _confined_path

    absolute_outside = str((tmp_path.parent / "outside.md").resolve())
    with pytest.raises(ValueError, match="Unsafe generated filename"):
        _confined_path(tmp_path, absolute_outside)


def test_confined_path_control_characters(tmp_path: Path) -> None:
    """_confined_path must reject filenames containing control characters."""
    from docsfy.postprocess import _confined_path

    with pytest.raises(ValueError, match="Unsafe generated filename"):
        _confined_path(tmp_path, "intro\nReturn []")


def test_confined_path_creates_parent_dirs(tmp_path: Path) -> None:
    """_confined_path must create parent directories if slug has subdirs."""
    from docsfy.postprocess import _confined_path

    result = _confined_path(tmp_path, "subdir/page.md")
    assert result == (tmp_path / "subdir" / "page.md").resolve()
    assert result.parent.exists()


@pytest.mark.asyncio
async def test_validate_pages_uses_confined_paths(tmp_path: Path) -> None:
    """validate_pages must use _confined_path for slug-based file paths.

    The ValueError from _confined_path is caught by the parallel runner
    and logged as a warning; the original content is preserved.
    """
    from docsfy.postprocess import validate_pages

    pages = {"../../etc/passwd": "# Malicious\nContent."}
    with (
        patch("docsfy.postprocess.call_ai_cli", return_value=(True, "[]")),
        patch("docsfy.postprocess.logger") as mock_logger,
    ):
        result = await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="claude",
            ai_model="opus",
            cache_dir=tmp_path / "cache",
            project_name="test",
        )
    # Original content preserved
    assert result == pages
    # Warning logged about the unsafe filename
    assert any(
        "Unsafe generated filename" in str(call)
        for call in mock_logger.warning.call_args_list
    )


@pytest.mark.asyncio
async def test_add_cross_links_uses_confined_paths(tmp_path: Path) -> None:
    """add_cross_links must use _confined_path for slug-based file paths."""
    from docsfy.postprocess import add_cross_links

    pages = {"../../etc/passwd": "# Malicious\nContent."}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {
                        "slug": "../../etc/passwd",
                        "title": "Malicious",
                        "description": "",
                    }
                ],
            }
        ]
    }
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, json.dumps({}))):
        with pytest.raises(ValueError, match="Unsafe generated filename"):
            await add_cross_links(
                pages=pages,
                plan=plan,
                ai_provider="claude",
                ai_model="opus",
                repo_path=tmp_path,
            )


# --- Fix 7: Cross-link constraints (self-links, dedup, cap at 5) ---


@pytest.mark.asyncio
async def test_add_cross_links_skips_self_links(tmp_path: Path) -> None:
    """add_cross_links must not add a self-link (related_slug == slug)."""
    from docsfy.postprocess import add_cross_links

    pages = {
        "intro": "# Intro\nContent.",
        "config": "# Config\nContent.",
    }
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {"slug": "intro", "title": "Intro", "description": ""},
                    {"slug": "config", "title": "Config", "description": ""},
                ],
            }
        ]
    }
    # AI suggests intro links to itself and config
    cross_links_json = json.dumps({"intro": ["intro", "config"]})
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, cross_links_json)):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
        )
    # Should have config link but NOT self-link
    assert "[Config](config.html)" in result["intro"]
    assert "[Intro](intro.html)" not in result["intro"]


@pytest.mark.asyncio
async def test_add_cross_links_deduplicates(tmp_path: Path) -> None:
    """add_cross_links must deduplicate related slugs."""
    from docsfy.postprocess import add_cross_links

    pages = {
        "intro": "# Intro\nContent.",
        "config": "# Config\nContent.",
    }
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {"slug": "intro", "title": "Intro", "description": ""},
                    {"slug": "config", "title": "Config", "description": ""},
                ],
            }
        ]
    }
    # AI suggests config twice
    cross_links_json = json.dumps({"intro": ["config", "config"]})
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, cross_links_json)):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
        )
    # Should appear only once
    assert result["intro"].count("[Config](config.html)") == 1


@pytest.mark.asyncio
async def test_add_cross_links_caps_at_five(tmp_path: Path) -> None:
    """add_cross_links must cap related pages at 5."""
    from docsfy.postprocess import add_cross_links

    slugs = [f"page{i}" for i in range(8)]
    pages = {slug: f"# {slug}\nContent." for slug in slugs}
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {"slug": slug, "title": slug.title(), "description": ""}
                    for slug in slugs
                ],
            }
        ]
    }
    # AI suggests 7 related pages for page0
    cross_links_json = json.dumps({"page0": slugs[1:]})
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, cross_links_json)):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
        )
    # Count the number of link items
    related_section = result["page0"].split("## Related Pages")[1]
    link_count = related_section.count("- [")
    assert link_count == 5


# --- Fix 8: Validation failure log must not include raw AI output ---


@pytest.mark.asyncio
async def test_validate_pages_ai_failure_does_not_log_raw_output(
    tmp_path: Path,
) -> None:
    """When AI call fails, the warning log must NOT contain the raw AI output."""
    from docsfy.postprocess import validate_pages

    raw_output = "SENSITIVE_RAW_AI_OUTPUT_SHOULD_NOT_APPEAR"
    pages = {"intro": "# Intro\nContent."}
    with (
        patch(
            "docsfy.postprocess.call_ai_cli",
            return_value=(False, raw_output),
        ),
        patch("docsfy.postprocess.logger") as mock_logger,
    ):
        result = await validate_pages(
            pages=pages,
            repo_path=tmp_path,
            ai_provider="claude",
            ai_model="opus",
            cache_dir=tmp_path / "cache",
            project_name="test",
        )
    assert result == pages
    # Warning must NOT contain the raw output
    for call in mock_logger.warning.call_args_list:
        assert raw_output not in str(call)
    # But debug SHOULD contain a truncated version
    assert any(
        "SENSITIVE_RAW" in str(call) for call in mock_logger.debug.call_args_list
    )


# --- Fix 9: Cross-link title escaping and fallback ---


@pytest.mark.asyncio
async def test_add_cross_links_escapes_markdown_in_titles(tmp_path: Path) -> None:
    """add_cross_links must escape markdown special chars in link titles."""
    from docsfy.postprocess import add_cross_links

    pages = {
        "intro": "# Intro\nContent.",
        "special": "# Special\nContent.",
    }
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {"slug": "intro", "title": "Introduction", "description": ""},
                    {
                        "slug": "special",
                        "title": "Config [advanced]",
                        "description": "",
                    },
                ],
            }
        ]
    }
    cross_links_json = json.dumps({"intro": ["special"]})
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, cross_links_json)):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
        )
    # Brackets must be escaped in the link text
    assert r"Config \[advanced\]" in result["intro"]
    assert "(special.html)" in result["intro"]


@pytest.mark.asyncio
async def test_add_cross_links_fallback_to_slug_for_unknown_pages(
    tmp_path: Path,
) -> None:
    """add_cross_links must use slug as fallback title for pages not in plan navigation."""
    from docsfy.postprocess import add_cross_links

    pages = {
        "intro": "# Intro\nContent.",
        "extra": "# Extra\nContent.",
    }
    plan = {
        "navigation": [
            {
                "group": "Docs",
                "pages": [
                    {"slug": "intro", "title": "Introduction", "description": ""},
                    # "extra" is NOT in the plan navigation
                ],
            }
        ]
    }
    # AI suggests linking intro -> extra (extra is in pages but not in plan)
    cross_links_json = json.dumps({"intro": ["extra"]})
    with patch("docsfy.postprocess.call_ai_cli", return_value=(True, cross_links_json)):
        result = await add_cross_links(
            pages=pages,
            plan=plan,
            ai_provider="claude",
            ai_model="opus",
            repo_path=tmp_path,
        )
    # Should have a link using slug as the fallback title, because extra is in `pages`
    assert "[extra](extra.html)" in result["intro"]


def test_fix_broken_internal_links_removes_invalid() -> None:
    from docsfy.postprocess import fix_broken_internal_links

    pages = {
        "intro": "See [Setup Guide](setup.html) and [FAQ](faq.html) for details.",
    }
    plan = {
        "navigation": [
            {"group": "Start", "pages": [{"slug": "intro", "title": "Intro"}]}
        ]
    }
    result = fix_broken_internal_links(pages, plan, project_name="test")
    # "setup" and "faq" are not in the plan, links should be removed but text kept
    assert "[Setup Guide](setup.html)" not in result["intro"]
    assert "[FAQ](faq.html)" not in result["intro"]
    assert "Setup Guide" in result["intro"]
    assert "FAQ" in result["intro"]


def test_fix_broken_internal_links_keeps_valid() -> None:
    from docsfy.postprocess import fix_broken_internal_links

    pages = {
        "intro": "See [Quick Start](quickstart.html) for details.",
        "quickstart": "# Quick Start",
    }
    plan = {
        "navigation": [
            {
                "group": "Start",
                "pages": [
                    {"slug": "intro", "title": "Intro"},
                    {"slug": "quickstart", "title": "Quick Start"},
                ],
            }
        ]
    }
    result = fix_broken_internal_links(pages, plan, project_name="test")
    assert "[Quick Start](quickstart.html)" in result["intro"]


def test_fix_broken_internal_links_handles_anchors() -> None:
    from docsfy.postprocess import fix_broken_internal_links

    pages = {
        "intro": "See [Config](config.html#advanced) for details.",
        "config": "# Config",
    }
    plan = {
        "navigation": [
            {
                "group": "Start",
                "pages": [
                    {"slug": "intro", "title": "Intro"},
                    {"slug": "config", "title": "Config"},
                ],
            }
        ]
    }
    result = fix_broken_internal_links(pages, plan, project_name="test")
    # config exists in plan, link should be preserved
    assert "config.html#advanced" in result["intro"]


def test_fix_broken_internal_links_case_insensitive() -> None:
    from docsfy.postprocess import fix_broken_internal_links

    pages = {
        "intro": "See [Quick Start](QuickStart.html) for details.",
        "quickstart": "# Quick Start",
    }
    plan = {
        "navigation": [
            {
                "group": "Start",
                "pages": [
                    {"slug": "intro", "title": "Intro"},
                    {"slug": "quickstart", "title": "Quick Start"},
                ],
            }
        ]
    }
    result = fix_broken_internal_links(pages, plan, project_name="test")
    # Case-insensitive match rewrites to canonical slug casing
    assert "quickstart.html" in result["intro"]
    assert "QuickStart.html" not in result["intro"]


def test_linkify_plain_references_converts_see_pattern() -> None:
    from docsfy.postprocess import linkify_plain_references

    pages = {
        "quickstart": "Install the tool. See Configuration for details.",
        "config": "# Configuration\n\nSettings here.",
    }
    plan = {
        "navigation": [
            {
                "group": "Start",
                "pages": [
                    {"slug": "quickstart", "title": "Quickstart"},
                    {"slug": "config", "title": "Configuration"},
                ],
            }
        ]
    }
    result = linkify_plain_references(pages, plan, project_name="test")
    assert "[Configuration](config.html)" in result["quickstart"]
    assert "See [Configuration](config.html)" in result["quickstart"]


def test_linkify_plain_references_skips_existing_links() -> None:
    from docsfy.postprocess import linkify_plain_references

    pages = {
        "quickstart": "See [Configuration](config.html) for details.",
        "config": "# Configuration",
    }
    plan = {
        "navigation": [
            {
                "group": "Start",
                "pages": [
                    {"slug": "quickstart", "title": "Quickstart"},
                    {"slug": "config", "title": "Configuration"},
                ],
            }
        ]
    }
    result = linkify_plain_references(pages, plan, project_name="test")
    # Should not double-link
    assert result["quickstart"].count("[Configuration]") == 1


def test_linkify_plain_references_skips_self_links() -> None:
    from docsfy.postprocess import linkify_plain_references

    pages = {
        "config": "See Configuration for more.",
    }
    plan = {
        "navigation": [
            {
                "group": "Ref",
                "pages": [
                    {"slug": "config", "title": "Configuration"},
                ],
            }
        ]
    }
    result = linkify_plain_references(pages, plan, project_name="test")
    # Should NOT self-link
    assert "[Configuration](config.html)" not in result["config"]


def test_linkify_plain_references_longest_match_first() -> None:
    from docsfy.postprocess import linkify_plain_references

    pages = {
        "intro": "See CLI Command Reference for flags.",
        "cli-ref": "# CLI Command Reference",
        "cli": "# CLI",
    }
    plan = {
        "navigation": [
            {
                "group": "Ref",
                "pages": [
                    {"slug": "intro", "title": "Introduction"},
                    {"slug": "cli-ref", "title": "CLI Command Reference"},
                    {"slug": "cli", "title": "CLI"},
                ],
            }
        ]
    }
    result = linkify_plain_references(pages, plan, project_name="test")
    # Should match the longer "CLI Command Reference", not just "CLI"
    assert "[CLI Command Reference](cli-ref.html)" in result["intro"]


def test_fix_broken_internal_links_dotted_slug_valid() -> None:
    from docsfy.postprocess import fix_broken_internal_links

    pages = {
        "intro": "See [API v2](api.v2.html) for details.",
        "api.v2": "# API v2",
    }
    plan = {
        "navigation": [
            {
                "group": "Ref",
                "pages": [
                    {"slug": "intro", "title": "Intro"},
                    {"slug": "api.v2", "title": "API v2"},
                ],
            }
        ]
    }
    result = fix_broken_internal_links(pages, plan, project_name="test")
    assert "[API v2](api.v2.html)" in result["intro"]


def test_fix_broken_internal_links_dotted_slug_broken() -> None:
    from docsfy.postprocess import fix_broken_internal_links

    pages = {
        "intro": "See [Old API](api.v1.html) for details.",
    }
    plan = {
        "navigation": [
            {
                "group": "Ref",
                "pages": [
                    {"slug": "intro", "title": "Intro"},
                ],
            }
        ]
    }
    result = fix_broken_internal_links(pages, plan, project_name="test")
    assert "[Old API](api.v1.html)" not in result["intro"]
    assert "Old API" in result["intro"]
