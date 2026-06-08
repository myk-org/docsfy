# Browsing Generated Documentation

You want to read, search, and share the documentation that docsfy generates from your repositories. This guide walks you through the doc site's interface — navigation, search, theme switching, URL patterns, and how to share specific pages with teammates.

## Prerequisites

- A docsfy project with status **Ready** (see [Generating Documentation](generating-docs.html))
- Access to the docsfy server in your browser

## Opening Your Documentation

The fastest way to open a generated doc site is from the dashboard:

1. Log in to the docsfy dashboard
2. Select a project and variant from the sidebar tree
3. Click **View Documentation** — the doc site opens in a new tab

Alternatively, navigate directly by URL:

```
https://your-server/docs/my-project/main/cursor/gpt-5.4-xhigh-fast/
```

The URL pattern is:

```
/docs/{project-name}/{branch}/{provider}/{model}/
```

If you only know the project name, use the short URL to load the latest variant automatically:

```
https://your-server/docs/my-project/index.html
```

> **Tip:** The short URL (`/docs/{project-name}/`) always serves the most recently generated variant. Use the full URL when you need a specific branch or AI provider.

## Navigating the Doc Site

### Sidebar

The left sidebar contains the project name, a tagline, a search box, and a grouped navigation menu. Pages are organized into sections (e.g., "Getting Started", "Guides", "Reference"). The currently active page is highlighted.

On mobile screens, the sidebar is hidden. Tap the **hamburger menu** (☰) in the top bar to open it. Tap the overlay or a link to close it.

### Page Navigation

At the bottom of every page, **Previous** and **Next** links let you step through the documentation in order. Use these to read docs sequentially without returning to the sidebar.

### On This Page (Table of Contents)

On wide screens (1280px+), a right-hand sidebar shows an "On this page" panel that lists section headings. Click any heading to jump to that section. The panel highlights your current position as you scroll.

### Top Bar

The top bar includes:

- **Project name** — links back to the doc site home page
- **Search button** — opens the search modal (see below)
- **GitHub link** — links to the source repository with a live star count
- **Theme toggle** — switches between light and dark mode
- **docsfy badge** — links to the docsfy project

## Searching Documentation

Open the search modal using any of these methods:

- Press **⌘K** (Mac) or **Ctrl+K** (Windows/Linux)
- Click the **⌘K Search** button in the top bar
- Click the search box in the sidebar

Then type your query. Results appear instantly, showing matching page titles and a content preview with the match highlighted in context. The search covers all page titles and content.

Navigate results with:

| Key | Action |
|---|---|
| **↑ / ↓** | Move between results |
| **Enter** | Open the selected result |
| **Esc** | Close the search modal |

> **Note:** Search is entirely client-side — it loads a pre-built index when the page opens, so results appear with zero network latency.

## Switching Themes

Click the **sun/moon toggle** in the top-right corner to switch between light and dark mode. Your preference is saved in the browser and persists across sessions and pages.

The doc site defaults to light mode. If you've previously set a theme in the docsfy dashboard, the doc site will respect that same choice — both share the same saved preference.

## Copying Code Snippets

Hover over any code block to reveal a **Copy** button in the top-right corner. Click it to copy the code to your clipboard. The button briefly shows "Copied!" to confirm.

On touch devices, the Copy button is always visible without hovering.

## Sharing Doc URLs

Every doc page has a stable, shareable URL. To share a specific page with your team, copy the URL from your browser's address bar:

```
https://your-server/docs/my-project/main/cursor/gpt-5.4-xhigh-fast/quickstart.html
```

The URL components break down as:

| Segment | Description |
|---|---|
| `my-project` | Project name |
| `main` | Git branch |
| `cursor` | AI provider used |
| `gpt-5.4-xhigh-fast` | AI model used |
| `quickstart.html` | Page slug |

> **Tip:** To link to a specific section within a page, click the section heading and copy the updated URL with the anchor fragment (e.g., `quickstart.html#installation`).

## Switching Between Variants

A "variant" is a unique combination of branch, AI provider, and model. The same repository can have multiple variants — for example, docs generated from the `main` branch with one model and from the `dev` branch with another.

To switch between variants:

1. Return to the docsfy dashboard
2. Expand the project in the sidebar tree
3. Select the variant you want (grouped by branch)
4. Click **View Documentation**

Each variant has its own URL path, so you can bookmark different variants independently.

## Downloading Documentation

To download a complete doc site as an archive:

- **From the dashboard:** Select a variant and click **Download** to get a `.tar.gz` file
- **By URL:** Navigate to the download endpoint directly:

```
https://your-server/api/projects/my-project/main/cursor/gpt-5.4-xhigh-fast/download
```

The downloaded archive contains all HTML, CSS, JavaScript, and search index files — ready to host as a static site anywhere. See [Managing Projects and Variants](managing-projects.html) for more download options including the CLI.

## AI-Friendly Documentation Files

Every generated doc site includes machine-readable files for AI tools:

| File | Purpose |
|---|---|
| `llms.txt` | Structured index listing all pages with titles, slugs, and descriptions |
| `llms-full.txt` | Complete documentation content concatenated into a single file |

Access these from:

- The **footer** of every page (links to both files)
- The **landing page** banner labeled "AI-friendly documentation"
- Direct URL: `https://your-server/docs/my-project/main/cursor/gpt-5.4-xhigh-fast/llms.txt`

Feed these files to AI assistants, chatbots, or code editors that support the `llms.txt` convention.

## Advanced Usage

### Printing Documentation

The doc site includes print-optimized styles. When you print a page (or save as PDF), the sidebar, top bar, and navigation controls are automatically hidden, leaving clean article content that fills the page width.

### Mobile Browsing

The doc site is fully responsive:

- **Sidebar** collapses into a slide-out drawer, activated by the hamburger menu
- **Table of contents** panel hides on screens narrower than 1280px
- **Code blocks** scroll horizontally if they exceed the viewport width
- **Card grid** on the landing page stacks into a single column

### Accessing Raw Markdown

Every page is also available as raw Markdown by changing the `.html` extension to `.md`:

```
https://your-server/docs/my-project/main/cursor/gpt-5.4-xhigh-fast/quickstart.md
```

This is useful for importing content into other tools or for quick reference without rendering.

## Troubleshooting

**Search returns no results**
The search index loads asynchronously when the page opens. If you search immediately after the page loads on a slow connection, the index may not be ready yet. Wait a moment and try again.

**"File not found" when opening a doc URL**
The variant may have been deleted or regenerated with a different provider/model. Use the short URL (`/docs/{project-name}/`) to load the latest available variant, or check the dashboard for current variants.

**Theme resets on a different browser**
Theme preference is stored in your browser's `localStorage`. Each browser maintains its own setting independently.

**Sidebar scroll position resets**
The sidebar remembers its scroll position within a session. If you open docs in a new tab or window, the sidebar scrolls the active page link into view automatically.

## Related Pages

- [Generating Documentation](generating-docs.html)
- [Managing Projects and Variants](managing-projects.html)
- [AI-Readable Documentation with llms.txt](llms-txt-ai-readable-docs.html)
- [Getting Started with docsfy](quickstart.html)
- [Common Workflow Recipes](recipes-common-workflows.html)