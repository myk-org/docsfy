# LLM-Friendly Output

Docsfy automatically generates machine-readable text files alongside the HTML documentation site. Every project build produces two complementary files — `llms.txt` and `llms-full.txt` — designed for consumption by large language models and AI-powered tools.

## What is llms.txt?

The `llms.txt` convention provides a standardized way for websites to expose their content in a format optimized for LLMs. Instead of requiring AI tools to parse HTML, CSS, and JavaScript, `llms.txt` files offer clean markdown that fits naturally into LLM context windows.

Docsfy produces two files following this convention:

| File | Purpose | Typical Size |
|------|---------|-------------|
| `llms.txt` | Structured index of all documentation pages with links and descriptions | ~2 KB |
| `llms-full.txt` | Complete documentation content concatenated into a single file | Varies with project size |

## How It Works

LLM output generation is built into the `render_site` function in `renderer.py` and runs automatically at the end of every site build. There is no configuration required and no way to disable it — both files are always generated as first-class outputs.

### Build Pipeline Integration

The LLM files are generated in the final rendering stage, after all AI-generated page content is ready:

```
POST /api/generate
  └─ _run_generation()
       ├─ run_planner()          → documentation plan (JSON)
       ├─ generate_all_pages()   → page content (markdown)
       └─ render_site()          → final output
            ├─ index.html
            ├─ {slug}.html       (per page)
            ├─ {slug}.md         (per page)
            ├─ search-index.json
            ├─ llms.txt          ← generated here
            └─ llms-full.txt     ← generated here
```

The relevant code in `renderer.py` (lines 222–227):

```python
# Generate llms.txt files
llms_txt = _build_llms_txt(plan)
(output_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")

llms_full_txt = _build_llms_full_txt(plan, valid_pages)
(output_dir / "llms-full.txt").write_text(llms_full_txt, encoding="utf-8")
```

Both functions receive the same documentation plan and page content that drive the HTML generation, ensuring the LLM output is always consistent with the rendered site.

## llms.txt — The Index File

The `llms.txt` file serves as a table of contents. It lists every documentation page organized by navigation group, with optional descriptions for each page.

### Format

```markdown
# Project Name

> Project tagline or description

## Section Name

- [Page Title](page-slug.md): Brief description of the page
- [Another Page](another-page.md): What this page covers

## Another Section

- [Page Title](page-slug.md)
```

### Structure Breakdown

- **Heading (`#`)**: The project name from the documentation plan
- **Blockquote (`>`)**: The project tagline (included only if present)
- **Section headings (`##`)**: Navigation group names matching the sidebar structure
- **List items (`-`)**: Links to individual pages using `[Title](slug.md)` syntax, with an optional description after a colon

### Generator Implementation

From `renderer.py` (lines 109–127):

```python
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
```

### Example Output

For a project with two navigation groups, the generated `llms.txt` might look like:

```markdown
# my-api-server

> A fast REST API framework for Python

## Getting Started

- [Introduction](introduction.md): Overview of the project and its goals
- [Installation](installation.md): How to install and configure the server
- [Quick Start](quick-start.md): Build your first API endpoint in minutes

## API Reference

- [Routes](routes.md): Defining HTTP routes and handlers
- [Middleware](middleware.md): Request/response middleware pipeline
- [Configuration](configuration.md): Server configuration options
```

## llms-full.txt — The Complete Content File

The `llms-full.txt` file concatenates all documentation pages into a single file. This is designed for scenarios where an LLM needs the full documentation context — for example, when answering questions about a project or generating code that uses a library.

### Format

```markdown
# Project Name

> Project tagline

---

Source: page-slug.md

# Page Title

Full markdown content of the page...

---

Source: another-page.md

# Another Page Title

Full markdown content of this page...

---
```

### Structure Breakdown

- **Header**: Same project name and tagline as `llms.txt`
- **Separator (`---`)**: Horizontal rules delimit each page's content
- **Source marker**: A `Source: slug.md` line before each page identifies its origin
- **Content**: The complete markdown content of each page, in navigation order

### Generator Implementation

From `renderer.py` (lines 130–152):

```python
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
```

### Page Ordering

Pages appear in `llms-full.txt` in **navigation order** — the same order they appear in the sidebar and in `llms.txt`. The generator iterates through navigation groups and their pages sequentially, ensuring a logical reading flow.

## Input Data Model

Both generators consume the documentation plan, a JSON structure produced by the AI planner. The plan schema is defined in `prompts.py`:

```json
{
  "project_name": "string - project name",
  "tagline": "string - one-line project description",
  "navigation": [
    {
      "group": "string - section group name",
      "pages": [
        {
          "slug": "string - URL-friendly page identifier",
          "title": "string - human-readable page title",
          "description": "string - brief description of what this page covers"
        }
      ]
    }
  ]
}
```

