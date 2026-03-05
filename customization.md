# Customization

docsfy generates polished static HTML documentation sites using Jinja2 templates and bundled CSS/JS assets. This page explains how to customize the templates, styling, assets, and site structure to fit your documentation needs.

## Site Structure Overview

Every generated documentation project follows a consistent filesystem layout under `/data/projects/`:

```
/data/projects/{project-name}/
  plan.json             # Documentation structure from AI planner
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # Final rendered HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

The `site/` directory contains the fully self-contained static site. You can download it as a `.tar.gz` archive via the API and host it anywhere:

```bash
curl -O http://localhost:8000/api/projects/my-project/download
tar -xzf my-project.tar.gz
```

## Jinja2 Templates

docsfy uses [Jinja2](https://jinja.palletsprojects.com/) as its templating engine. The HTML Renderer (Stage 4 of the generation pipeline) converts markdown pages and `plan.json` into polished static HTML by rendering each page through Jinja2 templates with the bundled CSS/JS assets.

### Template Location

Templates live in the `docsfy/templates/` directory within the application package:

```
docsfy/
  templates/
    base.html           # Base layout with common structure
    page.html           # Individual documentation page
    index.html          # Landing/home page
```

### Base Template Blocks

The base template defines the overall HTML structure and exposes blocks that child templates and customizations can override. Key blocks include:

```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ page.title }} - {{ project.name }}{% endblock %}</title>
    {% block head_css %}
    <link rel="stylesheet" href="assets/style.css">
    <link rel="stylesheet" href="assets/highlight.css">
    {% endblock %}
    {% block head_extra %}{% endblock %}
</head>
<body>
    {% block sidebar %}
    <nav class="sidebar">
        <!-- Navigation generated from plan.json -->
    </nav>
    {% endblock %}

    <main>
        {% block content %}{% endblock %}
    </main>

    {% block scripts %}
    <script src="assets/highlight.js"></script>
    <script src="assets/search.js"></script>
    <script src="assets/theme-toggle.js"></script>
    {% endblock %}
    {% block scripts_extra %}{% endblock %}
</body>
</html>
```

### Template Context Variables

When rendering each page, the following context variables are available in templates:

| Variable | Type | Description |
|----------|------|-------------|
| `project.name` | `str` | Project name derived from the repository |
| `project.repo_url` | `str` | Source repository URL |
| `page.title` | `str` | Current page title |
| `page.content` | `str` | Rendered HTML content from markdown |
| `page.slug` | `str` | URL-safe page identifier |
| `navigation` | `list` | Sidebar navigation hierarchy from `plan.json` |
| `pages` | `list` | All pages in the documentation site |
| `current_page` | `str` | Slug of the currently rendered page |

### Overriding Templates

To customize the generated HTML structure, you can provide your own Jinja2 templates. Place custom templates in a directory and ensure the renderer can locate them. Because the renderer processes templates during Stage 4 of the pipeline, customizations apply at generation time.

**Extending the base template:**

```html
{% extends "base.html" %}

{% block head_extra %}
<link rel="stylesheet" href="assets/custom.css">
<link rel="icon" href="assets/favicon.ico">
{% endblock %}

{% block sidebar %}
<nav class="sidebar custom-sidebar">
    <div class="logo">
        <img src="assets/logo.svg" alt="{{ project.name }}">
    </div>
    {{ super() }}
</nav>
{% endblock %}

{% block scripts_extra %}
<script src="assets/analytics.js"></script>
{% endblock %}
```

> **Tip:** Use `{{ super() }}` within a block to include the parent template's content alongside your additions, rather than replacing it entirely.

## CSS Assets

### Default Stylesheet

The bundled `style.css` provides the default styling for all generated documentation sites. It includes:

- Responsive layout with sidebar navigation
- Dark and light theme support via CSS custom properties
- Card layouts for feature highlights
- Callout boxes for notes, warnings, and informational content
- Typography optimized for documentation readability
- Mobile-friendly responsive design

### Theme System (Dark/Light Mode)

docsfy uses CSS custom properties (variables) to implement its theme system. The `data-theme` attribute on the `<html>` element controls which theme is active:

```css
/* Light theme (default) */
:root,
[data-theme="light"] {
    --color-bg: #ffffff;
    --color-text: #1a1a2e;
    --color-heading: #16213e;
    --color-link: #0f3460;
    --color-sidebar-bg: #f8f9fa;
    --color-sidebar-text: #333333;
    --color-sidebar-active: #0f3460;
    --color-code-bg: #f4f4f4;
    --color-border: #e0e0e0;
    --color-callout-note: #e3f2fd;
    --color-callout-warning: #fff3e0;
    --color-callout-info: #e8f5e9;
}

