# HTTP API and WebSocket Reference

> **Note:** Examples use `http://localhost:8000`. Host, port, cookie security, and default AI settings are configurable. See [Configuration Reference](configuration-reference.html) for deployment settings.

## Authentication

Protected HTTP routes accept either `Authorization: Bearer <token>` or a valid `docsfy_session` cookie. The WebSocket endpoint accepts either the same session cookie or `?token=<token>` in the connection URL.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `Authorization` | HTTP header | none | `Bearer <ADMIN_KEY>` or `Bearer <user_api_key>`. Accepted on protected `/api/*` routes and `/docs/*` file routes. |
| `docsfy_session` | cookie | none | Opaque session token created by `POST /api/auth/login`. Cookie attributes: `HttpOnly`, `SameSite=Strict`, `Max-Age=28800`; `Secure` follows the server `secure_cookies` setting. |
| `token` | query string | none | Raw `ADMIN_KEY` or user API key for `ws://.../api/ws`. |

```bash
curl -H "Authorization: Bearer <USER_API_KEY>" \
  http://localhost:8000/api/projects
```

```javascript
const ws = new WebSocket("ws://localhost:8000/api/ws?token=<USER_API_KEY>");
```

Authenticates protected HTTP requests and the WebSocket handshake.

Access rules:

| Role or identity | Read project data | Generate, abort, delete | Admin endpoints | Key rotation |
| --- | --- | --- | --- | --- |
| `admin` DB user | Yes | Yes | Yes | Yes |
| Bootstrap `ADMIN_KEY` identity | Yes | Yes | Yes | No |
| `user` | Yes | Yes, for owned variants only | No | Yes |
| `viewer` | Yes | No | No | Yes |

> **Warning:** Project and variant read routes return `404` instead of `403` when a resource exists but is not accessible to the caller.


> **Warning:** Unauthenticated `/docs/*` requests with `Accept: text/html` receive `302 /login`. Other unauthenticated `/docs/*` requests receive `401 {"detail":"Unauthorized"}`.

## Common response objects

### `ProjectVariant` object

Used by project listing, project lookup, generation lookup, and WebSocket `sync` payloads.

| Name | Type | Description |
| --- | --- | --- |
| `name` | string | Project name derived from `repo_url` or the basename of `repo_path`. |
| `branch` | string | Git branch for this variant. |
| `ai_provider` | string | AI provider used for generation. |
| `ai_model` | string | AI model used for generation. |
| `owner` | string | Variant owner username. May be an empty string for legacy ownerless rows. |
| `repo_url` | string | Stored source value. For local generation, this is the submitted `repo_path`. |
| `status` | string | Variant status. See the status table below. |
| `current_stage` | string or `null` | Current generation stage, or `null` when not set. |
| `last_commit_sha` | string or `null` | Commit SHA used for the most recent successful generation. |
| `last_generated` | string or `null` | Last successful generation timestamp in `YYYY-MM-DD HH:MM:SS` format. |
| `page_count` | integer | Current or final page count. |
| `error_message` | string or `null` | Terminal error text for `error` or `aborted` variants. |
| `plan_json` | string or `null` | Stringified JSON plan. This field is not parsed for you. |
| `generation_id` | string or `null` | Hyphenated UUID that identifies the variant. |
| `created_at` | string | Row creation timestamp in `YYYY-MM-DD HH:MM:SS` format. |
| `updated_at` | string | Last update timestamp in `YYYY-MM-DD HH:MM:SS` format. |

Status values:

| Value | Description |
| --- | --- |
| `generating` | Generation is active. |
| `ready` | A rendered site is available. |
| `error` | Generation failed. |
| `aborted` | Generation was cancelled. |

`current_stage` values:

| Value | Appears in | Description |
| --- | --- | --- |
| `cloning` | HTTP, WebSocket `progress` | Cloning or opening the source repository. |
| `incremental_planning` | HTTP, WebSocket `progress` | Selecting pages for incremental regeneration. |
| `planning` | HTTP, WebSocket `progress` | Building the initial page plan. |
| `generating_pages` | HTTP, WebSocket `progress` | Generating page markdown. |
| `validating` | HTTP, WebSocket `progress` | Validating generated pages. |
| `cross_linking` | HTTP, WebSocket `progress` | Fixing and adding internal links. |
| `rendering` | HTTP, WebSocket `progress` | Rendering the final static site. |
| `up_to_date` | HTTP only | The variant already matched the current commit and was marked ready without regenerating content. |
| `null` | HTTP | No stage is currently set. |

