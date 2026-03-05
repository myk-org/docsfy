# Plan JSON Schema

## Overview

The `plan.json` file is the central artifact produced by the AI Planner (Stage 2 of the generation pipeline). It defines the complete structure of a documentation site — pages, sections, and navigation hierarchy — and serves as the contract between all downstream stages.

```
Clone Repo ──▸ AI Planner ──▸ plan.json ──▸ AI Content Generator ──▸ HTML Renderer
                                  │                  │                     │
                                  │            reads plan to         reads plan to
                                  │          know which pages      build sidebar &
                                  └──────── to generate content    render site layout
```

The AI Planner analyzes the cloned repository — its source code, configuration files, READMEs, and project structure — and outputs a structured JSON plan that determines what documentation pages will be generated and how they are organized in the navigation sidebar.

## File Location

Each project's plan is stored on the filesystem at a well-known path:

```
/data/projects/{project-name}/
  plan.json             # doc structure from AI
  cache/
    pages/*.md          # AI-generated markdown (cached for incremental updates)
  site/                 # final rendered HTML
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

The `plan.json` file sits at the root of the project directory, alongside the `cache/` and `site/` directories it governs.

## Schema Definition

### Root Object

The top-level `plan.json` object describes the documentation site and contains the navigation hierarchy.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | `string` | Yes | The display name of the documentation site, typically derived from the project name |
| `description` | `string` | Yes | A brief summary of the project and its documentation |
| `sections` | `Section[]` | Yes | Ordered array of navigation sections that define the sidebar hierarchy |

```json
{
  "title": "My Project",
  "description": "API reference and guides for My Project",
  "sections": [
    ...
  ]
}
```

### Section Object

Sections are the top-level groupings in the sidebar navigation. Each section contains one or more pages.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | `string` | Yes | The section heading displayed in the sidebar navigation |
| `pages` | `Page[]` | Yes | Ordered array of pages within this section |

```json
{
  "title": "Getting Started",
  "pages": [
    {
      "slug": "introduction",
      "title": "Introduction",
      "description": "Overview of the project, what it does, and who it's for"
    },
    {
      "slug": "installation",
      "title": "Installation",
      "description": "How to install and configure the project"
    }
  ]
}
```

### Page Object

Each page represents a single documentation page. The slug determines both the cached markdown filename and the rendered HTML filename.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slug` | `string` | Yes | URL-safe identifier used as the filename for both the markdown cache and the HTML output |
| `title` | `string` | Yes | The page title displayed in the sidebar and as the page heading |
| `description` | `string` | Yes | Brief description of the page content; used by the AI Content Generator as a writing prompt and by the renderer for metadata |

```json
{
  "slug": "api-reference",
  "title": "API Reference",
  "description": "Complete reference for all REST API endpoints, request/response formats, and authentication"
}
```

> **Note:** The `slug` value must be unique across all sections. It maps directly to file paths — a slug of `"api-reference"` produces `cache/pages/api-reference.md` and `site/api-reference.html`.

## Complete Example

Below is a full `plan.json` example for a typical project:

```json
{
  "title": "docsfy",
  "description": "Documentation for docsfy, an AI-powered documentation site generator",
  "sections": [
    {
      "title": "Getting Started",
      "pages": [
        {
          "slug": "introduction",
          "title": "Introduction",
          "description": "What docsfy is, key features, and how it works at a high level"
        },
        {
          "slug": "quickstart",
          "title": "Quickstart",
          "description": "Get docsfy running locally in under five minutes with Docker Compose"
        }
      ]
    },
    {
      "title": "Configuration",
      "pages": [
        {
          "slug": "environment-variables",
          "title": "Environment Variables",
          "description": "All supported environment variables for AI providers, models, and runtime settings"
        },
        {
          "slug": "ai-providers",
          "title": "AI Providers",
          "description": "How to configure Claude, Gemini, and Cursor as AI backends"
        }
      ]
    },
    {
      "title": "Architecture",
      "pages": [
        {
          "slug": "generation-pipeline",
          "title": "Generation Pipeline",
          "description": "The four-stage pipeline: clone, plan, generate content, and render HTML"
        },
        {
          "slug": "plan-json-schema",
          "title": "Plan JSON Schema",
          "description": "Structure and schema of the plan.json file produced by the AI Planner"
        },
        {
          "slug": "incremental-updates",
          "title": "Incremental Updates",
          "description": "How docsfy detects changes and regenerates only affected pages"
        }
      ]
    },
    {
      "title": "API Reference",
      "pages": [
        {
          "slug": "api-endpoints",
          "title": "API Endpoints",
          "description": "Complete REST API reference for generating, querying, and downloading documentation"
        }
      ]
    }
  ]
}
```

