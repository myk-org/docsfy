from __future__ import annotations

import json
from typing import Any

from simple_logger.logger import get_logger

from docsfy.models import PAGE_TYPES

logger = get_logger(name=__name__)

_PAGE_TYPE_VALUES = ", ".join(PAGE_TYPES)

PLAN_SCHEMA = (
    """{
  "project_name": "string - project name",
  "tagline": "string - one-line project description (what it does for the user, not what it is)",
  "navigation": [
    {
      "group": "string - section group name",
      "pages": [
        {
          "slug": "string - URL-friendly page identifier",
          "title": "string - human-readable page title",
          "description": "string - brief description of what this page covers",
          "type": "string - one of: """
    + _PAGE_TYPE_VALUES
    + """"
        }
      ]
    }
  ]
}"""
)


def build_planner_prompt(project_name: str) -> str:
    return f"""You are a documentation planner focused on the USER EXPERIENCE. Explore this repository thoroughly.
Read source code, configuration files, tests, CI/CD pipelines, and project structure.
Do NOT rely on the README — understand the project from its code and configuration.

Then create a documentation plan as a JSON object. The plan must be structured as a USER JOURNEY,
not an architecture tour. Think: "What does a new user need to do first? Then what?"

NAVIGATION STRUCTURE (use these groups in order, skip any that don't apply):

1. "Getting Started" — Installation, prerequisites, quickstart. Get the user productive in 60 seconds.
   Page types: guide

2. "User Guides" — Task-oriented pages. Each page answers ONE question: "How do I do X?"
   Lead with the most common tasks. Titles should use action verbs (e.g., "Generating Documentation",
   "Managing Users", "Configuring Providers").
   Page types: guide

3. "Recipes" — ONLY if the project has enough common patterns/workflows to warrant it.
   Short, copy-paste-friendly patterns grouped on one or two pages.
   Page types: recipe

4. "Reference" — API endpoints, CLI commands, configuration options, environment variables.
   Structured for lookup, not for reading start-to-finish.
   Page types: reference

5. "Internals" — Architecture, data model, internal design. ONLY if the project is a framework/library
   where users genuinely need to understand internals to use it effectively. Skip for most tools/apps.
   Page types: concept

CRITICAL RULES:
- Do NOT create an "Introduction" or "Overview" page — fold that into the Getting Started quickstart page
- Do NOT put API details, internal code, or architecture in User Guides — that belongs in Reference or Internals
- Do NOT create pages that only describe what something IS — every page should help users DO something
- Aim for 8 to 15 pages for most projects, but adjust based on project complexity
- The tagline should describe what the project does FOR THE USER, not what it is technically
  Good: "Turn any Git repo into a polished documentation site in minutes"
  Bad: "AI-powered documentation generator using FastAPI and React"
- Each page description should state what the user will learn or accomplish, not what the page contains

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


_CALLOUT_FORMATS = """
Use these callout formats:
- Notes: > **Note:** text
- Warnings: > **Warning:** text
- Tips: > **Tip:** text"""

_GUIDE_WRITING_RULES = (
    """Write a task-oriented guide in markdown format. Follow these rules strictly:

STRUCTURE (in this order):
1. Opening: Start with 1-2 sentences about WHAT THE USER WANTS TO ACCOMPLISH and WHY.
   Do NOT start with a definition or description of what something is.
2. Prerequisites: If any, list them briefly in a bullet list.
3. Quick example: Show the simplest working example FIRST, before any explanation.
4. Step-by-step: Walk through the common use case with clear steps.
5. Advanced usage: AFTER the basics, cover advanced options, edge cases, or alternatives.
6. Troubleshooting: Common problems and solutions (only if relevant, keep brief).