```json
{
  "name": "for-testing-only",
  "branch": "main",
  "ai_provider": "claude",
  "ai_model": "opus",
  "owner": "admin",
  "repo_url": "https://github.com/myk-org/for-testing-only",
  "status": "ready",
  "current_stage": null,
  "last_commit_sha": "abc123def456",
  "last_generated": "2026-04-18 12:34:56",
  "page_count": 12,
  "error_message": null,
  "plan_json": "{\"project_name\":\"for-testing-only\",\"tagline\":\"Test repo\",\"navigation\":[]}",
  "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b",
  "created_at": "2026-04-18 12:00:00",
  "updated_at": "2026-04-18 12:34:56"
}
```

Returns a complete stored variant record. See [Tracking Generation Progress](track-generation-progress.html) for the dashboard view of these states.

### `ProjectsCollection` object

Used by `GET /api/projects`, `GET /api/status`, and WebSocket `sync`.

| Name | Type | Description |
| --- | --- | --- |
| `projects` | array of `ProjectVariant` | Visible variants for the caller, including non-ready variants. |
| `known_models` | object | Ready models grouped by provider. This list is global, not access-filtered. |
| `known_branches` | object | Ready branches grouped by project name. Admins see all owners; non-admin callers see only their own ready branches. |

```json
{
  "projects": [
    {
      "name": "for-testing-only",
      "branch": "main",
      "ai_provider": "claude",
      "ai_model": "opus",
      "owner": "admin",
      "repo_url": "https://github.com/myk-org/for-testing-only",
      "status": "ready",
      "current_stage": null,
      "last_commit_sha": "abc123def456",
      "last_generated": "2026-04-18 12:34:56",
      "page_count": 12,
      "error_message": null,
      "plan_json": null,
      "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b",
      "created_at": "2026-04-18 12:00:00",
      "updated_at": "2026-04-18 12:34:56"
    }
  ],
  "known_models": {
    "claude": ["opus"],
    "cursor": ["gpt-5.4-xhigh-fast"]
  },
  "known_branches": {
    "for-testing-only": ["main", "dev"]
  }
}
```

Returns a full snapshot for listing and refresh flows.

### Error body

Most explicit HTTP errors use a `detail` field. Request validation failures use FastAPI's default `422` body, where `detail` is an array.

```json
{"detail": "Unauthorized"}
```

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "branch"],
      "msg": "Value error, Invalid branch name: 'release/1.0'. Branch names cannot contain slashes — use hyphens instead (e.g., release-1.x).",
      "input": "release/1.0"
    }
  ]
}
```

Returns machine-readable error data for non-2xx responses.

## Health and discovery

### `GET /health`

Public health check.

Auth: `Public`

No parameters.

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok"}
```

Returns `200 OK` when the service is up.

### `GET /api/models`

Public discovery endpoint for supported providers, server defaults, and known ready models.

Auth: `Public`

No parameters.

Response body:

| Name | Type | Description |
| --- | --- | --- |
| `providers` | array of strings | Supported provider IDs. The current set is `claude`, `gemini`, `cursor`. |
| `default_provider` | string | Server default provider used when `POST /api/generate` omits `ai_provider`. |
| `default_model` | string | Server default model used when `POST /api/generate` omits `ai_model`. |
| `known_models` | object | Ready models grouped by provider. |

```bash
curl http://localhost:8000/api/models
```

```json
{
  "providers": ["claude", "gemini", "cursor"],
  "default_provider": "cursor",
  "default_model": "gpt-5.4-xhigh-fast",
  "known_models": {
    "claude": ["opus"],
    "gemini": ["pro"]
  }
}
```

Returns `200 OK`. `known_models` is derived from ready variants only.

## Authentication endpoints

### `POST /api/auth/login`

Create a session cookie and return the authenticated identity.

Auth: `Public`

Body parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `username` | string | none | Login name. Use `admin` only when authenticating with the bootstrap `ADMIN_KEY`. |
| `api_key` | string | none | Bootstrap `ADMIN_KEY` or a stored user API key. |

Response body:

| Name | Type | Description |
| --- | --- | --- |
| `username` | string | Authenticated username. |
| `role` | string | `admin`, `user`, or `viewer`. |
| `is_admin` | boolean | `true` for the bootstrap admin identity and DB-backed admin users. |

Response headers:

| Name | Value | Description |
| --- | --- | --- |
| `Set-Cookie` | `docsfy_session=...` | Creates the `docsfy_session` cookie for browser and WebSocket session auth. |

```bash
curl -i -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","api_key":"<ADMIN_KEY>"}'
```

