# AI-Readable Documentation with llms.txt

Make your project's documentation instantly consumable by AI tools, LLM agents, and chatbots by pointing them at the `llms.txt` and `llms-full.txt` files that docsfy generates automatically with every documentation site.

## Prerequisites

- A docsfy documentation site that has been generated and is in **ready** status
- The URL of your documentation site (either the docsfy server URL or a static hosting URL)

## Quick Example

Every generated documentation site includes two machine-readable files at its root. Access them by appending the filename to your doc site URL:

```
# Structured index of all pages
https://your-server/docs/my-project/llms.txt

# Complete documentation in a single file
https://your-server/docs/my-project/llms-full.txt
```

Feed the full documentation to an AI assistant in one command:

```bash
curl -s https://your-server/docs/my-project/llms-full.txt | llm -s "How do I configure authentication?"
```

## What Gets Generated

docsfy produces two complementary files following the [llms.txt standard](https://llmstxt.org/):

| File | Purpose | Best For |
|------|---------|----------|
| `llms.txt` | Structured index with page titles, links, and descriptions | Quick lookup, deciding which pages to read, lightweight context |
| `llms-full.txt` | All page content concatenated into one file | Full-context queries, RAG ingestion, comprehensive analysis |

Both files are plain text and require no authentication beyond what your docsfy server enforces.

## The llms.txt Index File

The `llms.txt` file provides a structured table of contents. Here's what the format looks like:

```
# My Project

> A brief tagline describing the project

## Getting Started

- [Installation](installation.md): How to install and configure the project
- [Quick Start](quickstart.md): Get up and running in five minutes

## API Reference

- [REST API](rest-api.md): Complete endpoint reference
- [Authentication](authentication.md): API keys and token management
```

Each entry includes:

- **Page title** — the human-readable name
- **Link** — relative path to the markdown source (`.md` extension)
- **Description** — one-line summary of the page content

Pages are organized under their navigation group headings, matching the sidebar structure of the HTML documentation site.

## The llms-full.txt Complete File

The `llms-full.txt` file concatenates every page's markdown content into a single file, separated by `---` dividers:

```
# My Project

> A brief tagline describing the project

---

Source: installation.md

# Installation

Follow these steps to install...

---

Source: quickstart.md

# Quick Start

This guide walks you through...

---
```

Each page section starts with a `Source:` line identifying the original file, followed by the full markdown content of that page.

## Accessing llms.txt Files

### By URL

The files live at the root of every documentation site. The URL depends on how you access the docs:

| Access Pattern | llms.txt URL |
|---|---|
| Latest variant | `/docs/{project}/llms.txt` |
| Specific variant | `/docs/{project}/{branch}/{provider}/{model}/llms.txt` |

Replace `llms.txt` with `llms-full.txt` for the complete content file.

```bash
# Latest variant
curl https://your-server/docs/my-project/llms.txt

# Specific branch and AI variant
curl https://your-server/docs/my-project/main/cursor/gpt-5.4-xhigh-fast/llms.txt
```

### From Downloaded Sites

When you download a documentation site using the CLI or dashboard, the archive includes both files at the site root:

```bash
docsfy download my-project --output ./docs
cat ./docs/llms.txt
cat ./docs/llms-full.txt
```

See [Managing Projects and Variants](managing-projects.html) for download instructions.

### HTML Discovery

Every generated page includes `<link>` tags in the HTML `<head>` for automatic discovery:

```html
<link rel="alternate" type="text/plain" title="LLM Documentation Index" href="llms.txt">
<link rel="alternate" type="text/plain" title="LLM Full Documentation" href="llms-full.txt">
```

Links to both files also appear in the footer of every page and in a banner on the documentation homepage. AI crawlers and tools that follow `rel="alternate"` links will find them automatically.

## Using llms.txt with AI Tools

### Claude, ChatGPT, and Other Chat Interfaces

Paste the URL directly into your conversation:

```
Read https://your-server/docs/my-project/llms-full.txt and then answer:
How do I set up webhook notifications?
```

Or download and attach the file if URL fetching isn't supported:

```bash
curl -s https://your-server/docs/my-project/llms-full.txt > project-docs.txt
# Attach project-docs.txt to your chat
```

> **Tip:** Use `llms.txt` (the index) first when you only need to identify which pages are relevant, then fetch specific `.md` files for detail. This saves tokens when working with large documentation sets.

### Cursor, Windsurf, and AI Code Editors

Point your AI coding assistant at the documentation for context-aware code suggestions:

1. Download the full docs file into your project:

   ```bash
   curl -s https://your-server/docs/my-project/llms-full.txt > .llms-full.txt
   ```

2. Reference it in your prompts or add it to your editor's context files

### Command-Line AI Tools

Pipe documentation directly to CLI-based AI tools:

```bash
# Ask a question with full documentation context
curl -s https://your-server/docs/my-project/llms-full.txt | \
  llm -s "Summarize the authentication options"

# Search the index to find relevant pages first
curl -s https://your-server/docs/my-project/llms.txt | grep -i "auth"
```

## Advanced Usage

### RAG Pipeline Ingestion

The `llms-full.txt` file is ideal for loading into a RAG (Retrieval-Augmented Generation) pipeline. Each page is separated by `---` dividers and labeled with `Source:` headers, making it straightforward to split into chunks:

```python
import requests

response = requests.get("https://your-server/docs/my-project/llms-full.txt")
content = response.text

# Split into individual pages
pages = content.split("\n---\n")

for page in pages:
    lines = page.strip().split("\n")
    # Find the Source: line to identify the page
    source = next((l for l in lines if l.startswith("Source:")), None)
    if source:
        filename = source.replace("Source: ", "").strip()
        page_content = "\n".join(lines[lines.index(source) + 1:]).strip()
        # Ingest into your vector store
        # vector_store.add(filename, page_content)
```

### Automating Documentation Fetches in CI/CD

Keep an up-to-date copy of your AI-readable docs alongside your code:

```bash
# In your CI pipeline, after docs are generated:
curl -sf https://your-server/docs/my-project/llms-full.txt -o docs/llms-full.txt
curl -sf https://your-server/docs/my-project/llms.txt -o docs/llms.txt
```

See [Common Workflow Recipes](recipes-common-workflows.html) for more CI/CD automation patterns.

### Multi-Branch Documentation

Each branch variant gets its own independent `llms.txt` and `llms-full.txt` files. This means you can point AI tools at the documentation for a specific branch:

```bash
# Main branch docs
curl https://your-server/docs/my-project/main/cursor/gpt-5.4-xhigh-fast/llms-full.txt

# Dev branch docs
curl https://your-server/docs/my-project/dev/cursor/gpt-5.4-xhigh-fast/llms-full.txt
```

> **Note:** The files reflect only the pages that were successfully generated. If a page was skipped due to an invalid slug, it won't appear in either file.

### Using the Index to Fetch Individual Pages

The `llms.txt` index links to `.md` files. You can fetch individual pages for focused context instead of loading everything:

```bash
# 1. Read the index to find relevant pages
curl -s https://your-server/docs/my-project/llms.txt

# 2. Fetch just the page you need (markdown source)
curl -s https://your-server/docs/my-project/authentication.md
```

This is useful when your documentation is large and you want to minimize token usage. Every page exists as both an `.html` file (for humans) and an `.md` file (for AI tools) at the same URL path.

## Troubleshooting

**Files return 404**
The documentation must be in **ready** status. If generation is still in progress or has failed, the files won't exist yet. Check your project status in the dashboard or with `docsfy list`.

**Files are empty or missing pages**
Pages with invalid slugs are filtered out during rendering. If your `llms.txt` shows fewer pages than expected, check the generation logs for "Skipping invalid slug" warnings.

**Authentication required**
If your docsfy server requires authentication, include your credentials when fetching:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://your-server/docs/my-project/llms-full.txt
```

See [Managing Users and Access Control](managing-users.html) for details on API keys and access permissions.

## Related Pages

- [Browsing Generated Documentation](browsing-docs.html)
- [Managing Projects and Variants](managing-projects.html)
- [Common Workflow Recipes](recipes-common-workflows.html)
- [Generating Documentation](generating-docs.html)
- [Managing Users and Access Control](managing-users.html)