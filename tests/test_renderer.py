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


def test_sanitize_html_unquoted_javascript() -> None:
    from docsfy.renderer import _sanitize_html

    result = _sanitize_html("<a href=javascript:alert(1)>x</a>")
    assert "javascript:" not in result

    result = _sanitize_html("<img src=javascript:alert(1)>")
    assert "javascript:" not in result

    result = _sanitize_html("<a href=data:text/html,<script>alert(1)</script>>x</a>")
    assert "data:" not in result

    result = _sanitize_html("<img src=data:text/html,evil>")
    assert "data:" not in result


def test_sanitize_html_whitespace_javascript() -> None:
    from docsfy.renderer import _sanitize_html

    result = _sanitize_html('<a href="   javascript:alert(1)">x</a>')
    assert "javascript:" not in result


def test_sanitize_html_entity_encoded_javascript() -> None:
    from docsfy.renderer import _sanitize_html

    # HTML entities would be decoded by the browser, making this dangerous
    result = _sanitize_html('<a href="&#x6a;avascript:alert(1)">x</a>')
    assert "javascript" not in result.lower() or 'href="#"' in result


def test_sanitize_html_keeps_safe_urls() -> None:
    from docsfy.renderer import _sanitize_html

    result = _sanitize_html('<a href="https://example.com">link</a>')
    assert "https://example.com" in result
    result2 = _sanitize_html('<a href="/path/to/page">link</a>')
    assert "/path/to/page" in result2
    result3 = _sanitize_html('<a href="#section">link</a>')
    assert "#section" in result3


def test_ensure_blank_lines_preprocessing() -> None:
    from docsfy.renderer import _ensure_blank_lines

    # Unordered list without preceding blank line
    result = _ensure_blank_lines("Some text\n- item one\n- item two")
    assert result == "Some text\n\n- item one\n- item two"

    # Ordered list without preceding blank line
    result = _ensure_blank_lines("Some text\n1. first\n2. second")
    assert result == "Some text\n\n1. first\n2. second"

    # Blockquote without preceding blank line
    result = _ensure_blank_lines("Some text\n> a quote\n> continued")
    assert result == "Some text\n\n> a quote\n> continued"

    # Code fence without preceding blank line (no blank lines inside fence)
    result = _ensure_blank_lines("Some text\n```python\ncode\n```")
    assert result == "Some text\n\n```python\ncode\n```"

    # Already has blank line - no double blank
    result = _ensure_blank_lines("Some text\n\n- item one")
    assert result == "Some text\n\n- item one"

    # Asterisk list items
    result = _ensure_blank_lines("Some text\n* item one\n* item two")
    assert result == "Some text\n\n* item one\n* item two"


def test_ensure_blank_lines_nested_fences() -> None:
    from docsfy.renderer import _ensure_blank_lines

    # Nested fences: inner ``` inside outer ```` must not toggle state
    text = "````markdown\nSome text\n```yaml\n- run: build\n```\n````"
    result = _ensure_blank_lines(text)
    # Should NOT insert blank lines inside the outer fence
    assert "\n\n- run:" not in result
    assert "- run: build" in result

    # Ensure the outer fence still closes properly and blank lines
    # are inserted after it when needed
    text2 = "````markdown\nSome text\n```yaml\ncode\n```\n````\n- item"
    result2 = _ensure_blank_lines(text2)
    assert "\n\n- item" in result2


def test_md_to_html_renders_lists_without_blank_lines() -> None:
    from docsfy.renderer import _md_to_html

    # Simulate AI output missing blank lines before list
    md_text = "Here are items:\n- First\n- Second\n- Third"
    content_html, _ = _md_to_html(md_text)
    assert "<li>" in content_html
    assert "<ul>" in content_html


def test_md_to_html_renders_blockquote_without_blank_lines() -> None:
    from docsfy.renderer import _md_to_html

    md_text = "Some context:\n> **Note:** Important info."
    content_html, _ = _md_to_html(md_text)
    assert "<blockquote>" in content_html