```json
{
  "username": "admin",
  "role": "admin",
  "is_admin": true
}
```

Returns `200 OK` and sets `docsfy_session`. For DB users, `username` must match the owner of the submitted API key. Returns `400` for malformed or non-object JSON, and `401` for invalid credentials.

### `POST /api/auth/logout`

Delete the current session cookie and remove its server-side session row if present.

Auth: `Public`

No parameters.

```bash
curl -X POST \
  -b "docsfy_session=<SESSION_TOKEN>" \
  http://localhost:8000/api/auth/logout
```

```json
{"ok": true}
```

Returns `200 OK`. The response always clears `docsfy_session`, even when no valid session existed.

### `GET /api/auth/me`

Return the current authenticated identity.

Auth: `Bearer token or session cookie`

No parameters.

```bash
curl -H "Authorization: Bearer <USER_API_KEY>" \
  http://localhost:8000/api/auth/me
```

```json
{
  "username": "alice",
  "role": "viewer",
  "is_admin": false
}
```

Returns `200 OK` with the active identity, or `401` when unauthenticated.

### `POST /api/auth/rotate-key`

Rotate the current DB-backed user's API key.

Auth: `Bearer token or session cookie`

Body parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `new_key` | string | auto-generated | Optional replacement API key. Must be at least 16 characters when provided. |

Response body:

| Name | Type | Description |
| --- | --- | --- |
| `username` | string | Rotated username. |
| `new_api_key` | string | New raw API key. |

Response headers:

| Name | Value | Description |
| --- | --- | --- |
| `Cache-Control` | `no-store` | Prevents caching of the returned secret. |
| `Set-Cookie` | expired `docsfy_session` | Clears the current session cookie. |

```bash
curl -X POST http://localhost:8000/api/auth/rotate-key \
  -b "docsfy_session=<SESSION_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"new_key":"my-very-secure-custom-password-123"}'
```

```json
{
  "username": "alice",
  "new_api_key": "my-very-secure-custom-password-123"
}
```

Returns `200 OK`, invalidates all sessions for that user, and clears the caller's `docsfy_session`. Returns `400` for malformed JSON, non-object JSON, short custom keys, or when the caller is the bootstrap `ADMIN_KEY` identity.

## Project listing and lookup

### `GET /api/projects` and `GET /api/status`

List visible project variants and the known ready models and branches.

Auth: `Bearer token or session cookie`

No parameters.

```bash
curl -H "Authorization: Bearer <USER_API_KEY>" \
  http://localhost:8000/api/projects
```

```json
{
  "projects": [
    {
      "name": "for-testing-only",
      "branch": "main",
      "ai_provider": "claude",
      "ai_model": "opus",
      "owner": "alice",
      "repo_url": "https://github.com/myk-org/for-testing-only",
      "status": "ready",
      "current_stage": null,
      "last_commit_sha": "abc123def456",
      "last_generated": "2026-04-18 12:34:56",
      "page_count": 12,
      "error_message": null,
      "plan_json": null,
      "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b",
      "created_at": "2026-04-18 12:00:00",
      "updated_at": "2026-04-18 12:34:56"
    }
  ],
  "known_models": {
    "claude": ["opus"]
  },
  "known_branches": {
    "for-testing-only": ["main", "dev"]
  }
}
```

Returns a `ProjectsCollection` object. Admins see all variants. Non-admin callers see owned variants plus any variants shared with them. `GET /api/status` is a direct alias of `GET /api/projects`.

### `GET /api/projects/by-id/{generation_id}`

Look up a variant by generation UUID.

Auth: `Bearer token or session cookie`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `generation_id` | string | none | Hyphenated UUID from `POST /api/generate` or a stored `ProjectVariant.generation_id`. |

```bash
curl -H "Authorization: Bearer <USER_API_KEY>" \
  http://localhost:8000/api/projects/by-id/5bf1495b-b6fa-4318-841c-dced628a2c5b
```

```json
{
  "name": "for-testing-only",
  "branch": "main",
  "ai_provider": "claude",
  "ai_model": "opus",
  "owner": "alice",
  "repo_url": "https://github.com/myk-org/for-testing-only",
  "status": "ready",
  "current_stage": null,
  "last_commit_sha": "abc123def456",
  "last_generated": "2026-04-18 12:34:56",
  "page_count": 12,
  "error_message": null,
  "plan_json": null,
  "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b",
  "created_at": "2026-04-18 12:00:00",
  "updated_at": "2026-04-18 12:34:56"
}
```

