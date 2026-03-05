# Generated Site Features

Every documentation site built by docsfy ships with a polished set of interactive features out of the box. No additional configuration, plugins, or JavaScript bundles are required — all features are built into the generated output and work with static hosting.

## Dark/Light Theme Toggle

The generated site includes a theme toggle button in the top bar that switches between light and dark modes. The user's preference is persisted in `localStorage` and restored on subsequent visits. If no preference has been saved, the site automatically follows the operating system's color scheme.

```javascript
// From src/docsfy/static/theme.js
var stored = getTheme();
if (stored) document.documentElement.setAttribute('data-theme', stored);
else if (window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.setAttribute('data-theme', 'dark');
```

Theme switching works by toggling the `data-theme` attribute on the `<html>` element between `"light"` and `"dark"`. All colors are driven by CSS custom properties on `:root` (light) and `[data-theme="dark"]` (dark), enabling an instant, flicker-free transition:

```css
/* Light theme (default) */
:root {
    --bg-primary: #ffffff;
    --text-primary: #111827;
    --accent: #4f46e5;
}

/* Dark theme */
[data-theme="dark"] {
    --bg-primary: #0f1117;
    --text-primary: #e5e7eb;
    --accent: #818cf8;
}
```

Background and text colors transition smoothly:

```css
body {
    transition: background-color var(--transition-normal), color var(--transition-normal);
}
```

The toggle button displays a sun icon in dark mode and a moon icon in light mode, making the current state and available action immediately clear.

> **Tip:** The theme toggle respects `prefers-color-scheme` on first visit. Users who have set their OS to dark mode will see the dark theme automatically.

## Client-Side Search

The generated site includes full-text search with a keyboard-driven modal interface. Press **Cmd+K** (macOS) or **Ctrl+K** (Windows/Linux) to open the search modal from any page. The search input in the sidebar also opens the modal when clicked.

### Search Index

During site generation, docsfy builds a `search-index.json` file containing the title and first 2,000 characters of content for every page:

```python
# From src/docsfy/renderer.py
def _build_search_index(pages, plan):
    index = []
    for slug, content in pages.items():
        index.append({
            "slug": slug,
            "title": title_map.get(slug, slug),
            "content": content[:2000],
        })
    return index
```

The index is fetched once when the page loads and all searching happens client-side with no server round-trips.

### Search Modal

The modal provides real-time results as you type, matching against both page titles and content. Results display the page title and a context snippet showing where the match occurs:

```javascript
// From src/docsfy/static/search.js
var matches = index.filter(function(item) {
  return item.title.toLowerCase().includes(q) || item.content.toLowerCase().includes(q);
}).slice(0, 10);
```

Up to 10 results are displayed at a time, each showing a content preview with approximately 40 characters before and 60 characters after the matched term.

### Keyboard Navigation

The search modal supports full keyboard navigation:

| Key | Action |
|-----|--------|
| `Cmd+K` / `Ctrl+K` | Open search modal |
| `Esc` | Close search modal |
| `↑` / `↓` | Navigate between results |
| `Enter` | Open selected result |

Clicking the overlay behind the modal also closes it.

## Responsive Mobile Design

The generated site is fully responsive across desktop, tablet, and mobile screen sizes. The layout uses three CSS breakpoints to adapt the interface.

### Desktop (> 768px)

On desktop, the site displays a fixed 280px sidebar on the left with navigation, a main content area, and (on screens wider than 1280px) a table-of-contents sidebar on the right:

```css
.sidebar {
    position: fixed;
    width: var(--sidebar-width); /* 280px */
}

/* TOC appears on wide screens */
@media (min-width: 1280px) {
    .toc-sidebar { display: block; }
    .content { margin-right: 220px; }
}
```

### Tablet and Mobile (≤ 768px)

On smaller screens, the sidebar transforms into a slide-out drawer that appears from the left edge, triggered by a hamburger menu button in the top bar:

```css
@media (max-width: 768px) {
    .sidebar {
        transform: translateX(-100%);
        transition: transform var(--transition-normal);
    }
    .sidebar.open {
        transform: translateX(0);
    }
    .main-wrapper { margin-left: 0; }
    .card-grid { grid-template-columns: 1fr; }
}
```

A semi-transparent overlay covers the content when the sidebar is open, and clicking it closes the menu:

```javascript
// From src/docsfy/templates/page.html
if (overlay) {
    overlay.addEventListener('click', function() {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
    });
}
```

### Small Mobile (≤ 480px)

On narrow screens, typography scales down further for readability:

```css
@media (max-width: 480px) {
    .hero-title  { font-size: 1.75rem; }
    .article-body h1 { font-size: 1.5rem; }
    .article-body h2 { font-size: 1.25rem; }
    .article-body h3 { font-size: 1.125rem; }
}
```

> **Note:** The table of contents sidebar is only visible on screens 1280px and wider. On narrower viewports it is hidden entirely to preserve content space.

## Code Syntax Highlighting

Code blocks are syntax-highlighted at build time using Python's [Pygments](https://pygments.org/) library via the `codehilite` Markdown extension. No client-side JavaScript is needed for highlighting.

### Markdown Configuration

The renderer configures syntax highlighting with the `codehilite` and `fenced_code` extensions:

```python
# From src/docsfy/renderer.py
md = markdown.Markdown(
    extensions=["fenced_code", "codehilite", "tables", "toc"],
    extension_configs={
        "codehilite": {"css_class": "highlight", "guess_lang": False},
        "toc": {"toc_depth": "2-3"},
    },
)
```

Setting `guess_lang` to `False` ensures that only explicitly tagged code blocks receive highlighting, avoiding false positives on plain text blocks.

### Language Labels

The generated site automatically detects the language specified in fenced code blocks and displays a label in the top-right corner. Over 30 languages are recognized:

```javascript
// From src/docsfy/static/codelabels.js
var labelMap = {
  'python': 'Python',  'js': 'JavaScript',  'ts': 'TypeScript',
  'bash': 'Bash',      'json': 'JSON',      'yaml': 'YAML',
  'html': 'HTML',      'css': 'CSS',        'go': 'Go',
  'rust': 'Rust',      'java': 'Java',      'ruby': 'Ruby',
  'sql': 'SQL',        'dockerfile': 'Dockerfile',
  'cpp': 'C++',        'csharp': 'C#',      'swift': 'Swift',
  // ... and more
};
```

### Color Scheme

Code blocks use a dark background (`#1e1e2e`) regardless of the active site theme, with syntax token colors inspired by the One Dark palette:

| Token | Color | Example |
|-------|-------|---------|
| Keywords | `#c678dd` | `def`, `class`, `import` |
| Strings | `#98c379` | `"hello"`, `'world'` |
| Functions | `#61afef` | `print()`, `render()` |
| Numbers | `#d19a66` | `42`, `3.14` |
| Comments | `#6a737d` | `# this is a comment` |
| Classes | `#e5c07b` | `MyClass` |

## Table of Contents with Scroll Spy

Each documentation page includes an auto-generated table of contents on the right side of the viewport. The TOC is generated server-side from the Markdown content using the `toc` extension, limited to h2 and h3 headings:

```python
"toc": {"toc_depth": "2-3"},
```

### Scroll Spy

As you scroll through the page, the currently visible section is highlighted in the TOC. The scroll spy uses `requestAnimationFrame` for smooth, performant updates:

```javascript
// From src/docsfy/static/scrollspy.js
var ticking = false;
window.addEventListener('scroll', function() {
  if (!ticking) {
    window.requestAnimationFrame(function() {
      updateActive();
      ticking = false;
    });
    ticking = true;
  }
});
```

The active link receives a visual accent — the left border and text color change to the site's accent color:

```css
.toc-container a {
    padding-left: 0.75rem;
    border-left: 2px solid var(--border-primary);
}

.toc-container a.toc-active {
    color: var(--accent);
    border-left-color: var(--accent);
    font-weight: 500;
}
```

The TOC header "On this page" is sticky at the top of the sidebar so it remains visible while scrolling through long lists of sections.

> **Note:** The TOC sidebar is only visible on screens 1280px and wider. It is rendered in the HTML on all pages but hidden via CSS on narrower viewports.

## Copy-to-Clipboard

Every code block in the generated site includes a "Copy" button. The button appears when you hover over a code block and copies the full content to the clipboard with a single click.

```javascript
// From src/docsfy/static/copy.js
if (navigator.clipboard && navigator.clipboard.writeText) {
  navigator.clipboard.writeText(text).then(function() {
    btn.textContent = 'Copied!';
    setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
  });
}
```

