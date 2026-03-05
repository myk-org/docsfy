# AI Generation Pipeline

The AI generation pipeline is the core engine of docsfy. It transforms a repository into structured documentation through a two-phase workflow: first planning the documentation structure, then generating markdown content for each page. This page explains how each phase works, how concurrency is managed, and how caching enables incremental updates.

## Pipeline Overview

When a generation request is received, docsfy orchestrates the full pipeline inside `_run_generation()` in `main.py`:

1. **Validate** the AI provider is available
2. **Clone** the repository (or resolve a local path)
3. **Check** whether cached output is already up to date
4. **Phase 1** — Run the AI planner to produce a documentation structure
5. **Phase 2** — Generate markdown content for every page (up to 5 in parallel)
6. **Render** the final HTML site from the generated markdown

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Repository  │────▶│  Phase 1: Plan   │────▶│  Phase 2: Pages  │
│  (clone/     │     │  (AI explores    │     │  (up to 5        │
│   local)     │     │   codebase)      │     │   concurrent)    │
└──────────────┘     └──────────────────┘     └────────┬─────────┘
                                                       │
                                              ┌────────▼─────────┐
                                              │   Render Site    │
                                              │   (HTML + assets)│
                                              └──────────────────┘
```

The pipeline runs as a background `asyncio` task, allowing the API to return HTTP 202 immediately while generation proceeds:

```python
# main.py — generation is kicked off as a background task
asyncio.create_task(
    _run_generation(
        repo_url=request.repo_url,
        repo_path=request.repo_path,
        project_name=project_name,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=request.ai_cli_timeout or settings.ai_cli_timeout,
        force=request.force,
    )
)
```

## Phase 1: Documentation Planning

Phase 1 asks the AI to explore the entire repository and produce a structured documentation plan as JSON. This plan defines the navigation groups, page slugs, titles, and descriptions that Phase 2 will use.

### How the Planner Works

The planner is implemented in `generator.py` as `run_planner()`:

```python
async def run_planner(
    repo_path: Path,
    project_name: str,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
) -> dict[str, Any]:
    logger.info(f"[{project_name}] Calling AI planner")
    prompt = build_planner_prompt(project_name)
    success, output = await call_ai_cli(
        prompt=prompt,
        cwd=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )
    if not success:
        msg = f"Planner failed: {output}"
        raise RuntimeError(msg)

    plan = parse_json_response(output)
    if plan is None:
        msg = "Failed to parse planner output as JSON"
        raise RuntimeError(msg)

    logger.info(
        f"[{project_name}] Plan generated: {len(plan.get('navigation', []))} groups"
    )
    return plan
```

Key details:

- The AI runs **inside the repository directory** (`cwd=repo_path`), giving it full access to read source code, configs, tests, and CI/CD pipelines.
- The prompt explicitly instructs the AI to **not rely on the README** — it should understand the project from its code.
- The planner output must be **valid JSON only** — no markdown code blocks, no explanatory text.

### Planner Prompt

The prompt is built by `build_planner_prompt()` in `prompts.py`:

```python
def build_planner_prompt(project_name: str) -> str:
    return f"""You are a technical documentation planner. Explore this repository thoroughly.
Explore the source code, configuration files, tests, CI/CD pipelines, and project structure.
Do NOT rely on the README — understand the project from its code and configuration.

Then create a documentation plan as a JSON object. The plan should cover:
- Introduction and overview
- Installation / getting started
- Configuration (if applicable)
- Usage guides for key features
- API reference (if the project has an API)
- Any other sections that would help users understand and use this project

Project name: {project_name}

CRITICAL: Your response must be ONLY a valid JSON object. No text before or after.
No markdown code blocks.

Output format:
{PLAN_SCHEMA}"""
```

### Plan Schema

The expected JSON structure is defined by `PLAN_SCHEMA` and validated by Pydantic models:

```python
class DocPage(BaseModel):
    slug: str          # URL-friendly page identifier (e.g., "getting-started")
    title: str         # Human-readable title (e.g., "Getting Started")
    description: str = ""  # Brief description of what the page covers