Returns a `ProjectVariant` object. Returns `400` for invalid UUID format and `404` when the generation ID does not exist or is not visible to the caller.

### `GET /api/projects/{name}`

List all visible variants for one project name.

Auth: `Bearer token or session cookie`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. Must start with an alphanumeric character and can contain letters, digits, `.`, `_`, and `-`. |

```bash
curl -H "Authorization: Bearer <ADMIN_KEY>" \
  http://localhost:8000/api/projects/for-testing-only
```

```json
{
  "name": "for-testing-only",
  "variants": [
    {
      "name": "for-testing-only",
      "branch": "main",
      "ai_provider": "claude",
      "ai_model": "opus",
      "owner": "alice",
      "repo_url": "https://github.com/myk-org/for-testing-only",
      "status": "ready",
      "current_stage": null,
      "last_commit_sha": "abc123def456",
      "last_generated": "2026-04-18 12:34:56",
      "page_count": 12,
      "error_message": null,
      "plan_json": null,
      "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b",
      "created_at": "2026-04-18 12:00:00",
      "updated_at": "2026-04-18 12:34:56"
    }
  ]
}
```

Returns all visible variants for that project name. Admins see all owners. Non-admin callers see owned variants plus shared variants. Returns `404` when no visible variants exist.

### `GET /api/projects/{name}/{branch}/{provider}/{model}`

Look up one variant by project name, branch, provider, and model.

Auth: `Bearer token or session cookie`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |
| `branch` | string | none | Branch name. Branches cannot contain `/` and must match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$`. |
| `provider` | string | none | Stored AI provider ID. |
| `model` | string | none | Stored AI model ID. |

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `owner` | string | none | Admin-only owner disambiguation. Ignored for non-admin callers. |

```bash
curl -H "Authorization: Bearer <ADMIN_KEY>" \
  "http://localhost:8000/api/projects/for-testing-only/main/claude/opus?owner=alice"
```

```json
{
  "name": "for-testing-only",
  "branch": "main",
  "ai_provider": "claude",
  "ai_model": "opus",
  "owner": "alice",
  "repo_url": "https://github.com/myk-org/for-testing-only",
  "status": "ready",
  "current_stage": null,
  "last_commit_sha": "abc123def456",
  "last_generated": "2026-04-18 12:34:56",
  "page_count": 12,
  "error_message": null,
  "plan_json": null,
  "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b",
  "created_at": "2026-04-18 12:00:00",
  "updated_at": "2026-04-18 12:34:56"
}
```

Returns a `ProjectVariant` object. Returns `404` when the variant does not exist or is not visible, and `409` when an admin lookup is ambiguous across multiple owners.

## Generation and control

### `POST /api/generate`

Start documentation generation for a remote Git repository or an admin-supplied local Git path.

Auth: `admin` or `user`

Body parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `repo_url` | string | none | Remote Git URL. Accepted forms are `http://host/org/repo`, `https://host/org/repo`, and `git@host:org/repo`, with optional `.git`. Exactly one of `repo_url` or `repo_path` is required. |
| `repo_path` | string | none | Absolute local Git repository path. Admin only. Exactly one of `repo_url` or `repo_path` is required. |
| `ai_provider` | string | server default | AI provider. Valid values: `claude`, `gemini`, `cursor`. |
| `ai_model` | string | server default | AI model name. |
| `ai_cli_timeout` | integer | server default | Per-call AI CLI timeout, in seconds. Must be greater than `0`. |
| `force` | boolean | `false` | Force full regeneration instead of reusing cached content. |
| `branch` | string | `main` | Branch to generate. Slashes are rejected. |

> **Note:** The request body does not include a `project_name` field. docsfy derives the project name from `repo_url` or the basename of `repo_path`.


> **Warning:** `repo_url` targets that point to localhost or private network addresses are rejected.


> **Warning:** `repo_path` must exist, be absolute, and contain a `.git` directory.

Common rejection cases:

| Condition | Status | Result |
| --- | --- | --- |
| Neither `repo_url` nor `repo_path` provided | `422` | FastAPI validation error |
| Both `repo_url` and `repo_path` provided | `422` | FastAPI validation error |
| Invalid `repo_url`, non-absolute `repo_path`, or invalid `branch` | `422` | FastAPI validation error |
| `repo_path` used by non-admin caller | `403` | Rejected before local path lookup |
| `repo_path` does not exist or is not a Git repo | `400` | Request rejected |
| Invalid `ai_provider` | `400` | Request rejected |
| Same owner/name/branch/provider/model already generating | `409` | Duplicate active generation |

