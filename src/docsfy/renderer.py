from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from simple_logger.logger import get_logger

logger = get_logger(name=__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )
    return _jinja_env


def _sanitize_html(html: str) -> str:
    """Remove dangerous HTML elements from AI-generated content."""
    # Remove script tags and content
    html = re.sub(
        r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    # Remove iframe, object, embed, form tags
    for tag in ["iframe", "object", "embed", "form"]:
        html = re.sub(
            rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(rf"<{tag}[^>]*/>", "", html, flags=re.IGNORECASE)
    # Remove event handler attributes
    html = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', "", html, flags=re.IGNORECASE)
    html = re.sub(r"\s+on\w+\s*=\s*\S+", "", html, flags=re.IGNORECASE)
    # Remove javascript: and data: URL schemes in href and src attributes
    html = re.sub(
        r'href\s*=\s*["\']javascript:[^"\']*["\']',
        'href="#"',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'src\s*=\s*["\']javascript:[^"\']*["\']', 'src="#"', html, flags=re.IGNORECASE
    )
    html = re.sub(
        r'href\s*=\s*["\']data:[^"\']*["\']', 'href="#"', html, flags=re.IGNORECASE
    )
    html = re.sub(
        r'src\s*=\s*["\']data:[^"\']*["\']', 'src="#"', html, flags=re.IGNORECASE
    )
    # Also catch unquoted javascript:/data: URLs
    html = re.sub(
        r"href\s*=\s*javascript:[^\s>]*", 'href="#"', html, flags=re.IGNORECASE
    )
    html = re.sub(r"src\s*=\s*javascript:[^\s>]*", 'src="#"', html, flags=re.IGNORECASE)
    html = re.sub(r"href\s*=\s*data:[^\s>]*", 'href="#"', html, flags=re.IGNORECASE)
    html = re.sub(r"src\s*=\s*data:[^\s>]*", 'src="#"', html, flags=re.IGNORECASE)
    return html


def _md_to_html(md_text: str) -> tuple[str, str]:
    """Convert markdown to HTML. Returns (content_html, toc_html)."""
    md = markdown.Markdown(
        extensions=["fenced_code", "codehilite", "tables", "toc"],
        extension_configs={
            "codehilite": {"css_class": "highlight", "guess_lang": False},
            "toc": {"toc_depth": "2-3"},
        },
    )
    content_html = _sanitize_html(md.convert(md_text))
    toc_html = getattr(md, "toc", "")
    return content_html, toc_html


def render_page(
    markdown_content: str,
    page_title: str,
    project_name: str,
    tagline: str,
    navigation: list[dict[str, Any]],
    current_slug: str,
    prev_page: dict[str, str] | None = None,
    next_page: dict[str, str] | None = None,
    repo_url: str = "",
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
        prev_page=prev_page,
        next_page=next_page,
        repo_url=repo_url,
    )


def render_index(
    project_name: str,
    tagline: str,
    navigation: list[dict[str, Any]],
    repo_url: str = "",
) -> str:
    env = _get_jinja_env()
    template = env.get_template("index.html")
    return template.render(
        title=project_name,
        project_name=project_name,
        tagline=tagline,
        navigation=navigation,
        repo_url=repo_url,
    )


def _build_search_index(
    pages: dict[str, str], plan: dict[str, Any]
) -> list[dict[str, str]]:
    index: list[dict[str, str]] = []
    title_map: dict[str, str] = {}
    for group in plan.get("navigation", []):
        for page in group.get("pages", []):
            title_map[page.get("slug", "")] = page.get("title", "")
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
        lines.extend([f"## {group.get('group', '')}", ""])
        for page in group.get("pages", []):
            desc = page.get("description", "")
            page_title = page.get("title", "")
            page_slug = page.get("slug", "")
            if desc:
                lines.append(f"- [{page_title}]({page_slug}.md): {desc}")
            else:
                lines.append(f"- [{page_title}]({page_slug}.md)")
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
            slug = page.get("slug", "")
            content = pages.get(slug, "")
            lines.extend(
                [
                    f"Source: {slug}.md",
                    "",
                    content,
                    "",
                    "---",
                    "",
                ]
            )
    return "\n".join(lines)


def render_site(plan: dict[str, Any], pages: dict[str, str], output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Prevent GitHub Pages from running Jekyll
    (output_dir / ".nojekyll").touch()

    project_name: str = plan.get("project_name", "Documentation")
    tagline: str = plan.get("tagline", "")
    navigation: list[dict[str, Any]] = plan.get("navigation", [])
    repo_url: str = plan.get("repo_url", "")

    if STATIC_DIR.exists():
        for static_file in STATIC_DIR.iterdir():
            if static_file.is_file():
                shutil.copy2(static_file, assets_dir / static_file.name)

    # Filter out invalid slugs
    valid_pages: dict[str, str] = {}
    for slug, content in pages.items():
        if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
            logger.warning(f"Skipping invalid slug: {slug}")
        else:
            valid_pages[slug] = content

    index_html = render_index(project_name, tagline, navigation, repo_url=repo_url)
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")

    # Build ordered list of valid slugs for prev/next navigation
    valid_slug_order: list[dict[str, str]] = []
    for group in navigation:
        for page in group.get("pages", []):
            slug = page.get("slug", "")
            if slug in valid_pages:
                valid_slug_order.append(
                    {"slug": slug, "title": page.get("title", slug)}
                )

    for idx, slug_info in enumerate(valid_slug_order):
        slug = slug_info["slug"]
        md_content = valid_pages[slug]
        title = slug_info["title"]

        prev_page = valid_slug_order[idx - 1] if idx > 0 else None
        next_page = (
            valid_slug_order[idx + 1] if idx < len(valid_slug_order) - 1 else None
        )

        page_html = render_page(
            markdown_content=md_content,
            page_title=title,
            project_name=project_name,
            tagline=tagline,
            navigation=navigation,
            current_slug=slug,
            prev_page=prev_page,
            next_page=next_page,
            repo_url=repo_url,
        )
        (output_dir / f"{slug}.html").write_text(page_html, encoding="utf-8")
        (output_dir / f"{slug}.md").write_text(md_content, encoding="utf-8")

    search_index = _build_search_index(valid_pages, plan)
    (output_dir / "search-index.json").write_text(
        json.dumps(search_index), encoding="utf-8"
    )

    # Generate llms.txt files
    llms_txt = _build_llms_txt(plan)
    (output_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")

    llms_full_txt = _build_llms_full_txt(plan, valid_pages)
    (output_dir / "llms-full.txt").write_text(llms_full_txt, encoding="utf-8")

    logger.info(f"Rendered site: {len(valid_pages)} pages to {output_dir}")
