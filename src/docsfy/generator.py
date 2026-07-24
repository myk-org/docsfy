from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from simple_logger.logger import get_logger

from docsfy.ai_client import AIResult, call_ai_once, run_parallel_with_limit
from docsfy.cost_tracker import add_cost
from docsfy.json_parser import parse_json_array_response, parse_json_response
from pydantic import ValidationError

from docsfy.models import DEFAULT_BRANCH, PAGE_TYPES, DocPlan
from docsfy.prompts import (
    SIDECAR_TOOLS,
    build_incremental_page_prompt,
    build_incremental_planner_prompt,
    build_page_prompt,
    build_planner_prompt,
    truncate_diff_content,
)

logger = get_logger(name=__name__)


def is_unsafe_slug(slug: str) -> bool:
    """Check if a slug contains path traversal characters."""
    return "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug


# An H1 heading line: a single leading "#" followed by whitespace and text.
# Deliberately excludes "##"+ so that sub-headings inside AI preamble don't
# get mistaken for the real page title.
_H1_LINE_RE = re.compile(r"^#\s+\S")

# How many leading lines we're willing to scan looking for the real H1 title
# when stripping AI exploration/planning chatter. Wide enough to survive
# multi-paragraph "let me start by..." preambles, narrow enough to avoid
# accidentally treating a legitimate document body as "preamble".
_PREAMBLE_SCAN_LINES = 50