Response body:

| Name | Type | Description |
| --- | --- | --- |
| `project` | string | Derived project name. |
| `status` | string | Always `generating` on acceptance. |
| `branch` | string | Resolved branch for the new run. |
| `generation_id` | string | Hyphenated UUID for the variant. |

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer <USER_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/myk-org/for-testing-only",
    "ai_provider": "claude",
    "ai_model": "opus",
    "branch": "main",
    "force": false
  }'
```

```json
{
  "project": "for-testing-only",
  "status": "generating",
  "branch": "main",
  "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b"
}
```

Returns `202 Accepted`. The server creates or updates the variant row immediately, then sends WebSocket `progress`, `status_change`, and `sync` messages to admins, the project owner, and users with access to that project/owner pair.

### `POST /api/projects/{name}/abort`

Abort the only active generation matching a project name.

Auth: `admin` or `user`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |

No query or body parameters.

> **Warning:** This route is not deterministic when more than one active variant exists for the same project name. Use the variant-scoped abort route for automation.

```bash
curl -X POST \
  -H "Authorization: Bearer <USER_API_KEY>" \
  http://localhost:8000/api/projects/for-testing-only/abort
```

```json
{"aborted": "for-testing-only"}
```

Returns `200 OK` when one matching active generation is cancelled. Non-admin callers can abort only their own active runs. Returns `404` when no active generation exists and `409` when more than one active variant exists or cancellation has not completed yet.

### `POST /api/projects/{name}/{branch}/{provider}/{model}/abort`

Abort one active variant.

Auth: `admin` or `user`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |
| `branch` | string | none | Branch name. |
| `provider` | string | none | AI provider. |
| `model` | string | none | AI model. |

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `owner` | string | none | Admin-only owner disambiguation when the active variant belongs to another owner or multiple owners have the same active variant. Ignored for non-admin callers. |

```bash
curl -X POST \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  "http://localhost:8000/api/projects/for-testing-only/main/claude/opus/abort?owner=alice"
```

```json
{"aborted": "for-testing-only/main/claude/opus"}
```

Returns `200 OK` when the matching task is cancelled. Returns `404` when no active generation matches, and `409` when the lookup is ambiguous or cancellation is still in progress. Successful aborts produce a terminal `status_change` and a follow-up `sync`.

## Deletion

### `DELETE /api/projects/{name}`

Delete all variants for one project name.

Auth: `admin` or `user`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `owner` | string | none | Required for admin callers. Ignored for non-admin callers, who can delete only their own variants. Use an empty value (`?owner=`) to target a legacy ownerless row. |

```bash
curl -X DELETE \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  "http://localhost:8000/api/projects/for-testing-only?owner=alice"
```

```json
{"deleted": "for-testing-only"}
```

Returns `200 OK` after deleting all variants for the target owner and project name. Returns `404` when nothing matches and `409` when any matching variant is still generating. A successful delete sends a WebSocket `sync`.

### `DELETE /api/projects/{name}/{branch}/{provider}/{model}`

Delete one variant.

Auth: `admin` or `user`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |
| `branch` | string | none | Branch name. |
| `provider` | string | none | AI provider. |
| `model` | string | none | AI model. |

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `owner` | string | none | Required for admin callers. Ignored for non-admin callers, who can delete only their own variants. Use an empty value (`?owner=`) to target a legacy ownerless row. |

```bash
curl -X DELETE \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  "http://localhost:8000/api/projects/for-testing-only/main/claude/opus?owner=alice"
```

```json
{"deleted": "for-testing-only/main/claude/opus"}
```

Returns `200 OK` after deleting the matching variant. Returns `404` when the variant does not exist and `409` when the variant is still generating. A successful delete sends a WebSocket `sync`.

## Downloads and generated files

### `GET /api/projects/{name}/download`

Download a tarball for the newest accessible ready variant of a project.

Auth: `Bearer token or session cookie`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |

No query parameters.

> **Warning:** This route resolves the newest accessible ready variant. For deterministic automation, use the variant-scoped download route.

Response headers:

| Name | Value | Description |
| --- | --- | --- |
| `Content-Type` | `application/gzip` | Gzip-compressed tar archive. |
| `Content-Disposition` | `attachment; filename="<name>-docs.tar.gz"` | Suggested download filename. |

```bash
curl -OJ \
  -H "Authorization: Bearer <USER_API_KEY>" \
  http://localhost:8000/api/projects/for-testing-only/download
