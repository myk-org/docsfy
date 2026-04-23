from __future__ import annotations

import json
import tempfile
from pathlib import Path


def test_build_planner_prompt() -> None:
    from docsfy.prompts import build_planner_prompt

    prompt = build_planner_prompt("my-repo")
    assert "my-repo" in prompt
    assert "JSON" in prompt
    assert "project_name" in prompt
    assert "navigation" in prompt


def test_build_page_prompt() -> None:
    from docsfy.prompts import build_page_prompt

    prompt = build_page_prompt(
        project_name="my-repo",
        page_title="Installation",
        page_description="How to install the project",
    )
    assert "my-repo" in prompt
    assert "Installation" in prompt
    assert "markdown" in prompt.lower()


def test_build_incremental_planner_prompt() -> None:
    from docsfy.prompts import build_incremental_planner_prompt

    changed_files = ["src/main.py", "src/config.py"]
    existing_plan = {
        "project_name": "my-repo",
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
                        "slug": "configuration",
                        "title": "Configuration",
                        "description": "Config guide",
                    },
                ],
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        plan_path = Path(tmp) / "existing_plan.json"
        plan_path.write_text(json.dumps(existing_plan, indent=2), encoding="utf-8")
        prompt = build_incremental_planner_prompt(
            "my-repo", changed_files, str(plan_path)
        )
    assert "my-repo" in prompt
    assert "src/main.py" in prompt
    assert "src/config.py" in prompt
    assert str(plan_path) in prompt
    assert "JSON array" in prompt
    assert "must be the only item" in prompt.lower()
    assert "do not output empty strings" in prompt.lower()


def test_build_incremental_page_prompt() -> None:
    from docsfy.prompts import build_incremental_page_prompt

    changed_files = ["src/main.py", "src/config.py"]

    with tempfile.TemporaryDirectory() as tmp:
        existing_page_path = Path(tmp) / "existing_page.md"
        existing_page_path.write_text(
            "# Introduction\n\nThis is the intro page.", encoding="utf-8"
        )
        diff_path = Path(tmp) / "diff.patch"
        diff_path.write_text("diff --git a/src/main.py\n+added line", encoding="utf-8")

        prompt = build_incremental_page_prompt(
            project_name="my-repo",
            page_title="Introduction",
            page_description="Overview of the project",
            existing_page_path=str(existing_page_path),
            changed_files=changed_files,
            diff_path=str(diff_path),
        )
    assert "my-repo" in prompt
    assert "Introduction" in prompt
    assert "UPDATE" in prompt or "update" in prompt.lower()
    assert "src/main.py" in prompt
    assert str(existing_page_path) in prompt
    assert str(diff_path) in prompt

    # Verify critical guardrail language is present
    assert "json object" in prompt.lower()
    assert '"updates"' in prompt
    assert '"old_text"' in prompt
    assert '"new_text"' in prompt
    assert '{"updates": []}' in prompt
    assert "do not return the full page" in prompt.lower()
    assert "entire existing page as a single" in prompt.lower()
    assert "smallest contiguous block" in prompt.lower()
    assert "byte-for-byte" in prompt.lower()
    assert "ignore" in prompt.lower()
    assert "escaped newlines" in prompt.lower()
    assert "\\\\n" in prompt
    assert "match the page's existing tone" in prompt.lower()
    assert "page type: guide" in prompt.lower()
    assert "> **note:** text" in prompt.lower()


def test_truncate_diff_content_large_diff() -> None:
    from docsfy.prompts import truncate_diff_content

    large_diff = "x" * 40000  # exceeds _MAX_DIFF_LENGTH (30000)
    result = truncate_diff_content(large_diff)
    assert "truncated" in result.lower()
    assert "do not guess" in result.lower()
    assert len(result) < len(large_diff)


def test_truncate_diff_content_small_diff() -> None:
    from docsfy.prompts import truncate_diff_content

    small_diff = "x" * 100
    result = truncate_diff_content(small_diff)
    assert result == small_diff


def test_page_prompt_excludes_mermaid_instructions() -> None:
    from docsfy.models import PAGE_TYPES
    from docsfy.prompts import build_incremental_page_prompt, build_page_prompt

    for page_type in PAGE_TYPES:
        prompt = build_page_prompt(
            project_name="test-repo",
            page_title="Test",
            page_description="desc",
            page_type=page_type,
        )
        assert "do not use mermaid" in prompt.lower(), (
            f"Mermaid ban missing in {page_type} page prompt"
        )

    for page_type in PAGE_TYPES:
        prompt = build_incremental_page_prompt(
            project_name="test-repo",
            page_title="Test",
            page_description="desc",
            existing_page_path="/tmp/existing.md",
            changed_files=["file.py"],
            diff_path="/tmp/diff.patch",
            page_type=page_type,
        )
        assert "do not use mermaid" in prompt.lower(), (
            f"Mermaid ban missing in {page_type} incremental prompt"
        )


def test_page_prompt_with_exclusions() -> None:
    from docsfy.prompts import build_page_prompt

    prompt = build_page_prompt(
        "test-repo",
        "Overview",
        "Project overview",
        exclusions_path="/tmp/docsfy-validation/abc/intro_exclusions.txt",
    )
    assert "/tmp/docsfy-validation/abc/intro_exclusions.txt" in prompt
    assert "deny-list" in prompt.lower() or "stale" in prompt.lower()


def test_page_prompt_without_exclusions() -> None:
    from docsfy.prompts import build_page_prompt

    prompt = build_page_prompt("test-repo", "Overview", "Project overview")
    assert "deny-list" not in prompt.lower()


def test_validation_prompt() -> None:
    from docsfy.prompts import build_validation_prompt

    prompt = build_validation_prompt("/tmp/docsfy-validation/abc123/intro.md")
    assert "/tmp/docsfy-validation/abc123/intro.md" in prompt
    assert "json" in prompt.lower()
    assert "stale" in prompt.lower() or "exist" in prompt.lower()


def test_cross_links_prompt() -> None:
    from docsfy.prompts import build_cross_links_prompt

    prompt = build_cross_links_prompt(
        "/tmp/docsfy-crosslinks/abc123/manifest.json",
        "/tmp/docsfy-crosslinks/abc123/",
    )
    assert "/tmp/docsfy-crosslinks/abc123/manifest.json" in prompt
    assert "/tmp/docsfy-crosslinks/abc123/" in prompt
    assert "json" in prompt.lower()
    assert "related" in prompt.lower()
