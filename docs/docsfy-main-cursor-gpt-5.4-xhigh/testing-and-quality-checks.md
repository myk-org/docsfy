# Testing and Quality Checks

docsfy uses several layers of testing. The fast checks are local and automated: `pytest` for the Python app, `Vitest` for the React frontend, `tox` for a repeatable backend run, and `pre-commit` for formatting, linting, type checks, and secret scanning. On top of that, the `test-plans/` directory contains detailed manual end-to-end plans for real user workflows such as login, generation, branch handling, WebSocket updates, and CLI usage.

## Quick Start

If you want a sensible default before you call a change done, run:

```bash
tox

cd frontend
npm test
npm run build
npm run lint

cd ..
pre-commit run --all-files
```

If your change affects user-visible behavior, also run the relevant manual plans in `test-plans/`.

> **Note:** This repository does not currently check in any `.github/workflows/` files. The quality controls you can inspect in the repo live in `tox.toml`, `.pre-commit-config.yaml`, `.coderabbit.yaml`, frontend configs, and the manual plans under `test-plans/`.

## Pytest

`pytest` is the main automated test runner for the Python side of docsfy. The checked-in config is small and clear:

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "pytest-xdist"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

A few practical takeaways from that config:

- async tests work out of the box via `pytest-asyncio`
- tests are expected to live under `tests/`
- code is imported from `src/`, so the suite exercises the actual package code

Most backend tests run the FastAPI app in-process instead of starting a separate server. That makes the suite faster and easier to debug. For example, `tests/test_api_projects.py` exercises the generate API like this:

```python
async def test_generate_starts(client: AsyncClient) -> None:
    """POST /api/generate starts generation (mock create_task), returns 202."""
    with patch("docsfy.api.projects.asyncio.create_task") as mock_task:
        mock_task.side_effect = lambda coro: coro.close()
        response = await client.post(
            "/api/generate",
            json={"repo_url": "https://github.com/org/repo.git"},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["project"] == "repo"
    assert body["status"] == "generating"
```

The backend suite covers much more than simple API status codes. The checked-in test files include auth, admin APIs, project APIs, storage, repository cloning and diffs, renderer behavior, generator logic, CLI commands, dashboard routes, and WebSocket behavior.

Real-time updates are covered too. In `tests/test_websocket.py`, authenticated clients are expected to receive an initial `sync` message, while unauthenticated clients are rejected.

```python
with sync_client.websocket_connect(f"/api/ws?token={TEST_ADMIN_KEY}") as ws:
    data = ws.receive_json()
    assert data["type"] == "sync"
    assert "projects" in data
    assert "known_models" in data
    assert "known_branches" in data
```

> **Tip:** Use `pytest` when you are iterating on backend code, but use `tox` when you want the repository's checked-in backend test command exactly as the project defines it.

## Vitest

