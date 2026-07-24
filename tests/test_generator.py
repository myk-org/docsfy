from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from docsfy.ai_client import AIResult


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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text=json.dumps(sample_plan)),
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

    with patch(
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=False, text="AI error"),
    ):
        with pytest.raises(RuntimeError, match="AI error"):
            await run_planner(
                repo_path=tmp_path,
                project_name="test-repo",
                ai_provider="claude",
                ai_model="opus",
            )


async def test_run_planner_bad_json(tmp_path: Path) -> None:
    from docsfy.generator import run_planner

    with patch(
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text="not json"),
    ):
        with pytest.raises(RuntimeError, match="Failed to parse"):
            await run_planner(
                repo_path=tmp_path,
                project_name="test-repo",
                ai_provider="claude",
                ai_model="opus",
            )


async def test_call_ai_or_raise_passes_tools(tmp_path: Path) -> None:
    from docsfy.generator import _call_ai_or_raise
    from docsfy.prompts import SIDECAR_TOOLS

    with patch(
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text="ok"),
    ) as mock_call:
        await _call_ai_or_raise(
            prompt="test",
            repo_path=tmp_path,
            ai_provider="claude",
            ai_model="opus",
        )

    mock_call.assert_called_once()
    call_kwargs = mock_call.call_args[1]
    assert call_kwargs["tools"] == list(SIDECAR_TOOLS)
    assert "bash" not in call_kwargs["tools"]


async def test_generate_page(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    with patch(
        "docsfy.generator.call_ai_once",
        return_value=AIResult(
            success=True,
            text=(
                "# Introduction\n\nWelcome! This page gives a complete overview of "
                "the project, what it does, and how to get started quickly."
            ),
        ),
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
    assert "Documentation generation failed" not in md
    assert (cache_dir / "introduction.md").exists()


async def test_generate_page_applies_incremental_updates(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    existing_content = (
        "# Introduction\n\nWelcome! This page gives a complete overview of the "
        "project and how it works end to end.\n\n"
        "## Configuration\n\nOld settings that describe legacy configuration "
        "options in detail for existing users.\n"
    )
    incremental_response = json.dumps(
        {
            "updates": [
                {
                    "old_text": (
                        "## Configuration\n\nOld settings that describe legacy "
                        "configuration options in detail for existing users.\n"
                    ),
                    "new_text": (
                        "## Configuration\n\nNew settings that describe the "
                        "current configuration options in detail for users.\n"
                    ),
                }
            ]
        }
    )

    with patch(
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text=incremental_response),
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

    assert "New settings that describe the current configuration" in md
    assert "Old settings" not in md
    assert (cache_dir / "introduction.md").read_text() == md


async def test_generate_page_falls_back_to_full_generation_on_invalid_incremental_update(
    tmp_path: Path,
) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    existing_content = (
        "# Introduction\n\nWelcome! This page gives a complete overview of the "
        "project and how it works end to end.\n"
    )
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
    full_page_response = (
        "# Introduction\n\nRegenerated content that fully describes the "
        "introduction page in much more depth and detail for readers.\n"
    )

    with patch(
        "docsfy.generator.call_ai_once",
        side_effect=[
            AIResult(success=True, text=invalid_incremental_response),
            AIResult(success=True, text=full_page_response),
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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text='["introduction"]'),
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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text="[]"),
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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text='[1, "valid", null]'),
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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text='["all", "introduction"]'),
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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text='["   "]'),
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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(
            success=True, text='[" introduction ", "introduction", "quickstart"]'
        ),
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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=False, text="AI error"),
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
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text="not json at all"),
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


def test_strip_ai_artifacts_removes_think_blocks() -> None:
    from docsfy.generator import _strip_ai_artifacts

    text = (
        "# Title\n\nContent here.\n\n<think>Some AI reasoning</think>\n\nMore content."
    )
    result = _strip_ai_artifacts(text)
    assert "<think>" not in result
    assert "</think>" not in result
    assert "# Title" in result
    assert "More content." in result


def test_strip_ai_artifacts_removes_orphan_think_tags() -> None:
    from docsfy.generator import _strip_ai_artifacts

    text = "# Title\n\nContent.\n</think>\nMore."
    result = _strip_ai_artifacts(text)
    assert "</think>" not in result
    assert "# Title" in result


