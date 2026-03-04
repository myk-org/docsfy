# HTML Theming & Output

docsfy generates polished, Mintlify-quality static HTML documentation sites from your repository's AI-generated markdown content. The HTML Renderer (Stage 4 of the generation pipeline) converts markdown pages and the `plan.json` navigation structure into a fully self-contained static site with sidebar navigation, dark/light theme toggle, client-side search, syntax highlighting, callout boxes, and responsive design.

## How the HTML Renderer Works

The HTML Renderer is the final stage of the docsfy generation pipeline. It takes two inputs:

1. **`plan.json`** — the documentation structure produced by the AI Planner (Stage 2), defining pages, sections, and navigation hierarchy.
2. **Cached markdown files** — the AI-generated content for each page, stored at `/data/projects/{name}/cache/pages/*.md`.

Using Jinja2 templates and bundled CSS/JS assets, the renderer produces a complete static site at `/data/projects/{name}/site/`.

```
/data/projects/{project-name}/
  site/                         # final rendered HTML
    index.html
    *.html
    assets/
      style.css                 # theme and layout styles
      search.js                 # client-side search logic
      theme-toggle.js           # dark/light mode switching
      highlight.js              # code syntax highlighting
    search-index.json           # pre-built search index
```

> **Note:** The entire `site/` directory is self-contained. You can download it via `GET /api/projects/{name}/download` as a `.tar.gz` archive and host it anywhere — no server-side runtime required.

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Templating | Jinja2 | HTML page generation from markdown content |
| Markdown processing | Python markdown library | Convert `.md` files to HTML fragments |
| Styling | Custom CSS (bundled) | Layout, theming, responsive design |
| Search | lunr.js (or similar) | Client-side full-text search |
| Code highlighting | highlight.js | Syntax highlighting for code blocks |
| Theme toggle | Custom JS (bundled) | Dark/light mode switching |

## Sidebar Navigation

The sidebar is automatically generated from the `plan.json` structure produced by the AI Planner. It renders a hierarchical navigation tree reflecting the pages and sections discovered in your repository.

### Navigation Hierarchy

The AI Planner analyzes your repository and outputs a structured plan:

```json
{
  "pages": [
    {
      "slug": "getting-started",
      "title": "Getting Started",
      "section": "Introduction"
    },
    {
      "slug": "configuration",
      "title": "Configuration",
      "section": "Usage"
    },
    {
      "slug": "api-reference",
      "title": "API Reference",
      "section": "Usage"
    }
  ]
}
```

The Jinja2 template groups pages by section and renders them as a collapsible sidebar with section headings. The current page is highlighted automatically in the navigation tree.

### Sidebar Behavior

