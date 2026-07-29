# docsfy Project Rules

## Private Data (HARD RULE)

**NEVER include private data in any file tracked by git.** This includes:
- API keys, passwords, tokens, credentials
- Internal URLs, IP addresses, hostnames
- User-specific configuration values

All secrets MUST be read from environment variables at runtime. Test plans use placeholders like `<ADMIN_KEY>`, `<TEST_USER_PASSWORD>` — never actual values.

## Entry Points

- `docsfy` — CLI for managing projects, users, and config from the terminal
- `docsfy-server` — starts the FastAPI server (uvicorn)

## Code Reusability (MANDATORY)

**Every element used more than once MUST be defined in ONE place and reused everywhere.**

When adding new code:
1. Check if a shared constant, style, or function already exists (see inventory below)
2. If it does, USE IT — do not redefine
3. If it doesn't but will be used in 2+ places, CREATE it in the appropriate shared location
4. Never duplicate CSS classes, constants, validators, or utility functions across files

### Where Shared Resources Live

| Resource Type | Location | Examples |
|---|---|---|
| Python constants | `src/docsfy/models.py` | `VALID_PROVIDERS`, `DEFAULT_BRANCH`, `PAGE_TYPES`, `REPO_TYPES`, `DOCSFY_DOCS_URL`, `DOCSFY_REPO_URL`, `DEFAULT_SIDECAR_BY_PROVIDER`, `CLI_SIDECAR_BY_PROVIDER`, `SIDECAR_*`, `RELATED_PAGES_HEADING` |

| Data models | `src/docsfy/models.py` | `GenerateRequest`, `DocPlan`, `DocPage`, `NavGroup`, `RepoType` |
| DB constants & validators | `src/docsfy/storage.py` | `VALID_STATUSES`, `VALID_ROLES`, `_validate_name()`, `_validate_owner()` |
| Git timeouts | `src/docsfy/repository.py` | `_CLONE_TIMEOUT`, `_FETCH_TIMEOUT`, `_DIFF_TIMEOUT` |
| Sidecar wrapper | `sidecar-helper/` | `startSidecar()` — Pi SDK HTTP sidecar for AI provider calls |
| Code graph | `src/docsfy/code_graph.py` | `build_code_graph()` — Graphify knowledge graph for AI context |
| Prompt constants | `src/docsfy/prompts.py` | `_MAX_DIFF_LENGTH`, `_GUIDE_WRITING_RULES`, `_REFERENCE_WRITING_RULES`, `_RECIPE_WRITING_RULES`, `_CONCEPT_WRITING_RULES`, `_INCREMENTAL_WRITING_RULES`, `_NAV_STRUCTURE_MAP`, `_REPO_TYPE_WRITING_RULES_MAP`, `truncate_diff_content()` |
| Page quality gate | `src/docsfy/generator.py` | `page_content_passes_quality_gate()`, `is_generation_failure_stub()`, `_PAGE_GENERATION_MAX_ATTEMPTS` |
| Image catalog | `src/docsfy/images.py` | `DOCSFY_IMAGES_DIR`, `IMAGE_EXTENSIONS`, `build_image_catalog()`, `copy_images_to_site()` |
| Frontend constants | `frontend/src/lib/constants.ts` | API base URL, poll intervals, toast durations, SK_VISION_PROVIDER, SK_VISION_MODEL |
| Frontend design tokens | `frontend/src/theme.css` | Command Deck color tokens, fonts, animations |
| Frontend types | `frontend/src/types/index.ts` | `Project`, `User`, `Variant`, `AuthState` |
| Frontend API client | `frontend/src/lib/api.ts` | `fetchProjects()`, `login()`, `generateDocs()` |
| Frontend WebSocket | `frontend/src/lib/websocket.ts` | `useWebSocket()`, connection manager |
| Doc site base template | `src/docsfy/templates/_doc_base.html` | Sidebar, top bar, footer, script imports |
| CLI config | `~/.config/docsfy/config.toml` | Server URL, API key, default provider/model |

### Rules for New CSS

- App UI uses the **Command Deck** design system defined in `frontend/src/theme.css`
- All colors must use semantic tokens: `surface-*`, `text-*`, `signal-*`, `border-*`, `glow-*`
- Typography: `font-display` (JetBrains Mono), `font-body` (IBM Plex Sans), `font-mono` (IBM Plex Mono)
- Both dark and light themes are supported via CSS custom properties (`:root` / `[data-theme='light']`)
- Never use hardcoded color values — always use design tokens from theme.css
- Doc site templates (`_doc_base.html`, `index.html`, `page.html`) have their own self-contained CSS

### Rules for New Constants

