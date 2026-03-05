# Testing

docsfy uses [pytest](https://docs.pytest.org/) as its testing framework with [tox](https://tox.wiki/) for environment management. The test suite contains **54 tests across 11 modules**, covering API endpoints, AI-powered generation, HTML rendering, database storage, data models, and a full end-to-end integration flow.

## Quick Start

Install the development dependencies:

```bash
pip install -e ".[dev]"
```

This installs the test toolchain defined in `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "pytest-xdist", "httpx"]
```

| Package | Purpose |
|---------|---------|
| `pytest` | Core test framework |
| `pytest-asyncio` | Async/await test support for async test functions |
| `pytest-xdist` | Parallel test execution across CPU cores |
| `httpx` | Async HTTP client for testing FastAPI endpoints via ASGI |

Run the full test suite:

```bash
pytest
```

## Pytest Configuration

All pytest settings live in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

- **`asyncio_mode = "auto"`** — Async test functions (`async def test_*`) are automatically detected and executed without requiring the `@pytest.mark.asyncio` decorator.
- **`testpaths = ["tests"]`** — Test discovery is scoped to the `tests/` directory.
- **`pythonpath = ["src"]`** — Adds `src/` to the Python path so that `from docsfy.xxx import ...` works correctly in test modules.

> **Note:** There is no `conftest.py` file. Each test module defines its own fixtures locally.

## Running Tests

### Basic Commands

```bash
# Run the full suite
pytest

# Run with verbose output
pytest -v

# Run a specific test module
pytest tests/test_main.py

# Run a single test function
pytest tests/test_main.py::test_health_endpoint

# Run with print output visible
pytest -v -s
```

### Parallel Execution with pytest-xdist

The `pytest-xdist` plugin distributes tests across multiple CPU cores for faster execution:

```bash
# Auto-detect CPU count and run in parallel
pytest -n auto

# Use a specific number of workers
pytest -n 4
```

> **Tip:** `pytest -n auto` is the default when running through tox (see below). It automatically matches the number of available CPU cores.

### Using tox

tox manages isolated test environments and is the recommended way to run the full validation suite. Configuration is in `tox.toml`:

```toml
skipsdist = true
envlist = ["unused-code", "unittests"]

[env.unused-code]
deps = ["python-utility-scripts"]
commands = [["pyutils-unusedcode"]]

[env.unittests]
deps = ["uv"]
commands = [["uv", "run", "--extra", "dev", "pytest", "-n", "auto", "tests"]]
```

Two environments are defined:

| Environment | Command | Purpose |
|-------------|---------|---------|
| `unused-code` | `pyutils-unusedcode` | Detects dead/unused code in the project |
| `unittests` | `uv run --extra dev pytest -n auto tests` | Runs the full test suite with parallel execution |

```bash
# Run all tox environments
tox

# Run only the test suite
tox -e unittests

# Run only the unused code checker
tox -e unused-code
```

> **Note:** The `unittests` environment uses [uv](https://docs.astral.sh/uv/) to resolve and install dependencies, then invokes pytest with `-n auto` for parallel test execution.

## Test Structure

The test suite is organized into 11 modules, each mapping to a corresponding source module in `src/docsfy/`:

```
tests/
├── __init__.py
├── test_main.py           # API endpoints          (8 tests)
├── test_models.py         # Data model validation   (10 tests)
├── test_storage.py        # Database operations     (7 tests)
├── test_json_parser.py    # JSON parsing            (7 tests)
├── test_repository.py     # Git operations          (6 tests)
├── test_generator.py      # AI-powered generation   (5 tests)
├── test_renderer.py       # HTML rendering          (3 tests)
├── test_config.py         # Configuration settings  (3 tests)
├── test_ai_client.py      # AI provider config      (2 tests)
├── test_prompts.py        # Prompt generation       (2 tests)
└── test_integration.py    # End-to-end flow         (1 test)
```

### test_main.py — API Endpoints (8 tests)

Tests the FastAPI application endpoints: health check, project status, generation triggering, project retrieval, deletion, local path support, and force-regeneration.

Uses an async `client` fixture that creates an isolated `httpx.AsyncClient` connected to the app via ASGI transport:

```python
@pytest.fixture
async def client(tmp_path: Path):
    import docsfy.storage as storage
    from docsfy.main import _generating

    orig_db = storage.DB_PATH
    orig_data = storage.DATA_DIR
    orig_projects = storage.PROJECTS_DIR

    storage.DB_PATH = tmp_path / "test.db"
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    _generating.clear()

    from docsfy.main import app

    await storage.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    storage.DB_PATH = orig_db
    storage.DATA_DIR = orig_data
    storage.PROJECTS_DIR = orig_projects
    _generating.clear()
```

Example endpoint tests:

```python
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_generate_endpoint_starts_generation(client: AsyncClient) -> None:
    with patch("docsfy.main.asyncio.create_task") as mock_task:
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

### test_models.py — Data Model Validation (10 tests)

Validates Pydantic models including `GenerateRequest`, `DocPage`, `DocPlan`, `NavGroup`, and `ProjectStatus`. Tests cover URL validation, project name extraction, local path support, and mutual exclusivity of `repo_url` and `repo_path`:

```python
def test_generate_request_extracts_project_name() -> None:
    from docsfy.models import GenerateRequest

    req = GenerateRequest(repo_url="https://github.com/org/my-repo.git")
    assert req.project_name == "my-repo"

    req2 = GenerateRequest(repo_url="https://github.com/org/my-repo")
    assert req2.project_name == "my-repo"


def test_generate_request_requires_source() -> None:
    from docsfy.models import GenerateRequest

    with pytest.raises(Exception):
        GenerateRequest()


def test_generate_request_rejects_both() -> None:
    from docsfy.models import GenerateRequest

    with pytest.raises(Exception):
        GenerateRequest(
            repo_url="https://github.com/org/repo.git", repo_path="/some/path"
        )
```

### test_storage.py — Database Operations (7 tests)

Tests the async SQLite storage layer (via `aiosqlite`): database initialization, project CRUD operations, listing, and deletion. Each test runs against an isolated temporary database:

```python
@pytest.fixture
async def db_path(tmp_path: Path) -> Path:
    import docsfy.storage as storage

    db = tmp_path / "test.db"
    storage.DB_PATH = db
    storage.DATA_DIR = tmp_path
    storage.PROJECTS_DIR = tmp_path / "projects"
    await storage.init_db()
    return db


async def test_save_and_get_project(db_path: Path) -> None:
    from docsfy.storage import get_project, save_project

    await save_project(
        name="my-repo",
        repo_url="https://github.com/org/my-repo.git",
        status="generating",
    )
    project = await get_project("my-repo")
    assert project is not None
    assert project["name"] == "my-repo"
    assert project["status"] == "generating"
```

### test_json_parser.py — JSON Parsing (7 tests)

Tests the `parse_json_response` function that extracts JSON from AI-generated output, which may include surrounding text, markdown code blocks, nested braces, and escaped characters:

```python
def test_parse_json_from_code_block() -> None:
    from docsfy.json_parser import parse_json_response

    raw = '```json\n{"project_name": "test", "navigation": []}\n```'
    result = parse_json_response(raw)
    assert result is not None
    assert result["project_name"] == "test"


def test_parse_json_returns_none_for_garbage() -> None:
    from docsfy.json_parser import parse_json_response

    result = parse_json_response("this is not json at all")
    assert result is None
```

### test_repository.py — Git Operations (6 tests)

Tests repository name extraction (HTTPS and SSH URLs), shallow cloning with `--depth 1`, SHA retrieval via `git rev-parse`, and error handling for failed clone and rev-parse operations. External `subprocess.run` calls are mocked:

```python
def test_clone_repo_success(tmp_path: Path) -> None:
    from docsfy.repository import clone_repo

    with patch("docsfy.repository.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="abc123def\n", stderr=""),
        ]
        repo_path, sha = clone_repo("https://github.com/org/repo.git", tmp_path)

    assert repo_path == tmp_path / "repo"
    assert sha == "abc123def"
    assert mock_run.call_count == 2
```

### test_generator.py — AI-Powered Generation (5 tests)

Tests the documentation planner and page generator with mocked AI CLI calls. Covers successful plan generation, AI failure handling, malformed JSON responses, page generation, and cache-hit behavior:

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

### test_renderer.py — HTML Rendering (3 tests)

Tests single-page HTML rendering, full site generation (including `index.html`, page HTML files, and CSS assets), and search index generation:

```python
def test_render_site(tmp_path: Path) -> None:
    from docsfy.renderer import render_site

    plan = {
        "project_name": "test-repo",
        "tagline": "A test project",
        "navigation": [
            {
                "group": "Getting Started",
                "pages": [
                    {"slug": "introduction", "title": "Introduction", "description": "Overview"},
                ],
            },
        ],
    }
    pages = {"introduction": "# Introduction\n\nWelcome to test-repo."}
    output_dir = tmp_path / "site"

    render_site(plan=plan, pages=pages, output_dir=output_dir)

    assert (output_dir / "index.html").exists()
    assert (output_dir / "introduction.html").exists()
    assert (output_dir / "assets" / "style.css").exists()


def test_search_index_generated(tmp_path: Path) -> None:
    from docsfy.renderer import render_site

    plan = {
        "project_name": "test-repo",
        "tagline": "Test",
        "navigation": [
            {"group": "Docs", "pages": [{"slug": "intro", "title": "Intro", "description": ""}]}
        ],
    }
    pages = {"intro": "# Intro\n\nSome searchable content here."}
    output_dir = tmp_path / "site"

    render_site(plan=plan, pages=pages, output_dir=output_dir)
    assert (output_dir / "search-index.json").exists()
```

### test_config.py — Configuration Settings (3 tests)

Validates the `Settings` Pydantic model with default values, custom environment overrides, and invalid input rejection:

```python
def test_default_settings() -> None:
    from docsfy.config import Settings

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
    assert settings.ai_provider == "claude"
    assert settings.ai_model == "claude-opus-4-6[1m]"
    assert settings.ai_cli_timeout == 60
    assert settings.log_level == "INFO"


def test_invalid_timeout_rejected() -> None:
    from docsfy.config import Settings

    with patch.dict(os.environ, {"AI_CLI_TIMEOUT": "0"}, clear=True):
        with pytest.raises(Exception):
            Settings(_env_file=None)
```

### test_ai_client.py — AI Provider Configuration (2 tests)

Verifies that the AI client module correctly exports provider configurations and that all three supported providers (`claude`, `gemini`, `cursor`) are registered:

```python
def test_reexports_available() -> None:
    from docsfy.ai_client import PROVIDERS, VALID_AI_PROVIDERS

    assert "claude" in PROVIDERS
    assert "gemini" in PROVIDERS
    assert "cursor" in PROVIDERS
    assert VALID_AI_PROVIDERS == frozenset({"claude", "gemini", "cursor"})


def test_provider_config_types() -> None:
    from docsfy.ai_client import PROVIDERS, ProviderConfig

    for name, config in PROVIDERS.items():
        assert isinstance(config, ProviderConfig)
        assert isinstance(config.binary, str)
        assert callable(config.build_cmd)
```

### test_prompts.py — Prompt Generation (2 tests)

Tests that generated AI prompts contain the expected project name, output format instructions, and required schema fields:

```python
def test_build_planner_prompt() -> None:
    from docsfy.prompts import build_planner_prompt

    prompt = build_planner_prompt("my-repo")
    assert "my-repo" in prompt
    assert "JSON" in prompt
    assert "project_name" in prompt
    assert "navigation" in prompt
```

### test_integration.py — End-to-End Flow (1 test)

A single comprehensive integration test that exercises the complete documentation generation lifecycle with mocked AI calls:

1. Saves a project with status `"generating"`
2. Runs the generation pipeline (planning + page generation + rendering)
3. Verifies status endpoint reports `"ready"`
4. Checks project details include the commit SHA
5. Confirms HTML documentation pages are served correctly
6. Downloads the project as a gzip archive
7. Deletes the project and verifies it returns 404

```python
async def test_full_flow_mock(client: AsyncClient, tmp_path: Path) -> None:
    """Test the full generate -> status -> download flow with mocked AI."""
    import docsfy.storage as storage

    sample_plan = {
        "project_name": "test-repo",
        "tagline": "A test project",
        "navigation": [
            {
                "group": "Getting Started",
                "pages": [
                    {"slug": "introduction", "title": "Introduction", "description": "Overview"},
                ],
            }
        ],
    }

    with (
        patch("docsfy.main.check_ai_cli_available", return_value=(True, "")),
        patch("docsfy.main.clone_repo", return_value=(tmp_path / "repo", "abc123")),
        patch("docsfy.main.run_planner", return_value=sample_plan),
        patch(
            "docsfy.main.generate_all_pages",
            return_value={"introduction": "# Intro\n\nWelcome!"},
        ),
    ):
        from docsfy.main import _run_generation

        await storage.save_project(
            name="test-repo",
            repo_url="https://github.com/org/test-repo.git",
            status="generating",
        )
        await _run_generation(
            repo_url="https://github.com/org/test-repo.git",
            repo_path=None,
            project_name="test-repo",
            ai_provider="claude",
            ai_model="opus",
            ai_cli_timeout=60,
        )

    # Verify the full lifecycle
    response = await client.get("/api/status")
    assert response.json()["projects"][0]["status"] == "ready"

    response = await client.get("/docs/test-repo/introduction.html")
    assert "Welcome!" in response.text

    response = await client.get("/api/projects/test-repo/download")
    assert response.headers["content-type"] == "application/gzip"

    response = await client.delete("/api/projects/test-repo")
    assert response.status_code == 200
```

## Testing Patterns

### Async-First Design

All tests that interact with the FastAPI app or the async SQLite storage layer are written as `async def` functions. With `asyncio_mode = "auto"` configured in `pyproject.toml`, pytest-asyncio handles the event loop automatically — no `@pytest.mark.asyncio` decorators are needed.

### Test Isolation

Every test that touches the filesystem or database uses pytest's built-in `tmp_path` fixture to create a unique temporary directory. Storage module globals (`DB_PATH`, `DATA_DIR`, `PROJECTS_DIR`) are redirected to temporary paths and restored after each test, ensuring no state leaks between tests.

### Mocking External Dependencies

AI CLI calls and git subprocess calls are mocked with `unittest.mock.patch` to keep tests fast, deterministic, and free of external dependencies. No real AI providers or git repositories are needed to run the test suite:

```python
with patch("docsfy.generator.call_ai_cli", return_value=(True, json.dumps(sample_plan))):
    plan = await run_planner(...)
```

### ASGI Transport for API Testing

Instead of starting a live HTTP server, tests use `httpx.AsyncClient` with `ASGITransport` to send requests directly through the FastAPI application in-process. This approach is faster and avoids port conflicts:

```python
transport = ASGITransport(app=app)
async with AsyncClient(transport=transport, base_url="http://test") as ac:
    yield ac
```

## Code Quality Checks

The project uses [pre-commit](https://pre-commit.com/) hooks defined in `.pre-commit-config.yaml` for automated quality enforcement:

| Tool | Version | Purpose |
|------|---------|---------|
| **ruff** | v0.15.2 | Linting and code formatting |
| **flake8** | v7.3.0 | Linting with RedHatQE M511 plugin |
| **mypy** | v1.19.1 | Static type checking (excludes `tests/`) |
| **gitleaks** | v8.30.0 | Secrets detection in commits |
| **detect-secrets** | v1.5.0 | Secret pattern detection |
| **pre-commit-hooks** | v6.0.0 | AST checks, merge conflicts, trailing whitespace, large files |

Run all pre-commit checks manually:

```bash
pre-commit run --all-files
```

> **Note:** mypy is configured to exclude the `tests/` directory, allowing test code to use relaxed type annotations while keeping production code strictly typed.