### Behavior

- **Hover to reveal**: The button is invisible by default and fades in when the mouse enters the code block (`opacity: 0` → `opacity: 1`)
- **Touch devices**: On devices without hover support, the button is always visible at reduced opacity (`opacity: 0.7`)
- **Feedback**: After clicking, the button text changes to "Copied!" for 2 seconds, then reverts to "Copy"
- **Fallback**: For browsers that do not support the Clipboard API, a fallback using `document.execCommand('copy')` is provided

```css
.copy-btn { opacity: 0; transition: opacity 0.15s ease; }
pre:hover .copy-btn { opacity: 1; }

/* Always visible on touch devices */
@media (hover: none) {
    .copy-btn { opacity: 0.7; }
}
```

## Callout Boxes

Docsfy transforms standard Markdown blockquotes into styled callout boxes when the first word is a recognized keyword in bold. Five callout types are supported:

### Syntax

Write callouts using standard Markdown blockquote syntax with a bold keyword:

```markdown
> **Note:** This is informational content.

> **Warning:** Be careful with this operation.

> **Tip:** Here's a helpful suggestion.

> **Danger:** This action is irreversible.

> **Important:** Don't skip this step.
```

### Supported Keywords

Each keyword maps to a callout type and visual style:

| Callout Type | Keywords | Border Color |
|-------------|----------|-------------|
| Note | `Note`, `Info` | Blue (`#3b82f6`) |
| Warning | `Warning`, `Caution` | Amber (`#f59e0b`) |
| Tip | `Tip`, `Hint` | Green (`#10b981`) |
| Danger | `Danger`, `Error` | *(default styling)* |
| Important | `Important` | *(default styling)* |

### How It Works

The `callouts.js` script scans all blockquotes on page load, detects `<strong>` tags, and adds the appropriate CSS class:

```javascript
// From src/docsfy/static/callouts.js
var text = firstStrong.textContent.toLowerCase().replace(':', '').trim();
if (text === 'note' || text === 'info') type = 'note';
else if (text === 'warning' || text === 'caution') type = 'warning';
else if (text === 'tip' || text === 'hint') type = 'tip';
```

Styled callouts have a colored left border, tinted background, and rounded corners:

```css
blockquote.callout-note {
    border-left: 4px solid #3b82f6;
    background: rgba(59, 130, 246, 0.08);
    padding: 1rem 1.25rem;
    border-radius: 0 8px 8px 0;
    margin: 1.5rem 0;
}
```

> **Tip:** Blockquotes that don't start with a recognized keyword are rendered as standard blockquotes with a neutral left border.

## Prev/Next Navigation

Every documentation page includes previous and next page links at the bottom, making it easy to read through the documentation sequentially. The page order follows the navigation structure defined in your `plan.json`.

### Rendering

The links are rendered from the page template with directional labels and page titles:

```html
<!-- From src/docsfy/templates/page.html -->
<nav class="page-nav">
    {% if prev_page %}
    <a href="{{ prev_page.slug }}.html" class="page-nav-link page-nav-prev">
        <span class="page-nav-label">Previous</span>
        <span class="page-nav-title">{{ prev_page.title }}</span>
    </a>
    {% endif %}
    {% if next_page %}
    <a href="{{ next_page.slug }}.html" class="page-nav-link page-nav-next">
        <span class="page-nav-label">Next</span>
        <span class="page-nav-title">{{ next_page.title }}</span>
    </a>
    {% endif %}
</nav>
```

### Page Order

The renderer builds an ordered list of all pages from the navigation groups and assigns each page a reference to its neighbors:

```python
# From src/docsfy/renderer.py
for idx, slug_info in enumerate(valid_slug_order):
    prev_page = valid_slug_order[idx - 1] if idx > 0 else None
    next_page = valid_slug_order[idx + 1] if idx < len(valid_slug_order) - 1 else None
```

The first page in the navigation has no "Previous" link, and the last page has no "Next" link. On hover, the navigation links highlight with the accent color and a subtle shadow:

```css
.page-nav-link:hover {
    border-color: var(--accent);
    box-shadow: 0 2px 8px rgba(79, 70, 229, 0.1);
}
```

> **Note:** Page order is determined by the sequence of groups and pages in your `plan.json` navigation structure. Reordering entries there changes the prev/next links throughout the site.
