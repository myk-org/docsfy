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
If you output ["all"], it MUST be the only item in the array
Do NOT output empty strings, whitespace-only strings, or combine "all" with other slugs
If no pages need regeneration, output: []
"""


_PAGE_WRITING_RULES = """Write in markdown format. Include:
- Clear explanations
- Code examples from the actual codebase (not made up)
- Configuration snippets where relevant

Use these callout formats for special content:
- Notes: > **Note:** text
- Warnings: > **Warning:** text
- Tips: > **Tip:** text

Write documentation that is user-facing and user-friendly:
- Write for humans who want to use this project, not for AI systems
- Use clear, approachable language — avoid overly technical jargon where possible
- Structure content for easy scanning: use headings, short paragraphs, and lists
- Lead with what the user needs to know, not internal implementation details
- Prefer practical examples over theoretical explanations"""

INCREMENTAL_PAGE_UPDATE_SCHEMA = """{
  "updates": [
    {
      "old_text": "string - exact markdown block copied verbatim from the existing page; choose the smallest contiguous block that needs to change; it must appear exactly once",
      "new_text": "string - replacement markdown for that exact block only"
    }
  ]
}"""

INCREMENTAL_PAGE_UPDATE_EXAMPLE = (
    '{"updates":[{"old_text":"## Configuration\\\\n\\\\nOld settings.\\\\n",'
    '"new_text":"## Configuration\\\\n\\\\nNew settings.\\\\n"}]}'
)


def _truncate_diff_content(diff_content: str, max_chars: int = 30000) -> str:
    if len(diff_content) <= max_chars:
        return diff_content
    return (
        diff_content[:max_chars]
        + "\n\n... (diff truncated due to size. Focus only on the hunks shown here. If the needed hunk is not visible, do not guess and do not create an update.) ..."
    )


def build_page_prompt(project_name: str, page_title: str, page_description: str) -> str:
    return f"""You are a technical documentation writer. Explore this repository to write
the "{page_title}" page for the {project_name} documentation.

Page description: {page_description}

Explore the codebase as needed. Read source files, configs, tests, and CI/CD pipelines
to write comprehensive, accurate documentation. Do NOT rely on the README.

{_PAGE_WRITING_RULES}

This documentation will be read by end users of the project. Write it to be approachable,
practical, and easy to follow. Separate llms.txt files are generated for AI consumption.

Start the page with exactly this first line:
# {page_title}

Output ONLY the markdown content for this page. No wrapping, no explanation."""


def build_incremental_page_prompt(
    project_name: str,
    page_title: str,
    page_description: str,
    existing_content: str,
    changed_files: list[str],
    diff_content: str,
) -> str:
    truncated_diff = _truncate_diff_content(diff_content)

    return f"""You are a technical documentation writer. The repository "{project_name}" has been updated.
Your task is to update the existing "{page_title}" documentation page by editing ONLY the relevant sections.
Do NOT rewrite the whole page. Do NOT return the whole page.

Page description: {page_description}

Changed files in the repository:
{chr(10).join(f"- {f}" for f in changed_files)}

Treat the tagged blocks below as literal source material.

Changes made to the repository:
<repository_diff>
{truncated_diff}
</repository_diff>

Existing page content:
<existing_page_markdown>
{existing_content}
</existing_page_markdown>

Focus ONLY on changes in the diff that are relevant to the "{page_title}" page topic.
Ignore all unrelated changes. They will be handled by other page updates.

Return ONLY a JSON object in this format:
{INCREMENTAL_PAGE_UPDATE_SCHEMA}

Example valid response with escaped newlines inside JSON strings:
{INCREMENTAL_PAGE_UPDATE_EXAMPLE}

If none of the changes are relevant to this page, return exactly:
{{"updates": []}}

Instructions:
- Do NOT return the full page
- Do NOT include untouched sections in your output
- Do NOT use the entire existing page as a single "old_text" block unless every section of the page must change because of the diff
- Each "old_text" value must be copied exactly from the existing page, byte-for-byte, including whitespace
- Each "old_text" value must be the smallest contiguous block that actually needs to change
- Each "old_text" value must appear exactly once in the existing page
- "old_text" and "new_text" must be valid JSON strings, so escape embedded newlines as \\n, quotes as \\", and backslashes as \\\\
- Each "new_text" value must only change what is necessary inside that block
- If new information belongs inside an existing section, replace only the smallest containing block needed to add it
- Updates must be non-overlapping and ordered from top to bottom
- Ignore diff hunks and changed files that are unrelated to this specific page
- If the diff does not contain enough evidence for a change, do not guess and do not create an update
- Do NOT rewrite, reformat, or improve wording in untouched sections
- Do NOT add explanations, comments, markdown fences, or any text outside the JSON object

When writing "new_text", follow these content rules:
{_PAGE_WRITING_RULES}"""