def test_strip_ai_artifacts_removes_tail_commentary() -> None:
    from docsfy.generator import _strip_ai_artifacts

    text = (
        "# Title\n\n" + "Content line.\n" * 50 + "\nWait - the user said something else"
    )
    result = _strip_ai_artifacts(text)
    assert "Wait -" not in result
    assert "# Title" in result
    assert "Content line." in result


def test_strip_ai_artifacts_preserves_legitimate_content() -> None:
    from docsfy.generator import _strip_ai_artifacts

    # "I should" appears in legitimate prose early in the document.
    # Text must exceed 500 chars so "I should" falls outside the tail window.
    text = (
        "# Guide\n\nI should mention that Docker is required.\n\n"
        "## Next Steps\n\n" + "More content here.\n" * 30
    )
    result = _strip_ai_artifacts(text)
    assert "I should mention that Docker is required." in result
    assert "## Next Steps" in result
    assert "More content here." in result


def test_strip_ai_artifacts_empty_and_short_text() -> None:
    from docsfy.generator import _strip_ai_artifacts

    assert _strip_ai_artifacts("") == ""
    assert _strip_ai_artifacts("# Title") == "# Title"
    assert _strip_ai_artifacts("Short content.") == "Short content."


def test_strip_ai_artifacts_marker_at_tail_boundary() -> None:
    """Regression test: marker at idx==0 of the tail window must still be stripped."""
    from docsfy.generator import _strip_ai_artifacts

    # Create text exactly 500 chars + a marker right at the tail boundary
    padding = "x" * 500
    text = padding + "\nWait - this is AI commentary"
    result = _strip_ai_artifacts(text)
    assert "Wait -" not in result
    assert result == padding


# --- Issue #121: page quality gate against CoT/exploration chatter ---


def test_strip_ai_preamble_recovers_h1_beyond_ten_lines() -> None:
    """Preamble longer than 10 lines must still be stripped if an H1 follows."""
    from docsfy.generator import _strip_ai_preamble

    preamble = "\n".join(
        f"Exploration line {i} about the repository structure." for i in range(20)
    )
    text = preamble + "\n\n# Real Title\n\nActual documentation content here."
    result = _strip_ai_preamble(text)
    assert result.startswith("# Real Title")
    assert "Exploration line" not in result


def test_strip_ai_preamble_returns_unchanged_when_no_h1_found() -> None:
    """Pure CoT chatter with no H1 anywhere must be left for the quality gate to reject."""
    from docsfy.generator import _strip_ai_preamble

    text = "Let me start by exploring the repository structure in detail."
    assert _strip_ai_preamble(text) == text


def test_strip_ai_preamble_does_not_treat_h2_as_title() -> None:
    """An H2 heading must not be mistaken for the real H1 page title."""
    from docsfy.generator import _strip_ai_preamble

    text = "Let me start by exploring things.\n\n## Not a real title\n\nMore chatter."
    assert _strip_ai_preamble(text) == text


def test_page_content_passes_quality_gate_accepts_valid_page() -> None:
    """A real page with a proper H1 and substantive body must pass, even if it
    legitimately mentions 'knowledge graph' mid-document."""
    from docsfy.generator import page_content_passes_quality_gate

    content = (
        "# Configuration Guide\n\n"
        "This guide explains all configuration options available in the "
        "application, how to set them via environment variables or the "
        "config file, and what each option controls in practice for both "
        "development and production deployments of the service.\n\n"
        "## Available Options\n\n"
        "Set FOO=bar to enable the feature flag, and set BAZ=qux to change "
        "the default timeout used when contacting the upstream service "
        "during normal operation of the application.\n\n"
        "## How Cross-Linking Works\n\n"
        "Internally, docsfy builds a knowledge graph of the repository to "
        "help generate accurate cross-page references once pages exist."
    )
    ok, reason = page_content_passes_quality_gate(
        content, expected_title="Configuration Guide"
    )
    assert ok is True
    assert reason == "ok"


def test_page_content_passes_quality_gate_rejects_empty_content() -> None:
    from docsfy.generator import page_content_passes_quality_gate

    ok, reason = page_content_passes_quality_gate("   \n\n  ")
    assert ok is False
    assert "empty" in reason