```

Returns the generated site as a tarball. Returns `404` when no accessible ready variant exists or the site directory is missing, and may return `409` when the newest accessible variant is ambiguous across owners.

### `GET /api/projects/{name}/{branch}/{provider}/{model}/download`

Download a tarball for one variant.

Auth: `Bearer token or session cookie`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |
| `branch` | string | none | Branch name. |
| `provider` | string | none | AI provider. |
| `model` | string | none | AI model. |

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `owner` | string | none | Admin-only owner disambiguation when more than one owner has the same variant. Ignored for non-admin callers. |

Response headers:

| Name | Value | Description |
| --- | --- | --- |
| `Content-Type` | `application/gzip` | Gzip-compressed tar archive. |
| `Content-Disposition` | `attachment; filename="<name>-<branch>-<provider>-<model>-docs.tar.gz"` | Suggested download filename. |

```bash
curl -OJ \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  "http://localhost:8000/api/projects/for-testing-only/main/claude/opus/download?owner=alice"
```

Returns the generated site for that variant. Returns `400` when the variant exists but is not `ready`, `404` when the variant or site is missing, and `409` when an admin lookup is ambiguous across owners.

### `GET /docs/{project}/{path:path}`

Serve a file from the newest accessible ready variant.

Auth: `Bearer token or session cookie`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project` | string | none | Project name. |
| `path` | string | `index.html` when the resolved path is empty | File path inside the generated site, such as `index.html`, `search-index.json`, or `assets/style.css`. |

No query parameters.

> **Warning:** This route resolves the newest accessible ready variant. For deterministic automation, use the variant-scoped docs route.

```bash
curl -H "Authorization: Bearer <USER_API_KEY>" \
  http://localhost:8000/docs/for-testing-only/search-index.json
```

Returns raw file bytes from the generated site. Returns `404` when no accessible docs are available or the file does not exist, `403` when the resolved file path escapes the generated site directory, and may return `409` when the newest accessible variant is ambiguous across owners.

### `GET /docs/{project}/{branch}/{provider}/{model}/{path:path}`

Serve a file from one variant.

Auth: `Bearer token or session cookie`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project` | string | none | Project name. |
| `branch` | string | none | Branch name. |
| `provider` | string | none | AI provider. |
| `model` | string | none | AI model. |
| `path` | string | `index.html` when the resolved path is empty | File path inside the generated site. |

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `owner` | string | none | Admin-only owner disambiguation when more than one owner has the same variant. Ignored for non-admin callers. |

```bash
curl -H "Authorization: Bearer <ADMIN_KEY>" \
  "http://localhost:8000/docs/for-testing-only/main/claude/opus/index.html?owner=alice"
```

Returns raw file bytes from the requested variant. Returns `404` when the variant or file does not exist, `403` when the resolved file path escapes the site directory, and `409` when an admin lookup is ambiguous across owners.

## Admin endpoints

### `GET /api/admin/users`

List all users.

Auth: `admin`

No parameters.

Response body:

| Name | Type | Description |
| --- | --- | --- |
| `users` | array | User rows without API key hashes. Each row contains `id`, `username`, `role`, and `created_at`. |

```bash
curl -H "Authorization: Bearer <ADMIN_KEY>" \
  http://localhost:8000/api/admin/users
