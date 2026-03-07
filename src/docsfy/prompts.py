from __future__ import annotations

import json
from typing import Any

PLAN_SCHEMA = """{
  "project_name": "string - project name",
  "tagline": "string - one-line project description",
  "navigation": [
    {
      "group": "string - section group name",
      "pages": [
        {
          "slug": "string - URL-friendly page identifier",
          "title": "string - human-readable page title",
          "description": "string - brief description of what this page covers"
        }
      ]
    }
  ]
}"""


def build_planner_prompt(project_name: str) -> str:
    return f"""You are a technical documentation planner. Explore this repository thoroughly.
Explore the source code, configuration files, tests, CI/CD pipelines, and project structure.
Do NOT rely on the README — understand the project from its code and configuration.

Then create a documentation plan as a JSON object. The plan should cover:
- Introduction and overview
- Installation / getting started
- Configuration (if applicable)
- Usage guides for key features
- API reference (if the project has an API)
- Any other sections that would help users understand and use this project

Project name: {project_name}

CRITICAL: Your response must be ONLY a valid JSON object. No text before or after. No markdown code blocks.

Output format:
{PLAN_SCHEMA}"""


def build_incremental_planner_prompt(
    project_name: str, changed_files: list[str], existing_plan: dict[str, Any]
) -> str:
    return f"""You are a technical documentation planner. The repository "{project_name}" has been updated.

Changed files:
{chr(10).join(f"- {f}" for f in changed_files)}

Existing documentation plan:
{json.dumps(existing_plan, indent=2)}

Which pages from the existing plan need to be regenerated based on the changed files?
Output a JSON array of page slugs that need regeneration.

CRITICAL: Output ONLY a JSON array of strings. No explanation.
Example: ["introduction", "api-reference", "configuration"]
If all pages need regeneration, output: ["all"]
If no pages need regeneration, output: []
"""


_PAGE_WRITING_RULES = """Write in markdown format. Include:
- Clear explanations
- Code examples from the actual codebase (not made up)
- Configuration snippets where relevant

Use these callout formats for special content:
- Notes: > **Note:** text
- Warnings: > **Warning:** text
- Tips: > **Tip:** text"""


def build_page_prompt(project_name: str, page_title: str, page_description: str) -> str:
    return f"""You are a technical documentation writer. Explore this repository to write
the "{page_title}" page for the {project_name} documentation.

Page description: {page_description}

Explore the codebase as needed. Read source files, configs, tests, and CI/CD pipelines
to write comprehensive, accurate documentation. Do NOT rely on the README.

{_PAGE_WRITING_RULES}

Output ONLY the markdown content for this page. No wrapping, no explanation."""


def build_incremental_page_prompt(
    project_name: str,
    page_title: str,
    page_description: str,
    existing_content: str,
    changed_files: list[str],
    diff_content: str,
) -> str:
    _MAX_DIFF_CHARS = 30000
    if len(diff_content) > _MAX_DIFF_CHARS:
        truncated_diff = (
            diff_content[:_MAX_DIFF_CHARS]
            + "\n\n... (diff truncated due to size. Focus on the hunks shown and the changed file list above.) ..."
        )
    else:
        truncated_diff = diff_content

    return f"""You are a technical documentation writer. The repository "{project_name}" has been updated.
Your task is to UPDATE the existing "{page_title}" documentation page — NOT rewrite it from scratch.

Page description: {page_description}

Changed files in the repository:
{chr(10).join(f"- {f}" for f in changed_files)}

Changes made to the repository:
---
{truncated_diff}
---

Existing page content:
---
{existing_content}
---

Focus ONLY on changes in the diff that are relevant to the "{page_title}" page topic.
Ignore all other changes — they will be handled by other page updates.

{_PAGE_WRITING_RULES}

Instructions:
- If none of the changes are relevant to this page, output the existing content exactly as-is with zero modifications
- ONLY modify sections directly affected by the changes shown above
- Unchanged sections MUST be preserved byte-for-byte — do NOT rephrase, reformat, or rewrite text that is not affected by the diff
- Ignore diff hunks and changed files that are unrelated to this specific page's topic
- If a code example references changed code, update ONLY that code example
- If a new feature was added that belongs on this page, add a minimal new section for it
- Do NOT remove, reorganize, or reword sections that are still accurate
- Do NOT add explanatory text, improve wording, or "enhance" sections not touched by the diff
- The output must be the complete page with unchanged sections copied exactly as-is and only affected sections modified

Output the complete updated page content in markdown format. No wrapping, no explanation."""
