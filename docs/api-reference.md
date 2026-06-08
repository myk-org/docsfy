# REST API Reference

Complete reference for all HTTP and WebSocket endpoints exposed by the docsfy server. All endpoints are served under the base URL where `docsfy-server` is running (default: `http://127.0.0.1:8000`).

> **Note:** For environment variables and server configuration, see [Configuration Reference](configuration-reference.html). For CLI usage against these endpoints, see [CLI Command Reference](cli-reference.html).

## Authentication

All `/api/` and `/docs/` endpoints require authentication except where noted. docsfy supports two authentication methods:

| Method | Header / Cookie | Usage |
|---|---|---|
| Bearer token | `Authorization: Bearer <token>` | API clients, CLI |
| Session cookie | `docsfy_session` cookie | Browser (set after login) |

Bearer tokens are either the `ADMIN_KEY` environment variable (for the built-in admin account) or a user-specific API key returned when a user is created.

```bash
# Bearer token authentication
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/projects

# Session-based authentication (login first, then use cookie)
curl -c cookies.txt -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "api_key": "YOUR_ADMIN_KEY"}'

curl -b cookies.txt http://localhost:8000/api/projects
```

### Roles

| Role | Permissions |
|---|---|
| `admin` | Full access: manage users, view all projects, delete any project, access admin endpoints |
| `user` | Create/generate/delete own projects, rotate own key |
| `viewer` | Read-only access to projects shared with them |

> **Note:** The built-in `admin` account authenticates with `ADMIN_KEY`. Database users with `role: admin` also receive full admin privileges. See [Managing Users and Access Control](managing-users.html) for details.

---

## Health Check

### `GET /health`

Returns server health status. No authentication required.

**Response**

```json
{"status": "ok"}
```

---

## Authentication Endpoints

### `POST /api/auth/login`

Authenticate and receive a session cookie. No authentication required.

**Request Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `username` | string | Yes | Username (`"admin"` for the built-in admin) |
| `api_key` | string | Yes | API key or admin key |

**Response** `200 OK`

```json
{
  "username": "admin",
  "role": "admin",
  "is_admin": true
}
```

A `docsfy_session` cookie is set on the response with the following attributes:

| Attribute | Value |
|---|---|
| `httponly` | `true` |
| `samesite` | `strict` |
| `secure` | Controlled by `SECURE_COOKIES` env var |
| `max_age` | 28800 (8 hours) |

**Errors**

| Status | Condition |
|---|---|
| 400 | Invalid JSON body |
| 401 | Invalid credentials |

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "api_key": "docsfy_abc123..."}'
```

---

### `POST /api/auth/logout`

Clear the session cookie and delete the server-side session. Requires authentication.

**Response** `200 OK`

```json
{"ok": true}
```

```bash
curl -X POST http://localhost:8000/api/auth/logout -b cookies.txt
```

---

### `GET /api/auth/me`

Return information about the currently authenticated user. Requires authentication.

**Response** `200 OK`

```json
{
  "username": "alice",
  "role": "user",
  "is_admin": false
}
```

---

### `POST /api/auth/rotate-key`

Rotate the current user's API key. The session is invalidated after rotation — the user must re-login with the new key.

> **Warning:** Users authenticated via `ADMIN_KEY` (the built-in admin) cannot rotate keys through this endpoint. Change the `ADMIN_KEY` environment variable instead.

**Request Body** (optional)

| Field | Type | Required | Description |
|---|---|---|---|
| `new_key` | string | No | Custom API key (minimum 16 characters). If omitted, a key is auto-generated. |

**Response** `200 OK`

```json
{
  "username": "alice",
  "new_api_key": "docsfy_aBcDeFgHiJkLmNoPqRsTuVwXyZ..."
}
```

The response includes `Cache-Control: no-store` to prevent caching of the key.

**Errors**

| Status | Condition |
|---|---|
| 400 | Built-in admin attempting rotation, or custom key too short |

```bash
curl -X POST http://localhost:8000/api/auth/rotate-key \
  -H "Authorization: Bearer docsfy_old_key..."
