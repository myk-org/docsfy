# Contributing

Thank you for your interest in contributing to docsfy! This guide covers everything you need to set up your development environment, follow project conventions, and submit high-quality contributions.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — the only supported package manager (do not use pip)
- **Git**
- **Node.js and npm** — required for AI CLI tools and client-side dependencies

> **Warning:** docsfy does not support pip-based workflows. All dependency management, virtual environment creation, and script execution must go through `uv`.

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
```

### 2. Install Dependencies

Use `uv` to create a virtual environment and install all dependencies, including development extras:

```bash
uv sync
```

### 3. Install Pre-commit Hooks

Pre-commit hooks are mandatory. They enforce code quality on every commit:

```bash
uv run pre-commit install
```

To verify your setup, run the hooks against all files:

```bash
uv run pre-commit run --all-files
```

## Build System

docsfy uses **[hatchling](https://hatch.pypa.io/)** as its build backend. The project metadata and build configuration live in `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

To build the package:

```bash
uv build
```

> **Note:** Since `uv` is the only supported package manager, always use `uv run` to execute project scripts and tools rather than activating a virtual environment manually.

## Code Style and Linting

docsfy enforces consistent code style through pre-commit hooks that run automatically on every commit. The following tools are configured:

### Ruff (Lint + Format)

[Ruff](https://docs.astral.sh/ruff/) handles both linting and code formatting in a single tool. It replaces the need for separate formatters like Black.

```bash
# Check for lint errors
uv run ruff check .

# Auto-fix lint errors where possible
uv run ruff check --fix .

# Format code
uv run ruff format .

# Check formatting without modifying files
uv run ruff format --check .
```

### mypy (Strict Mode)

Type checking is enforced in **strict mode**. All code must include type annotations:

```bash
uv run mypy .
```

> **Tip:** When adding new functions or methods, always include complete type annotations for parameters and return values. Strict mode requires explicit types — `Any` should be avoided unless truly necessary.

### flake8

flake8 provides additional lint checks beyond what Ruff covers:

```bash
uv run flake8 .
```

### Security Scanning

Two tools scan for secrets accidentally committed to the repository:

- **[gitleaks](https://github.com/gitleaks/gitleaks)** — scans git history for hardcoded secrets
- **[detect-secrets](https://github.com/Yelp/detect-secrets)** — prevents new secrets from being committed

> **Warning:** Never commit API keys, tokens, or credentials. If a pre-commit hook flags a secret, remove it from your code and rotate the exposed credential immediately.

### Standard Pre-commit Hooks

The configuration also includes standard hooks such as:

- Trailing whitespace removal
- End-of-file fixer
- YAML/TOML syntax validation
- Large file checks

### Running All Checks

To run the full pre-commit suite manually:

```bash
uv run pre-commit run --all-files
```

## Running Tests

### Unit Tests

Tests are run through **tox**, which uses `uv` under the hood:

```bash
uv run tox
```

To run only the unit test environment:

```bash
uv run tox -e tests
```

You can also run pytest directly for faster iteration during development:

```bash
uv run pytest
```

To run a specific test file or test function:

```bash
# Run a specific test file
uv run pytest tests/test_renderer.py

# Run a specific test by name
uv run pytest tests/test_renderer.py::test_markdown_to_html -v
```

### Unused Code Check

Tox includes an environment for detecting unused code:

```bash
uv run tox -e unused-code
```

> **Tip:** Run the unused-code check before submitting a pull request. Dead code should be removed, not left commented out.

## Project Structure

docsfy follows a `src`-layout Python package structure:

```
docsfy/
├── docs/
│   └── plans/                  # Design documents
├── src/
│   └── docsfy/
│       ├── main.py             # FastAPI application entry point
│       └── ...                 # Application modules
├── tests/                      # Unit and integration tests
├── pyproject.toml              # Project metadata and build config
├── .pre-commit-config.yaml     # Pre-commit hook definitions
├── tox.ini                     # Tox test environments
├── Dockerfile                  # Container build
└── docker-compose.yaml         # Local development with Docker
```

Key application components from the design:

| Module Area | Responsibility |
|-------------|---------------|
| API layer | FastAPI routes for `/api/generate`, `/api/status`, `/api/projects`, `/health` |
| Pipeline | Clone → AI Planner → AI Content Generator → HTML Renderer |
| AI CLI integration | Provider abstraction for Claude, Gemini, and Cursor |
| HTML renderer | Jinja2 templates with bundled CSS/JS assets |
| Storage | SQLite for metadata, filesystem for generated docs |

## Conventions

### Python Version

All code must be compatible with Python 3.12+. Use modern Python features (type unions with `|`, `match` statements, etc.) where appropriate.

### Async First

docsfy is built on FastAPI. Use `async def` for route handlers and I/O-bound operations. CPU-bound work (like subprocess calls to AI CLIs) should be offloaded with `asyncio.to_thread()`:

```python
result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)
```

### Type Annotations

With mypy in strict mode, all functions require complete type annotations:

```python
# Good
async def generate_page(project_name: str, page_id: int) -> tuple[bool, str]:
    ...

# Bad — will fail mypy strict
async def generate_page(project_name, page_id):
    ...
```

### Dataclasses for Configuration

Use frozen dataclasses for configuration objects, following the established provider pattern:

```python
@dataclass(frozen=True)
class ProviderConfig:
    binary: str
    build_cmd: Callable
    uses_own_cwd: bool = False
```

### Environment Variables

Configuration is read from environment variables. Use descriptive names with a clear prefix pattern:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `claude` | AI CLI provider to use |
| `AI_MODEL` | `claude-opus-4-6` | Model identifier |
| `AI_CLI_TIMEOUT` | `60` | Timeout in minutes |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Error Handling

Functions that invoke AI CLI subprocesses return `tuple[bool, str]` — a success flag and the output or error message. Follow this pattern for consistency.

## Docker Development

For running the full stack locally:

```bash
# Build and start the service
docker compose up --build

# Health check
curl http://localhost:8000/health
```

Create a `.env` file from the example for local configuration:

```bash
cp .env.example .env
# Edit .env with your API keys
```

> **Warning:** Never commit your `.env` file. It is listed in `.gitignore` to prevent accidental exposure of API keys.

## Submitting Changes

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the conventions above.

3. **Run the full check suite** before committing:
   ```bash
   uv run pre-commit run --all-files
   uv run tox
   ```

4. **Commit with clear messages** describing *what* changed and *why*.

5. **Open a pull request** against `main` with a clear description of the changes.

### Pull Request Checklist

- [ ] All pre-commit hooks pass (`uv run pre-commit run --all-files`)
- [ ] All tests pass (`uv run tox`)
- [ ] No unused code introduced (`uv run tox -e unused-code`)
- [ ] Type annotations added for all new functions
- [ ] New features include corresponding tests
- [ ] No secrets or credentials in the diff
