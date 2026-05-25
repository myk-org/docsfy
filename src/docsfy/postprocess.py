from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import tempfile
import uuid
from configparser import ConfigParser
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

from simple_logger.logger import get_logger

from docsfy.ai_client import AIResult, call_ai_once, run_parallel_with_limit
from docsfy.cost_tracker import add_cost
from docsfy.generator import generate_full_page_content
from docsfy.json_parser import parse_json_array_response, parse_json_response
from docsfy.models import PAGE_TYPES
from docsfy.config import get_settings
from docsfy.prompts import (
    build_completeness_prompt,
    build_cross_links_prompt,
    build_validation_prompt,
)

logger = get_logger(name=__name__)


_CALLOUT_RE = re.compile(r"^>\s*\*\*(Note|Warning|Tip):\*\*", re.IGNORECASE)

_DETAILS_OPEN_RE = re.compile(
    r"<details[^>]*>\s*<summary[^>]*>(.*?)</summary>",
    re.IGNORECASE | re.DOTALL,
)
_DETAILS_CLOSE_RE = re.compile(
    r"</details\s*>",
    re.IGNORECASE,
)

# Regex to identify code fences (backtick and tilde) and inline code that should be skipped
_CODE_BLOCK_RE = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]+`)")


def separate_adjacent_callouts(md_text: str) -> str:
    """Separate adjacent blockquote callouts so each renders independently.

    When the AI generates consecutive callouts like:
        > **Warning:** text
        > **Note:** text
    they collapse into a single blockquote. This inserts blank lines
    between them so each callout is styled independently.
    """
    lines = md_text.split("\n")
    result: list[str] = []
    in_fence = False
    opening_fence_len = 0
    opening_fence_char = "`"

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track fenced code blocks (backtick and tilde fence matching)
        if stripped.startswith(("```", "~~~")):
            fence_char = stripped[0]
            fence_count = len(stripped) - len(stripped.lstrip(fence_char))
            rest = stripped[fence_count:].strip()
            if not in_fence:
                in_fence = True
                opening_fence_len = fence_count
                opening_fence_char = fence_char
            elif (
                fence_char == opening_fence_char
                and fence_count >= opening_fence_len
                and not rest
            ):
                in_fence = False
                opening_fence_len = 0

        if not in_fence and i > 0 and _CALLOUT_RE.match(stripped):
            # Check if previous non-empty line was also a blockquote
            prev_idx = i - 1
            while prev_idx >= 0 and not lines[prev_idx].strip():
                prev_idx -= 1
            if prev_idx >= 0 and lines[prev_idx].strip().startswith(">"):
                # Insert separator between adjacent callouts
                # Remove any blank lines we just passed over
                while result and not result[-1].strip():
                    result.pop()
                result.append("")
                result.append("")

        result.append(line)

    return "\n".join(result)


def convert_details_to_headings(md_text: str) -> str:
    """Convert HTML <details><summary> blocks to regular Markdown headings.

    The Python markdown library cannot parse Markdown inside raw HTML blocks,
    so <details><summary>Title</summary>...</details> renders with literal
    **bold** markers instead of <strong> tags. Convert these to ## headings.

    Fenced code blocks are skipped to preserve code examples.
    """
    parts = _CODE_BLOCK_RE.split(md_text)
    result: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Inside a code fence — preserve as-is
            result.append(part)
        else:
            # Outside code fence — apply transforms
            part = _DETAILS_OPEN_RE.sub(
                lambda m: f"\n## {m.group(1).strip()}\n",
                part,
            )
            part = _DETAILS_CLOSE_RE.sub("", part)
            result.append(part)
    return "".join(result)


