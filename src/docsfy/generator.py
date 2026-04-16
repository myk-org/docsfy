from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from simple_logger.logger import get_logger

from docsfy.ai_client import call_ai_cli, run_parallel_with_limit
from docsfy.json_parser import parse_json_array_response, parse_json_response
from pydantic import ValidationError

from docsfy.models import DEFAULT_BRANCH, MAX_CONCURRENT_PAGES, PAGE_TYPES, DocPlan
from docsfy.prompts import (
    build_incremental_page_prompt,
    build_incremental_planner_prompt,
    build_page_prompt,
    build_planner_prompt,
)

logger = get_logger(name=__name__)


def is_unsafe_slug(slug: str) -> bool:
    """Check if a slug contains path traversal characters."""
    return "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug


def _strip_ai_preamble(text: str) -> str:
    """Strip AI thinking/planning text that appears before actual content."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i > 10:
            break
        if line.startswith("#"):
            return "\n".join(lines[i:])
    return text


async def _call_ai_or_raise(
    prompt: str,
    repo_path: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
) -> str:
    cli_flags = ["--trust"] if ai_provider == "cursor" else None
    success, output = await call_ai_cli(
        prompt=prompt,
        cwd=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
        cli_flags=cli_flags,
    )
    if not success:
        raise RuntimeError(output)
    return output


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
) -> str:
    prompt = build_page_prompt(
        project_name=project_name,
        page_title=page_title,
        page_description=page_description,
        page_type=page_type,
        exclusions_path=exclusions_path,
    )
    output = await _call_ai_or_raise(
        prompt=prompt,
        repo_path=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )
    return _strip_ai_preamble(output)


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
) -> str:
    prompt = build_incremental_page_prompt(
        project_name=project_name,
        page_title=page_title,
        page_description=page_description,
        existing_content=existing_content,
        changed_files=changed_files,
        diff_content=diff_content,
        page_type=page_type,
    )
    output = await _call_ai_or_raise(
        prompt=prompt,
        repo_path=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )
    return _apply_incremental_page_updates(existing_content, output)


async def run_planner(
    repo_path: Path,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
) -> dict[str, Any]:
    logger.info(f"[{project_name}] Calling AI planner")
    prompt = build_planner_prompt(project_name)
    output = await _call_ai_or_raise(
        prompt=prompt,
        repo_path=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )

    plan = parse_json_response(output)
    if plan is None:
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
                )
            except (RuntimeError, ValueError) as exc:
                logger.warning(
                    f"[{_label}] Incremental update failed for page '{slug}', "
                    f"falling back to full page generation: {exc}"
                )
                output = await generate_full_page_content(
                    repo_path=repo_path,
                    project_name=prompt_project_name,
                    page_title=title,
                    page_description=description,
                    ai_provider=ai_provider,
                    ai_model=ai_model,
                    ai_cli_timeout=ai_cli_timeout,
                    page_type=page_type,
                )
        else:
            output = await generate_full_page_content(
                repo_path=repo_path,
                project_name=prompt_project_name,
                page_title=title,
                page_description=description,
                ai_provider=ai_provider,
                ai_model=ai_model,
                ai_cli_timeout=ai_cli_timeout,
                page_type=page_type,
            )
    except RuntimeError as exc:
        logger.warning(f"[{_label}] Failed to generate page '{slug}': {exc}")
        output = f"# {title}\n\n*Documentation generation failed. Please re-run.*"
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
            all_pages.append(
                {
                    "slug": slug,
                    "title": title,
                    "description": page.get("description", ""),
                    "type": page.get("type", "guide")
                    if page.get("type") in PAGE_TYPES
                    else "guide",
                }
            )

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
        )
        for p in all_pages
    ]

    results = await run_parallel_with_limit(
        coroutines, max_concurrency=MAX_CONCURRENT_PAGES
    )
    pages: dict[str, str] = {}
    for page_info, result in zip(all_pages, results):
        if isinstance(result, Exception):
            logger.warning(
                f"[{_label}] Page generation failed for '{page_info['slug']}': {result}"
            )
            pages[page_info["slug"]] = (
                f"# {page_info['title']}\n\n*Documentation generation failed.*"
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
    prompt = build_incremental_planner_prompt(
        project_name, changed_files, existing_plan
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
        logger.warning(f"[{project_name}] Incremental planner failed, regenerating all")
        return ["all"]

    raw_result = parse_json_array_response(output)
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