def test_page_content_passes_quality_gate_rejects_cot_only_no_h1() -> None:
    """Fixture 1: a CoT paragraph with no H1 at all must be rejected."""
    from docsfy.generator import page_content_passes_quality_gate

    content = (
        "Let me start by reading the knowledge graph report to understand "
        "the repository structure before I write any documentation for "
        "this page. I'll also check the pages manifest for related pages."
    )
    ok, reason = page_content_passes_quality_gate(content)
    assert ok is False
    assert "H1" in reason


def test_page_content_passes_quality_gate_rejects_cot_with_only_related_pages() -> None:
    """Fixture 2: CoT chatter dressed up with a Related Pages section must fail."""
    from docsfy.generator import page_content_passes_quality_gate

    content = (
        "Let me start by exploring the codebase and reading the pages "
        "manifest to figure out what this page should say before writing "
        "anything real.\n\n"
        "## Related Pages\n\n- [Introduction](introduction.html)"
    )
    ok, _reason = page_content_passes_quality_gate(content)
    assert ok is False


def test_page_content_passes_quality_gate_rejects_leading_agent_speak_with_h1() -> None:
    """Fixture 5: agent-speak dominating the opening must fail even with an H1 present."""
    from docsfy.generator import page_content_passes_quality_gate

    content = (
        "# Deployment Guide\n\n"
        "Now let me explore the deployment scripts to understand how this "
        "project is deployed before writing the real content for this page."
    )
    ok, reason = page_content_passes_quality_gate(content)
    assert ok is False
    assert "agent-narration" in reason


def test_page_content_passes_quality_gate_recovers_after_strip_when_h1_exists_later() -> (
    None
):
    """Fixture 4: CoT preamble followed by a real H1 later must pass once stripped."""
    from docsfy.generator import _strip_ai_preamble, page_content_passes_quality_gate

    raw = (
        "Let me start by reading the knowledge graph and pages manifest to "
        "plan out this page before writing it.\n\n"
        "# Deployment Guide\n\n"
        "This guide walks through deploying the application to production "
        "using Docker Compose, including environment variable setup."
    )
    stripped = _strip_ai_preamble(raw)
    ok, reason = page_content_passes_quality_gate(stripped)
    assert ok is True, reason
    assert stripped.startswith("# Deployment Guide")


def test_strip_ai_preamble_recovers_h1_beyond_scan_window_via_narration_strip() -> None:
    """Review fix #4: a single long narration block (one paragraph, many lines,
    no blank-line breaks) that pushes the real H1 beyond _PREAMBLE_SCAN_LINES
    must still be recovered by stripping the leading narration paragraph as a
    whole before retrying the H1 scan."""
    from docsfy.generator import _strip_ai_preamble

    # One giant paragraph (no "\n\n" inside it) so it counts as line-count 60+,
    # well beyond _PREAMBLE_SCAN_LINES (50), but is a single narration
    # "paragraph" that _strip_leading_agent_narration_paragraphs can remove
    # as one unit.
    narration_lines = "\n".join(
        f"Let me start by reading file {i} in the repository." for i in range(60)
    )
    text = narration_lines + "\n\n# Real Title\n\nActual documentation content here."
    result = _strip_ai_preamble(text)
    assert result.startswith("# Real Title")
    assert "Let me start" not in result


def test_page_content_passes_quality_gate_rejects_narration_leaking_beyond_opening() -> (
    None
):
    """Review fix #2: agent-narration that leaks in beyond the first 400 chars
    (not just the opening) must still be rejected, as long as it opens a line."""
    from docsfy.generator import page_content_passes_quality_gate

    filler = "This is real-sounding filler prose that pads out the body. " * 8
    content = (
        "# Deployment Guide\n\n"
        + filler
        + "\n\nNow let me also cover the rollback procedure in more detail."
    )
    assert len(content) > 400  # confirm the narration line is beyond the old window
    ok, reason = page_content_passes_quality_gate(content)
    assert ok is False
    assert "agent-narration" in reason


def test_page_content_passes_quality_gate_accepts_generic_phrase_mid_sentence() -> None:
    """Review fix #9: generic phrasing like 'let me check' must NOT cause a
    false-reject when it appears mid-sentence (not opening a line/paragraph)
    deep in otherwise-legitimate documentation."""
    from docsfy.generator import page_content_passes_quality_gate

    content = (
        "# Troubleshooting Guide\n\n"
        "If the deployment fails, the first thing you should do is open the "
        "logs viewer: let me check the error output there before restarting "
        "any services, since most issues are visible immediately in the "
        "stack trace shown on that page."
    )
    ok, reason = page_content_passes_quality_gate(content)
    assert ok is True, reason