def fix_broken_internal_links(
    pages: dict[str, str],
    plan: dict[str, Any],
    project_name: str = "",
) -> dict[str, str]:
    """Remove or fix internal links that point to non-existent pages.

    AI-generated content often includes links to pages that were not part of
    the documentation plan (hallucinated page names). This function finds all
    internal .html links and removes those that don't match any plan slug.
    """
    _label = project_name or "unknown"

    # Build set of valid slugs from the plan
    valid_slugs: set[str] = set()
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            slug = page.get("slug", "")
            if slug:
                valid_slugs.add(slug)

    # Also add slugs from pages dict (in case plan is incomplete)
    valid_slugs.update(pages.keys())

    # Build canonical slug casing lookup (keys are lowercase for case-insensitive matching)
    slug_to_canonical: dict[str, str] = {s.lower(): s for s in valid_slugs}

    # Pattern: [link text](slug.html) — internal links only (no http://, no /)
    link_pattern = re.compile(
        r"\[([^\]]+)\]\(((?!\.)[a-zA-Z0-9._-]+)\.html(?:#[^\s)\"]*)?(?:\s*\"[^\"]*\")?\)"
    )

    updated: dict[str, str] = {}
    for slug, content in pages.items():

        def _replace_link(match: re.Match[str], _slug: str = slug) -> str:
            link_text = match.group(1)
            target_slug = match.group(2)
            target_lower = target_slug.lower()
            if target_lower in slug_to_canonical:
                # Rewrite to canonical slug casing for case-sensitive hosts
                canonical = slug_to_canonical.get(target_lower, target_slug)
                if canonical != target_slug:
                    # Reconstruct with canonical slug casing (limit=1 to avoid
                    # corrupting link text that happens to contain the slug)
                    return match.group(0).replace(
                        f"({target_slug}.html", f"({canonical}.html", 1
                    )
                return match.group(0)  # Already correct casing
            logger.info(
                f"[{_label}] Removing broken link to '{target_slug}.html' "
                f"in page '{_slug}'"
            )
            return link_text  # Remove the link, keep the text

        # Split content into code and non-code segments, only fix links in non-code
        parts = _CODE_BLOCK_RE.split(content)
        new_parts: list[str] = []
        for part in parts:
            if _CODE_BLOCK_RE.match(part):
                new_parts.append(part)  # Code segment, keep as-is
            else:
                new_parts.append(link_pattern.sub(_replace_link, part))
        updated[slug] = "".join(new_parts)

    return updated


def linkify_plain_references(
    pages: dict[str, str],
    plan: dict[str, Any],
    project_name: str = "",
) -> dict[str, str]:
    """Convert plain-text page references to markdown hyperlinks.

    AI-generated content often writes "See Page Title" or "see Page Title for"
    instead of proper markdown links. This finds those patterns and converts
    them to [Page Title](slug.html) when a matching page exists in the plan.
    """
    _label = project_name or "unknown"

    # Build title -> slug mapping from the plan
    title_to_slug: dict[str, str] = {}
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            title = page.get("title", "")
            slug = page.get("slug", "")
            if title and slug:
                title_to_slug[title] = slug

    if not title_to_slug:
        return pages

    # Sort titles by length (longest first) to avoid partial matches
    # e.g., "CLI Command Reference" should match before "CLI"
    sorted_titles = sorted(title_to_slug.keys(), key=len, reverse=True)
    lower_to_canonical: dict[str, str] = {t.lower(): t for t in sorted_titles}

    # Build a single regex pattern for all titles
    # Match: See <Title> (not inside an existing markdown link)
    title_alternatives = "|".join(re.escape(t) for t in sorted_titles)
    # Pattern matches "See <Title>" or "see <Title>" where Title is not inside []()
    pattern = re.compile(
        r"(?<!\[)"  # Not preceded by [
        r"(see\s+)"  # "See " or "see " (IGNORECASE handles casing)
        r"(" + title_alternatives + r")"  # One of the page titles
        r"(?!\]\()",  # Not followed by ]( (already a link)
        re.IGNORECASE,
    )

    updated: dict[str, str] = {}
    for page_slug, content in pages.items():

        def _replace(match: re.Match[str], _page_slug: str = page_slug) -> str:
            see_prefix = match.group(1)
            matched_title = match.group(2)
            # Find the canonical title (preserve original casing from plan)
            canonical_title = lower_to_canonical.get(matched_title.lower())
            if not canonical_title:
                return match.group(0)
            target_slug = title_to_slug[canonical_title]
            if target_slug == _page_slug:
                return match.group(0)  # Don't self-link
            # Escape markdown special chars in the title for safe link text
            safe_title = (
                canonical_title.replace("\\", "\\\\")
                .replace("[", "\\[")
                .replace("]", "\\]")
            )
            return f"{see_prefix}[{safe_title}]({target_slug}.html)"

        # Split content into code and non-code segments, only linkify non-code
        parts = _CODE_BLOCK_RE.split(content)
        new_parts: list[str] = []
        for part in parts:
            if _CODE_BLOCK_RE.match(part):
                new_parts.append(part)  # Code segment, keep as-is
            else:
                new_parts.append(pattern.sub(_replace, part))
        new_content = "".join(new_parts)

        if new_content != content:
            link_count = new_content.count(".html)") - content.count(".html)")
            if link_count > 0:
                logger.info(
                    f"[{_label}] Linkified {link_count} plain-text reference(s) in page '{page_slug}'"
                )
        updated[page_slug] = new_content

    return updated


