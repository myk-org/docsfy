from __future__ import annotations


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
    prompt = build_incremental_planner_prompt("my-repo", changed_files, existing_plan)
    assert "my-repo" in prompt
    assert "src/main.py" in prompt
    assert "src/config.py" in prompt
    assert "introduction" in prompt
    assert "configuration" in prompt
    assert "JSON array" in prompt


def test_build_incremental_page_prompt() -> None:
    from docsfy.prompts import build_incremental_page_prompt

    existing_content = "# Introduction\n\nThis is the intro page."
    changed_files = ["src/main.py", "src/config.py"]
    diff_content = "diff --git a/src/main.py\n+added line"

    prompt = build_incremental_page_prompt(
        project_name="my-repo",
        page_title="Introduction",
        page_description="Overview of the project",
        existing_content=existing_content,
        changed_files=changed_files,
        diff_content=diff_content,
    )
    assert "my-repo" in prompt
    assert "Introduction" in prompt
    assert "UPDATE" in prompt or "update" in prompt.lower()
    assert "src/main.py" in prompt
    assert existing_content in prompt
    assert diff_content in prompt

    # Verify critical guardrail language is present
    assert "byte-for-byte" in prompt.lower() or "exactly as-is" in prompt.lower()
    assert "ignore" in prompt.lower()  # ignore unrelated changes
    assert "do not" in prompt.lower() or "do NOT" in prompt  # prohibition language


def test_build_incremental_page_prompt_truncates_large_diff() -> None:
    from docsfy.prompts import build_incremental_page_prompt

    large_diff = "x" * 40000  # exceeds _MAX_DIFF_CHARS (30000)
    prompt = build_incremental_page_prompt(
        project_name="my-repo",
        page_title="API",
        page_description="API docs",
        existing_content="# API\n\nAPI page.",
        changed_files=["src/api.py"],
        diff_content=large_diff,
    )
    assert "truncated" in prompt.lower()
    assert len(prompt) < len(large_diff)  # prompt must be shorter than raw diff