The frontend uses `Vitest` with Testing Library. The scripts in `frontend/package.json` show the main entry points:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "test": "vitest run"
}
```

The Vitest config is straightforward:

```ts
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
```

That means frontend tests run in a browser-like `jsdom` environment, can use global test helpers, and load `frontend/src/test/setup.ts`, which imports `@testing-library/jest-dom/vitest`.

The checked-in frontend test coverage is currently focused on the login page. `frontend/src/pages/LoginPage.test.tsx` checks basic rendering and user-visible text:

```tsx
describe('LoginPage', () => {
  it('renders username and password inputs', () => {
    renderLogin()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('renders the submit button', () => {
    renderLogin()
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument()
  })
})
```

In practice, the frontend has three separate local checks:

- `npm test` runs the Vitest suite
- `npm run build` runs `tsc -b` before building, so TypeScript errors fail the build
- `npm run lint` runs ESLint on the frontend source

## Tox

`tox` is the project's repeatable backend test wrapper. The entire checked-in config is short enough to read in one glance:

```toml
skipsdist = true

envlist = ["unittests"]

[env.unittests]
deps = ["uv"]
commands = [["uv", "run", "--extra", "dev", "pytest", "-n", "auto", "tests"]]
```

This tells you three important things:

- `tox` is focused on backend tests, not the frontend
- it uses `uv` to supply the Python test environment
- it runs `pytest` with `-n auto`, so `pytest-xdist` parallelizes the test suite across available CPU cores

If you want the exact backend command the project uses, `tox` is the safest choice.

## Pre-Commit

`pre-commit` is the broadest single quality gate in this repository. It combines file hygiene checks, Python linting and formatting, type checking, and secret scanning.

Here is the most relevant part of `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v6.0.0
  hooks:
    - id: check-added-large-files
    - id: detect-private-key
    - id: trailing-whitespace
      args: [--markdown-linebreak-ext=md]
    - id: end-of-file-fixer

# flake8 retained for RedHatQE M511 plugin; ruff handles standard linting
- repo: https://github.com/PyCQA/flake8
  rev: 7.3.0
  hooks:
    - id: flake8
      args: [--config=.flake8]

- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets

- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.15.6
  hooks:
    - id: ruff
    - id: ruff-format

- repo: https://github.com/gitleaks/gitleaks
  rev: v8.30.1
  hooks:
    - id: gitleaks

- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.19.1
  hooks:
    - id: mypy
      exclude: (tests/)
```

A few details are worth calling out:

- `ruff` handles general Python linting and formatting
- `flake8` is still present for the specialized RedHatQE `M511` plugin
- `mypy` is part of the hook set, but the hook excludes `tests/`
- `detect-private-key`, `detect-secrets`, and `gitleaks` give you multiple chances to catch secrets before they land in git
- the whitespace hook is configured with `--markdown-linebreak-ext=md`, which helps avoid breaking intentional Markdown line breaks

The config also contains a `ci:` section with `autofix_prs: false`, which is a strong hint that automated hook runs are expected in PR workflows, but the project does not want silent auto-fixes on pull requests.

> **Tip:** `pre-commit run --all-files` is the best one-command local sweep before you push. It is especially useful after docs changes, refactors, or dependency updates.

## Type Checks

docsfy uses strict type settings on both the Python and TypeScript sides.

For Python, `mypy` is configured in `pyproject.toml` with a strict baseline:

```toml
[tool.mypy]
check_untyped_defs = true
disallow_any_generics = true
disallow_incomplete_defs = true
disallow_untyped_defs = true
no_implicit_optional = true
show_error_codes = true
warn_unused_ignores = true
strict_equality = true
extra_checks = true
warn_unused_configs = true
warn_redundant_casts = true
```

This is not a best-effort type setup. It expects annotated, consistently typed application code.

On the frontend, the checked-in type enforcement happens through the build and strict TypeScript compiler options. `frontend/tsconfig.app.json` and `frontend/tsconfig.node.json` both enable `strict: true`, along with several extra guardrails:

```json
"strict": true,
"noUnusedLocals": true,
"noUnusedParameters": true,
"noFallthroughCasesInSwitch": true,
"noUncheckedSideEffectImports": true
```

Because `frontend/package.json` defines the build as `tsc -b && vite build`, TypeScript errors fail `npm run build` even though there is no separate `typecheck` script.

> **Note:** If you want frontend type checking exactly as the repo defines it, run `npm run build`. That is the checked-in command that enforces `tsc -b`.

## Secret Scanning

This project takes secret detection seriously, and it does it in layers.

First, the hook set includes three separate secret-related checks:

- `detect-private-key`
- `detect-secrets`
- `gitleaks`

Second, the repo keeps allowlists narrow. `.gitleaks.toml` only allowlists one file:

```toml
[extend]
useDefault = true

[allowlist]
paths = [
    '''tests/test_repository\.py''',
]
```

Third, obviously fake test values are marked inline so scanners do not create noise. For example, `tests/test_api_auth.py` contains this intentionally invalid credential:

```python
response = await unauthed_client.post(
    "/api/auth/login",
    json={
        "username": "someone",
        "api_key": "totally-wrong",  # pragma: allowlist secret
    },
)
```

That comment is there because the string looks secret-like to scanners, even though it is only a test fixture.

> **Warning:** Fake test keys such as `test-admin-secret-key` exist in the test suite on purpose. They are not real credentials, and they are specifically allowlisted. Do not copy that pattern for real secrets. Real keys, tokens, and passwords should come from environment variables or local untracked config, never from tracked files.

## Review Automation

The repository includes CodeRabbit review configuration in `.coderabbit.yaml`. It is set up to auto-review pull requests into `main`, use an assertive review profile, and request changes when critical issues are found.

A shortened version of the config looks like this:

```yaml
reviews:
  profile: assertive
  request_changes_workflow: true
  auto_review:
    enabled: true
    drafts: false
    base_branches:
      - main

  tools:
    ruff:
      enabled: true
    pylint:
      enabled: true
    eslint:
      enabled: true
    shellcheck:
      enabled: true
    yamllint:
      enabled: true
    gitleaks:
      enabled: true
    semgrep:
      enabled: true
    actionlint:
      enabled: true
    hadolint:
      enabled: true
```

That tells you what the project expects from review automation:

- Python and frontend linting matter
- secret scanning is part of review, not just local hooks
- shell, YAML, Docker, and GitHub workflow quality are all considered when relevant files are touched

CodeRabbit is useful, but it is not a replacement for local testing. Think of it as an extra reviewer, not your primary test runner.

## End-to-End Plans

The `test-plans/` directory is where docsfy verifies complete user journeys.

Start with `test-plans/e2e-ui-test-plan.md`. It is the index and shared rulebook for all manual plans. It defines:

- the server URL: `http://localhost:8800`
- how to capture `ADMIN_KEY` from `.dev/.env`
- the test repository: `https://github.com/myk-org/for-testing-only`
- the branches used for testing: `main` and `dev`
- the model pair used for generation coverage: `gemini-2.5-flash` and `gemini-2.0-flash`
- how to log results to `UI-TESTS-RESULTS.md`
- the required order of the sub-plans

The linked plans cover a wide range of real behavior:

- authentication and role-based permissions
- generation and dashboard behavior
- generated docs quality, including sidebar, footer, copy buttons, and `llms.txt` files
- cross-user isolation and direct URL authorization
- incremental updates and JSON patch behavior
- delete and owner scoping
- UI component behavior
- cross-model updates
- branch support
- WebSocket connection and real-time progress
- CLI workflows
- cleanup and teardown

The plans are very explicit. For example, the CLI plan in `test-plans/e2e-12-cli.md` starts by configuring the CLI against a live server:

```shell
export DOCSFY_SERVER="http://localhost:8800"
export DOCSFY_API_KEY="<ADMIN_KEY>"

docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
```

The WebSocket plan in `test-plans/e2e-11-websocket.md` checks real browser behavior, not just unit-test behavior:

```shell
agent-browser javascript "new Promise(resolve => { const ws = new WebSocket('ws://localhost:8800/api/ws'); ws.onopen = () => { resolve('connected'); ws.close(); }; ws.onerror = () => resolve('error'); setTimeout(() => resolve('timeout'), 5000); })"
```

Two details make these plans especially important:

- they are the closest thing this repo has to acceptance tests for user-facing behavior
- they are the only place where full flows such as login, dashboard interaction, generation progress, docs viewing, CLI use, and cleanup are exercised end to end

> **Tip:** Do not jump straight into a random sub-plan. Start with `test-plans/e2e-ui-test-plan.md` every time. That file contains shared variables, environment rules, logging requirements, and the master execution order.

## Choosing The Right Check

Use the smallest check that matches your change, then step up when the change becomes more user-visible.

- changing Python business logic, APIs, auth, storage, or rendering: start with `tox` or backend `pytest`
- changing React components or frontend behavior: run `npm test`, `npm run build`, and `npm run lint`
- changing anything likely to affect formatting, linting, typing, or secrets: run `pre-commit run --all-files`
- changing user-facing workflows such as login, generation, status updates, docs output, WebSocket behavior, branch handling, or CLI behavior: run the relevant `test-plans/` sections

In short, `pytest` and `Vitest` catch fast regressions, `tox` makes backend runs repeatable, `pre-commit` blocks common mistakes, CodeRabbit adds review-time scrutiny, and the manual end-to-end plans are where you prove the product still works the way users expect.