- If a value is used in 2+ files → define in `models.py` and import
- If a value is used in SQL → accepted exception (SQL DDL can't reference Python vars)
- Magic numbers → named constants in the file that owns them
- Frontend constants → define in `frontend/src/lib/constants.ts`

### Rules for Templates

- Only doc site templates remain: `_doc_base.html`, `_sidebar.html`, `_theme.html`, `index.html`, `page.html`
- `index.html` and `page.html` extend `_doc_base.html`
- App UI (dashboard, admin, login, status) is now a React SPA in `frontend/`
- Template variables (provider list, branch, URLs) come from the backend — never hardcoded in HTML

## Branch Support

- `branch` is a field on `GenerateRequest` (default: `"main"`)
- Branch is part of the DB primary key: `(name, branch, ai_provider, ai_model, owner)`
- URL pattern: `/{name}/{branch}/{provider}/{model}`
- Branch validation: `^[a-zA-Z0-9][a-zA-Z0-9._/-]*$` — slashes are allowed. Branches with slashes (e.g., `feat/issue-1`) are encoded as `feat~2Fissue-1` in URL path segments and disk paths via `encode_branch_for_path()` / `decode_branch_from_path()` in `models.py`. Frontend uses `encodeBranch()` from `lib/utils.ts`.
- Disk path: `PROJECTS_DIR / owner / name / branch / provider / model`

## Default AI Provider/Model

- Configured via environment variables (pydantic_settings loads environment variables which override config defaults)
- Defaults are stored in the DB `settings` table, seeded from env vars on startup
- When no default is configured (empty), users must select provider/model explicitly
- Admin can change defaults via Settings page (Admin → Settings) or `PUT /api/admin/settings`
- Env vars (`AI_PROVIDER`, `AI_MODEL`) override DB values on server restart
- Vision AI provider/model (`VISION_PROVIDER`, `VISION_MODEL`) control image description — falls back to generation provider/model
- The UI reads defaults from `GET /api/models` response (`default_provider`, `default_model`)
- AI calls are routed through pi-sidecar-client to a local HTTP sidecar service (default port 9100 via `SIDECAR_PORT` env var)
- Sidecar agent discovery (optional): `ACPX_AGENTS` / `CLI_AGENTS` (comma-separated). Models appear under friendly providers (`claude`/`gemini`/`cursor`) with `source` tags (`acpx`|`cli`|`api`). Unset = disabled. Entrypoint resolves `SIDECAR_ACPX_EXTENSION_PATH`, `SIDECAR_CLI_PROVIDER_EXTENSION_PATH`, and `SIDECAR_PROVIDER_EXTENSION_PATH` (unified provider registration).

## Testing

- Run tests: `uv run pytest -v --tb=short`
- E2e test plans: `test-plans/e2e-*.md`
- Test repo: `https://github.com/myk-org/for-testing-only` (branches: `main`, `dev`)

## E2E Test Plans

- E2e test plans live in `test-plans/e2e-*.md`
- **After ANY code change that affects the UI, API endpoints, or user-facing behavior, update or add e2e tests accordingly**
- When adding a new feature: add a new test section to the relevant e2e plan file (or create a new `e2e-XX-*.md` file)
- When modifying existing behavior: update the affected test steps, expected results, and URLs
- When changing URL patterns: update ALL e2e test files that reference those URLs
- The e2e test index is `test-plans/e2e-ui-test-plan.md` — update the Summary table when adding new tests

## AI Prompt Design (GOLDEN RULE)

**NEVER blow up prompts with content.** All AI prompts must contain instructions only — never embed file contents, file trees, page content, or large data structures in the prompt text.

- Write data to temp files and tell the AI where to read them
- The AI CLI runs with `cwd` access to the repo — it can explore files itself
- Prompts should be short instructions: what to do, where to find input, what format to return
- This applies to ALL prompts: planning, page generation, validation, cross-linking, everything

## Page Quality Gate

AI page generation occasionally returns exploration/chain-of-thought chatter
(e.g. "Let me start by reading the knowledge graph...") instead of real
documentation. To prevent that from being cached/published:

- `page_content_passes_quality_gate()` (`src/docsfy/generator.py`) rejects
  content that is empty, lacks a proper `# Title` H1, is too short to be
  substantive, matches known agent-narration phrasing (in its opening, or as
  a line opening with narration verb phrasing anywhere in the body), or is
  a known generation-failure stub.
- `generate_full_page_content()` runs the gate after stripping AI artifacts;
  on failure it regenerates once, then falls back to `_generation_failure_stub()`,
  which produces one of two known stub formats (both matched by
  `is_generation_failure_stub()`), never caches/publishes chatter:
  - Long form (`retry_hint=True`, the default): used when `generate_full_page_content()`
    exhausts its retries — `# {title}\n\n*Documentation generation failed. Please re-run.*`
  - Short form (`retry_hint=False`): used by `generate_all_pages()` when a page's
    generation coroutine raises an exception outright (no retry already happened
    at that layer) — `# {title}\n\n*Documentation generation failed.*`
- `generate_page()`'s incremental-update path strips AI artifacts and runs the
  same gate, falling back to full generation if the incremental result fails it.
- `postprocess.add_cross_links()` skips appending `## Related Pages` to any
  page that fails the gate or is a known failure stub (either format), so
  broken pages don't get dressed up to look complete.
- `renderer.render_site()` excludes known failure stubs (either format) from
  `llms.txt` / `llms-full.txt` (they remain visible on the HTML site itself as
  a failure notice, just not indexed as valid docs for AI consumers).

## Generated Documentation

The `docs/` directory contains AI-generated documentation from docsfy.
**NEVER edit these files manually.** To update documentation, regenerate using docsfy.