def test_clean_code_fence_annotations_line_range_filepath() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    # Pattern: ```135:150:src/jenkins_job_insight/main.py
    md = "Some text\n```135:150:src/jenkins_job_insight/main.py\ndef foo():\n    pass\n```"
    result = _clean_code_fence_annotations(md)
    assert "```python" in result
    assert "135:150" not in result

    # Pattern: ```96:104:examples/analyze_build.py
    md = "Some text\n```96:104:examples/analyze_build.py\ncode\n```"
    result = _clean_code_fence_annotations(md)
    assert "```python" in result
    assert "96:104" not in result


def test_clean_code_fence_annotations_unknown_extension() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    md = "```10:20:src/data.xyz\nstuff\n```"
    result = _clean_code_fence_annotations(md)
    # Unknown extension should produce plain ``` with no language
    assert result.startswith("```\n")
    assert "10:20" not in result


def test_clean_code_fence_annotations_filepath_as_language() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    # Pattern: ```src/utils/helper.js
    md = "```src/utils/helper.js\nconsole.log('hi');\n```"
    result = _clean_code_fence_annotations(md)
    assert "```javascript" in result
    assert "src/utils" not in result


def test_clean_code_fence_annotations_bare_filename() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    # Pattern: ```config.yaml
    md = "```config.yaml\nkey: value\n```"
    result = _clean_code_fence_annotations(md)
    assert "```yaml" in result
    assert "config.yaml" not in result

    # Pattern: ```Dockerfile.dockerfile  (unlikely but tests the map)
    md2 = "```script.sh\n#!/bin/bash\necho hi\n```"
    result2 = _clean_code_fence_annotations(md2)
    assert "```bash" in result2


def test_clean_code_fence_annotations_preserves_normal_fences() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    # Normal language specifier should NOT be altered
    md = "```python\ndef foo():\n    pass\n```"
    result = _clean_code_fence_annotations(md)
    assert result == md

    # Plain fence without language
    md2 = "```\nsome code\n```"
    result2 = _clean_code_fence_annotations(md2)
    assert result2 == md2


def test_clean_code_fence_annotations_quad_backticks() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    md = "````10:20:src/main.go\nfunc main() {}\n````"
    result = _clean_code_fence_annotations(md)
    assert "````go" in result
    assert "10:20" not in result


def test_clean_code_fence_annotations_multiple_blocks() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    md = (
        "Text before\n"
        "```1:10:app.py\nprint('hello')\n```\n"
        "Middle text\n"
        "```20:30:utils.js\nconsole.log('hi');\n```\n"
        "End text"
    )
    result = _clean_code_fence_annotations(md)
    assert "```python" in result
    assert "```javascript" in result
    assert "1:10" not in result
    assert "20:30" not in result


def test_clean_code_fence_annotations_nested_outer_fence() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    text = "````markdown\n```\n```10:20:src/file.py\nprint('x')\n```\n````"
    result = _clean_code_fence_annotations(text)
    # Inner annotated fence should NOT be rewritten
    assert "```10:20:src/file.py" in result


def test_md_to_html_with_annotated_code_fence() -> None:
    from docsfy.renderer import _md_to_html

    # This is the actual rendering bug: annotated fences break the parser
    md_text = (
        "## Example\n\n"
        "Here is some code:\n"
        "```135:150:src/jenkins_job_insight/main.py\n"
        "def analyze():\n"
        "    return True\n"
        "```\n\n"
        "This text should still render normally.\n\n"
        "## Another Section\n\n"
        "More content here."
    )
    content_html, _ = _md_to_html(md_text)
    # The key assertion: the text AFTER the code block must not be swallowed
    assert "This text should still render normally" in content_html
    assert "Another Section" in content_html
    assert "More content here" in content_html


def test_lang_from_filepath() -> None:
    from docsfy.renderer import _lang_from_filepath

    assert _lang_from_filepath("src/main.py") == "python"
    assert _lang_from_filepath("lib/utils.ts") == "typescript"
    assert _lang_from_filepath("Makefile") == "makefile"
    assert _lang_from_filepath("src/Dockerfile") == "dockerfile"
    assert _lang_from_filepath("build/Makefile") == "makefile"
    assert _lang_from_filepath("ci/Jenkinsfile") == "groovy"
    assert _lang_from_filepath("unknown_no_ext") == ""
    assert _lang_from_filepath("config.yaml") == "yaml"
    assert _lang_from_filepath("  app.go  ") == "go"