def _confined_path(base: Path, relative_name: str) -> Path:
    """Ensure a relative filename resolves inside the base directory."""
    if any(ord(ch) < 32 for ch in relative_name):
        raise ValueError(f"Unsafe generated filename: {relative_name!r}")
    candidate = (base / relative_name).resolve()
    base_resolved = base.resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError(f"Unsafe generated filename: {relative_name!r}") from exc
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def detect_version(repo_path: Path) -> str | None:
    """Auto-detect project version from common sources.

    Checks in order: pyproject.toml, package.json, Cargo.toml, setup.cfg, git tags.
    Returns the first version found, or None.
    """
    # 1. pyproject.toml
    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            version = data.get("project", {}).get("version")
            if version:
                return str(version)
            version = data.get("tool", {}).get("poetry", {}).get("version")
            if version:
                return str(version)
        except Exception:
            logger.debug("Failed to parse pyproject.toml for version")

    # 2. package.json
    package_json = repo_path / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            version = data.get("version")
            if version:
                return str(version)
        except Exception:
            logger.debug("Failed to parse package.json for version")

    # 3. Cargo.toml
    cargo_toml = repo_path / "Cargo.toml"
    if cargo_toml.exists():
        try:
            import tomllib

            data = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
            version = data.get("package", {}).get("version")
            if version:
                return str(version)
        except Exception:
            logger.debug("Failed to parse Cargo.toml for version")

    # 4. setup.cfg
    setup_cfg = repo_path / "setup.cfg"
    if setup_cfg.exists():
        try:
            parser = ConfigParser()
            parser.read(str(setup_cfg), encoding="utf-8")
            version = parser.get("metadata", "version", fallback=None)
            if version:
                return str(version)
        except Exception:
            logger.debug("Failed to parse setup.cfg for version")

    # 5. Git tags
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        tag = result.stdout.strip()
        if tag:
            return tag
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        logger.debug("git describe failed or no tags available")

    return None


async def _validate_single_page(
    slug: str,
    content: str,
    repo_path: Path,
    ai_provider: str,
    ai_model: str,
    cache_dir: Path,
    project_name: str,
    page_title: str,
    page_description: str,
    job_dir: Path,
    ai_cli_timeout: int | None = None,
    page_type: str = "guide",
    other_pages_path: str | None = None,
) -> str:
    """Validate a single page and regenerate if stale references are found.

    Writes page content to a temp file, calls AI to check for stale references,
    and regenerates content via generate_full_page_content if issues are found.
    Returns the (possibly updated) page content.
    """
    temp_file = _confined_path(job_dir, f"{slug}.md")
    await asyncio.to_thread(temp_file.write_text, content, "utf-8")

    prompt = build_validation_prompt(str(temp_file))
    result: AIResult = await call_ai_once(
        prompt,
        ai_provider=ai_provider,
        ai_model=ai_model,
        cwd=str(repo_path),
        ai_call_timeout=ai_cli_timeout,
    )
    add_cost(result.usage.cost_usd if result.usage else None)

    if not result.success:
        logger.warning(f"[{project_name}] Validation AI call failed for page '{slug}'")
        logger.debug(
            f"[{project_name}] Validation output for '{slug}': {result.text[:200]}"
        )
        return content

    stale_refs = parse_json_array_response(result.text)
    if stale_refs is None:
        logger.warning(
            f"[{project_name}] Validation returned invalid JSON for page '{slug}', keeping original content"
        )
        return content
    if not stale_refs:
        return content

    exclusions = [
        ref.get("reference", "") for ref in stale_refs if isinstance(ref, dict)
    ]
    exclusions = [e for e in exclusions if e]

    if not exclusions:
        return content

    logger.info(
        f"[{project_name}] Page '{slug}' has {len(exclusions)} stale references, regenerating"
    )

    try:
        exclusions_file = _confined_path(job_dir, f"{slug}_exclusions.txt")
        await asyncio.to_thread(
            exclusions_file.write_text,
            "\n".join(exclusions),
            encoding="utf-8",
        )
        new_content = await generate_full_page_content(
            repo_path=repo_path,
            project_name=project_name,
            page_title=page_title,
            page_description=page_description,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=ai_cli_timeout,
            exclusions_path=str(exclusions_file),
            page_type=page_type,
            other_pages_path=other_pages_path,
        )
        cache_file = _confined_path(cache_dir, f"{slug}.md")
        await asyncio.to_thread(cache_file.write_text, new_content, encoding="utf-8")
        return new_content
    except Exception as exc:
        logger.warning(f"[{project_name}] Regeneration failed for page '{slug}': {exc}")
        return content


