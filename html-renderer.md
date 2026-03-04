# HTML Renderer & Theming

The HTML Renderer is Stage 4 of the docsfy generation pipeline. It takes the AI-generated markdown pages and `plan.json` structure and produces a polished, self-contained static HTML site with sidebar navigation, syntax highlighting, search, and responsive theming.

## How Rendering Works

The renderer sits at the end of the four-stage pipeline:

```
Clone Repo → AI Planner (plan.json) → AI Content Generator (*.md) → HTML Renderer (site/)
```

It reads two inputs:

1. **`plan.json`** — the documentation structure, sections, and navigation hierarchy produced by the AI Planner (Stage 2)
2. **Markdown files** — the AI-generated page content cached at `/data/projects/{name}/cache/pages/*.md` (Stage 3)

And produces a complete static site at `/data/projects/{name}/site/`.

### Output Structure

```
/data/projects/{project-name}/site/
├── index.html              # Landing page
├── *.html                  # One HTML file per documentation page
├── assets/
│   ├── style.css           # Main stylesheet (dark/light themes)
│   ├── theme-toggle.js     # Dark/light mode switching
│   ├── search.js           # Client-side full-text search
│   └── highlight.js        # Code syntax highlighting
└── search-index.json       # Pre-built search index
```

## Jinja2 Templating

The renderer uses **Jinja2** as its template engine and the **Python markdown library** for markdown-to-HTML conversion. Each page defined in `plan.json` is rendered through a Jinja2 template that injects the converted HTML content into a consistent page shell with navigation, header, and footer.

```python
from jinja2 import Environment, FileSystemLoader
import markdown

env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("page.html")

md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
html_content = md.convert(page_markdown)

rendered = template.render(
    title=page["title"],
    content=html_content,
    navigation=plan["navigation"],
    sections=plan["sections"],
)
```

The template receives the full navigation tree from `plan.json` so it can render the sidebar consistently across every page.

## Sidebar Navigation

The sidebar is generated directly from the `plan.json` navigation hierarchy. The AI Planner analyzes the repository and produces a structured JSON plan containing pages, sections, and their ordering:

```json
{
  "pages": [
    {
      "slug": "getting-started",
      "title": "Getting Started",
      "section": "introduction",
      "description": "Installation and quickstart guide"
    }
  ],
  "sections": [
    {
      "slug": "introduction",
      "title": "Introduction"
    },
    {
      "slug": "api-reference",
      "title": "API Reference"
    }
  ],
  "navigation": [
    {
      "section": "introduction",
      "pages": ["getting-started", "configuration"]
    },
    {
      "section": "api-reference",
      "pages": ["endpoints", "authentication"]
    }
  ]
}
```

The Jinja2 template iterates over this structure to build a hierarchical sidebar with collapsible sections:

```html
<nav class="sidebar">
  {% for group in navigation %}
  <div class="nav-section">
    <h3 class="nav-section-title">{{ sections[group.section].title }}</h3>
    <ul class="nav-list">
      {% for page_slug in group.pages %}
      <li class="nav-item {% if page_slug == current_page %}active{% endif %}">
        <a href="{{ page_slug }}.html">{{ pages[page_slug].title }}</a>
      </li>
      {% endfor %}
    </ul>
  </div>
  {% endfor %}
</nav>
```

The currently active page is highlighted in the sidebar, and on mobile devices the sidebar collapses into a toggleable menu.

## Syntax Highlighting via highlight.js

All fenced code blocks in the markdown content receive syntax highlighting through **highlight.js**. The library is bundled as a static asset at `assets/highlight.js` — no CDN dependency is required, keeping the site fully self-contained.

Code blocks in the source markdown use standard fenced syntax with language identifiers:

````markdown
```python
def generate_docs(repo_url: str) -> None:
    """Generate documentation for a repository."""
    clone_repo(repo_url)
    plan = run_ai_planner()
    pages = generate_pages(plan)
    render_html(pages, plan)
```
````

The rendered HTML page initializes highlight.js on load:

```html
<link rel="stylesheet" href="assets/highlight.css">
<script src="assets/highlight.js"></script>
<script>hljs.highlightAll();</script>
```

