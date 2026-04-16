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
| Python constants | `src/docsfy/models.py` | `VALID_PROVIDERS`, `DEFAULT_BRANCH`, `PAGE_TYPES`, `DOCSFY_DOCS_URL`, `DOCSFY_REPO_URL` |
| Data models | `src/docsfy/models.py` | `GenerateRequest`, `DocPlan`, `DocPage`, `NavGroup` |
| DB constants & validators | `src/docsfy/storage.py` | `VALID_STATUSES`, `VALID_ROLES`, `_validate_name()`, `_validate_owner()` |
| Git timeouts | `src/docsfy/repository.py` | `_CLONE_TIMEOUT`, `_FETCH_TIMEOUT`, `_DIFF_TIMEOUT` |
| Prompt constants | `src/docsfy/prompts.py` | `_MAX_DIFF_LENGTH`, `_GUIDE_WRITING_RULES`, `_REFERENCE_WRITING_RULES`, `_RECIPE_WRITING_RULES`, `_CONCEPT_WRITING_RULES`, `_INCREMENTAL_WRITING_RULES`, `truncate_diff_content()` |
| Frontend constants | `frontend/src/lib/constants.ts` | API base URL, poll intervals, toast durations |
| Frontend types | `frontend/src/types/index.ts` | `Project`, `User`, `Variant`, `AuthState` |
| Frontend API client | `frontend/src/lib/api.ts` | `fetchProjects()`, `login()`, `generateDocs()` |
| Frontend WebSocket | `frontend/src/lib/websocket.ts` | `useWebSocket()`, connection manager |
| Doc site base template | `src/docsfy/templates/_doc_base.html` | Sidebar, top bar, footer, script imports |
| CLI config | `~/.config/docsfy/config.toml` | Server URL, API key, default provider/model |

### Rules for New CSS

- App UI styles are managed by Tailwind CSS in the React frontend (`frontend/`)
- The old `_app_styles.html` has been removed — do not recreate it
- Doc site templates (`_doc_base.html`, `index.html`, `page.html`) have their own self-contained CSS
- Use Tailwind utility classes and shadcn/ui components for all new app UI

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
- Branch validation: `^[a-zA-Z0-9][a-zA-Z0-9._-]*$` — slashes are rejected because branch appears as a single FastAPI path segment and in JS split('/') parsing. Use hyphens instead (e.g., `release-1.x` instead of `release/1.x`).
- Disk path: `PROJECTS_DIR / owner / name / branch / provider / model`

## Default AI Provider/Model

- Configured via environment variables (pydantic_settings loads environment variables which override config defaults)
- Currently: `cursor` / `gpt-5.4-xhigh-fast`
- The UI always uses server defaults for new repos — provider/model are NOT persisted in sessionStorage

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