def test_clean_code_fence_annotations_extensionless_path() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    result = _clean_code_fence_annotations("```src/Dockerfile\nFROM python\n```")
    assert result == "```dockerfile\nFROM python\n```"


def test_clean_code_fence_annotations_makefile_path() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    result = _clean_code_fence_annotations("```build/Makefile\nall:\n```")
    assert result == "```makefile\nall:\n```"


def test_clean_code_fence_annotations_unknown_extensionless_path() -> None:
    from docsfy.renderer import _clean_code_fence_annotations

    result = _clean_code_fence_annotations("```src/somefile\ndata\n```")
    assert result == "```\ndata\n```"


def test_render_page_with_version() -> None:
    from docsfy.renderer import render_page

    html = render_page(
        markdown_content="# Test\nHello",
        page_title="Test",
        project_name="test-repo",
        tagline="A test",
        navigation=[],
        current_slug="test",
        version="2.1.0",
    )
    assert "v2.1.0" in html
    assert "footer-version" in html


def test_render_page_without_version() -> None:
    from docsfy.renderer import render_page

    html = render_page(
        markdown_content="# Test\nHello",
        page_title="Test",
        project_name="test-repo",
        tagline="A test",
        navigation=[],
        current_slug="test",
    )
    assert "footer-version" not in html


def test_render_index_with_version() -> None:
    from docsfy.renderer import render_index

    html = render_index(
        project_name="test-repo",
        tagline="A test",
        navigation=[],
        version="1.0.0",
    )
    assert "v1.0.0" in html
    assert "footer-version" in html


def test_render_site_passes_version(tmp_path: Path) -> None:
    from docsfy.renderer import render_site

    plan = {
        "project_name": "test-repo",
        "tagline": "A test",
        "navigation": [
            {
                "group": "Getting Started",
                "pages": [{"slug": "intro", "title": "Introduction"}],
            },
        ],
        "version": "3.0.0",
    }
    pages = {"intro": "# Introduction\nHello world"}
    output_dir = tmp_path / "site"
    render_site(plan=plan, pages=pages, output_dir=output_dir)
    index_html = (output_dir / "index.html").read_text()
    assert "v3.0.0" in index_html
    page_html = (output_dir / "intro.html").read_text()
    assert "v3.0.0" in page_html


def test_prerender_mermaid_replaces_block() -> None:
    import subprocess
    from unittest.mock import patch

    from docsfy.renderer import _prerender_mermaid

    md = "# Title\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\nMore text"

    # Test with mmdc available and succeeding
    with patch("docsfy.renderer.shutil.which", return_value="/usr/bin/mmdc"):
        with patch("docsfy.renderer.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            with patch("pathlib.Path.read_text", return_value="<svg>diagram</svg>"):
                result = _prerender_mermaid(md)
    assert "mermaid-diagram" in result and "<svg>" in result


def test_prerender_mermaid_no_mermaid_blocks() -> None:
    from docsfy.renderer import _prerender_mermaid

    md = "# Title\n\n```python\nprint('hello')\n```\n"
    result = _prerender_mermaid(md)
    assert result == md


def test_prerender_mermaid_fallback_on_failure() -> None:
    import subprocess
    from unittest.mock import patch

    from docsfy.renderer import _prerender_mermaid

    md = "# Title\n\n```mermaid\ninvalid syntax {{{\n```\n"
    with patch("docsfy.renderer.shutil.which", return_value="/usr/bin/mmdc"):
        with patch("docsfy.renderer.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "mmdc")
            result = _prerender_mermaid(md)
    assert "```mermaid" in result
    assert "invalid syntax" in result


def test_prerender_mermaid_multiple_blocks() -> None:
    from docsfy.renderer import _prerender_mermaid

    md = "```mermaid\nflowchart LR\n  A-->B\n```\n\nText\n\n```mermaid\nsequenceDiagram\n  A->>B: Hello\n```\n"
    result = _prerender_mermaid(md)
    assert "Text" in result


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