class NavGroup(BaseModel):
    group: str             # Section group name (e.g., "Guides")
    pages: list[DocPage]

class DocPlan(BaseModel):
    project_name: str
    tagline: str = ""
    navigation: list[NavGroup] = Field(default_factory=list)
```

A typical plan output looks like:

```json
{
  "project_name": "my-project",
  "tagline": "A CLI tool for managing deployments",
  "navigation": [
    {
      "group": "Getting Started",
      "pages": [
        {
          "slug": "introduction",
          "title": "Introduction",
          "description": "Overview of the project and its key features"
        },
        {
          "slug": "installation",
          "title": "Installation",
          "description": "How to install and set up the tool"
        }
      ]
    },
    {
      "group": "Guides",
      "pages": [
        {
          "slug": "configuration",
          "title": "Configuration",
          "description": "Configuration options and environment variables"
        }
      ]
    }
  ]
}
```

### Robust JSON Parsing

Since AI models sometimes wrap JSON in markdown code blocks or include thinking/preamble text, docsfy uses a multi-strategy parser in `json_parser.py`:

```python
def parse_json_response(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    # Strategy 1: Direct JSON parse
    if text.startswith("{"):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
    # Strategy 2: Brace-matching extraction
    result = _extract_json_by_braces(text)
    if result is not None:
        return result
    # Strategy 3: Code block extraction
    result = _extract_json_from_code_blocks(text)
    if result is not None:
        return result
    logger.warning("Failed to parse AI response as JSON")
    return None
```

The three strategies, in order:

| Strategy | Description | Handles |
|----------|-------------|---------|
| Direct parse | `json.loads()` on the full text | Clean JSON responses |
| Brace-matching | Finds first `{`, tracks nesting depth, extracts to matching `}` | JSON with surrounding text/thinking |
| Code block extraction | Regex extracts content from `` ```json `` blocks | JSON wrapped in markdown |

> **Note:** The brace-matching strategy correctly handles nested braces, quoted strings, and escape characters. If one strategy fails, the parser silently falls through to the next.

### Storing the Plan

After the plan is generated, it is persisted in two places:

1. **Database** — stored as `plan_json` so the API can expose document structure while pages are still generating
2. **Filesystem** — written to `{project_dir}/plan.json` for downstream rendering

```python
# main.py — _generate_from_path()
await update_project_status(
    project_name,
    status="generating",
    plan_json=json.dumps(plan),
)
```

## Phase 2: Content Generation

Phase 2 takes the plan from Phase 1 and generates markdown content for each page. Pages are generated concurrently with a configurable concurrency limit to avoid overwhelming the AI provider.

### Single Page Generation

Each page is generated by `generate_page()` in `generator.py`. The function:

1. Checks the cache for an existing result
2. Builds a page-specific prompt
3. Calls the AI with the repository as working directory
4. Strips any AI preamble from the output
5. Caches the result to disk
6. Updates the project's page count in the database

```python
async def generate_page(
    repo_path: Path,
    slug: str,
    title: str,
    description: str,
    cache_dir: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    use_cache: bool = False,
    project_name: str = "",
) -> str:
    # Validate slug to prevent path traversal
    if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
        msg = f"Invalid page slug: '{slug}'"
        raise ValueError(msg)

    cache_file = cache_dir / f"{slug}.md"
    if use_cache and cache_file.exists():
        logger.debug(f"[{_label}] Using cached page: {slug}")
        return cache_file.read_text(encoding="utf-8")

    prompt = build_page_prompt(
        project_name=repo_path.name, page_title=title, page_description=description
    )
    success, output = await call_ai_cli(
        prompt=prompt,
        cwd=repo_path,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=ai_cli_timeout,
    )
    if not success:
        logger.warning(f"[{_label}] Failed to generate page '{slug}': {output}")
        output = f"# {title}\n\n*Documentation generation failed. Please re-run.*"

    output = _strip_ai_preamble(output)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(output, encoding="utf-8")
    return output
```

### Page Prompt

Each page gets its own tailored prompt via `build_page_prompt()`:

```python
def build_page_prompt(project_name: str, page_title: str, page_description: str) -> str:
    return f"""You are a technical documentation writer. Explore this repository to write
the "{page_title}" page for the {project_name} documentation.

Page description: {page_description}

Explore the codebase as needed. Read source files, configs, tests, and CI/CD pipelines
to write comprehensive, accurate documentation. Do NOT rely on the README.

Write in markdown format. Include:
- Clear explanations
- Code examples from the actual codebase (not made up)
- Configuration snippets where relevant

Use these callout formats for special content:
- Notes: > **Note:** text
- Warnings: > **Warning:** text
- Tips: > **Tip:** text

Output ONLY the markdown content for this page. No wrapping, no explanation."""
```

> **Tip:** The page description from Phase 1 gives the AI focused guidance on what to cover, while still allowing it to explore the codebase freely for relevant details.

### Stripping AI Preamble

Some AI models emit thinking or planning text before the actual markdown content. The `_strip_ai_preamble()` helper handles this by scanning the first 10 lines for a markdown header (`#`):

```python
def _strip_ai_preamble(text: str) -> str:
    """Strip AI thinking/planning text that appears before actual content."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i > 10:
            break
        if line.startswith("#"):
            return "\n".join(lines[i:])
    return text
```

If no header is found within the first 10 lines, the full text is returned unchanged.

### Parallel Execution

All pages are generated concurrently through `generate_all_pages()`, which collects coroutines and dispatches them with a concurrency limit:

```python
MAX_CONCURRENT_PAGES = 5

async def generate_all_pages(
    repo_path: Path,
    plan: dict[str, Any],
    cache_dir: Path,
    ai_provider: str,
    ai_model: str,
    ai_cli_timeout: int | None = None,
    use_cache: bool = False,
    project_name: str = "",
) -> dict[str, str]:
    # ... extract pages from plan ...

    coroutines = [
        generate_page(
            repo_path=repo_path,
            slug=p["slug"],
            title=p["title"],
            description=p["description"],
            cache_dir=cache_dir,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_cli_timeout=ai_cli_timeout,
            use_cache=use_cache,
            project_name=project_name,
        )
        for p in all_pages
    ]

    results = await run_parallel_with_limit(
        coroutines, max_concurrency=MAX_CONCURRENT_PAGES
    )
```

The `run_parallel_with_limit()` function is provided by the `ai-cli-runner` library and uses an `asyncio.Semaphore` internally to cap active AI calls at 5.

```
Page generation timeline (MAX_CONCURRENT_PAGES = 5):

Time ──────────────────────────────────────────────────▶

Slot 1: ████ intro ████    ████ api-ref ████
Slot 2: ██ quickstart ██   ████ config ████
Slot 3: ████ install ████       ██ faq ██
Slot 4: ██ usage ██        ██ deploy ██
Slot 5: ███ arch ███       █ troubleshoot █
```

> **Warning:** The `MAX_CONCURRENT_PAGES` constant is set to 5 in `generator.py`. Increasing it may lead to rate limiting from AI providers or excessive resource consumption.

### Slug Validation

Before processing, each page slug is validated at two levels to prevent path traversal attacks:

```python
# In generate_all_pages() — skips unsafe slugs with a warning
if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
    logger.warning(f"[{_label}] Skipping path-unsafe slug: '{slug}'")
    continue

# In generate_page() — raises ValueError for unsafe slugs
if "/" in slug or "\\" in slug or slug.startswith(".") or ".." in slug:
    msg = f"Invalid page slug: '{slug}'"
    raise ValueError(msg)
```

### Result Aggregation

After all coroutines complete, results are paired with their page metadata. Failed pages receive fallback content instead of crashing the entire pipeline:

```python
pages: dict[str, str] = {}
for page_info, result in zip(all_pages, results):
    if isinstance(result, Exception):
        logger.warning(
            f"[{_label}] Page generation failed for '{page_info['slug']}': {result}"
        )
        pages[page_info["slug"]] = (
            f"# {page_info['title']}\n\n*Documentation generation failed.*"
        )
    else:
        pages[page_info["slug"]] = result
```

> **Note:** Phase 1 (planning) is treated as **critical** — if it fails, the entire pipeline stops with a `RuntimeError`. Phase 2 (page generation) is **best-effort** — individual page failures produce fallback content and the pipeline continues.

## Caching and Incremental Updates

Docsfy implements caching at multiple levels to avoid redundant AI calls and support resumable generation.

### Cache Directory Structure

Each project's cached pages are stored as individual markdown files:

```
/data/projects/{project_name}/
├── cache/
│   └── pages/
│       ├── introduction.md
│       ├── quickstart.md
│       ├── configuration.md
│       └── api-reference.md
├── site/              # Rendered HTML output
│   ├── index.html
│   ├── introduction.html
│   └── ...
└── plan.json          # Documentation structure
```

The cache directory path is resolved by `get_project_cache_dir()` in `storage.py`:

```python
def get_project_cache_dir(name: str) -> Path:
    return PROJECTS_DIR / _validate_name(name) / "cache" / "pages"
```

### Per-Page Caching

When `use_cache=True`, each page checks for a cached file before calling the AI:

```python
cache_file = cache_dir / f"{slug}.md"
if use_cache and cache_file.exists():
    logger.debug(f"[{_label}] Using cached page: {slug}")
    return cache_file.read_text(encoding="utf-8")
```

After generation, every page is written to the cache regardless of success or failure:

```python
cache_dir.mkdir(parents=True, exist_ok=True)
cache_file.write_text(output, encoding="utf-8")
```

This means if generation is interrupted (e.g., server restart, timeout), previously completed pages are preserved and won't be regenerated on the next run.

### Commit-Based Freshness

Before starting the pipeline, docsfy compares the repository's current commit SHA against the stored value:

```python
# main.py — _generate_from_path()
existing = await get_project(project_name)
if (
    existing
    and existing.get("last_commit_sha") == commit_sha
    and existing.get("status") == "ready"
):
    logger.info(f"[{project_name}] Project is up to date at {commit_sha[:8]}")
    await update_project_status(project_name, status="ready")
    return
```

If the commit SHA matches and the project status is `"ready"`, the entire pipeline is skipped. This prevents unnecessary regeneration when re-triggering documentation for an unchanged repository.

### Force Regeneration

Setting `force=True` in the generation request bypasses all caching:

```python
if force:
    cache_dir = get_project_cache_dir(project_name)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        logger.info(f"[{project_name}] Cleared cache (force=True)")
    await update_project_status(project_name, status="generating", page_count=0)
```

When forced:
- The entire cache directory is deleted
- The page count is reset to 0
- `use_cache` is set to `False` in the `generate_all_pages()` call
- Every page is regenerated from scratch

## Duplicate Generation Prevention

A global in-memory set tracks projects currently being generated, preventing concurrent generation of the same project:

```python
_generating: set[str] = set()

# In the generate() endpoint:
if project_name in _generating:
    raise HTTPException(
        status_code=409,
        detail=f"Project '{project_name}' is already being generated",
    )

_generating.add(project_name)
```

The project name is removed from the set in a `finally` block to ensure cleanup even on failure:

```python
# In _run_generation():
finally:
    _generating.discard(project_name)
```

## Error Handling

The pipeline uses a layered error handling strategy:

| Layer | Behavior | Rationale |
|-------|----------|-----------|
| AI provider check | Fails fast with error status | No point starting without a working provider |
| Phase 1 (planner) | Raises `RuntimeError` | Cannot generate pages without a plan |
| Phase 2 (per-page) | Logs warning, uses fallback content | One failed page shouldn't block others |
| Phase 2 (aggregation) | Catches exceptions per result | Ensures all pages produce output |
| Pipeline wrapper | Catches all exceptions, sets status to `"error"` | API consumers see the failure reason |

```python
# main.py — _run_generation() wraps everything
except Exception as exc:
    logger.error(f"Generation failed for {project_name}: {exc}")
    await update_project_status(
        project_name, status="error", error_message=str(exc)
    )
finally:
    _generating.discard(project_name)
```

## Project Status Tracking

Throughout the pipeline, the project status is updated in the SQLite database so API consumers can monitor progress:

```
save_project(status="generating")        # Request received
  │
  ├─ check_ai_cli_available()
  │   └─ [fail] → status="error"
  │
  ├─ run_planner()
  │   └─ update_project_status(plan_json=...)   # Plan available
  │
  ├─ generate_page() × N
  │   └─ update_project_status(page_count=N)    # Progress updates
  │
  ├─ render_site()
  │
  └─ update_project_status(
         status="ready",
         last_commit_sha=...,
         page_count=...,
     )                                          # Complete
```

The page count is updated incrementally as each page completes, by counting cached markdown files:

```python
if project_name:
    existing_pages = len(list(cache_dir.glob("*.md")))
    await update_project_status(
        project_name, status="generating", page_count=existing_pages
    )
```

## AI Provider Configuration

The pipeline delegates all AI communication to the `ai-cli-runner` library, which manages provider-specific CLI tools:

```python
# ai_client.py — re-exports from ai-cli-runner
from ai_cli_runner import (
    PROVIDERS,              # Dict of provider configurations
    VALID_AI_PROVIDERS,     # frozenset: {"claude", "gemini", "cursor"}
    ProviderConfig,         # Dataclass with binary path, build command, etc.
    call_ai_cli,            # Main function for making AI calls
    check_ai_cli_available, # Validates provider and model availability
    get_ai_cli_timeout,     # Gets timeout for a provider
    run_parallel_with_limit,# Concurrency-limited parallel execution
)
```

Default settings in `config.py`:

```python
class Settings(BaseSettings):
    ai_provider: str = "claude"
    ai_model: str = "claude-opus-4-6[1m]"  # [1m] = 1 million token context window
    ai_cli_timeout: int = Field(default=60, gt=0)
```

These can be overridden via environment variables or per-request:

| Setting | Env Variable | Per-Request Field | Default |
|---------|-------------|-------------------|---------|
| Provider | `AI_PROVIDER` | `ai_provider` | `claude` |
| Model | `AI_MODEL` | `ai_model` | `claude-opus-4-6[1m]` |
| Timeout | `AI_CLI_TIMEOUT` | `ai_cli_timeout` | `60` seconds |

> **Tip:** The `[1m]` suffix on the default model specifies a 1 million token context window, giving the AI ample room to explore large codebases during both planning and page generation.

## Testing the Pipeline

The generator test suite in `tests/test_generator.py` validates both phases by mocking the AI calls:

```python
async def test_run_planner(tmp_path: Path, sample_plan: dict) -> None:
    from docsfy.generator import run_planner

    with patch(
        "docsfy.generator.call_ai_cli", return_value=(True, json.dumps(sample_plan))
    ):
        plan = await run_planner(
            repo_path=tmp_path,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
        )

    assert plan is not None
    assert plan["project_name"] == "test-repo"
    assert len(plan["navigation"]) == 1


async def test_generate_page_uses_cache(tmp_path: Path) -> None:
    from docsfy.generator import generate_page

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached = cache_dir / "introduction.md"
    cached.write_text("# Cached content")

    md = await generate_page(
        repo_path=tmp_path,
        slug="introduction",
        title="Introduction",
        description="Overview",
        cache_dir=cache_dir,
        ai_provider="claude",
        ai_model="opus",
        use_cache=True,
    )

    assert md == "# Cached content"
```

Key test scenarios covered:

- Successful planner execution and JSON parsing
- Planner failure (AI returns error)
- Planner with invalid JSON output
- Page generation with AI mock
- Page generation from cache (no AI call made)
