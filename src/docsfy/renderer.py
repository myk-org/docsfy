from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from simple_logger.logger import get_logger

logger = get_logger(name=__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _md_to_html(md_text: str) -> tuple[str, str]:
    """Convert markdown to HTML. Returns (content_html, toc_html)."""
    md = markdown.Markdown(
        extensions=["fenced_code", "codehilite", "tables", "toc"],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False},
            "toc": {"toc_depth": "2-3"},
        },
    )
    content_html = md.convert(md_text)
    toc_html = getattr(md, "toc", "")
    return content_html, toc_html


def render_page(
    markdown_content: str,
    page_title: str,
    project_name: str,
    tagline: str,
    navigation: list[dict[str, Any]],
    current_slug: str,
) -> str:
    env = _get_jinja_env()
    template = env.get_template("page.html")
    content_html, toc_html = _md_to_html(markdown_content)
    return template.render(
        title=page_title,
        project_name=project_name,
        tagline=tagline,
        content=content_html,
        toc=toc_html,
        navigation=navigation,
        current_slug=current_slug,
    )


def render_index(
    project_name: str, tagline: str, navigation: list[dict[str, Any]]
) -> str:
    env = _get_jinja_env()
    template = env.get_template("index.html")
    return template.render(
        title=project_name,
        project_name=project_name,
        tagline=tagline,
        navigation=navigation,
    )


def _build_search_index(
    pages: dict[str, str], plan: dict[str, Any]
) -> list[dict[str, str]]:
    index: list[dict[str, str]] = []
    title_map: dict[str, str] = {}
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            title_map[page["slug"]] = page["title"]
    for slug, content in pages.items():
        index.append(
            {
                "slug": slug,
                "title": title_map.get(slug, slug),
                "content": content[:2000],
            }
        )
    return index


def _build_llms_txt(plan: dict[str, Any]) -> str:
    """Build llms.txt index file."""
    project_name = plan.get("project_name", "Documentation")
    tagline = plan.get("tagline", "")
    lines = [f"# {project_name}", ""]
    if tagline:
        lines.extend([f"> {tagline}", ""])
    for group in plan.get("navigation", []):
        lines.extend([f"## {group['group']}", ""])
        for page in group.get("pages", []):
            desc = page.get("description", "")
            if desc:
                lines.append(f"- [{page['title']}]({page['slug']}.html): {desc}")
            else:
                lines.append(f"- [{page['title']}]({page['slug']}.html)")
        lines.append("")
    return "\n".join(lines)


def _build_llms_full_txt(plan: dict[str, Any], pages: dict[str, str]) -> str:
    """Build llms-full.txt with all content concatenated."""
    project_name = plan.get("project_name", "Documentation")
    tagline = plan.get("tagline", "")
    lines = [f"# {project_name}", ""]
    if tagline:
        lines.extend([f"> {tagline}", ""])
    lines.extend(["---", ""])
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            slug = page["slug"]
            content = pages.get(slug, "")
            lines.extend(
                [
                    f"# {page['title']}",
                    "",
                    f"Source: {slug}.html",
                    "",
                    content,
                    "",
                    "---",
                    "",
                ]
            )
    return "\n".join(lines)


def render_site(plan: dict[str, Any], pages: dict[str, str], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    project_name: str = plan.get("project_name", "Documentation")
    tagline: str = plan.get("tagline", "")
    navigation: list[dict[str, Any]] = plan.get("navigation", [])

    if STATIC_DIR.exists():
        for static_file in STATIC_DIR.iterdir():
            if static_file.is_file():
                shutil.copy2(static_file, assets_dir / static_file.name)

    index_html = render_index(project_name, tagline, navigation)
    (output_dir / "index.html").write_text(index_html)

    for slug, md_content in pages.items():
        title = slug
        for group in navigation:
            for page in group.get("pages", []):
                if page["slug"] == slug:
                    title = page["title"]
                    break
        page_html = render_page(
            markdown_content=md_content,
            page_title=title,
            project_name=project_name,
            tagline=tagline,
            navigation=navigation,
            current_slug=slug,
        )
        (output_dir / f"{slug}.html").write_text(page_html)

    search_index = _build_search_index(pages, plan)
    (output_dir / "search-index.json").write_text(json.dumps(search_index))

    # Generate llms.txt files
    llms_txt = _build_llms_txt(plan)
    (output_dir / "llms.txt").write_text(llms_txt)

    llms_full_txt = _build_llms_full_txt(plan, pages)
    (output_dir / "llms-full.txt").write_text(llms_full_txt)

    logger.info(f"Rendered site: {len(pages)} pages to {output_dir}")