```

```json
{
  "users": [
    {
      "id": 1,
      "username": "alice",
      "role": "user",
      "created_at": "2026-04-18 12:00:00"
    }
  ]
}
```

Returns `200 OK`. Non-admin callers receive `403`.

### `POST /api/admin/users`

Create a new user and return its raw API key.

Auth: `admin`

Body parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `username` | string | none | Username. Must be 2-50 characters, start with an alphanumeric character, and use only letters, digits, `.`, `_`, and `-`. `admin` is reserved. |
| `role` | string | `user` | User role. Valid values: `admin`, `user`, `viewer`. |

Response body:

| Name | Type | Description |
| --- | --- | --- |
| `username` | string | Created username. |
| `api_key` | string | New raw API key. |
| `role` | string | Assigned role. |

Response headers:

| Name | Value | Description |
| --- | --- | --- |
| `Cache-Control` | `no-store` | Prevents caching of the returned secret. |

```bash
curl -X POST http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","role":"viewer"}'
```

```json
{
  "username": "alice",
  "api_key": "docsfy_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "role": "viewer"
}
```

Returns `200 OK`. Returns `400` for invalid usernames, reserved `admin`, duplicate users, invalid roles, or malformed JSON.

### `DELETE /api/admin/users/{username}`

Delete a user.

Auth: `admin`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `username` | string | none | Existing username to delete. |

```bash
curl -X DELETE \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  http://localhost:8000/api/admin/users/alice
```

```json
{"deleted": "alice"}
```

Returns `200 OK` after deleting the user, all of their sessions, any owned projects, access grants they received, access grants to their projects, and their project directory. Returns `400` when an admin tries to delete their own account, `404` when the user does not exist, and `409` when that user has an active generation.

### `POST /api/admin/users/{username}/rotate-key`

Rotate another user's API key.

Auth: `admin`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `username` | string | none | Existing username to rotate. |

Body parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `new_key` | string | auto-generated | Optional replacement API key. Must be at least 16 characters when provided. |

Response body:

| Name | Type | Description |
| --- | --- | --- |
| `username` | string | Rotated username. |
| `new_api_key` | string | New raw API key. |

Response headers:

| Name | Value | Description |
| --- | --- | --- |
| `Cache-Control` | `no-store` | Prevents caching of the returned secret. |

```bash
curl -X POST http://localhost:8000/api/admin/users/alice/rotate-key \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"new_key":"admin-chosen-password-long"}'
```

```json
{
  "username": "alice",
  "new_api_key": "admin-chosen-password-long"
}
```

Returns `200 OK` and invalidates all sessions for the target user. Returns `400` for invalid custom keys or malformed JSON and `404` when the user does not exist.

### `GET /api/admin/projects/{name}/access`

List users who have access to a project/owner pair.

Auth: `admin`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `owner` | string | none | Required project owner. Access grants are scoped by owner, not just by project name. |

```bash
curl -H "Authorization: Bearer <ADMIN_KEY>" \
  "http://localhost:8000/api/admin/projects/for-testing-only/access?owner=alice"
