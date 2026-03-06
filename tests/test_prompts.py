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