This same plan drives HTML rendering, search index generation, and LLM output — a single source of truth for all output formats.

The corresponding Pydantic models in `models.py`:

```python
class DocPage(BaseModel):
    slug: str
    title: str
    description: str = ""

class NavGroup(BaseModel):
    group: str
    pages: list[DocPage]

class DocPlan(BaseModel):
    project_name: str
    tagline: str = ""
    navigation: list[NavGroup] = Field(default_factory=list)
```

## Page Descriptions

The `description` field on each page in the plan controls what appears after the colon in `llms.txt` entries. When the AI planner generates the documentation plan, it produces a brief description for each page:

```python
if desc:
    lines.append(f"- [{page_title}]({page_slug}.md): {desc}")
else:
    lines.append(f"- [{page_title}]({page_slug}.md)")
```

Pages without descriptions are listed with just their title and link. This keeps the index clean while still providing context where available.

## Slug Validation and Security

Before any content reaches the LLM generators, slugs are validated to prevent path traversal attacks. The `render_site` function filters out unsafe slugs before passing pages to either builder:

```python
# Filter out invalid slugs
valid_pages: dict[str, str] = {}
for slug, content in pages.items():
    if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
        logger.warning(f"Skipping invalid slug: {slug}")
    else:
        valid_pages[slug] = content
```

Only pages with valid slugs are included in `llms.txt` and `llms-full.txt`. This same validation is also enforced earlier in the pipeline during page generation (`generator.py`, line 74).

> **Note:** Invalid slugs are silently excluded from the output with a warning log. If pages are missing from your LLM files, check the logs for "Skipping invalid slug" messages.

## Output File Location

Generated files are written to the project's site directory:

```
/data/projects/{project-name}/
├── site/
│   ├── index.html
│   ├── introduction.html
│   ├── introduction.md
│   ├── search-index.json
│   ├── llms.txt
│   ├── llms-full.txt
│   └── assets/
│       └── style.css
└── cache/
    └── pages/
        └── introduction.md
```

Both files are served as static content through the docs endpoint:

```
GET /docs/{project}/llms.txt
GET /docs/{project}/llms-full.txt
```

The serving is handled by the `serve_docs` endpoint in `main.py`, which serves any file from the site directory:

```python
@app.get("/docs/{project}/{path:path}")
async def serve_docs(project: str, path: str = "index.html") -> FileResponse:
    project = _validate_project_name(project)
    site_dir = get_project_site_dir(project)
    file_path = site_dir / path
    # Path traversal check
    try:
        file_path.resolve().relative_to(site_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
```

## Downloading LLM Files

The project download endpoint packages the entire site directory — including both LLM files — into a `.tar.gz` archive:

```
GET /api/projects/{name}/download
```

This returns a compressed archive containing all site files:

```
my-project/
├── index.html
├── llms.txt
├── llms-full.txt
├── ...
```

## Relationship to Markdown Page Files

In addition to `llms.txt` and `llms-full.txt`, docsfy writes individual `.md` files for each page alongside the HTML:

```python
(output_dir / f"{slug}.html").write_text(page_html, encoding="utf-8")
(output_dir / f"{slug}.md").write_text(md_content, encoding="utf-8")
```

This creates a three-tier access pattern for AI consumers:

1. **`llms.txt`** — Discover what documentation exists (lightweight index)
2. **Individual `.md` files** — Fetch specific pages by slug (targeted retrieval)
3. **`llms-full.txt`** — Load everything at once (full context)

The links in `llms.txt` point to these individual `.md` files using relative paths (e.g., `introduction.md`), enabling AI tools to selectively fetch only the pages they need.

> **Tip:** For AI tools with limited context windows, use `llms.txt` to identify relevant pages, then fetch individual `.md` files. For tools with large context windows, `llms-full.txt` provides everything in a single request.

## Use Cases

### AI Code Assistants

Tools like Claude, Cursor, and GitHub Copilot can ingest `llms-full.txt` to gain complete understanding of a project's documentation, enabling more accurate code suggestions and answers.

### Documentation Search

The structured `llms.txt` index allows AI agents to quickly identify which documentation pages are relevant to a query before fetching full content.

### RAG Pipelines

Retrieval-Augmented Generation systems can use `llms.txt` as a document manifest and `llms-full.txt` as a pre-chunked corpus, with `Source:` markers providing natural document boundaries for splitting.

### CI/CD Integration

Since LLM files are generated automatically with every build, they stay in sync with the HTML documentation without any additional workflow steps.