async def validate_pages(
    pages: dict[str, str],
    repo_path: Path,
    ai_provider: str,
    ai_model: str,
    cache_dir: Path,
    project_name: str,
    plan: dict[str, Any] | None = None,
    ai_cli_timeout: int | None = None,
) -> dict[str, str]:
    """Validate all pages for stale references and regenerate any that have issues.

    Uses the AI CLI to check each page for references to features, files, or APIs
    that no longer exist in the codebase. Pages with stale references are regenerated
    with explicit exclusion hints.

    Args:
        pages: Mapping of slug -> markdown content.
        repo_path: Root of the repository being documented.
        ai_provider: AI provider name.
        ai_model: AI model name.
        cache_dir: Directory where cached pages are stored.
        project_name: Name of the project (used for logging and regeneration prompts).
        plan: Optional documentation plan containing page titles/descriptions.
        ai_cli_timeout: Timeout in minutes for AI CLI calls.

    Returns:
        Updated mapping of slug -> markdown content (unchanged pages or regenerated).
    """
    # Build slug -> metadata map from plan
    slug_meta: dict[str, dict[str, str]] = {}
    if plan:
        for group in plan.get("navigation", []):
            for page in group.get("pages", []):
                slug = page.get("slug", "")
                if slug:
                    _page_type = page.get("type", "guide")
                    if _page_type not in PAGE_TYPES:
                        logger.warning(
                            f"[{project_name}] Unknown page type '{_page_type}' for slug '{slug}', "
                            f"falling back to 'guide'"
                        )
                        _page_type = "guide"
                    slug_meta[slug] = {
                        "title": page.get("title", slug),
                        "description": page.get("description", ""),
                        "type": _page_type,
                    }

    job_id = str(uuid.uuid4())
    job_dir = Path(tempfile.mkdtemp(prefix=f"docsfy-validation-{job_id}-"))

    try:
        # Write page manifest for cross-referencing
        manifest_path: Path | None = None
        if slug_meta:
            manifest_lines = [
                f"- [{meta.get('title', s)}]({s}.html) \u2014 {meta.get('description', '')}"
                for s, meta in slug_meta.items()
            ]
            manifest_path = job_dir / "pages.txt"
            await asyncio.to_thread(
                manifest_path.write_text, "\n".join(manifest_lines), "utf-8"
            )

        coroutines = [
            _validate_single_page(
                slug=slug,
                content=content,
                repo_path=repo_path,
                ai_provider=ai_provider,
                ai_model=ai_model,
                cache_dir=cache_dir,
                project_name=project_name,
                page_title=slug_meta.get(slug, {}).get("title", slug),
                page_description=slug_meta.get(slug, {}).get("description", ""),
                job_dir=job_dir,
                ai_cli_timeout=ai_cli_timeout,
                page_type=slug_meta.get(slug, {}).get("type", "guide"),
                other_pages_path=str(manifest_path) if manifest_path else None,
            )
            for slug, content in pages.items()
        ]

        results = await run_parallel_with_limit(
            coroutines, max_concurrency=get_settings().max_concurrent_pages
        )
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    updated: dict[str, str] = {}
    for (slug, _), result in zip(pages.items(), results, strict=True):
        if isinstance(result, Exception):
            logger.warning(
                f"[{project_name}] Validation failed for page '{slug}': {result}"
            )
            updated[slug] = pages[slug]
        else:
            updated[slug] = result

    return updated