highlight.js auto-detects the language from the `class` attribute set by the markdown processor (`language-python`, `language-javascript`, etc.) and applies appropriate token coloring. The highlight theme integrates with the dark/light mode toggle so code blocks remain readable in both themes.

> **Tip:** The AI Content Generator (Stage 3) is instructed to always include language identifiers on fenced code blocks. This ensures highlight.js applies the correct syntax rules rather than relying on auto-detection.

## Callout Boxes

The renderer supports three types of callout boxes for emphasizing important content: **note**, **warning**, and **info**. These are generated by the AI Content Generator as styled blockquotes in the markdown source and rendered as visually distinct containers.

### Markdown Source

```markdown
> **Note:** This feature requires Python 3.12 or later.

> **Warning:** Regenerating a project will overwrite all existing pages.

> **Info:** You can download the generated site as a `.tar.gz` archive for self-hosting.
```

### Rendered Output

The renderer applies CSS classes to transform these blockquotes into colored callout panels:

```css
.callout {
  border-left: 4px solid;
  border-radius: 4px;
  padding: 12px 16px;
  margin: 16px 0;
}

.callout-note {
  border-color: #3b82f6;
  background-color: rgba(59, 130, 246, 0.08);
}

.callout-warning {
  border-color: #f59e0b;
  background-color: rgba(245, 158, 11, 0.08);
}

.callout-info {
  border-color: #8b5cf6;
  background-color: rgba(139, 92, 246, 0.08);
}
```

> **Note:** Callout colors adapt automatically when switching between dark and light themes, using adjusted opacity values to maintain contrast.

## Card Layouts

The renderer supports card-based layouts for visually organizing groups of related content such as feature overviews, API endpoint summaries, or quickstart options. Cards are rendered as CSS grid items with consistent styling:

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin: 24px 0;
}

.card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  transition: box-shadow 0.2s ease;
}

.card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.card h3 {
  margin-top: 0;
  font-size: 1.1rem;
}

.card p {
  color: var(--text-secondary);
  font-size: 0.9rem;
}
```

The grid automatically adjusts column count based on available width — three columns on desktop, two on tablet, and a single column on mobile.

## Dark/Light Theme Toggle

The site ships with both dark and light themes, controlled by a toggle in the page header. Theme switching is handled by `assets/theme-toggle.js`, which persists the user's preference in `localStorage`:

```javascript
const toggle = document.querySelector('.theme-toggle');
const root = document.documentElement;

function setTheme(theme) {
  root.setAttribute('data-theme', theme);
  localStorage.setItem('docsfy-theme', theme);
}

// Restore saved preference or follow system preference
const saved = localStorage.getItem('docsfy-theme');
if (saved) {
  setTheme(saved);
} else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
  setTheme('dark');
}

toggle.addEventListener('click', () => {
  const current = root.getAttribute('data-theme');
  setTheme(current === 'dark' ? 'light' : 'dark');
});
```

Theme colors are defined as CSS custom properties, making it straightforward to restyle the entire site:

```css
:root,
[data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f8f9fa;
  --text-primary: #1a1a2e;
  --text-secondary: #555;
  --border-color: #e2e8f0;
  --sidebar-bg: #f1f5f9;
  --accent-color: #3b82f6;
  --code-bg: #f5f5f5;
}

[data-theme="dark"] {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --border-color: #2d3748;
  --sidebar-bg: #16213e;
  --accent-color: #60a5fa;
  --code-bg: #2d2d2d;
}
```

> **Tip:** The theme toggle respects the operating system's `prefers-color-scheme` media query on first visit. If the user has their OS set to dark mode, docsfy defaults to the dark theme automatically.

## Responsive Design

The site layout adapts to different screen sizes using CSS media queries and a flexible layout structure:

```css
.page-layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 260px;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border-color);
}

.main-content {
  flex: 1;
  max-width: 800px;
  padding: 32px 40px;
  margin: 0 auto;
}

/* Tablet */
@media (max-width: 1024px) {
  .sidebar {
    width: 220px;
  }

  .main-content {
    padding: 24px 20px;
  }
}

