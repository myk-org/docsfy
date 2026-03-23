# Generated Output

Every successful `docsfy` run produces a self-contained static documentation bundle for one variant: project, branch, AI provider, and AI model. That bundle is what `docsfy` serves under `/docs/...`, what the download API returns as a `.tar.gz`, and what you can publish on any static file host.

For people, the primary output is the HTML site. The extra text artifacts such as `llms.txt` and `llms-full.txt` are there for AI and automation workflows.

> **Note:** The published output is the variant’s `site/` directory. `docsfy` also keeps internal generation files such as `plan.json` and cached page Markdown under `cache/pages/`, but those support regeneration rather than the public site.

## Published files

Each successful generation publishes the same core set of artifacts:

| Artifact | What it contains | What it is for |
| --- | --- | --- |
| `index.html` | The docs homepage | Landing page with project title, tagline, and navigation groups |
| `<slug>.html` | One rendered HTML page per generated doc page | Human-friendly browsing |
| `<slug>.md` | One Markdown copy per generated doc page | Reuse, downloads, text-based workflows, AI tooling |
| `search-index.json` | JSON search data | Client-side search in the published site |
| `llms.txt` | Compact index of Markdown pages | Lightweight AI-friendly map of the docs |
| `llms-full.txt` | All page Markdown concatenated into one file | Single-file ingestion for LLMs and other text tools |
| `assets/` | CSS and JavaScript bundle | Theme, search, code copy buttons, callouts, TOC highlighting, sidebar behavior, and GitHub badge support |
| `.nojekyll` | Empty marker file | Prevents Jekyll processing on GitHub Pages-style hosting |

The renderer in `src/docsfy/renderer.py` writes those published files directly:

```python
(output_dir / ".nojekyll").touch()

(output_dir / "index.html").write_text(index_html, encoding="utf-8")

(output_dir / f"{slug}.html").write_text(page_html, encoding="utf-8")
(output_dir / f"{slug}.md").write_text(md_content, encoding="utf-8")

search_index = _build_search_index(valid_pages, plan)
(output_dir / "search-index.json").write_text(
    json.dumps(search_index), encoding="utf-8"
)

llms_txt = _build_llms_txt(plan, navigation=filtered_navigation)
(output_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")

llms_full_txt = _build_llms_full_txt(
    plan, valid_pages, navigation=filtered_navigation
)
(output_dir / "llms-full.txt").write_text(llms_full_txt, encoding="utf-8")
```

> **Note:** `docsfy` recreates the entire `site/` directory on each render. If a page disappears in a newer generation, its old published files do not stay behind.

## What the bundle looks like

A generated site is a flat static bundle. Page filenames come from page slugs, so you get files like `introduction.html` and `introduction.md` at the site root.

```text
site/
  .nojekyll
  index.html
  introduction.html
  introduction.md
  quickstart.html
  quickstart.md
  search-index.json
  llms.txt
  llms-full.txt
  assets/
    style.css
    theme.js
    search.js
    copy.js
    callouts.js
    scrollspy.js
    codelabels.js
    github.js
```

The exact page filenames depend on the generated navigation and page slugs.

> **Warning:** `docsfy` only publishes path-safe page slugs. Slugs containing `/`, `\`, leading `.`, or `..` are treated as unsafe and skipped, so published pages are always flat files rather than nested directories.

## HTML pages

The HTML output is meant for people first. `index.html` is a real homepage, not just a redirect. It shows the project name, tagline, grouped navigation, and a “Get Started” link to the first page. Each generated page becomes its own `<slug>.html` file, with sidebar navigation, previous/next links, a footer, and an optional “On this page” table of contents.

The HTML pages pull their behavior from the generated `assets/` directory. In `src/docsfy/templates/_doc_base.html`, the published bundle includes:

```html
<script src="assets/theme.js"></script>
<script src="assets/search.js"></script>
<script src="assets/copy.js"></script>
<script src="assets/callouts.js"></script>
<script src="assets/scrollspy.js"></script>
<script src="assets/codelabels.js"></script>
<script src="assets/github.js"></script>
```

The page renderer also turns Markdown into HTML with fenced code blocks, syntax highlighting, tables, and a heading-based TOC:

```python
md = markdown.Markdown(
    extensions=["fenced_code", "codehilite", "tables", "toc"],
    extension_configs={
        "codehilite": {"css_class": "highlight", "guess_lang": False},
        "toc": {"toc_depth": "2-3"},
    },
)
md_text = _clean_code_fence_annotations(md_text)
md_text = _ensure_blank_lines(md_text)
content_html = _sanitize_html(md.convert(md_text))
```

In practice, that means the published site includes:

- a sidebar with section links
- a theme toggle
- keyboard-driven search
- code copy buttons
- code language labels
- “On this page” navigation for level 2 and level 3 headings
- styled callouts such as `> **Note:**`, `> **Warning:**`, and `> **Tip:**`

`docsfy` also sanitizes the generated HTML before writing it, removing script tags, forms, embedded objects, inline event handlers, and unsafe URLs.

> **Tip:** If you want output that can be hosted almost anywhere, this is exactly what `docsfy` produces: plain HTML, CSS, JavaScript, JSON, and Markdown files.

## Search index

`docsfy` ships search as part of the static bundle. There is no separate search service to run.

The generator writes `search-index.json` with one entry per page:

```python
index.append(
    {
        "slug": slug,
        "title": title_map.get(slug, slug),
        "content": content[:2000],
    }
)
```

The published search UI then loads that file in the browser and matches against both titles and content:

```javascript
fetch('search-index.json').then(function(r) { return r.json(); })
  .then(function(data) { index = data; }).catch(function() {});