async def check_and_fill_completeness(
    pages: dict[str, str],
    repo_path: Path,
    plan: dict[str, Any],
    ai_provider: str,
    ai_model: str,
    cache_dir: Path,
    project_name: str,
    ai_cli_timeout: int | None = None,
    graph_report_path: Path | None = None,
    graph_report_available: bool = False,
    repo_type: str = "app",
    on_page_generated: Callable[[int], Awaitable[None]] | None = None,
    owner: str = "",
    branch: str = "main",
) -> tuple[dict[str, str], dict[str, Any]]:
    """Check docs completeness and generate pages for any gaps.

    Returns updated (pages, plan) tuple with any new pages added.
    """
    # Write page manifest to temp file (GOLDEN RULE: no content in prompts)
    job_dir = Path(tempfile.mkdtemp(prefix="docsfy-completeness-"))
    try:
        manifest_lines: list[str] = []
        for group in plan.get("navigation", []):
            manifest_lines.append(f"## {group.get('group', '')}")
            for page in group.get("pages", []):
                slug = page.get("slug", "")
                title = page.get("title", slug)
                desc = page.get("description", "")
                manifest_lines.append(f"- [{title}]({slug}.html) \u2014 {desc}")

        manifest_path = job_dir / "pages_manifest.txt"
        manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")

        prompt = build_completeness_prompt(
            pages_manifest_path=str(manifest_path),
            graph_report_path=str(graph_report_path) if graph_report_path else None,
        )

        result: AIResult = await call_ai_once(
            prompt,
            ai_provider=ai_provider,
            ai_model=ai_model,
            cwd=str(repo_path),
            ai_call_timeout=ai_cli_timeout,
        )
        add_cost(result.usage.cost_usd if result.usage else None)

        if not result.success:
            logger.warning(
                f"[{project_name}] Completeness check failed: {result.text[:200]}"
            )
            return pages, plan

        if not result.text or not result.text.strip():
            logger.warning(
                f"[{project_name}] Completeness check returned empty response"
            )
            return pages, plan

        from docsfy.generator import _strip_ai_artifacts

        gaps = parse_json_array_response(_strip_ai_artifacts(result.text))
        if gaps is None or not isinstance(gaps, list):
            logger.warning(f"[{project_name}] Completeness check returned invalid JSON")
            return pages, plan

        # Filter to valid entries only
        valid_gaps = [
            g for g in gaps if isinstance(g, dict) and g.get("slug") and g.get("title")
        ]

        if not valid_gaps:
            logger.info(f"[{project_name}] Completeness check: docs are complete")
            return pages, plan

        logger.info(
            f"[{project_name}] Completeness check found {len(valid_gaps)} gap(s): "
            + ", ".join(g.get("title", "") for g in valid_gaps)
        )

        # Generate pages for each gap
        from docsfy.generator import generate_page

        # Write updated manifest including new pages for cross-referencing
        all_manifest_lines = list(manifest_lines)
        for gap in valid_gaps:
            all_manifest_lines.append(
                f"- [{gap['title']}]({gap['slug']}.html) \u2014 {gap.get('description', '')}"
            )
        updated_manifest = job_dir / "pages_full.txt"
        updated_manifest.write_text("\n".join(all_manifest_lines), encoding="utf-8")

        for gap in valid_gaps:
            slug = gap["slug"]
            title = gap["title"]
            description = gap.get("description", "")
            page_type = gap.get("type", "guide")
            if page_type not in PAGE_TYPES:
                page_type = "guide"

            logger.info(f"[{project_name}] Generating gap page: {title} ({slug})")
            try:
                content = await generate_page(
                    repo_path=repo_path,
                    slug=slug,
                    title=title,
                    description=description,
                    cache_dir=cache_dir,
                    ai_provider=ai_provider,
                    ai_model=ai_model,
                    ai_cli_timeout=ai_cli_timeout,
                    project_name=project_name,
                    owner=owner,
                    branch=branch,
                    on_page_generated=on_page_generated,
                    page_type=page_type,
                    other_pages_path=str(updated_manifest),
                    repo_type=repo_type,
                    graph_report_available=graph_report_available,
                )
                pages[slug] = content

                # Add to plan navigation
                target_group = gap.get("group", "User Guides")
                group_found = False
                for nav_group in plan.get("navigation", []):
                    if nav_group.get("group") == target_group:
                        nav_group["pages"].append(
                            {
                                "slug": slug,
                                "title": title,
                                "description": description,
                                "type": page_type,
                            }
                        )
                        group_found = True
                        break
                if not group_found:
                    # Add to last non-reference group, or create new
                    plan.setdefault("navigation", []).append(
                        {
                            "group": target_group,
                            "pages": [
                                {
                                    "slug": slug,
                                    "title": title,
                                    "description": description,
                                    "type": page_type,
                                }
                            ],
                        }
                    )

                logger.info(
                    f"[{project_name}] Gap page generated: {title} ({len(content)} chars)"
                )
            except Exception as exc:
                logger.warning(
                    f"[{project_name}] Failed to generate gap page '{slug}': {exc}"
                )

    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    return pages, plan


