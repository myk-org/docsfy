# Generation Endpoint

The generation endpoint triggers asynchronous documentation generation for a git repository. It accepts either a remote repository URL or a local filesystem path and returns immediately while generation runs in the background.

## Endpoint

```
POST /api/generate
```

**Content-Type:** `application/json`

**Success Status Code:** `202 Accepted`

---

## Request Body Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo_url` | `string \| null` | Conditional | `null` | Git repository URL (HTTPS or SSH) |
| `repo_path` | `string \| null` | Conditional | `null` | Absolute path to a local git repository |
| `ai_provider` | `string \| null` | No | Server default | AI provider to use for generation |
| `ai_model` | `string \| null` | No | Server default | AI model identifier |
| `ai_cli_timeout` | `integer \| null` | No | Server default | Timeout in seconds for AI CLI operations |
| `force` | `boolean` | No | `false` | Force full regeneration, ignoring cache |

> **Note:** Exactly one of `repo_url` or `repo_path` must be provided. See [Mutual Exclusivity](#mutual-exclusivity-of-repo_url-and-repo_path) below.

### `repo_url`

A git repository URL in HTTPS or SSH format. When provided, the server clones the repository to a temporary directory before generating documentation.

Accepted formats:

```
# HTTPS (with or without .git suffix)
https://github.com/org/repo
https://github.com/org/repo.git

# SSH (with or without .git suffix)
git@github.com:org/repo
git@github.com:org/repo.git
```

The URL is validated against two regular expression patterns:

```python
# HTTPS pattern
r"^https?://[\w.\-]+/[\w.\-]+/[\w.\-]+(\.git)?$"

# SSH pattern
r"^git@[\w.\-]+:[\w.\-]+/[\w.\-]+(\.git)?$"
```

> **Warning:** URLs with trailing slashes, query parameters, fragments, or subpaths (e.g., `https://github.com/org/repo/tree/main`) will be rejected by validation.

### `repo_path`

An absolute filesystem path to a local git repository. When provided, the server reads the repository directly without cloning.

Two checks are performed during validation:

1. The path must exist on the filesystem
2. The path must contain a `.git` subdirectory (confirming it is a git repository root)

```python
path = Path(v)
if not path.exists():
    raise ValueError(f"Repository path does not exist: '{v}'")
if not (path / ".git").exists():
    raise ValueError(f"Not a git repository (no .git directory): '{v}'")
```

### `ai_provider`

The AI provider CLI to use for documentation generation. Accepted values:

| Value | Description |
|-------|-------------|
| `"claude"` | Anthropic Claude CLI |
| `"gemini"` | Google Gemini CLI |
| `"cursor"` | Cursor AI CLI |

When omitted, the server falls back to the `AI_PROVIDER` environment variable or the built-in default of `"claude"`.

### `ai_model`

The specific AI model to use within the chosen provider. This is a free-form string — no server-side validation is performed on the model name.

When omitted, the server falls back to the `AI_MODEL` environment variable or the built-in default of `"claude-opus-4-6[1m]"`.

### `ai_cli_timeout`

Timeout in seconds for individual AI CLI operations. Must be a positive integer (greater than 0).

When omitted, the server falls back to the `AI_CLI_TIMEOUT` environment variable or the built-in default of `60` seconds.

### `force`

When set to `true`, the endpoint clears the project's page cache and regenerates all documentation from scratch. When `false` (the default), the server skips regeneration if the repository's HEAD commit SHA matches the last successfully generated commit.

---

## Mutual Exclusivity of `repo_url` and `repo_path`

The request body must contain exactly one of `repo_url` or `repo_path`. This constraint is enforced by a Pydantic model validator that runs after individual field validation:

```python
@model_validator(mode="after")
def validate_source(self) -> GenerateRequest:
    if not self.repo_url and not self.repo_path:
        msg = "Either 'repo_url' or 'repo_path' must be provided"
        raise ValueError(msg)
    if self.repo_url and self.repo_path:
        msg = "Provide either 'repo_url' or 'repo_path', not both"
        raise ValueError(msg)
    return self
```

The three possible outcomes:

| `repo_url` | `repo_path` | Result |
|------------|-------------|--------|
| provided | omitted | Valid — clone remote repository |
| omitted | provided | Valid — use local repository |
| omitted | omitted | **422** — `"Either 'repo_url' or 'repo_path' must be provided"` |
| provided | provided | **422** — `"Provide either 'repo_url' or 'repo_path', not both"` |

---

## Response Format

### Success (`202 Accepted`)

Generation is started as a background task. The endpoint returns immediately without waiting for completion.

```json
{
  "project": "repo",
  "status": "generating"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `project` | `string` | Derived project name (used to query status and retrieve docs) |
| `status` | `string` | Always `"generating"` on a successful request |

#### Project Name Derivation

The project name is automatically extracted from the repository source:

- **From `repo_url`**: the last path segment of the URL, with `.git` stripped if present
  - `https://github.com/org/my-app.git` → `"my-app"`
  - `git@github.com:org/my-app` → `"my-app"`

- **From `repo_path`**: the resolved directory name
  - `/home/user/projects/my-app` → `"my-app"`

```python
@property
def project_name(self) -> str:
    if self.repo_url:
        name = self.repo_url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name
    if self.repo_path:
        return Path(self.repo_path).resolve().name
    return "unknown"
```

### Error Responses

#### `409 Conflict` — Concurrent Generation

Returned when a generation task is already in progress for the same project name.

```json
{
  "detail": "Project 'repo' is already being generated"
}
```

The server tracks active generations in a module-level set. A project name is added to this set when generation begins and removed when it completes (whether successfully or with an error).

#### `422 Unprocessable Entity` — Validation Error

Returned when the request body fails validation. FastAPI returns errors in the standard Pydantic validation error format:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, Either 'repo_url' or 'repo_path' must be provided",
      "input": {},
      "url": "https://errors.pydantic.dev/2.11/v/value_error"
    }
  ]
}
```

Common validation errors:

| Condition | Error Message |
|-----------|---------------|
| Neither source provided | `Either 'repo_url' or 'repo_path' must be provided` |
| Both sources provided | `Provide either 'repo_url' or 'repo_path', not both` |
| Malformed URL | `Invalid git repository URL: '<url>'` |
| Path does not exist | `Repository path does not exist: '<path>'` |
| Path is not a git repository | `Not a git repository (no .git directory): '<path>'` |
| `ai_cli_timeout` ≤ 0 | `Input should be greater than 0` |
| Invalid `ai_provider` | `Input should be 'claude', 'gemini' or 'cursor'` |

---

## Examples

### Generate from a remote HTTPS repository

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/repo.git"}'
```