## How the Plan Is Generated

The AI Planner (Stage 2) generates `plan.json` by running an AI CLI tool with its working directory set to the cloned repository:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

The AI CLI is invoked with the prompt passed via stdin:

```python
subprocess.run(cmd, input=prompt, capture_output=True, text=True)
```

The prompt instructs the AI to analyze the repository and output a JSON documentation plan. The supported providers are:

| Provider | Binary | Command |
|----------|--------|---------|
| Claude | `claude` | `claude --model <model> --dangerously-skip-permissions -p` |
| Gemini | `gemini` | `gemini --model <model> --yolo` |
| Cursor | `agent` | `agent --force --model <model> --print --workspace <path>` |

> **Tip:** The default provider is `claude` with model `claude-opus-4-6[1m]`. Configure these via the `AI_PROVIDER` and `AI_MODEL` environment variables.

### JSON Extraction from AI Output

AI CLI tools may produce output that contains the JSON embedded within surrounding text, markdown formatting, or commentary. docsfy uses a multi-strategy extraction pipeline to reliably parse the plan:

1. **Direct JSON parse** — attempt `json.loads()` on the raw output
2. **Brace matching** — find the outermost `{...}` JSON object in the output
3. **Markdown code block extraction** — extract JSON from ` ```json ` fenced code blocks
4. **Regex recovery** — fallback pattern matching to locate JSON fragments

This approach ensures robust plan extraction regardless of which AI provider is used or how it formats its response.

## How the Plan Is Consumed

### Stage 3: AI Content Generator

The Content Generator iterates over every page defined in `plan.json` and runs the AI CLI once per page. Each invocation receives the page's `title` and `description` as part of its prompt, directing the AI to write the appropriate markdown content for that page.

Pages can be generated concurrently using async execution with semaphore-limited concurrency. The output is cached at:

```
/data/projects/{project-name}/cache/pages/{slug}.md
```

### Stage 4: HTML Renderer

The HTML Renderer reads `plan.json` to build:

- **Sidebar navigation** — sections become collapsible groups, pages become navigation links
- **Page rendering** — each page's markdown is converted to HTML using Jinja2 templates
- **Site structure** — `index.html` (landing page) plus `{slug}.html` for each page
- **Search index** — `search-index.json` built from page titles, descriptions, and content
- **Site features** — dark/light theme toggle, client-side search, code syntax highlighting, responsive layout

The final rendered site is output to:

```
/data/projects/{project-name}/site/
```

## Incremental Updates and Plan Diffing

When a project is regenerated, docsfy uses `plan.json` to minimize unnecessary work:

1. Fetch the repository and compare the current commit SHA against the stored SHA in SQLite
2. If the SHA has changed, re-run the AI Planner to produce a new `plan.json`
3. Compare the new plan against the existing plan to detect structural changes
4. If the plan structure is unchanged and only specific source files changed, regenerate only the pages whose content may be affected
5. If the plan structure changed (sections added/removed, pages reordered), regenerate all affected pages

> **Note:** The commit SHA is tracked per project in the SQLite database at `/data/docsfy.db`. This enables docsfy to skip regeneration entirely when the repository hasn't changed.

## Slug Conventions

Page slugs are the backbone of the file-naming convention across the entire pipeline. A single slug value flows through every stage:

```
plan.json slug: "api-reference"
        │
        ├──▸ Content cache:  cache/pages/api-reference.md
        ├──▸ HTML output:    site/api-reference.html
        └──▸ Served at:      /docs/{project}/api-reference
```

When defining slugs, follow these conventions:

- Use lowercase letters, numbers, and hyphens only
- No leading or trailing hyphens
- No spaces or special characters
- Keep slugs concise but descriptive
- Ensure uniqueness across the entire plan (not just within a section)

> **Warning:** Duplicate slugs across sections will cause content files to overwrite each other. Each slug must be globally unique within a single `plan.json`.

## Relationship to API Endpoints

The `plan.json` structure surfaces through several API endpoints:

| Endpoint | How `plan.json` is used |
|----------|------------------------|
| `POST /api/generate` | Triggers the pipeline that creates `plan.json` |
| `GET /api/projects/{name}` | Returns project details including page information derived from the plan |
| `GET /docs/{project}/{path}` | Serves HTML pages whose structure is defined by the plan |
| `GET /api/projects/{name}/download` | Packages the rendered site (built from the plan) as a `.tar.gz` archive |