def test_page_content_passes_quality_gate_rejects_related_pages_at_body_start() -> None:
    """Review fix: when the H1's body consists ONLY of a "## Related Pages"
    section (i.e. the heading sits at the very start of the stripped body,
    with no leading blank line to anchor a "\\n## Related Pages" match), the
    Related Pages section must still be excluded from the substantive-body
    length check so the page is correctly rejected as too short."""
    from docsfy.generator import page_content_passes_quality_gate

    content = "# Title\n\n## Related Pages\n- [a](b.html)"
    ok, reason = page_content_passes_quality_gate(content)
    assert ok is False
    assert "short" in reason


def test_page_content_passes_quality_gate_rejects_long_related_pages_only_body() -> (
    None
):
    """Same bug as above, but padded past _MIN_SUBSTANTIVE_BODY_CHARS so the
    old "\\n## Related Pages" split (which never matched a heading sitting at
    the very start of the body) would have incorrectly let this pass as
    substantive content instead of counting it as link-only filler."""
    from docsfy.generator import page_content_passes_quality_gate

    content = (
        "# Title\n\n"
        "## Related Pages\n"
        "- [Introduction Guide](introduction.html)\n"
        "- [Configuration Guide](configuration.html)\n"
        "- [Deployment Guide](deployment.html)"
    )
    ok, reason = page_content_passes_quality_gate(content)
    assert ok is False
    assert "short" in reason


def test_page_content_passes_quality_gate_rejects_too_short_body() -> None:
    from docsfy.generator import page_content_passes_quality_gate

    ok, reason = page_content_passes_quality_gate("# Title\n\nToo short.")
    assert ok is False
    assert "short" in reason


def test_page_content_passes_quality_gate_rejects_known_failure_stub() -> None:
    from docsfy.generator import page_content_passes_quality_gate

    ok, reason = page_content_passes_quality_gate(
        "# Introduction\n\n*Documentation generation failed. Please re-run.*"
    )
    assert ok is False
    assert "stub" in reason


def test_is_generation_failure_stub_matches_both_known_formats() -> None:
    from docsfy.generator import is_generation_failure_stub

    assert is_generation_failure_stub(
        "# Introduction\n\n*Documentation generation failed. Please re-run.*"
    )
    assert is_generation_failure_stub(
        "# Introduction\n\n*Documentation generation failed.*"
    )
    assert not is_generation_failure_stub(
        "# Introduction\n\nThis is real substantive documentation content "
        "that is long enough to be a real page."
    )


def test_is_generation_failure_stub_rejects_multi_paragraph_doc_ending_with_stub_phrase() -> (
    None
):
    """Review fix #1 regression test: a real multi-paragraph document that
    happens to *end* with the exact failure-stub phrase (e.g. quoting it as
    an example, or documenting the failure-stub feature itself) must NOT be
    misclassified as a stub. Before the DOTALL removal, "." matched
    newlines, so the greedy title group could swallow the whole body."""
    from docsfy.generator import is_generation_failure_stub

    content = (
        "# Failure Handling\n\n"
        "This page documents how docsfy handles generation failures for "
        "individual pages when the AI backend cannot produce usable "
        "content after retrying.\n\n"
        "## What You'll See\n\n"
        "When a page fails to generate even after a retry, docsfy replaces "
        "its content with a clearly-labeled placeholder so the failure is "
        "obvious to both readers and AI consumers of the site, instead of "
        "silently publishing broken or empty output.\n\n"
        "*Documentation generation failed. Please re-run.*"
    )
    assert not is_generation_failure_stub(content)


def test_is_generation_failure_stub_still_matches_exact_stub_with_multiline_title_guard() -> (
    None
):
    """The title portion of a real stub must stay on a single line; a
    "title" spanning multiple lines is not a valid stub and must not match."""
    from docsfy.generator import is_generation_failure_stub

    assert not is_generation_failure_stub(
        "# Introduction\nSubtitle line\n\n"
        "*Documentation generation failed. Please re-run.*"
    )