var matches = index.filter(function(item) {
  return item.title.toLowerCase().includes(q) || item.content.toLowerCase().includes(q);
}).slice(0, 10);
```

That gives you a few useful guarantees:

- search works from the static bundle alone
- page titles are searchable
- page body text is searchable
- results are capped at 10 matches per query in the UI

> **Note:** The built-in search index stores the page title plus the first 2,000 characters of each page. That keeps the bundle small, but very deep matches later in a long page may not appear in search results.

## Markdown and LLM-friendly text files

### Markdown copies

For every published HTML page, `docsfy` also publishes a Markdown copy beside it. If you have `quickstart.html`, you also have `quickstart.md` in the same `site/` directory.

Those Markdown copies are useful when you want to:

- inspect the raw generated content without HTML wrapping
- diff generated content in a cleaner format
- reuse the docs in another publishing workflow
- feed the output into external tools that prefer text over HTML

This is separate from the internal page cache used during regeneration. The `site/*.md` files are part of the public output bundle.

### `llms.txt`

`llms.txt` is a compact index of the docs. It is grouped by navigation section and links to the published Markdown page copies, not the HTML pages.

This is how `src/docsfy/renderer.py` builds it:

```python
for group in nav:
    lines.extend([f"## {group.get('group', '')}", ""])
    for page in group.get("pages", []):
        desc = page.get("description", "")
        page_title = page.get("title", "")
        page_slug = page.get("slug", "")
        if desc:
            lines.append(f"- [{page_title}]({page_slug}.md): {desc}")
        else:
            lines.append(f"- [{page_title}]({page_slug}.md)")
```

That format makes `llms.txt` useful as a lightweight map of the generated docs: page titles, descriptions, and direct links to the Markdown copies.

### `llms-full.txt`

`llms-full.txt` is the single-file version. It concatenates every published page’s Markdown into one document, with a source label before each page:

```python
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
```

If you want the entire documentation set in one file, this is the artifact to use.

The generated site makes both files easy to discover. In `src/docsfy/templates/_doc_base.html`, they are exposed as alternate text resources:

```html
<link rel="alternate" type="text/plain" title="LLM Documentation Index" href="llms.txt">
<link rel="alternate" type="text/plain" title="LLM Full Documentation" href="llms-full.txt">
```

> **Tip:** Use `llms.txt` when you want a small index you can crawl page by page. Use `llms-full.txt` when you want one file to hand to an LLM, a RAG ingestion job, or any other text-processing pipeline.

## Where output lives

By default, `docsfy` stores generated data under `/data`. The published site for a variant lives under that root in a branch/provider/model-aware path.

From `src/docsfy/config.py`:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admin_key: str = ""
    ai_provider: str = "cursor"
    ai_model: str = "gpt-5.4-xhigh-fast"
    ai_cli_timeout: int = Field(default=60, gt=0)
    log_level: str = "INFO"
    data_dir: str = "/data"
```

From `docker-compose.yaml`:

```yaml
services:
  docsfy:
    volumes:
      - ./data:/data
```

And from `src/docsfy/storage.py`:

```python
def get_project_site_dir(
    name: str,
    ai_provider: str = "",
    ai_model: str = "",
    owner: str = "",
    branch: str = DEFAULT_BRANCH,
) -> Path:
    return get_project_dir(name, ai_provider, ai_model, owner, branch) / "site"
```

With the default configuration, that means a published site ends up at a path like this:

```text
/data/projects/<owner>/<project>/<branch>/<provider>/<model>/site/
```

This is why generated output is variant-aware: branch, provider, and model are part of the output identity, not just labels in the UI.

> **Note:** The default Docker setup already mounts `./data` into `/data`, so generated bundles persist outside the container without extra setup.

## Browsing and downloading output

`docsfy` exposes published output in two useful ways:

- browse a specific variant under `/docs/<project>/<branch>/<provider>/<model>/`
- browse the latest accessible variant under `/docs/<project>/`

The route definitions in `src/docsfy/main.py` are:

```python
@app.get("/docs/{project}/{branch}/{provider}/{model}/{path:path}")
async def serve_variant_docs(
    request: Request,
    project: str,
    branch: str,
    provider: str,
    model: str,
    path: str = "index.html",
) -> FileResponse:
```

```python
@app.get("/docs/{project}/{path:path}")
async def serve_docs(
    request: Request, project: str, path: str = "index.html"
) -> FileResponse:
```

You can also download the published site bundle as a `.tar.gz`. The CLI wraps the download API and uses predictable archive names:

```python
if branch and provider and model:
    url_path = (
        f"/api/projects/{name}/{branch}/{provider}/{model}/download{owner_qs}"
    )
    archive_name = f"{name}-{branch}-{provider}-{model}-docs.tar.gz"
else:
    url_path = f"/api/projects/{name}/download{owner_qs}"
    archive_name = f"{name}-docs.tar.gz"
```

Example CLI usage:

```shell
docsfy download my-repo -b main -p cursor -m gpt-5
docsfy download my-repo -b main -p cursor -m gpt-5 -o ./site-copy
```

The first command saves the archive in your current directory. The second downloads and extracts the bundle into `./site-copy`.

If you omit branch, provider, and model, `docsfy` downloads the latest accessible variant instead.

> **Note:** The download archive contains the published `site/` bundle. It is the static output you can browse or deploy, not the full internal project directory with caches and planning metadata.

## What users should expect

When a generation is ready, you should expect more than a single HTML file. `docsfy` publishes a complete static docs package:

- a browsable HTML site
- raw Markdown copies of every page
- a client-side search index
- compact and full-text LLM artifacts
- a bundle that is easy to serve, archive, and redeploy

That mix is what makes `docsfy` practical in day-to-day use: one generation gives you polished docs for people and portable text artifacts for everything else.