def _find_h1_within_scan_window(text: str) -> str | None:
    """Return text starting at the first H1 found within the scan window, or None."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i > _PREAMBLE_SCAN_LINES:
            break
        if _H1_LINE_RE.match(line):
            return "\n".join(lines[i:])
    return None


def _strip_leading_agent_narration_paragraphs(text: str) -> str:
    """Strip a leading run of paragraphs that read as agent narration.

    Defense-in-depth only: reuses ``_AGENT_NARRATION_PATTERNS`` to drop
    exploration chatter ("Let me start by...", "Now let me...") sitting at
    the very front of the output, one whole paragraph at a time, as long as
    each paragraph matches at least one narration pattern. Stops at the
    first paragraph that doesn't match. The quality gate remains the
    authoritative check; this just gives real content a better chance of
    being recognized when it's preceded by chatter the H1 scan alone can't
    see past (e.g. preamble long enough to push the real H1 beyond
    ``_PREAMBLE_SCAN_LINES``).
    """
    paragraphs = text.split("\n\n")
    idx = 0
    while idx < len(paragraphs) - 1 and any(
        pattern.search(paragraphs[idx]) for pattern in _AGENT_NARRATION_PATTERNS
    ):
        idx += 1
    if idx == 0:
        return text
    return "\n\n".join(paragraphs[idx:])


def _strip_ai_preamble(text: str) -> str:
    """Strip AI thinking/planning text that appears before actual content.

    Scans up to ``_PREAMBLE_SCAN_LINES`` lines looking for the first real H1
    heading and discards everything before it (including any agent-speak
    paragraphs). As defense-in-depth, if no H1 is found in that window, a
    leading run of agent-narration paragraphs is stripped first (see
    ``_strip_leading_agent_narration_paragraphs``) and the H1 scan is
    retried, which recovers cases where narration chatter pushed the real H1
    beyond the scan window. If no H1 is found either way, the original text
    is returned unchanged so the quality gate can reject it explicitly.
    """
    found = _find_h1_within_scan_window(text)
    if found is not None:
        return found

    narration_stripped = _strip_leading_agent_narration_paragraphs(text)
    if narration_stripped is not text:
        found = _find_h1_within_scan_window(narration_stripped)
        if found is not None:
            return found

    return text


_AI_COMMENTARY_END_MARKERS = (
    "\nWait -",
    "\nWait,",
    "\nLet me refine",
    "\nLet me remove",
    "\nI should ",
    "\nI'll also ",
    "\nI'll remove",
    "\nSo I should",
    "\n`</think>`",
)


def _strip_ai_artifacts(text: str) -> str:
    """Strip AI thinking/reasoning artifacts from generated content.

    Removes:
    - <think>...</think> blocks anywhere in the text
    - </think> orphan closing tags
    - Self-referential AI commentary at the end (e.g., "Wait - the user said...",
      "Let me refine:", "I should NOT include...")
    """
    # Remove <think>...</think> blocks (including multiline)
    while "<think>" in text and "</think>" in text:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # Remove orphan </think> tags
    text = re.sub(r"</think>", "", text)

    # Remove orphan <think> tags
    text = re.sub(r"<think>", "", text)

    # Only scan the tail of the output for self-referential AI commentary.
    # These markers only appear at the very end when the AI "thinks out loud"
    # after finishing. Scanning the full text risks truncating legitimate prose.
    if len(text) > 500:
        tail_offset = len(text) - 500
        for marker in _AI_COMMENTARY_END_MARKERS:
            idx = text.find(marker, tail_offset)
            if idx >= 0:
                text = text[:idx]
                break  # Only apply the first match

    return text.strip()


# Heading used by postprocess.add_cross_links when appending suggested links.
# Shared so the quality gate can strip it off before measuring substantive
# body length, and so postprocess doesn't duplicate the literal string.
RELATED_PAGES_HEADING = "## Related Pages"

# Minimum length (in characters) of page body content after the H1 title,
# excluding any "## Related Pages" section, for the content to be considered
# substantive documentation rather than a near-empty stub dressed up with
# cross-links.
_MIN_SUBSTANTIVE_BODY_CHARS = 80

# Only scan the opening of the content for the noun-phrase patterns below.
# Real docs can legitimately mention things like "knowledge graph" deep in
# the prose (as a topic, not narration); CoT chatter puts this kind of
# phrasing at the very start, matching the observed rootcoz failure shape
# (issue #121: "Let me start by reading the knowledge graph...").
_NARRATION_SCAN_CHARS = 400

# Ambiguous noun phrases: topics that real documentation can legitimately
# discuss anywhere in its body (docsfy's own docs describe its knowledge
# graph feature, for instance), so these are only treated as a narration
# signal when found in the opening window above, matching how the original
# rootcoz failures actually looked.
_AGENT_NARRATION_NOUN_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bknowledge graph\b",
        r"\bpages? manifest\b",
    )
)

# First-person narration verb-phrases that strongly indicate the AI is
# narrating its own exploration process ("chain of thought") instead of
# writing documentation. Unlike the noun phrases above, these are checked
# across the *entire* content (title + body), anchored to the start of a
# line via _AGENT_NARRATION_LINE_START_RE below rather than as a free
# substring search. Anchoring to line-start is what makes a full-document
# scan safe: real prose can mention "check the config" or "look at the log"
# mid-sentence anywhere, but real documentation essentially never *opens a
# line* with first-person narration like "Let me check..." or "Now let me
# explore...". This lets exploration chatter be caught wherever it leaks in
# (not just the opening 400 chars) while avoiding false-rejects on the same
# generic verbs used naturally mid-sentence.
_AGENT_NARRATION_VERB_PHRASES: tuple[str, ...] = (
    r"let me (?:start|now|read|explore|look|check|examine|search|analyze)\b",
    r"now let me\b",
    r"i'll start by\b",
    r"i will start by\b",
    r"first,? i(?:'ll| will)\b",
    r"i need to (?:read|explore|check|look at|examine)\b",
    r"exploring the (?:repo|repository|codebase)\b",
)

_AGENT_NARRATION_LINE_START_RE = re.compile(
    r"^[ \t]*(?:" + "|".join(_AGENT_NARRATION_VERB_PHRASES) + r")",
    re.IGNORECASE | re.MULTILINE,
)

# Full pattern set (noun phrases + verb phrases as free substrings), retained
# for _strip_leading_agent_narration_paragraphs's defense-in-depth stripping,
# where over-stripping a misidentified leading paragraph is low-risk (worst
# case it falls through to the ordinary "no H1 found" rejection).
_AGENT_NARRATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    _AGENT_NARRATION_NOUN_PATTERNS
    + tuple(
        re.compile(pattern, re.IGNORECASE) for pattern in _AGENT_NARRATION_VERB_PHRASES
    )
)

_FAILURE_STUB_MESSAGE = "*Documentation generation failed. Please re-run.*"
_FAILURE_STUB_MESSAGE_SHORT = "*Documentation generation failed.*"

# Matches both known failure-stub formats used across the codebase:
#   "# {title}\n\n*Documentation generation failed. Please re-run.*"
#   "# {title}\n\n*Documentation generation failed.*"
#
# Deliberately NOT re.DOTALL, and the title is restricted to a single line
# ([^\n]+ rather than .+). Without these constraints, "." matches newlines,
# so a real multi-paragraph document that happens to *end* with this exact
# phrase would have its entire body greedily swallowed as part of the
# "title" and get misclassified as a stub (see issue #121 review).
_FAILURE_STUB_RE = re.compile(
    r"^#[ \t]+[^\n]+\n\n\*Documentation generation failed\.(?: Please re-run\.)?\*\s*$"
)


def _generation_failure_stub(title: str, *, retry_hint: bool = True) -> str:
    """Build the standard loud failure stub for pages that never produced usable content."""
    message = _FAILURE_STUB_MESSAGE if retry_hint else _FAILURE_STUB_MESSAGE_SHORT
    return f"# {title}\n\n{message}"


def is_generation_failure_stub(content: str) -> bool:
    """Check whether content is one of the known generation-failure stub formats.

    Used by postprocessing (cross-links, llms.txt/llms-full.txt indexing) to
    avoid treating a failed page as if it were real, complete documentation.
    """
    return bool(_FAILURE_STUB_RE.match(content.strip()))


def page_content_passes_quality_gate(
    content: str, expected_title: str | None = None
) -> tuple[bool, str]:
    """Check whether generated page content is real documentation, not AI chatter.

    Rejects content that is empty, lacks a proper ``# Title`` H1, is a known
    generation-failure stub, is too short to be substantive, or whose opening
    reads like AI exploration narration (chain-of-thought) rather than
    documentation prose.

    Args:
        content: The page content to check. Callers on the full-generation
            path pre-strip via ``_strip_ai_artifacts``/``_strip_ai_preamble``;
            the incremental-update path also strips before calling this (see
            ``generate_page``). The checks here are conservative enough to
            still behave correctly on unstripped content, so this is a
            best-effort convention rather than a hard precondition.
        expected_title: Optional planned page title, used only to produce a
            more actionable rejection reason.

    Returns:
        A ``(passes, reason)`` tuple. ``reason`` is ``"ok"`` when passing,
        otherwise a short human-readable explanation for logging.
    """
    stripped = content.strip()
    if not stripped:
        return False, "content is empty"

    if is_generation_failure_stub(stripped):
        return False, "content is a known generation-failure stub"

    lines = stripped.split("\n", 1)
    first_line = lines[0]
    if not _H1_LINE_RE.match(first_line):
        reason = "content does not start with an H1 heading (# Title)"
        if expected_title:
            reason += f" (expected title: {expected_title!r})"
        return False, reason

    body = lines[1].strip() if len(lines) > 1 else ""
    body_without_related = re.split(
        rf"\n{re.escape(RELATED_PAGES_HEADING)}\b", body, maxsplit=1
    )[0].strip()
    if len(body_without_related) < _MIN_SUBSTANTIVE_BODY_CHARS:
        return False, "content body is too short to be substantive documentation"

    # Scan the whole opening (title line included) for ambiguous noun-phrase
    # topics since CoT chatter can leak into the title itself, not just the
    # body, and these are only suspicious when they appear immediately.
    opening = stripped[:_NARRATION_SCAN_CHARS]
    for pattern in _AGENT_NARRATION_NOUN_PATTERNS:
        if pattern.search(opening):
            return (
                False,
                f"opening content matches agent-narration pattern {pattern.pattern!r}",
            )

    # Scan the *entire* content (not just the opening) for lines that open
    # with first-person agent-narration verb phrasing. This catches CoT
    # chatter that leaks in beyond the opening window while staying safe
    # against false-rejects on generic verbs used mid-sentence, since it
    # only fires on line-start matches (see _AGENT_NARRATION_LINE_START_RE).
    line_start_match = _AGENT_NARRATION_LINE_START_RE.search(stripped)
    if line_start_match:
        return (
            False,
            f"content contains a line opening with agent-narration phrasing {line_start_match.group(0)!r}",
        )

    return True, "ok"


async def _call_ai_or_raise(
    prompt: str,
    repo_path: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
) -> str:
    """Call AI CLI, accumulate cost, and raise on failure."""
    result: AIResult = await call_ai_once(
        prompt,
        ai_provider=ai_provider,
        ai_model=ai_model,
        cwd=str(repo_path),
        ai_call_timeout=ai_cli_timeout,
        tools=list(SIDECAR_TOOLS),
    )
    add_cost(result.usage.cost_usd if result.usage else None)
    if not result.success:
        raise RuntimeError(result.text[:2000])
    return result.text


def _normalize_incremental_planner_result(raw_result: list[Any]) -> list[str]:
    if not all(isinstance(item, str) for item in raw_result):
        msg = "Incremental planner output must be a JSON array of strings"
        raise ValueError(msg)

    result: list[str] = []
    seen: set[str] = set()
    for item in raw_result:
        slug = item.strip()
        if not slug:
            msg = "Incremental planner output must not contain empty slugs"
            raise ValueError(msg)
        if slug == "all":
            if len(raw_result) != 1:
                msg = (
                    "Incremental planner output must not combine 'all' with other slugs"
                )
                raise ValueError(msg)
            return ["all"]
        if slug not in seen:
            seen.add(slug)
            result.append(slug)

    return result


def _parse_incremental_page_updates(raw_text: str) -> list[tuple[str, str]]:
    payload = parse_json_response(raw_text)
    if payload is None:
        msg = "Failed to parse incremental page update JSON"
        raise ValueError(msg)

    raw_updates = payload.get("updates")
    if not isinstance(raw_updates, list):
        msg = "Incremental page update payload must contain an 'updates' list"
        raise ValueError(msg)

    updates: list[tuple[str, str]] = []
    for idx, item in enumerate(raw_updates):
        if not isinstance(item, dict):
            msg = f"Incremental update #{idx + 1} must be an object"
            raise ValueError(msg)
        old_text = item.get("old_text")
        new_text = item.get("new_text")
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            msg = f"Incremental update #{idx + 1} must contain string old_text/new_text values"
            raise ValueError(msg)
        if not old_text:
            msg = f"Incremental update #{idx + 1} has an empty old_text value"
            raise ValueError(msg)
        updates.append((old_text, new_text))

    return updates


def _apply_incremental_page_updates(existing_content: str, raw_text: str) -> str:
    updates = _parse_incremental_page_updates(raw_text)
    if not updates:
        return existing_content

    replacements: list[tuple[int, int, str]] = []
    for idx, (old_text, new_text) in enumerate(updates):
        start = existing_content.find(old_text)
        if start == -1:
            msg = f"Incremental update #{idx + 1} old_text was not found in the existing page"
            raise ValueError(msg)
        if existing_content.find(old_text, start + 1) != -1:
            msg = f"Incremental update #{idx + 1} old_text is not unique in the existing page"
            raise ValueError(msg)
        replacements.append((start, start + len(old_text), new_text))

    replacements.sort(key=lambda item: item[0])
    for i in range(1, len(replacements)):
        prev_end = replacements[i - 1][1]
        start = replacements[i][0]
        if start < prev_end:
            msg = "Incremental updates overlap; expected non-overlapping top-to-bottom replacements"
            raise ValueError(msg)

    parts: list[str] = []
    cursor = 0
    for start, end, new_text in replacements:
        parts.append(existing_content[cursor:start])
        parts.append(new_text)
        cursor = end
    parts.append(existing_content[cursor:])
    return "".join(parts)


async def generate_full_page_content(
    repo_path: Path,
    project_name: str,
    page_title: str,
    page_description: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    exclusions_path: str | None = None,
    page_type: str = "guide",
    other_pages_path: str | None = None,
    repo_type: str = "app",
    graph_report_available: bool = False,
    image_catalog_path: str | None = None,
) -> str:
    if image_catalog_path:
        logger.debug("Page '%s': image catalog at %s", page_title, image_catalog_path)
    prompt = build_page_prompt(
        project_name=project_name,
        page_title=page_title,
        page_description=page_description,
        page_type=page_type,
        exclusions_path=exclusions_path,
        other_pages_path=other_pages_path,
        repo_type=repo_type,
        graph_report_available=graph_report_available,
        image_catalog_path=image_catalog_path,
    )
    for attempt in range(2):
        output = await _call_ai_or_raise(
            prompt=prompt,
            repo_path=repo_path,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=ai_cli_timeout,
        )
        content = _strip_ai_artifacts(_strip_ai_preamble(output))
        ok, reason = page_content_passes_quality_gate(
            content, expected_title=page_title
        )
        if ok:
            return content
        if attempt == 0:
            logger.warning(
                f"Page '{page_title}' failed quality gate ({reason}); regenerating once"
            )
        else:
            logger.error(
                f"Page '{page_title}' failed quality gate after regeneration ({reason})"
            )

    return _generation_failure_stub(page_title)


async def _generate_incremental_page_content(
    repo_path: Path,
    project_name: str,
    page_title: str,
    page_description: str,
    existing_content: str,
    changed_files: list[str],
    diff_content: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    page_type: str = "guide",
    repo_type: str = "app",
    image_catalog_path: str | None = None,
) -> str:
    job_dir = Path(tempfile.mkdtemp(prefix="docsfy-incremental-page-"))
    try:
        existing_page_file = job_dir / "existing_page.md"
        existing_page_file.write_text(existing_content, encoding="utf-8")

        truncated_diff = truncate_diff_content(diff_content)
        diff_file = job_dir / "diff.patch"
        diff_file.write_text(truncated_diff, encoding="utf-8")

        prompt = build_incremental_page_prompt(
            project_name=project_name,
            page_title=page_title,
            page_description=page_description,
            existing_page_path=str(existing_page_file),
            changed_files=changed_files,
            diff_path=str(diff_file),
            page_type=page_type,
            repo_type=repo_type,
            image_catalog_path=image_catalog_path,
        )
        output = await _call_ai_or_raise(
            prompt=prompt,
            repo_path=repo_path,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=ai_cli_timeout,
        )
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
    return _apply_incremental_page_updates(existing_content, output)


async def run_planner(
    repo_path: Path,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    repo_type: str | None = None,
    graph_report_available: bool = False,
) -> dict[str, Any]:
    logger.info(f"[{project_name}] Calling AI planner")
    prompt = build_planner_prompt(
        project_name, repo_type=repo_type, graph_report_available=graph_report_available
    )
    output = await _call_ai_or_raise(
        prompt=prompt,
        repo_path=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )

    plan = parse_json_response(_strip_ai_artifacts(output))
    if plan is None:
        logger.warning(
            f"[{project_name}] Planner output is not valid JSON "
            f"({len(output)} chars). Use DEBUG level to see content."
        )
        logger.debug(f"[{project_name}] Planner output preview: {output[:500]}")
        msg = "Failed to parse planner output as JSON"
        raise RuntimeError(msg)

    if not isinstance(plan, dict):
        msg = f"[{project_name}] Planner returned {type(plan).__name__} instead of a JSON object"
        raise RuntimeError(msg)

    # Validate plan structure
    try:
        validated = DocPlan(**plan)
        plan = validated.model_dump()
    except ValidationError as exc:
        msg = f"[{project_name}] Planner returned an invalid plan: {exc}"
        raise RuntimeError(msg) from exc

    logger.info(
        f"[{project_name}] Plan generated: {len(plan.get('navigation', []))} groups"
    )
    return plan


async def generate_page(
    repo_path: Path,
    slug: str,
    title: str,
    description: str,
    cache_dir: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    use_cache: bool = False,
    project_name: str = "",
    owner: str = "",
    existing_content: str | None = None,
    changed_files: list[str] | None = None,
    diff_content: str | None = None,
    branch: str = DEFAULT_BRANCH,
    on_page_generated: Callable[[int], Awaitable[None]] | None = None,
    page_type: str = "guide",
    other_pages_path: str | None = None,
    repo_type: str = "app",
    graph_report_available: bool = False,
    image_catalog_path: str | None = None,
) -> str:
    _label = project_name or repo_path.name
    prompt_project_name = project_name or repo_path.name

    if project_name and not owner:
        logger.warning(f"[{_label}] owner missing for page count update, skipping")

    # Validate slug to prevent path traversal
    if is_unsafe_slug(slug):
        msg = f"Invalid page slug: '{slug}'"
        raise ValueError(msg)

    cache_file = cache_dir / f"{slug}.md"
    if use_cache and cache_file.exists():
        logger.debug(f"[{_label}] Using cached page: {slug}")
        return cache_file.read_text(encoding="utf-8")

    async def _run_full_page_generation() -> str:
        """Shared full-generation fallback, avoiding repeating the same kwargs 3x."""
        return await generate_full_page_content(
            repo_path=repo_path,
            project_name=prompt_project_name,
            page_title=title,
            page_description=description,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=ai_cli_timeout,
            page_type=page_type,
            other_pages_path=other_pages_path,
            repo_type=repo_type,
            graph_report_available=graph_report_available,
            image_catalog_path=image_catalog_path,
        )

    try:
        if existing_content is not None and changed_files is not None:
            try:
                output = await _generate_incremental_page_content(
                    repo_path=repo_path,
                    project_name=prompt_project_name,
                    page_title=title,
                    page_description=description,
                    existing_content=existing_content,
                    changed_files=changed_files,
                    diff_content=diff_content or "",
                    ai_provider=ai_provider,
                    ai_model=ai_model,
                    ai_cli_timeout=ai_cli_timeout,
                    page_type=page_type,
                    repo_type=repo_type,
                    image_catalog_path=image_catalog_path,
                )
                # Defense-in-depth: strip AI artifacts before the gate, same
                # as the full-generation path, so the gate's "content should
                # already be stripped" convention holds here too.
                output = _strip_ai_artifacts(output)
                ok, reason = page_content_passes_quality_gate(
                    output, expected_title=title
                )
                if not ok:
                    logger.warning(
                        f"[{_label}] Incremental update for page '{slug}' failed "
                        f"quality gate ({reason}), falling back to full page generation"
                    )
                    output = await _run_full_page_generation()
            except (RuntimeError, ValueError) as exc:
                logger.warning(
                    f"[{_label}] Incremental update failed for page '{slug}', "
                    f"falling back to full page generation: {exc}"
                )
                output = await _run_full_page_generation()
        else:
            output = await _run_full_page_generation()
    except RuntimeError as exc:
        logger.warning(f"[{_label}] Failed to generate page '{slug}': {exc}")
        output = _generation_failure_stub(title)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(output, encoding="utf-8")
    logger.info(f"[{_label}] Generated page: {slug} ({len(output)} chars)")

    # Update page count in DB if project_name provided
    if project_name:
        from docsfy.storage import update_project_status

        # Count cached pages to get current total
        existing_pages = len(list(cache_dir.glob("*.md")))
        await update_project_status(
            project_name,
            ai_provider,
            ai_model,
            owner=owner,
            status="generating",
            page_count=existing_pages,
            branch=branch,
        )
        if on_page_generated is not None:
            try:
                await on_page_generated(existing_pages)
            except Exception as exc:
                logger.debug(
                    f"[{_label}] on_page_generated callback failed for '{slug}': {exc}"
                )

    return output


async def generate_all_pages(
    repo_path: Path,
    plan: dict[str, Any],
    cache_dir: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    use_cache: bool = False,
    project_name: str = "",
    owner: str = "",
    changed_files: list[str] | None = None,
    existing_pages: dict[str, str] | None = None,
    diff_content: str | None = None,
    branch: str = DEFAULT_BRANCH,
    on_page_generated: Callable[[int], Awaitable[None]] | None = None,
    repo_type: str = "app",
    graph_report_available: bool = False,
    image_catalog_path: str | None = None,
) -> dict[str, str]:
    _label = project_name or repo_path.name

    all_pages: list[dict[str, str]] = []
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            slug = page.get("slug", "")
            title = page.get("title", slug)
            if not slug:
                logger.warning(
                    f"[{_label}] Skipping page with no slug in group '{group.get('group', 'unknown')}'"
                )
                continue
            if is_unsafe_slug(slug):
                logger.warning(f"[{_label}] Skipping path-unsafe slug: '{slug}'")
                continue
            _page_type = page.get("type", "guide")
            if _page_type not in PAGE_TYPES:
                logger.warning(
                    f"[{_label}] Unknown page type '{_page_type}' for slug '{slug}', "
                    f"falling back to 'guide'"
                )
                _page_type = "guide"
            all_pages.append(
                {
                    "slug": slug,
                    "title": title,
                    "description": page.get("description", ""),
                    "type": _page_type,
                }
            )

    # Write page manifest once for cross-referencing (GOLDEN RULE: don't inline in prompts)
    pages_manifest_dir = Path(tempfile.mkdtemp(prefix="docsfy-pages-manifest-"))
    try:
        pages_manifest_path = pages_manifest_dir / "pages.txt"
        manifest_lines = [
            f"- [{p['title']}]({p['slug']}.html) \u2014 {p['description']}"
            for p in all_pages
        ]
        pages_manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")

        _existing_pages = existing_pages or {}
        coroutines = [
            generate_page(
                repo_path=repo_path,
                slug=p["slug"],
                title=p["title"],
                description=p["description"],
                cache_dir=cache_dir,
                page_type=p["type"],
                ai_provider=ai_provider,
                ai_model=ai_model,
                ai_cli_timeout=ai_cli_timeout,
                use_cache=use_cache,
                project_name=project_name,
                owner=owner,
                existing_content=_existing_pages.get(p["slug"]),
                changed_files=changed_files,
                diff_content=diff_content,
                branch=branch,
                on_page_generated=on_page_generated,
                other_pages_path=str(pages_manifest_path),
                repo_type=repo_type,
                graph_report_available=graph_report_available,
                image_catalog_path=image_catalog_path,
            )
            for p in all_pages
        ]

        from docsfy.storage import get_max_concurrent_pages

        results = await run_parallel_with_limit(
            coroutines, max_concurrency=await get_max_concurrent_pages()
        )
    finally:
        shutil.rmtree(pages_manifest_dir, ignore_errors=True)
    pages: dict[str, str] = {}
    for page_info, result in zip(all_pages, results):
        if isinstance(result, Exception):
            logger.warning(
                f"[{_label}] Page generation failed for '{page_info['slug']}': {result}"
            )
            pages[page_info["slug"]] = _generation_failure_stub(
                page_info["title"], retry_hint=False
            )
        else:
            pages[page_info["slug"]] = result

    logger.info(f"[{_label}] Generated {len(pages)} pages total")
    return pages


async def run_incremental_planner(
    repo_path: Path,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    changed_files: list[str],
    existing_plan: dict[str, Any],
    ai_cli_timeout: int | None = None,
) -> list[str]:
    """Ask AI which pages need regeneration based on changed files."""
    logger.info(
        f"[{project_name}] Running incremental planner for {len(changed_files)} changed files"
    )
    job_dir = Path(tempfile.mkdtemp(prefix="docsfy-incremental-plan-"))
    try:
        plan_file = job_dir / "existing_plan.json"
        plan_file.write_text(json.dumps(existing_plan, indent=2), encoding="utf-8")

        prompt = build_incremental_planner_prompt(
            project_name, changed_files, str(plan_file)
        )
        try:
            output = await _call_ai_or_raise(
                prompt=prompt,
                repo_path=repo_path,
                ai_provider=ai_provider,
                ai_model=ai_model,
                ai_cli_timeout=ai_cli_timeout,
            )
        except RuntimeError:
            logger.warning(
                f"[{project_name}] Incremental planner failed, regenerating all"
            )
            return ["all"]
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    raw_result = parse_json_array_response(_strip_ai_artifacts(output))
    if raw_result is None or not isinstance(raw_result, list):
        logger.warning(
            f"[{project_name}] Incremental planner returned unparseable output, "
            f"regenerating all. Raw output: {output[:200]}"
        )
        return ["all"]
    try:
        result = _normalize_incremental_planner_result(raw_result)
    except ValueError as exc:
        logger.warning(
            f"[{project_name}] Incremental planner normalization failed: {exc}. "
            f"Raw result: {raw_result}"
        )
        return ["all"]
    logger.info(
        f"[{project_name}] Incremental planner identified {len(result)} pages to regenerate"
    )
    return result