async def test_generate_full_page_content_retries_once_then_accepts_good_output(
    tmp_path: Path,
) -> None:
    """First AI response is CoT chatter, second is a real page: the good one wins."""
    from docsfy.generator import generate_full_page_content

    cot_response = (
        "Let me start by reading the knowledge graph report before writing "
        "anything for this page."
    )
    good_response = (
        "# Introduction\n\nThis page introduces the project, explains what "
        "it does, and walks through the basic setup steps for new users."
    )
    with patch(
        "docsfy.generator.call_ai_once",
        side_effect=[
            AIResult(success=True, text=cot_response),
            AIResult(success=True, text=good_response),
        ],
    ) as mock_call:
        content = await generate_full_page_content(
            repo_path=tmp_path,
            project_name="test-repo",
            page_title="Introduction",
            page_description="Overview",
            ai_provider="claude",
            ai_model="opus",
        )

    assert content == good_response
    assert mock_call.call_count == 2


async def test_generate_full_page_content_returns_failure_stub_when_both_attempts_fail_gate(
    tmp_path: Path,
) -> None:
    """When both attempts return CoT chatter, a loud failure stub is returned, not chatter."""
    from docsfy.generator import generate_full_page_content

    cot_response = (
        "Let me start by reading the knowledge graph report before writing "
        "anything for this page."
    )
    with patch(
        "docsfy.generator.call_ai_once",
        return_value=AIResult(success=True, text=cot_response),
    ) as mock_call:
        content = await generate_full_page_content(
            repo_path=tmp_path,
            project_name="test-repo",
            page_title="Introduction",
            page_description="Overview",
            ai_provider="claude",
            ai_model="opus",
        )

    assert (
        content == "# Introduction\n\n*Documentation generation failed. Please re-run.*"
    )
    assert mock_call.call_count == 2


async def test_generate_page_caches_good_content_after_gate_retry(
    tmp_path: Path,
) -> None:
    """generate_page must only cache content once it passes the quality gate."""
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cot_response = (
        "Let me start by exploring the pages manifest before I write this page."
    )
    good_response = (
        "# Introduction\n\nThis page introduces the project, explains what "
        "it does, and walks through the basic setup steps for new users."
    )
    with patch(
        "docsfy.generator.call_ai_once",
        side_effect=[
            AIResult(success=True, text=cot_response),
            AIResult(success=True, text=good_response),
        ],
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

    assert md == good_response
    assert (cache_dir / "introduction.md").read_text() == good_response


async def test_generate_page_falls_back_to_full_generation_when_incremental_output_fails_quality_gate(
    tmp_path: Path,
) -> None:
    """An incremental update that degenerates into CoT chatter must fall back to full generation."""
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    existing_content = (
        "# Introduction\n\nWelcome! This page gives a complete overview of "
        "the project and how it works end to end.\n"
    )
    incremental_response = json.dumps(
        {
            "updates": [
                {
                    "old_text": (
                        "Welcome! This page gives a complete overview of "
                        "the project and how it works end to end.\n"
                    ),
                    "new_text": (
                        "Let me start by exploring the diff before writing "
                        "the real update for this page.\n"
                    ),
                }
            ]
        }
    )
    full_page_response = (
        "# Introduction\n\nRegenerated content that fully describes the "
        "introduction page in much more depth and detail for readers.\n"
    )
    with patch(
        "docsfy.generator.call_ai_once",
        side_effect=[
            AIResult(success=True, text=incremental_response),
            AIResult(success=True, text=full_page_response),
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


async def test_generate_page_incremental_strips_ai_preamble_before_gate(
    tmp_path: Path,
) -> None:
    """Review fix: the incremental path must strip AI preamble (not just
    artifacts) before running the quality gate, same as the full-generation
    path. Here the incremental update replaces the leading H1 with narration
    followed by a real H1 further down; without preamble stripping the
    merged content wouldn't start with an H1 and would incorrectly fall back
    to full generation."""
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    existing_content = (
        "# Introduction\n\nWelcome! This page gives a complete overview of "
        "the project and how it works end to end.\n"
    )
    incremental_response = json.dumps(
        {
            "updates": [
                {
                    "old_text": "# Introduction\n\n",
                    "new_text": (
                        "Let me start by exploring the diff before writing "
                        "the real update for this page.\n\n"
                        "# Introduction\n\n"
                    ),
                }
            ]
        }
    )
    with patch(
        "docsfy.generator.call_ai_once",
        side_effect=[AIResult(success=True, text=incremental_response)],
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

    assert md.startswith("# Introduction")
    assert "Let me start" not in md
    assert mock_call.call_count == 1
