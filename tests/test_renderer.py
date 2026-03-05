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
