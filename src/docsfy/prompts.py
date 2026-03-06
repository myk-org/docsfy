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


def build_page_prompt(project_name: str, page_title: str, page_description: str) -> str:
    return f"""You are a technical documentation writer. Explore this repository to write
the "{page_title}" page for the {project_name} documentation.

Page description: {page_description}

Explore the codebase as needed. Read source files, configs, tests, and CI/CD pipelines
to write comprehensive, accurate documentation. Do NOT rely on the README.

Write in markdown format. Include:
- Clear explanations
- Code examples from the actual codebase (not made up)
- Configuration snippets where relevant

Use these callout formats for special content:
- Notes: > **Note:** text
- Warnings: > **Warning:** text
- Tips: > **Tip:** text

Output ONLY the markdown content for this page. No wrapping, no explanation."""