/* Dark theme */
[data-theme="dark"] {
    --color-bg: #1a1a2e;
    --color-text: #e0e0e0;
    --color-heading: #e8e8e8;
    --color-link: #64b5f6;
    --color-sidebar-bg: #16213e;
    --color-sidebar-text: #cccccc;
    --color-sidebar-active: #64b5f6;
    --color-code-bg: #2d2d44;
    --color-border: #333355;
    --color-callout-note: #1a237e;
    --color-callout-warning: #4e342e;
    --color-callout-info: #1b5e20;
}
```

### Custom CSS Overrides

To apply custom styles to your generated site, add a `custom.css` file to the `site/assets/` directory after generation. Reference these variables to maintain theme compatibility:

```css
/* custom.css - Consistent with dark/light themes */
.sidebar {
    width: 280px;
    background-color: var(--color-sidebar-bg);
    border-right: 1px solid var(--color-border);
}

.content h1 {
    color: var(--color-heading);
    border-bottom: 2px solid var(--color-link);
    padding-bottom: 0.5em;
}

/* Custom callout style */
.callout.custom {
    background-color: var(--color-callout-info);
    border-left: 4px solid var(--color-link);
    padding: 1em;
    margin: 1em 0;
    border-radius: 4px;
}
```

> **Warning:** If you modify files in the `site/` directory directly, your changes will be overwritten on the next generation or incremental update. For persistent customizations, modify the templates or asset sources before generation.

### Callout Boxes

The default stylesheet includes styling for three callout types that the AI content generator uses when writing documentation pages:

| Type | Usage | Visual Style |
|------|-------|-------------|
| Note | General supplementary information | Blue-tinted background |
| Warning | Important cautions or caveats | Orange-tinted background |
| Info | Helpful tips and extra context | Green-tinted background |

Callouts are rendered as styled `<div>` elements:

```html
<div class="callout note">
    <strong>Note:</strong> This is supplementary information.
</div>

<div class="callout warning">
    <strong>Warning:</strong> This action cannot be undone.
</div>
```

## JavaScript Assets

docsfy bundles three JavaScript files that provide interactive functionality in the generated site.

### Theme Toggle (`theme-toggle.js`)

Handles dark/light mode switching with local storage persistence:

```javascript
// Theme preference is stored in localStorage
// and applied on page load to prevent flash of wrong theme
const toggle = document.querySelector('.theme-toggle');
toggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
});
```

The user's theme preference persists across page loads and is applied before the page renders to prevent a flash of unstyled content.

### Client-Side Search (`search.js`)

Search is powered by a client-side index using [lunr.js](https://lunrjs.com/) (or a similar library). During Stage 4 of the generation pipeline, a `search-index.json` file is built containing the searchable content from all pages:

```json
{
  "pages": [
    {
      "slug": "getting-started",
      "title": "Getting Started",
      "content": "Stripped plain-text content for indexing..."
    }
  ]
}
```

The search interface loads this index on the client side, enabling fast, offline-capable full-text search with no server round-trips.

### Syntax Highlighting (`highlight.js`)

Code blocks in the generated documentation are syntax-highlighted using [highlight.js](https://highlightjs.org/). The renderer applies language-specific highlighting based on the fenced code block language identifiers from the markdown source:

````markdown
```python
def hello():
    print("Hello, world!")
```
````

> **Tip:** The AI content generator automatically includes language identifiers in fenced code blocks based on the source repository's languages, so syntax highlighting works out of the box.

### Adding Custom JavaScript

To add custom scripts (analytics, widgets, interactive components), use the `scripts_extra` block in a custom template:

```html
{% block scripts_extra %}
<script>
    // Custom initialization
    document.addEventListener('DOMContentLoaded', () => {
        // Add copy-to-clipboard buttons on code blocks
        document.querySelectorAll('pre code').forEach((block) => {
            const button = document.createElement('button');
            button.className = 'copy-btn';
            button.textContent = 'Copy';
            button.addEventListener('click', () => {
                navigator.clipboard.writeText(block.textContent);
                button.textContent = 'Copied!';
                setTimeout(() => button.textContent = 'Copy', 2000);
            });
            block.parentElement.style.position = 'relative';
            block.parentElement.appendChild(button);
        });
    });