- **Active page highlighting** — the current page is visually distinguished in the sidebar.
- **Section grouping** — pages are organized under their parent section headings.
- **Persistent state** — expanded/collapsed sections persist during navigation.
- **Mobile collapse** — on small screens the sidebar collapses into a hamburger menu (see [Responsive Design](#responsive-design)).

## Dark / Light Theme Toggle

docsfy ships with a built-in dark/light theme toggle, powered by `theme-toggle.js` in the site assets directory.

### How It Works

The theme toggle button is rendered in the site header. Clicking it switches between dark and light color schemes by toggling a `data-theme` attribute on the document root. The user's preference is persisted to `localStorage` so it survives page reloads and navigation.

```
assets/
  theme-toggle.js     # toggle logic + localStorage persistence
  style.css           # contains both light and dark theme variables
```

### Theme Persistence

1. On page load, `theme-toggle.js` checks `localStorage` for a saved theme preference.
2. If no preference is found, it respects the operating system's preference via `prefers-color-scheme`.
3. When the user clicks the toggle, the new theme is applied immediately and saved to `localStorage`.

> **Tip:** The theme toggle respects the user's OS-level dark mode setting by default. Users only need to click the toggle if they want to override their system preference.

### CSS Theme Variables

Both themes are defined using CSS custom properties in `style.css`. This approach makes it straightforward to customize colors without modifying JavaScript:

```css
/* Light theme (default) */
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f8f9fa;
  --text-primary: #1a1a2e;
  --text-secondary: #4a4a6a;
  --border-color: #e2e8f0;
  --accent-color: #6366f1;
  --sidebar-bg: #f1f5f9;
  --code-bg: #f4f4f5;
}

/* Dark theme */
[data-theme="dark"] {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --border-color: #334155;
  --accent-color: #818cf8;
  --sidebar-bg: #16213e;
  --code-bg: #0f172a;
}
```

All UI components reference these variables so that switching themes updates the entire site consistently.

## Client-Side Search

docsfy includes a client-side full-text search powered by a JavaScript search library (lunr.js or similar). Search runs entirely in the browser — no server is needed after the static site is generated.

### Search Index

During HTML rendering, docsfy builds a `search-index.json` file that contains the searchable content from every page in the documentation:

```
site/
  search-index.json    # pre-built index of all page content
  assets/
    search.js          # search UI and query logic
```

The index includes page titles, section headings, and body text, enabling fast full-text search across the entire documentation site.

### Search UI

The search interface is embedded in the site header. Users can:

- Click the search box or use a keyboard shortcut to activate search.
- Type a query to see matching results in real time.
- Click a result to navigate directly to the matching page.

Results are ranked by relevance and display the page title along with a snippet of matching content.

> **Note:** Because search is fully client-side, it works even when the static site is hosted on a simple file server or CDN with no backend. The `search-index.json` file is loaded once on first search and cached by the browser.

### Search Scope

The search index covers:

- **Page titles** — weighted highest for relevance.
- **Section headings** — weighted for structural matches.
- **Body content** — full-text search across all prose and code examples.

## Syntax Highlighting

All code blocks in the generated documentation are syntax-highlighted using [highlight.js](https://highlightjs.org/). The highlight.js library is bundled as a site asset at `assets/highlight.js`.

### Supported Languages

highlight.js provides automatic language detection for fenced code blocks. When a language is specified in the markdown source, that language's grammar is used directly:

````markdown
```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```
````

This renders with full Python syntax highlighting — keywords, decorators, type hints, and string literals are all colored appropriately.

### Theme-Aware Highlighting

Code block colors adapt to the current theme. In light mode, code blocks use a light background (`--code-bg`) with dark syntax colors. In dark mode, the palette inverts to provide comfortable reading with reduced eye strain. The highlight.js theme is coordinated with the site's CSS custom properties so switching themes updates code blocks seamlessly.

### Inline Code

Inline code (`` `like this` ``) is styled with a subtle background color and monospace font but does not receive syntax highlighting. Only fenced code blocks with triple backticks are processed by highlight.js.

## Callout Boxes

docsfy supports styled callout boxes for notes, warnings, and informational content. These are rendered from markdown blockquote patterns into visually distinct, themed containers.

### Callout Types

Three callout types are supported:

| Type | Purpose | Visual Style |
|------|---------|-------------|
| **Note** | General supplementary information | Blue accent with info icon |
| **Warning** | Cautions and potential pitfalls | Amber/yellow accent with warning icon |
| **Info** | Contextual tips and helpful details | Green accent with lightbulb icon |

### Markdown Syntax

Callouts are written as blockquotes with a bold type prefix:

```markdown
> **Note:** The entire site directory is self-contained and can be hosted anywhere.

> **Warning:** Regenerating documentation will overwrite the existing site output.

> **Info:** You can download the static site as a `.tar.gz` for self-hosting.
```

The HTML Renderer detects these patterns during markdown-to-HTML conversion and wraps them in styled `<div>` elements with the appropriate CSS classes:

```html
<div class="callout callout-note">
  <p>The entire site directory is self-contained and can be hosted anywhere.</p>
</div>

<div class="callout callout-warning">
  <p>Regenerating documentation will overwrite the existing site output.</p>
</div>
```

### Callout Styling

Callouts adapt to both light and dark themes through CSS custom properties. Each type has a distinct left border color and background tint:

```css
.callout {
  border-left: 4px solid;
  padding: 1rem 1.25rem;
  margin: 1.5rem 0;
  border-radius: 0.375rem;
}

.callout-note {
  border-left-color: var(--callout-note-border);
  background-color: var(--callout-note-bg);
}

.callout-warning {
  border-left-color: var(--callout-warning-border);
  background-color: var(--callout-warning-bg);
}

.callout-info {
  border-left-color: var(--callout-info-border);
  background-color: var(--callout-info-bg);
}
```

## Responsive Design

The generated HTML site is fully responsive and optimized for desktop, tablet, and mobile screens. All layout, navigation, and interactive features adapt to the viewport width using CSS media queries and flexible layouts.

### Breakpoints

The site layout responds to standard breakpoints:

| Breakpoint | Behavior |
|-----------|----------|
| **Desktop** (≥1024px) | Full layout with persistent sidebar, inline search, and spacious content area |
| **Tablet** (768px–1023px) | Sidebar collapses to an overlay; content area expands to full width |
| **Mobile** (<768px) | Hamburger menu for navigation; stacked layout; touch-friendly tap targets |

### Sidebar on Mobile

On screens narrower than 1024px, the sidebar collapses and is accessible via a hamburger menu button in the header. Tapping the button slides the sidebar in as an overlay. Tapping outside the sidebar or selecting a page dismisses it.

### Content Layout

The main content area uses a fluid layout with a maximum width constraint for readability:

```css
.content {
  max-width: 48rem;
  margin: 0 auto;
  padding: 2rem 1.5rem;
  width: 100%;
}

@media (max-width: 768px) {
  .content {
    padding: 1rem;
  }
}
```

### Responsive Elements

- **Code blocks** — horizontally scrollable on small screens to prevent layout overflow.
- **Tables** — wrapped in a scrollable container for wide data tables.
- **Images** — constrained to `max-width: 100%` to prevent overflow.
- **Search** — adapts to a full-width modal on mobile devices.
- **Theme toggle** — remains accessible in the header across all screen sizes.

> **Tip:** The static site is designed to perform well on all devices without any additional configuration. Responsive behavior is handled entirely by the bundled CSS.

## Serving and Hosting

docsfy provides two ways to access the generated HTML site:

### Direct Serving via API

The FastAPI server serves generated docs directly:

```
GET /docs/{project}/{path}
```

For example, after generating docs for a project named `my-app`:

```
GET /docs/my-app/             → index.html
GET /docs/my-app/config       → config.html
GET /docs/my-app/assets/style.css → static asset
```

### Self-Hosting (Static Download)

Download the entire site as a `.tar.gz` archive for hosting anywhere:

```
GET /api/projects/{name}/download
```

The downloaded archive contains the complete `site/` directory — HTML, CSS, JS, and the search index. You can deploy it to:

- **GitHub Pages** — push the contents to a `gh-pages` branch.
- **Netlify / Vercel** — drag-and-drop the extracted directory.
- **Nginx / Apache** — serve the directory as a static file root.
- **S3 + CloudFront** — upload to an S3 bucket with static website hosting.

> **Note:** No server-side runtime is required for self-hosting. The site is entirely static — all interactivity (search, theme toggle, navigation) runs client-side in JavaScript.

## Asset Summary

The complete set of bundled assets in the generated site:

| Asset | File | Description |
|-------|------|-------------|
| Stylesheet | `assets/style.css` | All layout, theming (light + dark), callouts, and responsive styles |
| Search | `assets/search.js` | Client-side search UI and query engine |
| Theme toggle | `assets/theme-toggle.js` | Dark/light mode switching with localStorage persistence |
| Syntax highlighting | `assets/highlight.js` | Code block syntax highlighting via highlight.js |
| Search index | `search-index.json` | Pre-built full-text search index for all documentation pages |