```json
{
  "project": "repo",
  "status": "generating"
}
```

### Generate from an SSH URL

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "git@github.com:org/repo.git"}'
```

### Generate from a local repository

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/home/user/projects/my-app"}'
```

```json
{
  "project": "my-app",
  "status": "generating"
}
```

### Force regeneration with custom AI settings

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/repo.git",
    "ai_provider": "gemini",
    "ai_model": "gemini-2.5-pro",
    "ai_cli_timeout": 120,
    "force": true
  }'
```

### Invalid request — both sources provided

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/repo.git",
    "repo_path": "/home/user/projects/repo"
  }'
```

Returns `422`:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "Value error, Provide either 'repo_url' or 'repo_path', not both"
    }
  ]
}
```

---

## Background Generation Lifecycle

The `POST /api/generate` endpoint is asynchronous by design. Understanding the background lifecycle is important for integrating with this endpoint.

1. **Request accepted** — The endpoint validates the request, records the project with status `"generating"`, and spawns a background task.
2. **AI CLI check** — The background task verifies that the configured AI CLI tool is available. If not, the project status is set to `"error"`.
3. **Repository resolution** — For `repo_url`, the repository is cloned to a temporary directory. For `repo_path`, the local path is used directly.
4. **Cache check** (when `force` is `false`) — If the repository HEAD commit SHA matches the last successful generation, the task completes immediately without regenerating.
5. **Planning** — The AI generates a documentation plan (page structure and navigation).
6. **Page generation** — Each documentation page is generated by the AI, with caching support.
7. **Rendering** — The generated pages are rendered into a static site.
8. **Completion** — The project status is updated to `"ready"` with the commit SHA and page count.

If any step fails, the project status is set to `"error"` with a descriptive error message.

> **Tip:** After submitting a generation request, poll `GET /api/projects/{name}` using the `project` value from the response to track progress and check for completion or errors.

---

## Server Defaults

When optional fields are omitted from the request, the server applies defaults from environment variables or built-in values:

| Field | Environment Variable | Built-in Default |
|-------|---------------------|------------------|
| `ai_provider` | `AI_PROVIDER` | `"claude"` |
| `ai_model` | `AI_MODEL` | `"claude-opus-4-6[1m]"` |
| `ai_cli_timeout` | `AI_CLI_TIMEOUT` | `60` |

These can be configured via a `.env` file in the project root:

```env
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60
```