/* Mobile */
@media (max-width: 768px) {
  .page-layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    height: auto;
    position: fixed;
    z-index: 100;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .main-content {
    padding: 16px;
    max-width: 100%;
  }

  .card-grid {
    grid-template-columns: 1fr;
  }
}
```

### Breakpoints

| Breakpoint | Target | Sidebar Behavior |
|------------|--------|-----------------|
| > 1024px | Desktop | Fixed sidebar, 260px wide |
| 768–1024px | Tablet | Narrower sidebar, 220px |
| < 768px | Mobile | Sidebar hidden, toggle to slide in |

On mobile, a hamburger menu icon appears in the header. Tapping it slides the sidebar in as an overlay, and tapping outside or selecting a page dismisses it.

## Search Indexing

The renderer builds a client-side search index so users can find content without a server-side search backend. This keeps the generated site fully static and self-hostable.

### Index Generation

During rendering, the content of every page is indexed and written to `search-index.json`:

```python
import json

search_entries = []
for page in plan["pages"]:
    search_entries.append({
        "slug": page["slug"],
        "title": page["title"],
        "section": page["section"],
        "body": strip_markdown(page_content[page["slug"]]),
    })

with open(site_dir / "search-index.json", "w") as f:
    json.dump(search_entries, f)
```

The `body` field contains the plain-text content of each page with markdown syntax stripped, enabling accurate full-text matching.

### Client-Side Search

The `assets/search.js` script loads the index on page load and provides instant search results as the user types:

```javascript
let searchIndex = [];

fetch('search-index.json')
  .then(res => res.json())
  .then(data => { searchIndex = data; });

function search(query) {
  const terms = query.toLowerCase().split(/\s+/);
  return searchIndex
    .map(entry => {
      const text = (entry.title + ' ' + entry.body).toLowerCase();
      const score = terms.reduce((s, t) => s + (text.includes(t) ? 1 : 0), 0);
      return { ...entry, score };
    })
    .filter(entry => entry.score > 0)
    .sort((a, b) => b.score - a.score);
}
```

Search results display the page title, its section, and a text snippet showing the matched context. Selecting a result navigates directly to the relevant page.

> **Note:** The search index is generated at render time, not at query time. Regenerating a project (via `POST /api/generate`) rebuilds the search index automatically.

## Rendering Configuration

The renderer uses technology choices defined in the project's technology stack:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Template engine | Jinja2 | Page layout and navigation rendering |
| Markdown processor | Python `markdown` library | Markdown-to-HTML conversion |
| Syntax highlighting | highlight.js (bundled) | Code block coloring |
| Theme system | CSS custom properties | Dark/light mode support |
| Search | Client-side JavaScript | Full-text search over `search-index.json` |

### Markdown Extensions

The Python `markdown` library is configured with extensions for full-featured rendering:

```python
import markdown

md = markdown.Markdown(extensions=[
    "fenced_code",   # ```language fenced code blocks
    "tables",        # GitHub-style tables
    "toc",           # Table of contents generation
])
```

### Asset Bundling

All CSS and JavaScript assets are bundled into the `assets/` directory of each generated site. No external CDN requests are made at runtime, so the site works fully offline once generated:

- `style.css` — all layout, typography, theme, callout, and card styles
- `theme-toggle.js` — dark/light mode persistence and switching
- `search.js` — client-side search index loading and query matching
- `highlight.js` — syntax highlighting library and language grammars

> **Warning:** The `site/` directory is fully overwritten on each regeneration. Do not manually edit files inside the generated site — any changes will be lost when the project is regenerated.

## Serving the Rendered Site

The generated static site can be accessed in two ways:

### Direct Serving via the API

docsfy serves the rendered HTML directly through the FastAPI endpoint:

```
GET /docs/{project}/{path}
```

For example, `GET /docs/my-project/getting-started.html` serves the rendered Getting Started page for `my-project`.

### Download for Self-Hosting

The entire site can be downloaded as a `.tar.gz` archive:

```
GET /api/projects/{name}/download
```

The archive contains the complete `site/` directory, including all HTML pages, assets, and the search index. Extract it and serve from any static file host (Nginx, Apache, GitHub Pages, S3, etc.).
