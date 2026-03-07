from __future__ import annotations

from pathlib import Path
from typing import Any

from simple_logger.logger import get_logger

from docsfy.ai_client import call_ai_cli, run_parallel_with_limit
from docsfy.json_parser import parse_json_list_response, parse_json_response
from docsfy.prompts import (
    build_incremental_page_prompt,
    build_incremental_planner_prompt,
    build_page_prompt,
    build_planner_prompt,
)

logger = get_logger(name=__name__)

MAX_CONCURRENT_PAGES = 5


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


async def run_planner(
    repo_path: Path,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
) -> dict[str, Any]:
    logger.info(f"[{project_name}] Calling AI planner")
    prompt = build_planner_prompt(project_name)
    # Build CLI flags based on provider
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
        msg = f"Planner failed: {output}"
        raise RuntimeError(msg)

    plan = parse_json_response(output)
    if plan is None:
        msg = "Failed to parse planner output as JSON"
        raise RuntimeError(msg)

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
) -> str:
    _label = project_name or repo_path.name

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

    if existing_content and changed_files:
        prompt = build_incremental_page_prompt(
            project_name=repo_path.name,
            page_title=title,
            page_description=description,
            existing_content=existing_content,
            changed_files=changed_files,
            diff_content=diff_content or "",
        )
    else:
        prompt = build_page_prompt(
            project_name=repo_path.name, page_title=title, page_description=description
        )
    # Build CLI flags based on provider
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
        logger.warning(f"[{_label}] Failed to generate page '{slug}': {output}")
        output = f"# {title}\n\n*Documentation generation failed. Please re-run.*"

    output = _strip_ai_preamble(output)
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
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=ai_cli_timeout,
            use_cache=use_cache,
            project_name=project_name,
            owner=owner,
            existing_content=_existing_pages.get(p["slug"]),
            changed_files=changed_files,
            diff_content=diff_content,
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
        logger.warning(f"[{project_name}] Incremental planner failed, regenerating all")
        return ["all"]

    result = parse_json_list_response(output)
    if result is None or not isinstance(result, list):
        return ["all"]
    # Validate all items are strings
    result = [item for item in result if isinstance(item, str)]
    if not result:
        return ["all"]
    logger.info(
        f"[{project_name}] Incremental planner identified {len(result)} pages to regenerate"
    )
    return result
