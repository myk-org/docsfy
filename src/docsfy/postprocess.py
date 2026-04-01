from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from configparser import ConfigParser
from pathlib import Path
from typing import Any

from simple_logger.logger import get_logger

from docsfy.ai_client import call_ai_cli, run_parallel_with_limit
from docsfy.generator import MAX_CONCURRENT_PAGES, _generate_full_page_content
from docsfy.json_parser import parse_json_array_response, parse_json_response
from docsfy.prompts import build_cross_links_prompt, build_validation_prompt

logger = get_logger(name=__name__)


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
) -> str:
    """Validate a single page and regenerate if stale references are found.

    Writes page content to a temp file, calls AI to check for stale references,
    and regenerates content via _generate_full_page_content if issues are found.
    Returns the (possibly updated) page content.
    """
    temp_file = job_dir / f"{slug}.md"
    temp_file.write_text(content, encoding="utf-8")

    prompt = build_validation_prompt(str(temp_file))
    success, output = await call_ai_cli(
        prompt=prompt,
        cwd=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
    )

    if not success:
        logger.warning(
            f"[{project_name}] Validation AI call failed for page '{slug}': {output}"
        )
        return content

    stale_refs = parse_json_array_response(output)
    if not stale_refs:
        # Either empty list (no issues) or parse failure — keep original
        return content

    exclusions = [
        ref.get("reference", "") for ref in stale_refs if isinstance(ref, dict)
    ]
    exclusions = [e for e in exclusions if e]

    logger.info(
        f"[{project_name}] Page '{slug}' has {len(exclusions)} stale references, regenerating"
    )

    try:
        new_content = await _generate_full_page_content(
            repo_path=repo_path,
            project_name=project_name,
            page_title=page_title,
            page_description=page_description,
            ai_provider=ai_provider,
            ai_model=ai_model,
            exclusions=exclusions,
        )
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{slug}.md").write_text(new_content, encoding="utf-8")
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
                    slug_meta[slug] = {
                        "title": page.get("title", slug),
                        "description": page.get("description", ""),
                    }

    job_id = str(uuid.uuid4())
    job_dir = Path(f"/tmp/docsfy-validation/{job_id}")
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
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
            )
            for slug, content in pages.items()
        ]

        results = await run_parallel_with_limit(
            coroutines, max_concurrency=MAX_CONCURRENT_PAGES
        )
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    updated: dict[str, str] = {}
    for (slug, _), result in zip(pages.items(), results):
        if isinstance(result, Exception):
            logger.warning(
                f"[{project_name}] Validation failed for page '{slug}': {result}"
            )
            updated[slug] = pages[slug]
        else:
            updated[slug] = result

    return updated


async def add_cross_links(
    pages: dict[str, str],
    plan: dict[str, Any],
    ai_provider: str,
    ai_model: str,
    repo_path: Path,
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

    Returns:
        Updated mapping of slug -> markdown content with cross-links appended.
    """
    # Build slug -> title map for link labels
    slug_titles: dict[str, str] = {}
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            slug = page.get("slug", "")
            if slug:
                slug_titles[slug] = page.get("title", slug)

    job_id = str(uuid.uuid4())
    job_dir = Path(f"/tmp/docsfy-crosslinks/{job_id}")
    pages_dir = job_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write manifest
        manifest = [
            {"slug": slug, "title": slug_titles.get(slug, slug)} for slug in pages
        ]
        manifest_path = job_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Write page files
        for slug, content in pages.items():
            (pages_dir / f"{slug}.md").write_text(content, encoding="utf-8")

        prompt = build_cross_links_prompt(
            manifest_path=str(manifest_path),
            pages_dir=str(pages_dir),
        )
        success, output = await call_ai_cli(
            prompt=prompt,
            cwd=repo_path,
            ai_provider=ai_provider,
            ai_model=ai_model,
        )
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    if not success:
        logger.warning("add_cross_links: AI call failed, returning pages unchanged")
        return pages

    cross_links = parse_json_response(output)
    if not cross_links:
        logger.warning(
            "add_cross_links: Failed to parse AI cross-links response, returning pages unchanged"
        )
        return pages

    updated = dict(pages)
    for slug, related_slugs in cross_links.items():
        if slug not in updated:
            continue
        if not isinstance(related_slugs, list) or not related_slugs:
            continue

        link_items: list[str] = []
        for related_slug in related_slugs:
            if not isinstance(related_slug, str) or related_slug not in slug_titles:
                continue
            title = slug_titles[related_slug]
            link_items.append(f"- [{title}]({related_slug}.html)")

        if link_items:
            related_section = "\n\n## Related Pages\n\n" + "\n".join(link_items)
            updated[slug] = updated[slug] + related_section

    return updated