```

```json
{
  "project": "for-testing-only",
  "owner": "alice",
  "users": ["bob", "carol"]
}
```

Returns `200 OK` with usernames sorted alphabetically. Returns `400` when `owner` is missing and `403` for non-admin callers.

### `POST /api/admin/projects/{name}/access`

Grant a user read access to all variants of a project owned by one owner.

Auth: `admin`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |

Body parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `username` | string | none | Target username that will receive access. |
| `owner` | string | none | Required project owner. The grant applies to this `name` and this owner only. |

```bash
curl -X POST http://localhost:8000/api/admin/projects/for-testing-only/access \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","owner":"alice"}'
```

```json
{
  "granted": "for-testing-only",
  "username": "bob",
  "owner": "alice"
}
```

Returns `200 OK`. Returns `400` for malformed JSON or missing fields, `404` when the target user does not exist or the project/owner pair does not exist, and sends a WebSocket `sync` to the target user's active connections.

### `DELETE /api/admin/projects/{name}/access/{username}`

Revoke a user access grant for one project/owner pair.

Auth: `admin`

Path parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | none | Project name. |
| `username` | string | none | Username to revoke. |

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `owner` | string | none | Required project owner. |

```bash
curl -X DELETE \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  "http://localhost:8000/api/admin/projects/for-testing-only/access/bob?owner=alice"
```

```json
{
  "revoked": "for-testing-only",
  "username": "bob",
  "owner": "alice"
}
```

Returns `200 OK` and sends a WebSocket `sync` to the target user's active connections. Returns `400` when `owner` is missing and `403` for non-admin callers. This route is idempotent: it does not error when the grant is already absent.

## WebSocket

### WebSocket `/api/ws`

Real-time stream of project snapshots and generation updates.

Auth: `docsfy_session` cookie or `?token=<api_key>`

Query parameters:

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `token` | string | none | Optional raw `ADMIN_KEY` or user API key. Use this for non-browser clients that cannot send the session cookie. |

Connection behavior:

| Item | Value |
| --- | --- |
| Initial server message | `sync` |
| Server heartbeat | `{"type":"ping"}` every 30 seconds |
| Required client response | `{"type":"pong"}` |
| Pong timeout | 10 seconds |
| Max missed pongs | 2 |
| Unauthenticated close code | `1008` |
| Missed-pong close code | `1001` |
| Broadcast recipients | Admins, the project owner, and users granted access to that project/owner pair |

```javascript
const ws = new WebSocket("ws://localhost:8000/api/ws?token=<USER_API_KEY>");

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === "ping") {
    ws.send(JSON.stringify({ type: "pong" }));
    return;
  }

  console.log(message);
};
```

Opens a live subscription. The server sends a full `sync` immediately after connect, then incremental messages as projects change.

### `sync` message

Full snapshot message.

Fields:

| Name | Type | Description |
| --- | --- | --- |
| `type` | string | Always `sync`. |
| `projects` | array of `ProjectVariant` | Full visible project snapshot. |
| `known_models` | object | Same structure as `GET /api/projects`. |
| `known_branches` | object | Same structure as `GET /api/projects`. |

```json
{
  "type": "sync",
  "projects": [
    {
      "name": "for-testing-only",
      "branch": "main",
      "ai_provider": "claude",
      "ai_model": "opus",
      "owner": "alice",
      "repo_url": "https://github.com/myk-org/for-testing-only",
      "status": "ready",
      "current_stage": null,
      "last_commit_sha": "abc123def456",
      "last_generated": "2026-04-18 12:34:56",
      "page_count": 12,
      "error_message": null,
      "plan_json": null,
      "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b",
      "created_at": "2026-04-18 12:00:00",
      "updated_at": "2026-04-18 12:34:56"
    }
  ],
  "known_models": {
    "claude": ["opus"]
  },
  "known_branches": {
    "for-testing-only": ["main", "dev"]
  }
}
```

Sent immediately after connect and again after access changes, deletions, and terminal generation refreshes.

### `progress` message

Incremental update for an in-progress generation.

Fields:

| Name | Type | Description |
| --- | --- | --- |
| `type` | string | Always `progress`. |
| `name` | string | Project name. |
| `branch` | string | Branch name. |
| `provider` | string | AI provider. |
| `model` | string | AI model. |
| `owner` | string | Variant owner. |
| `status` | string | Current in-progress status. The current implementation sends `generating`. |
| `current_stage` | string, optional | Current stage, such as `cloning`, `planning`, or `generating_pages`. |
| `page_count` | integer, optional | Current generated page count. |
| `plan_json` | string, optional | Stringified plan JSON once planning is available. |
| `error_message` | string, optional | Error text when present during an in-progress update. |
| `generation_id` | string, optional | Variant UUID. |

```json
{
  "type": "progress",
  "name": "for-testing-only",
  "branch": "main",
  "provider": "claude",
  "model": "opus",
  "owner": "alice",
  "status": "generating",
  "current_stage": "generating_pages",
  "page_count": 4,
  "plan_json": "{\"project_name\":\"for-testing-only\",\"tagline\":\"Test repo\",\"navigation\":[]}",
  "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b"
}
```

Sent during non-terminal stages. Clients should merge this message by the tuple `(name, branch, provider, model, owner)`.

### `status_change` message

Terminal update for a variant.

Fields:

| Name | Type | Description |
| --- | --- | --- |
| `type` | string | Always `status_change`. |
| `name` | string | Project name. |
| `branch` | string | Branch name. |
| `provider` | string | AI provider. |
| `model` | string | AI model. |
| `owner` | string | Variant owner. |
| `status` | string | Terminal status: `ready`, `error`, or `aborted`. |
| `page_count` | integer, optional | Final page count when available. |
| `last_generated` | string, optional | Completion timestamp when `status` is `ready`. |
| `last_commit_sha` | string, optional | Final commit SHA when available. |
| `error_message` | string, optional | Error or abort text when available. |
| `generation_id` | string, optional | Variant UUID. |

```json
{
  "type": "status_change",
  "name": "for-testing-only",
  "branch": "main",
  "provider": "claude",
  "model": "opus",
  "owner": "alice",
  "status": "ready",
  "page_count": 12,
  "last_generated": "2026-04-18 12:34:56",
  "last_commit_sha": "abc123def456",
  "generation_id": "5bf1495b-b6fa-4318-841c-dced628a2c5b"
}
```

Sent when a variant reaches a terminal state. A full `sync` may follow.

### `ping` message

Server heartbeat message.

Fields:

| Name | Type | Description |
| --- | --- | --- |
| `type` | string | Always `ping`. |

```json
{"type": "ping"}
```

Sent every 30 seconds per open connection. Clients should respond with `pong`.

### `pong` message

Client heartbeat response.

Fields:

| Name | Type | Description |
| --- | --- | --- |
| `type` | string | Always `pong`. |

```json
{"type": "pong"}
```

Acknowledges the most recent server `ping`. If the server misses 2 consecutive pongs, it closes the connection with code `1001`.

## Related Pages

- [Configuration Reference](configuration-reference.html)
- [Generating Documentation](generate-documentation.html)
- [Tracking Generation Progress](track-generation-progress.html)
- [Viewing and Downloading Docs](view-and-download-docs.html)
- [Managing Users and Access](manage-users-and-access.html)