async def add_cross_links(
    pages: dict[str, str],
    plan: dict[str, Any],
    ai_provider: str,
    ai_model: str,
    repo_path: Path,
    project_name: str = "",
    ai_cli_timeout: int | None = None,
) -> dict[str, str]:
    """Add cross-reference links between related pages.

    Writes a manifest and page files to a temp directory, asks the AI to suggest
    related pages for each slug, then programmatically appends a "## Related Pages"
    section to each page that has suggestions.

    Args:
        pages: Mapping of slug -> markdown content.
        plan: Documentation plan containing navigation structure with slugs/titles.
        ai_provider: AI provider name.
        ai_model: AI model name.
        repo_path: Root of the repository (used as cwd for AI CLI calls).
        project_name: Name of the project (used in log prefixes).
        ai_cli_timeout: Timeout in minutes for AI CLI calls.

    Returns:
        Updated mapping of slug -> markdown content with cross-links appended.
    """
    # Build slug -> title map for link labels (fallback to slug itself for pages not in plan)
    slug_titles: dict[str, str] = {slug: slug for slug in pages}
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            slug = page.get("slug", "")
            if slug:
                slug_titles[slug] = page.get("title", slug)

    job_id = str(uuid.uuid4())
    pages_dir = Path(tempfile.mkdtemp(prefix=f"docsfy-crosslinks-{job_id}-"))

    try:
        # Write manifest
        manifest = [
            {"slug": slug, "title": slug_titles.get(slug, slug)} for slug in pages
        ]
        manifest_path = pages_dir / "manifest.json"
        await asyncio.to_thread(
            manifest_path.write_text, json.dumps(manifest, indent=2), "utf-8"
        )

        # Write page files
        for slug, content in pages.items():
            page_file = _confined_path(pages_dir, f"{slug}.md")
            await asyncio.to_thread(page_file.write_text, content, "utf-8")

        prompt = build_cross_links_prompt(
            manifest_path=str(manifest_path),
            pages_dir=str(pages_dir),
        )
        result: AIResult | None = None
        try:
            result = await call_ai_once(
                prompt,
                ai_provider=ai_provider,
                ai_model=ai_model,
                cwd=str(repo_path),
                ai_call_timeout=ai_cli_timeout,
            )
        except Exception as exc:
            logger.warning(
                f"[{project_name}] add_cross_links: AI call raised {exc}, returning pages unchanged"
            )
            return pages
    finally:
        shutil.rmtree(pages_dir, ignore_errors=True)

    add_cost(result.usage.cost_usd if result and result.usage else None)

    if result is None or not result.success:
        logger.warning(
            f"[{project_name}] add_cross_links: AI call failed, returning pages unchanged"
        )
        if result is not None:
            logger.debug(
                f"[{project_name}] add_cross_links output: {result.text[:200]}"
            )
        return pages

    cross_links = parse_json_response(result.text)
    if not isinstance(cross_links, dict):
        logger.warning(
            f"[{project_name}] add_cross_links: Invalid AI cross-links response, returning pages unchanged"
        )
        return pages

    updated = dict(pages)
    for slug, related_slugs in cross_links.items():
        if slug not in updated:
            continue
        if not isinstance(related_slugs, list) or not related_slugs:
            continue

        link_items: list[str] = []
        seen: set[str] = set()
        for related_slug in related_slugs:
            if (
                not isinstance(related_slug, str)
                or related_slug == slug
                or related_slug not in updated
                or related_slug in seen
            ):
                continue
            seen.add(related_slug)
            title = (
                slug_titles.get(related_slug, related_slug)
                .replace("\\", "\\\\")
                .replace("[", "\\[")
                .replace("]", "\\]")
                .replace("\n", " ")
                .replace("\r", " ")
            )
            link_items.append(f"- [{title}]({related_slug}.html)")
            if len(link_items) == 5:
                break

        if link_items:
            related_section = "\n\n## Related Pages\n\n" + "\n".join(link_items)
            updated[slug] = updated[slug] + related_section

    return updated