CONTENT RULES:
- Lead with examples. Show the command/code BEFORE explaining what it does.
- Use code examples from the actual codebase (not made up).
- Use comparison tables when showing "before/after" or "old way vs new way."
- Progressive disclosure: simple first, advanced later. The user should be productive after reading just the first half.
- Do NOT include internal implementation details, architecture, or source code structure.
- Do NOT show raw API request/response payloads unless this page is specifically about the API.
- Do NOT duplicate content that belongs on other pages — link to them instead with: "See [Page Title](page-slug.html)"
- Write for humans who want to GET THINGS DONE, not understand internals.
- Use short paragraphs (2-3 sentences max).
- Prefer bullet lists and numbered steps over long prose.
- Where architecture, data flow, or component relationships would benefit from a visual, include a Mermaid diagram using a ```mermaid code block. Use flowchart, sequence, or class diagrams as appropriate."""
    + _CALLOUT_FORMATS
)

_REFERENCE_WRITING_RULES = (
    """Write a structured reference page in markdown format. Follow these rules strictly:

STRUCTURE:
- Organize by resource, endpoint, command, or configuration key.
- For each item: name, description, parameters/options, example, return value/effect.
- Use tables for parameters and options.
- Put code examples after each item, not in a separate section.

CONTENT RULES:
- Be precise and scannable — users come here to LOOK UP specific information, not to read.
- Every parameter/option must have: name, type, default value (if any), description.
- Include at least one concrete example per endpoint/command/option.
- Do NOT include narrative explanations or tutorials — that belongs in User Guides.
- Do NOT explain WHY something works the way it does — just document WHAT it does.
- Use code blocks generously.
- Group related items under clear headings."""
    + _CALLOUT_FORMATS
)

_RECIPE_WRITING_RULES = (
    """Write a collection of practical recipes in markdown format. Follow these rules strictly:

STRUCTURE for each recipe:
1. Recipe title (## heading)
2. One sentence: what this recipe solves
3. Code block: the complete, copy-paste-ready solution
4. Brief explanation (2-4 sentences max): what the code does and when to use it
5. Optional: variations or tips as bullet points

CONTENT RULES:
- Each recipe must be SELF-CONTAINED and copy-paste ready.
- Keep recipes SHORT — if it takes more than a screen, it's a guide, not a recipe.
- Order recipes from most common to least common.
- Do NOT include long explanations — link to the relevant guide page instead.
- Practical over theoretical. If it can't be copy-pasted, it's not a recipe.
- Include real values and realistic examples, not abstract placeholders."""
    + _CALLOUT_FORMATS
)

_CONCEPT_WRITING_RULES = (
    """Write an explanatory page in markdown format. Follow these rules strictly:

STRUCTURE:
1. Opening: What is this concept and WHY should the user care?
2. The big picture: Use a diagram (Mermaid) if it helps understanding.
3. Key concepts: Explain each concept clearly with examples.
4. How it affects the user: Connect internals back to user-visible behavior.
5. Related pages: Point to guides and reference pages where users can take action.

CONTENT RULES:
- Always connect technical concepts back to user-visible effects.
- Use diagrams (Mermaid) for architecture, data flow, or relationships.
- Do NOT go deeper than the user needs — this is not a code walkthrough.
- Where architecture, data flow, or component relationships would benefit from a visual, include a Mermaid diagram using a ```mermaid code block.
- Use clear, approachable language — avoid jargon where possible."""
    + _CALLOUT_FORMATS
)


def _get_writing_rules(page_type: str) -> str:
    """Return writing rules based on page type."""
    rules_map = {
        "guide": _GUIDE_WRITING_RULES,
        "reference": _REFERENCE_WRITING_RULES,
        "recipe": _RECIPE_WRITING_RULES,
        "concept": _CONCEPT_WRITING_RULES,
    }
    if page_type not in rules_map:
        logger.warning(f"Unknown page type '{page_type}', falling back to 'guide'")
        page_type = "guide"
    return rules_map[page_type]


_INCREMENTAL_WRITING_RULES = {
    "guide": "Match the page's existing tone. For new_text: lead with examples, use short paragraphs, prefer bullet lists and numbered steps, avoid internal implementation details.",
    "reference": "Match the page's existing tone. For new_text: be precise and scannable, use tables for parameters, include code examples, avoid narrative explanations.",
    "recipe": "Match the page's existing tone. For new_text: keep recipes self-contained and copy-paste ready, short explanations only.",
    "concept": "Match the page's existing tone. For new_text: connect concepts to user-visible effects, use diagrams where helpful, avoid deep code walkthroughs.",
}


def _get_incremental_writing_rules(page_type: str) -> str:
    """Return condensed writing rules for incremental page updates."""
    if page_type not in _INCREMENTAL_WRITING_RULES:
        page_type = "guide"
    return _INCREMENTAL_WRITING_RULES[page_type]


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


_MAX_DIFF_LENGTH = 30000


def _truncate_diff_content(diff_content: str, max_chars: int = _MAX_DIFF_LENGTH) -> str:
    if len(diff_content) <= max_chars:
        return diff_content
    return (
        diff_content[:max_chars]
        + "\n\n... (diff truncated due to size. Focus only on the hunks shown here. If the needed hunk is not visible, do not guess and do not create an update.) ..."
    )


def build_page_prompt(
    project_name: str,
    page_title: str,
    page_description: str,
    page_type: str = "guide",
    exclusions_path: str | None = None,
) -> str:
    writing_rules = _get_writing_rules(page_type)
    exclusions_block = ""
    if exclusions_path:
        exclusions_block = f"""

