# docsfy Project Rules

## Private Data (HARD RULE)

**NEVER include private data in any file tracked by git.** This includes:
- API keys, passwords, tokens, credentials
- Internal URLs, IP addresses, hostnames
- User-specific configuration values

All secrets MUST be read from environment variables at runtime. Test plans use placeholders like `<ADMIN_KEY>`, `<TEST_USER_PASSWORD>` — never actual values.

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
| Python constants | `src/docsfy/models.py` | `VALID_PROVIDERS`, `DEFAULT_BRANCH`, `DOCSFY_DOCS_URL`, `DOCSFY_REPO_URL` |
| Data models | `src/docsfy/models.py` | `GenerateRequest`, `DocPlan`, `DocPage`, `NavGroup` |
| DB constants & validators | `src/docsfy/storage.py` | `VALID_STATUSES`, `VALID_ROLES`, `_validate_name()`, `_validate_owner()` |
| Git timeouts | `src/docsfy/repository.py` | `_CLONE_TIMEOUT`, `_FETCH_TIMEOUT`, `_DIFF_TIMEOUT` |
| Prompt constants | `src/docsfy/prompts.py` | `_MAX_DIFF_LENGTH`, `_PAGE_WRITING_RULES` |
| App CSS (buttons, forms, layout) | `src/docsfy/templates/_app_styles.html` | `.btn-*`, `.form-*`, `.status-dot-*`, `.spinner`, `.progress-bar-*` |
| Doc site base template | `src/docsfy/templates/_doc_base.html` | Sidebar, top bar, footer, script imports |

### Rules for New CSS

- ALL shared styles go in `_app_styles.html`
- Button styles: use `.btn` + `.btn-primary` / `.btn-secondary` / `.btn-danger` / `.btn-warning`
- No backgrounds or borders by default — only on hover
- Individual templates only contain styles SPECIFIC to that template
- Use CSS variables from `_app_styles.html` — never hardcode colors

### Rules for New Constants

- If a value is used in 2+ files → define in `models.py` and import
- If a value is used in SQL → accepted exception (SQL DDL can't reference Python vars)
- Magic numbers → named constants in the file that owns them

### Rules for Templates

- `dashboard.html`, `status.html`, `admin.html`, `login.html` all include `_app_styles.html`
- `index.html`, `page.html` extend `_doc_base.html`
- Template variables (provider list, branch, URLs) come from the backend — never hardcoded in HTML
- JS timing values use named constants (`POLL_INTERVAL_MS`, `TOAST_DEFAULT_MS`, etc.)

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