```

---

## Models & Discovery

### `GET /api/models`

Return available AI providers, server default settings, and discovered models. **No authentication required.**

Models are discovered dynamically from the Pi SDK sidecar service.

**Response** `200 OK`

```json
{
  "providers": ["claude", "gemini", "cursor"],
  "default_provider": "cursor",
  "default_model": "gpt-5.4-xhigh-fast",
  "available_models": {
    "claude": [
      {"id": "claude-sonnet-4-20250514", "provider": "anthropic/claude"}
    ],
    "gemini": [],
    "cursor": [
      {"id": "gpt-5.4-xhigh-fast", "provider": "cursor"}
    ]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `providers` | string[] | List of valid provider names |
| `default_provider` | string | Server's default AI provider |
| `default_model` | string | Server's default AI model |
| `available_models` | object | Models per provider, discovered from sidecar |

```bash
curl http://localhost:8000/api/models
```

> **Tip:** See [Configuring AI Providers](configuring-ai-providers.html) for details on provider setup and the Pi SDK sidecar.

---

## Cost

### `GET /api/cost`

Return total AI generation cost. Admins see all costs; regular users see only their own.

**Response** `200 OK`

```json
{"total_cost_usd": 1.2345}
```

```bash
curl -H "Authorization: Bearer YOUR_KEY" http://localhost:8000/api/cost
```

---

## Projects & Generation

### `GET /api/projects`

List all projects visible to the authenticated user. Also accessible at `GET /api/status` (alias).

Admins see all projects. Regular users see their own projects plus projects shared with them.

**Response** `200 OK`

```json
{
  "projects": [
    {
      "name": "my-repo",
      "branch": "main",
      "ai_provider": "cursor",
      "ai_model": "gpt-5.4-xhigh-fast",
      "owner": "alice",
      "generation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "repo_url": "https://github.com/org/my-repo",
      "status": "ready",
      "current_stage": null,
      "last_commit_sha": "abc1234",
      "last_generated": "2026-06-08 12:00:00",
      "page_count": 12,
      "error_message": null,
      "plan_json": "{...}",
      "repo_type": "library",
      "total_cost_usd": 0.45,
      "created_at": "2026-06-07 10:00:00",
      "updated_at": "2026-06-08 12:00:00"
    }
  ],
  "known_branches": {
    "my-repo": ["main", "dev"]
  },
  "total_cost_usd": 1.23
}
```

| Field | Type | Description |
|---|---|---|
| `projects` | object[] | Array of project variant records |
| `known_branches` | object | Map of project name → list of branches with `ready` variants |
| `total_cost_usd` | float | Total generation cost for the user (or all users if admin) |

**Project variant fields**

| Field | Type | Description |
|---|---|---|
| `name` | string | Project name (extracted from repo URL) |
| `branch` | string | Git branch |
| `ai_provider` | string | AI provider used |
| `ai_model` | string | AI model used |
| `owner` | string | Username of the project owner |
| `generation_id` | string | UUID identifying this generation run |
| `repo_url` | string | Source repository URL |
| `status` | string | One of: `generating`, `ready`, `error`, `aborted` |
| `current_stage` | string \| null | Current generation stage (when status is `generating`) |
| `last_commit_sha` | string \| null | Git commit SHA of last generation |
| `last_generated` | string \| null | Timestamp of last successful generation |
| `page_count` | integer \| null | Number of documentation pages |
| `error_message` | string \| null | Error description (when status is `error` or `aborted`) |
| `plan_json` | string \| null | JSON-encoded documentation plan |
| `repo_type` | string \| null | Detected repository type: `app`, `library`, `framework`, or `tests` |
| `total_cost_usd` | float \| null | AI generation cost for this variant |
| `created_at` | string | Creation timestamp |
| `updated_at` | string | Last update timestamp |

```bash
curl -H "Authorization: Bearer YOUR_KEY" http://localhost:8000/api/projects
```

---

### `GET /api/projects/{name}`

Get all variants for a project by name. Returns variants the authenticated user owns plus any shared variants.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |

**Response** `200 OK`

```json
{
  "name": "my-repo",
  "variants": [
    {
      "name": "my-repo",
      "branch": "main",
      "ai_provider": "cursor",
      "ai_model": "gpt-5.4-xhigh-fast",
      "owner": "alice",
      "status": "ready",
      "page_count": 12
    }
  ]
}
```

**Errors**

| Status | Condition |
|---|---|
| 400 | Invalid project name |
| 404 | Project not found or not accessible |

```bash
curl -H "Authorization: Bearer YOUR_KEY" http://localhost:8000/api/projects/my-repo
```

---

### `GET /api/projects/{name}/{branch}/{provider}/{model}`

Get details for a specific project variant.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |
| `branch` | string | Git branch |
| `provider` | string | AI provider (`claude`, `gemini`, or `cursor`) |
| `model` | string | AI model identifier |

**Query Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `owner` | string | No | Filter by owner (admin only) |

**Response** `200 OK`

Returns a single project variant object (same fields as described in [project variant fields](#project-variant-fields) above).

**Errors**

| Status | Condition |
|---|---|
| 400 | Invalid project name |
| 404 | Variant not found or not accessible |
| 409 | Multiple owners found for this variant (admin must specify `?owner=`) |

```bash
curl -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/api/projects/my-repo/main/cursor/gpt-5.4-xhigh-fast
```

---

### `GET /api/projects/by-id/{generation_id}`

Look up a project variant by its generation UUID.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `generation_id` | string | UUID in canonical hyphenated format (`8-4-4-4-12`) |

**Response** `200 OK`

Returns a single project variant object.

**Errors**

| Status | Condition |
|---|---|
| 400 | Invalid UUID format |
| 404 | Generation ID not found or not accessible |

```bash
curl -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/api/projects/by-id/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### `POST /api/generate`

Submit a repository for documentation generation. Returns immediately with `202 Accepted`; generation runs asynchronously in the background.

> **Note:** This endpoint requires `admin` or `user` role. Viewers cannot generate docs.

**Request Body**

| Field | Type | Default | Required | Description |
|---|---|---|---|---|
| `repo_url` | string | — | One of `repo_url` or `repo_path` | Git repository URL (HTTPS or SSH) |
| `repo_path` | string | — | One of `repo_url` or `repo_path` | Absolute path to local git repo (admin only) |
| `ai_provider` | string | Server default | No | AI provider: `claude`, `gemini`, or `cursor` |
| `ai_model` | string | Server default | No | AI model identifier |
| `ai_cli_timeout` | integer | Server default | No | AI call timeout in seconds (must be > 0) |
| `force` | boolean | `false` | No | Force full regeneration, ignoring cache |
| `repo_type` | string | Auto-detected | No | Repository type: `app`, `library`, `framework`, or `tests` |
| `branch` | string | `"main"` | No | Git branch to generate docs from |

**Branch validation:** Must match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$`. Slashes are rejected — use hyphens instead (e.g., `release-1.x` not `release/1.x`).

**Response** `202 Accepted`

```json
{
  "project": "my-repo",
  "status": "generating",
  "branch": "main",
  "generation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "repo_type": null
}
```

**Errors**

| Status | Condition |
|---|---|
| 400 | Invalid provider, empty model, repo path doesn't exist, private/internal URL |
| 403 | `repo_path` used by non-admin, or viewer role |
| 409 | Same variant is already being generated |
| 422 | Validation error (invalid URL format, missing source, etc.) |

```bash
# Generate docs from a GitHub repo
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/my-repo.git",
    "branch": "main",
    "ai_provider": "cursor",
    "ai_model": "gpt-5.4-xhigh-fast"
  }'

# Force full regeneration
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/org/my-repo.git",
    "force": true
  }'

# Generate from a local path (admin only)
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/home/user/projects/my-repo"}'
```

> **Tip:** Monitor generation progress in real time via the [WebSocket endpoint](#websocket-real-time-updates). For incremental update behavior, see [Working with Incremental Updates](incremental-updates.html).

**Generation Stages**

While status is `generating`, the `current_stage` field progresses through:

| Stage | Description |
|---|---|
| `cloning` | Cloning the git repository |
| `analyzing` | Building code knowledge graph |
| `planning` | AI planning documentation structure |
| `incremental_planning` | AI determining which pages need updates |
| `generating_pages` | AI writing documentation pages |
| `validating` | Validating generated content |
| `completeness_check` | Checking for undocumented features |
| `cross_linking` | Adding cross-references between pages |
| `rendering` | Building the HTML documentation site |
| `up_to_date` | No changes detected, docs already current |

---

### `POST /api/projects/{name}/abort`

Abort an active generation for the given project. If multiple variants are generating, use the variant-specific abort endpoint instead.

> **Note:** Requires `admin` or `user` role. Non-admin users can only abort their own generations.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |

**Response** `200 OK`

```json
{"aborted": "my-repo"}
```

**Errors**

| Status | Condition |
|---|---|
| 404 | No active generation for this project |
| 409 | Multiple active variants (use variant-specific abort), or abort still in progress |

```bash
curl -X POST http://localhost:8000/api/projects/my-repo/abort \
  -H "Authorization: Bearer YOUR_KEY"
```

---

### `POST /api/projects/{name}/{branch}/{provider}/{model}/abort`

Abort a specific variant's generation.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |
| `branch` | string | Git branch |
| `provider` | string | AI provider |
| `model` | string | AI model |

**Query Parameters (admin only)**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `owner` | string | No | Target a specific owner's generation |

**Response** `200 OK`

```json
{"aborted": "my-repo/main/cursor/gpt-5.4-xhigh-fast"}
```

**Errors**

| Status | Condition |
|---|---|
| 404 | No active generation for this variant |
| 409 | Generation already finished, or abort in progress, or multiple owners found |

```bash
curl -X POST \
  http://localhost:8000/api/projects/my-repo/main/cursor/gpt-5.4-xhigh-fast/abort \
  -H "Authorization: Bearer YOUR_KEY"
```

---

### `DELETE /api/projects/{name}`

Delete all variants of a project.

> **Note:** Requires `admin` or `user` role. Cannot delete while any variant is actively generating — abort first.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |

**Query Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `owner` | string | Yes (admin only) | Owner of the project to delete. Use `?owner=` (empty) for legacy unowned projects. Non-admin users always delete their own. |

**Response** `200 OK`

```json
{"deleted": "my-repo"}
```

**Errors**

| Status | Condition |
|---|---|
| 400 | Admin did not specify `?owner=` |
| 404 | Project not found |
| 409 | Generation in progress (abort first) |

```bash
# Non-admin: deletes own project
curl -X DELETE http://localhost:8000/api/projects/my-repo \
  -H "Authorization: Bearer YOUR_KEY"

# Admin: must specify owner
curl -X DELETE "http://localhost:8000/api/projects/my-repo?owner=alice" \
  -H "Authorization: Bearer ADMIN_KEY"
```

---

### `DELETE /api/projects/{name}/{branch}/{provider}/{model}`

Delete a specific project variant.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |
| `branch` | string | Git branch |
| `provider` | string | AI provider |
| `model` | string | AI model |

**Query Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `owner` | string | Yes (admin only) | Owner of the variant. Non-admins always delete their own. |

**Response** `200 OK`

```json
{"deleted": "my-repo/main/cursor/gpt-5.4-xhigh-fast"}
```

**Errors**

| Status | Condition |
|---|---|
| 400 | Admin did not specify `?owner=` |
| 404 | Variant not found |
| 409 | Generation in progress for this variant |

```bash
curl -X DELETE \
  "http://localhost:8000/api/projects/my-repo/main/cursor/gpt-5.4-xhigh-fast?owner=alice" \
  -H "Authorization: Bearer ADMIN_KEY"
```

---

## Download

### `GET /api/projects/{name}/download`

Download the latest ready variant as a `.tar.gz` archive. Resolves to the most recently generated `ready` variant across all branches and providers.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |

**Response** `200 OK`

- Content-Type: `application/gzip`
- Content-Disposition: `attachment; filename="<name>-docs.tar.gz"`

**Errors**

| Status | Condition |
|---|---|
| 404 | No ready variant found |

```bash
curl -O -J -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/api/projects/my-repo/download
```

---

### `GET /api/projects/{name}/{branch}/{provider}/{model}/download`

Download a specific variant as a `.tar.gz` archive.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |
| `branch` | string | Git branch |
| `provider` | string | AI provider |
| `model` | string | AI model |

**Response** `200 OK`

- Content-Type: `application/gzip`
- Content-Disposition: `attachment; filename="<name>-<branch>-<provider>-<model>-docs.tar.gz"`

**Errors**

| Status | Condition |
|---|---|
| 400 | Variant not ready |
| 404 | Site not found or variant not accessible |

```bash
curl -O -J -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/api/projects/my-repo/main/cursor/gpt-5.4-xhigh-fast/download
```

> **Tip:** See [Common Workflow Recipes](recipes-common-workflows.html) for patterns on downloading and hosting static sites.

---

## Serving Generated Documentation

### `GET /docs/{project}/{branch}/{provider}/{model}/{path}`

Serve files from a specific variant's generated documentation site.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `project` | string | Project name |
| `branch` | string | Git branch |
| `provider` | string | AI provider |
| `model` | string | AI model |
| `path` | string | File path within the site (defaults to `index.html`) |

**Response** `200 OK` — The requested file.

**Errors**

| Status | Condition |
|---|---|
| 302 | Unauthenticated browser redirected to `/login` |
| 403 | Path traversal attempt |
| 404 | File or variant not found |

```
http://localhost:8000/docs/my-repo/main/cursor/gpt-5.4-xhigh-fast/
http://localhost:8000/docs/my-repo/main/cursor/gpt-5.4-xhigh-fast/quickstart.html
```

---

### `GET /docs/{project}/{path}`

Serve files from the latest ready variant of a project (auto-resolved).

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `project` | string | Project name |
| `path` | string | File path within the site (defaults to `index.html`) |

```
http://localhost:8000/docs/my-repo/
```

> **Note:** See [Browsing Generated Documentation](browsing-docs.html) for details on navigating the generated sites.

---

## Admin: User Management

All endpoints in this section require **admin** role.

### `POST /api/admin/users`

Create a new user account. Returns the generated API key.

**Request Body**

| Field | Type | Default | Required | Description |
|---|---|---|---|---|
| `username` | string | — | Yes | 2–50 characters, alphanumeric plus `.`, `-`, `_`. Cannot be `"admin"`. |
| `role` | string | `"user"` | No | One of: `admin`, `user`, `viewer` |

**Response** `200 OK`

```json
{
  "username": "alice",
  "api_key": "docsfy_aBcDeFgHiJkLmNoPqRsTuVwXyZ...",
  "role": "user"
}
```

The response includes `Cache-Control: no-store`.

**Errors**

| Status | Condition |
|---|---|
| 400 | Missing/invalid username, invalid role, username `"admin"` is reserved, duplicate username |
| 403 | Non-admin caller |

```bash
curl -X POST http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "role": "user"}'
```

---

### `GET /api/admin/users`

List all user accounts (without API key hashes).

**Response** `200 OK`

```json
{
  "users": [
    {
      "id": 1,
      "username": "alice",
      "role": "user",
      "created_at": "2026-06-08 10:00:00"
    }
  ]
}
```

**Errors**

| Status | Condition |
|---|---|
| 403 | Non-admin caller |

```bash
curl -H "Authorization: Bearer ADMIN_KEY" http://localhost:8000/api/admin/users
```

---

### `DELETE /api/admin/users/{username}`

Delete a user account. Invalidates all sessions, removes owned projects and their files, and cleans up access grants.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `username` | string | Username to delete |

**Response** `200 OK`

```json
{"deleted": "alice"}
```

**Errors**

| Status | Condition |
|---|---|
| 400 | Attempting to delete your own account |
| 403 | Non-admin caller |
| 404 | User not found |
| 409 | User has an active generation in progress |

```bash
curl -X DELETE http://localhost:8000/api/admin/users/alice \
  -H "Authorization: Bearer ADMIN_KEY"
```

---

### `POST /api/admin/users/{username}/rotate-key`

Admin-initiated API key rotation for any user.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `username` | string | Target username |

**Request Body** (optional)

| Field | Type | Required | Description |
|---|---|---|---|
| `new_key` | string | No | Custom API key (minimum 16 characters). Auto-generated if omitted. |

**Response** `200 OK`

```json
{
  "username": "alice",
  "new_api_key": "docsfy_aBcDeFgHiJkLmNoPqRsTuVwXyZ..."
}
```

The response includes `Cache-Control: no-store`.

**Errors**

| Status | Condition |
|---|---|
| 400 | Custom key too short |
| 403 | Non-admin caller |
| 404 | User not found |

```bash
curl -X POST http://localhost:8000/api/admin/users/alice/rotate-key \
  -H "Authorization: Bearer ADMIN_KEY"
```

---

## Admin: Project Access Control

All endpoints in this section require **admin** role.

### `POST /api/admin/projects/{name}/access`

Grant a user access to all variants of a project (scoped to a specific owner's copy).

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |

**Request Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `username` | string | Yes | Username to grant access to |
| `owner` | string | Yes | Owner of the project |

**Response** `200 OK`

```json
{
  "granted": "my-repo",
  "username": "bob",
  "owner": "alice"
}
```

**Errors**

| Status | Condition |
|---|---|
| 400 | Missing username or owner |
| 403 | Non-admin caller |
| 404 | User or project not found |

```bash
curl -X POST http://localhost:8000/api/admin/projects/my-repo/access \
  -H "Authorization: Bearer ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "owner": "alice"}'
```

---

### `DELETE /api/admin/projects/{name}/access/{username}`

Revoke a user's access to a project.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |
| `username` | string | Username to revoke |

**Query Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `owner` | string | Yes | Owner of the project |

**Response** `200 OK`

```json
{
  "revoked": "my-repo",
  "username": "bob",
  "owner": "alice"
}
```

**Errors**

| Status | Condition |
|---|---|
| 400 | Missing `?owner=` |
| 403 | Non-admin caller |

```bash
curl -X DELETE \
  "http://localhost:8000/api/admin/projects/my-repo/access/bob?owner=alice" \
  -H "Authorization: Bearer ADMIN_KEY"
```

---

### `GET /api/admin/projects/{name}/access`

List users with access to a project.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| `name` | string | Project name |

**Query Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `owner` | string | Yes | Owner of the project |

**Response** `200 OK`

```json
{
  "project": "my-repo",
  "owner": "alice",
  "users": ["bob", "carol"]
}
```

**Errors**

| Status | Condition |
|---|---|
| 400 | Missing `?owner=` |
| 403 | Non-admin caller |

```bash
curl "http://localhost:8000/api/admin/projects/my-repo/access?owner=alice" \
  -H "Authorization: Bearer ADMIN_KEY"
```

> **Note:** For more on sharing projects and managing access, see [Managing Users and Access Control](managing-users.html).

---

## WebSocket Real-Time Updates

### `WebSocket /api/ws`

Persistent WebSocket connection for receiving real-time project status updates. Authenticates via query parameter or session cookie.

**Authentication**

| Method | Example |
|---|---|
| Query parameter | `ws://localhost:8000/api/ws?token=YOUR_API_KEY` |
| Session cookie | Connect with `docsfy_session` cookie set |

Unauthenticated connections are closed immediately with code `1008` (Policy Violation).

```javascript
const ws = new WebSocket("ws://localhost:8000/api/ws?token=YOUR_API_KEY");
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.type, msg);
};
```

### Message Types

#### `sync`

Full project list snapshot. Sent immediately on connection and whenever project data changes (creation, deletion, access changes).

```json
{
  "type": "sync",
  "projects": [ ... ],
  "known_branches": { "my-repo": ["main", "dev"] },
  "total_cost_usd": 1.23
}
```

The `projects`, `known_branches`, and `total_cost_usd` fields have the same structure as the `GET /api/projects` response.

#### `progress`

Sent during active generation to report stage and page count changes.

```json
{
  "type": "progress",
  "name": "my-repo",
  "branch": "main",
  "provider": "cursor",
  "model": "gpt-5.4-xhigh-fast",
  "owner": "alice",
  "status": "generating",
  "generation_id": "a1b2c3d4-...",
  "current_stage": "generating_pages",
  "page_count": 5,
  "plan_json": "{...}"
}
```

| Field | Type | Description |
|---|---|---|
| `name` | string | Project name |
| `branch` | string | Git branch |
| `provider` | string | AI provider |
| `model` | string | AI model |
| `owner` | string | Project owner |
| `status` | string | Always `"generating"` for progress messages |
| `generation_id` | string | Generation UUID |
| `current_stage` | string \| null | Current generation stage |
| `page_count` | integer \| null | Pages generated so far |
| `plan_json` | string \| null | Documentation plan JSON (sent when plan is ready) |
| `error_message` | string \| null | Error details if applicable |

#### `status_change`

Sent when generation reaches a terminal state (`ready`, `error`, or `aborted`).

```json
{
  "type": "status_change",
  "name": "my-repo",
  "branch": "main",
  "provider": "cursor",
  "model": "gpt-5.4-xhigh-fast",
  "owner": "alice",
  "status": "ready",
  "generation_id": "a1b2c3d4-...",
  "page_count": 12,
  "last_generated": "2026-06-08 12:00:00",
  "last_commit_sha": "abc1234"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | One of: `ready`, `error`, `aborted` |
| `page_count` | integer \| null | Final page count |
| `last_generated` | string \| null | Timestamp (only for `ready`) |
| `last_commit_sha` | string \| null | Commit SHA |
| `error_message` | string \| null | Error details (for `error` or `aborted`) |

#### `ping`

Server-sent heartbeat every 30 seconds. Clients must respond with a `pong` message. After 2 missed pongs (within 10-second timeout each), the server closes the connection.

```json
{"type": "ping"}
```

**Client pong response:**

```json
{"type": "pong"}
```

### Message Visibility

WebSocket messages are scoped to the authenticated user:

- **Admins** receive updates for all projects
- **Project owners** receive updates for their own projects
- **Granted users** receive updates for projects they have access to

> **Note:** See [Generating Documentation](generating-docs.html) for details on monitoring generation progress through the web dashboard.

---

## Error Response Format

All API errors return a JSON body with a `detail` field:

```json
{
  "detail": "Human-readable error description"
}
```

Validation errors (422) from Pydantic return a structured `detail` array:

```json
{
  "detail": [
    {
      "loc": ["body", "repo_url"],
      "msg": "Invalid git repository URL: 'not-a-url'",
      "type": "value_error"
    }
  ]
}
```

### Common HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 202 | Accepted (generation started asynchronously) |
| 302 | Redirect (unauthenticated browser to login) |
| 400 | Bad request (invalid input) |
| 401 | Unauthorized (missing or invalid credentials) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not found (or not accessible to the current user) |
| 409 | Conflict (concurrent generation, multiple owners) |
| 422 | Validation error (request body schema mismatch) |
| 500 | Internal server error |

> **Note:** For security, endpoints return `404` instead of `403` when a resource exists but the user lacks access, preventing enumeration of other users' projects.

## Related Pages

- [CLI Command Reference](cli-reference.html)
- [Configuration Reference](configuration-reference.html)
- [Managing Users and Access Control](managing-users.html)
- [Generating Documentation](generating-docs.html)
- [Managing Projects and Variants](managing-projects.html)