</script>
{% endblock %}
```

## Customizing the Documentation Plan

The `plan.json` file drives the entire site structure — navigation, page ordering, and content hierarchy. It is generated by the AI Planner in Stage 2 of the pipeline.

### Plan Structure

```json
{
  "name": "my-project",
  "pages": [
    {
      "slug": "index",
      "title": "Introduction",
      "description": "Overview and getting started guide",
      "section": "Getting Started"
    },
    {
      "slug": "installation",
      "title": "Installation",
      "description": "How to install and configure the project",
      "section": "Getting Started"
    },
    {
      "slug": "api-reference",
      "title": "API Reference",
      "description": "Complete API documentation",
      "section": "Reference"
    }
  ],
  "sections": [
    {
      "name": "Getting Started",
      "order": 1
    },
    {
      "name": "Reference",
      "order": 2
    }
  ]
}
```

### Modifying the Plan

You can edit `plan.json` directly to customize the documentation structure before or after generation:

- **Reorder pages** by changing their position in the `pages` array or adjusting section `order` values
- **Add new pages** by inserting entries and providing corresponding markdown files in `cache/pages/`
- **Remove pages** by deleting entries from the plan (the cached markdown and rendered HTML can be cleaned up separately)
- **Rename sections** to change the sidebar navigation grouping

After modifying `plan.json`, re-run the HTML Renderer (Stage 4) to regenerate the site with the updated structure.

> **Note:** If you trigger a full regeneration via `POST /api/generate`, the AI Planner will overwrite your custom `plan.json`. To preserve manual edits, back up your plan before regenerating.

### Sidebar Navigation

The sidebar navigation is automatically generated from `plan.json`. Pages are grouped by their `section` field and ordered according to the section `order` and page sequence within the `pages` array.

```html
<nav class="sidebar">
    <div class="sidebar-header">
        <h2>{{ project.name }}</h2>
        <button class="theme-toggle" aria-label="Toggle theme">🌓</button>
    </div>
    <div class="sidebar-search">
        <input type="text" placeholder="Search docs..." id="search-input">
    </div>
    {% for section in navigation %}
    <div class="sidebar-section">
        <h3>{{ section.name }}</h3>
        <ul>
            {% for page in section.pages %}
            <li class="{% if page.slug == current_page %}active{% endif %}">
                <a href="{{ page.slug }}.html">{{ page.title }}</a>
            </li>
            {% endfor %}
        </ul>
    </div>
    {% endfor %}
</nav>
```

## Responsive Design

The default layout is responsive and adapts to different screen sizes. The sidebar collapses into a toggleable menu on mobile viewports:

```css
/* Mobile responsive breakpoint */
@media (max-width: 768px) {
    .sidebar {
        position: fixed;
        transform: translateX(-100%);
        transition: transform 0.3s ease;
        z-index: 100;
    }

    .sidebar.open {
        transform: translateX(0);
    }

    main {
        margin-left: 0;
        width: 100%;
    }
}
```

> **Tip:** When adding custom styles, always test at mobile breakpoints. The sidebar, search overlay, and content area all reflow at `768px`.

## Post-Generation Customization

Since the final output in `site/` is plain static HTML, CSS, and JavaScript, you can apply any post-processing after generation:

1. **Inject analytics** — Add tracking scripts to each HTML file
2. **Add a custom favicon** — Place `favicon.ico` in `site/assets/`
3. **Include additional assets** — Add fonts, images, or third-party libraries to `site/assets/`
4. **Modify individual pages** — Edit the rendered HTML files directly
5. **Deploy anywhere** — The `site/` directory is fully self-contained with no server dependencies

```bash
# Download and customize a generated site
curl -o docs.tar.gz http://localhost:8000/api/projects/my-project/download
tar -xzf docs.tar.gz

# Add a custom favicon
cp my-favicon.ico site/assets/favicon.ico

# Inject a custom stylesheet into all pages
for f in site/*.html; do
    sed -i 's|</head>|<link rel="stylesheet" href="assets/custom.css"></head>|' "$f"
done

# Deploy to any static hosting
rsync -av site/ user@server:/var/www/docs/
```

> **Warning:** Direct edits to files in `site/` are overwritten on regeneration. For durable customizations, modify the Jinja2 templates or asset source files so changes persist across incremental updates.

## Incremental Updates and Customization

docsfy supports incremental updates that only regenerate pages affected by repository changes. Understanding this process is important for customization:

1. On re-generate, docsfy compares the current commit SHA against the stored SHA
2. If the repository has changed, the AI Planner re-evaluates the documentation structure
3. Only pages affected by the changes are regenerated
4. The HTML Renderer re-runs Stage 4 for the full site, applying templates and assets

Because Stage 4 always re-renders the full site from templates, any customizations made to the Jinja2 templates or source assets in `docsfy/templates/` and `docsfy/static/` are automatically applied during incremental updates. Customizations made directly to `site/` output files, however, will be lost.

> **Note:** Cached markdown in `cache/pages/*.md` is preserved across incremental updates unless the AI determines a page needs regeneration. You can manually edit cached markdown to make persistent content changes that survive re-renders.