IMPORTANT: Before writing, read the stale-reference deny-list at:
{exclusions_path}

Do not mention any reference listed in that file.
Only document features and files that exist in the current codebase."""

    return f"""You are a technical documentation writer. Explore this repository to write
the "{page_title}" page for the {project_name} documentation.

Page description: {page_description}
Page type: {page_type}

Explore the codebase as needed. Read source files, configs, tests, and CI/CD pipelines
to write accurate documentation based on the actual code. Do NOT rely on the README.

{writing_rules}

ANTI-REDUNDANCY: This page should OWN its topic exclusively. Do NOT duplicate content
that belongs on other pages. Instead, link to them: "See [Page Title](page-slug.html)".

This documentation will be read by end users of the project. Separate llms.txt files
are generated for AI consumption.{exclusions_block}

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
    page_type: str = "guide",
) -> str:
    truncated_diff = _truncate_diff_content(diff_content)

    return f"""You are a technical documentation writer. The repository "{project_name}" has been updated.
Your task is to update the existing "{page_title}" documentation page by editing ONLY the relevant sections.
Do NOT rewrite the whole page. Do NOT return the whole page.

Page description: {page_description}
Page type: {page_type}

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
{_get_incremental_writing_rules(page_type)}
{_CALLOUT_FORMATS}"""


VALIDATION_SCHEMA = """[
  {
    "reference": "string - the stale reference found",
    "reason": "string - why it is considered stale"
  }
]"""


def build_validation_prompt(page_temp_path: str) -> str:
    return f"""You are a documentation quality validator. Read the documentation page at:
{page_temp_path}

Then explore this repository thoroughly. Verify that ALL referenced files, features,
modules, classes, functions, and tools actually exist in the current codebase.

Check for:
- File paths that do not exist
- Function or class names that are not defined
- Features described that have been removed or replaced
- Module names that do not exist
- CLI commands or flags that are not implemented

CRITICAL: Your response must be ONLY a valid JSON array. No text before or after.

If all references are valid, return exactly: []

If stale references are found, return:
{VALIDATION_SCHEMA}"""


def build_cross_links_prompt(manifest_path: str, pages_dir: str) -> str:
    return f"""You are a documentation cross-linking assistant. Read the page manifest at:
{manifest_path}

Then read ALL the page markdown files in:
{pages_dir}

For each page, suggest related pages based on content overlap, topic relevance,
and natural reading flow. Pages that reference similar concepts, APIs, or features
should be linked together.
If the manifest has 3 or more pages, return 2-5 unique related slugs.
If fewer pages exist, return as many unique non-self slugs as are available
(use [] only when no other page exists).

CRITICAL: Your response must be ONLY a valid JSON object. No text before or after.

Output format:
{{
  "page-slug": ["related-slug-1", "related-slug-2"],
  "another-slug": ["related-slug-3", "related-slug-4", "related-slug-5"]
}}

Every slug in the output must come from the manifest. Do not invent page slugs.
Do not include a page's own slug in its related list.
Do not repeat slugs within a related list.
Return an entry for every manifest slug."""
