from __future__ import annotations

from pathlib import Path
from typing import Any

from simple_logger.logger import get_logger

from docsfy.ai_client import call_ai_cli, run_parallel_with_limit
from docsfy.json_parser import parse_json_response
from docsfy.prompts import build_page_prompt, build_planner_prompt

logger = get_logger(name=__name__)

MAX_CONCURRENT_PAGES = 5


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
    prompt = build_planner_prompt(project_name)
    success, output = await call_ai_cli(
        prompt=prompt,
        cwd=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )
    if not success:
        msg = f"Planner failed: {output}"
        raise RuntimeError(msg)

    plan = parse_json_response(output)
    if plan is None:
        msg = "Failed to parse planner output as JSON"
        raise RuntimeError(msg)

    logger.info(f"Plan generated: {len(plan.get('navigation', []))} groups")
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
) -> str:
    # Validate slug to prevent path traversal
    if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
        msg = f"Invalid page slug: '{slug}'"
        raise ValueError(msg)

    cache_file = cache_dir / f"{slug}.md"
    if use_cache and cache_file.exists():
        logger.debug(f"Using cached page: {slug}")
        return cache_file.read_text()

    prompt = build_page_prompt(
        project_name=repo_path.name, page_title=title, page_description=description
    )
    success, output = await call_ai_cli(
        prompt=prompt,
        cwd=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )
    if not success:
        logger.warning(f"Failed to generate page '{slug}': {output}")
        output = f"# {title}\n\n*Documentation generation failed. Please re-run.*"

    output = _strip_ai_preamble(output)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(output)
    logger.info(f"Generated page: {slug} ({len(output)} chars)")
    return output


async def generate_all_pages(
    repo_path: Path,
    plan: dict[str, Any],
    cache_dir: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    use_cache: bool = False,
) -> dict[str, str]:
    all_pages: list[dict[str, str]] = []
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            all_pages.append(
                {
                    "slug": page["slug"],
                    "title": page["title"],
                    "description": page.get("description", ""),
                }
            )

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
                f"Page generation failed for '{page_info['slug']}': {result}"
            )
            pages[page_info["slug"]] = (
                f"# {page_info['title']}\n\n*Documentation generation failed.*"
            )
        else:
            pages[page_info["slug"]] = result

    logger.info(f"Generated {len(pages)} pages total")
    return pages
