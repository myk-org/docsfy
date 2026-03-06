from __future__ import annotations

from pathlib import Path


def test_render_page_to_html() -> None:
    from docsfy.renderer import render_page

    html = render_page(
        markdown_content="# Hello\n\nThis is a test.",
        page_title="Hello",
        project_name="test-repo",
        tagline="A test project",
        navigation=[{"group": "Docs", "pages": [{"slug": "hello", "title": "Hello"}]}],
        current_slug="hello",
    )
    assert "<html" in html
    assert "Hello" in html
    assert "test-repo" in html
    assert "This is a test." in html


def test_render_site(tmp_path: Path) -> None:
    from docsfy.renderer import render_site

    plan = {
        "project_name": "test-repo",
        "tagline": "A test project",
        "navigation": [
            {
                "group": "Getting Started",
                "pages": [
                    {
                        "slug": "introduction",
                        "title": "Introduction",
                        "description": "Overview",
                    },
                ],
            },
        ],
    }
    pages = {"introduction": "# Introduction\n\nWelcome to test-repo."}
    output_dir = tmp_path / "site"

    render_site(plan=plan, pages=pages, output_dir=output_dir)

    assert (output_dir / "index.html").exists()
    assert (output_dir / "introduction.html").exists()
    assert (output_dir / "assets" / "style.css").exists()
    index_html = (output_dir / "index.html").read_text()
    assert "test-repo" in index_html
    page_html = (output_dir / "introduction.html").read_text()
    assert "Welcome to test-repo" in page_html


def test_sanitize_html_removes_script_tags() -> None:
    from docsfy.renderer import _sanitize_html

    html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
    result = _sanitize_html(html)
    assert "<script" not in result
    assert "alert" not in result
    assert "<p>Hello</p>" in result
    assert "<p>World</p>" in result


def test_sanitize_html_removes_iframe_object_embed_form() -> None:
    from docsfy.renderer import _sanitize_html

    html = '<p>Safe</p><iframe src="evil.com"></iframe><object data="x"></object><embed src="y"/><form action="z">data</form>'
    result = _sanitize_html(html)
    assert "<iframe" not in result
    assert "<object" not in result
    assert "<embed" not in result
    assert "<form" not in result
    assert "<p>Safe</p>" in result


def test_sanitize_html_removes_event_handlers() -> None:
    from docsfy.renderer import _sanitize_html

    html = '<img src="x" onerror="alert(1)"><div onclick="evil()">text</div>'
    result = _sanitize_html(html)
    assert "onerror" not in result
    assert "onclick" not in result
    assert "text" in result


def test_md_to_html_sanitizes_content() -> None:
    from docsfy.renderer import _md_to_html

    md_text = '# Title\n\n<script>alert("xss")</script>\n\nSafe content.'
    content_html, _ = _md_to_html(md_text)
    assert "<script" not in content_html
    assert "Safe content" in content_html


def test_search_index_generated(tmp_path: Path) -> None:
    from docsfy.renderer import render_site

    plan = {
        "project_name": "test-repo",
        "tagline": "Test",
        "navigation": [
            {
                "group": "Docs",
                "pages": [{"slug": "intro", "title": "Intro", "description": ""}],
            }
        ],
    }
    pages = {"intro": "# Intro\n\nSome searchable content here."}
    output_dir = tmp_path / "site"

    render_site(plan=plan, pages=pages, output_dir=output_dir)
    assert (output_dir / "search-index.json").exists()

    import json

    index = json.loads((output_dir / "search-index.json").read_text())
    assert len(index) == 1
    assert index[0]["slug"] == "intro"
    assert index[0]["title"] == "Intro"
    assert "searchable content" in index[0]["content"]
