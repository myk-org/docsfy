# HTTP API Reference

## Authentication

| Mechanism | Type | Default | Description |
| --- | --- | --- | --- |
| `Authorization: Bearer <token>` | Header | — | Accepted on protected API and docs routes. Use the admin key or a user's API key. |
| `docsfy_session` | Cookie | Set by `POST /api/auth/login` | Browser session cookie. `HttpOnly`, `SameSite=Strict`, max age `28800` seconds. The `Secure` flag follows server cookie settings. |

| Role | Type | Default | Description |
| --- | --- | --- | --- |
| `admin` | Role | — | Full access, including `/api/admin/*`. |
| `user` | Role | New users default here | Read/write access to owned projects and accessible shared projects. |
| `viewer` | Role | — | Read-only access to owned projects and accessible shared projects. Write routes return `403`. |

> **Note:** Public routes are `GET /api/models`, `POST /api/auth/login`, and `POST /api/auth/logout`.

> **Note:** JSON error responses use `{"detail": "..."}`. Unauthenticated `/docs/*` requests return `302 /login` for HTML clients and `401` JSON for non-HTML clients.

> **Note:** A database user with role `admin` has the same API permissions as the `ADMIN_KEY` admin user.

## Common Response Objects

### `ErrorResponse`

| Field | Type | Description |
| --- | --- | --- |
| `detail` | `string` | Human-readable error message for JSON `4xx` and `5xx` responses. |

### `AuthResponse`

| Field | Type | Description |
| --- | --- | --- |
| `username` | `string` | Authenticated username. |
| `role` | `string` | User role: `admin`, `user`, or `viewer`. |
| `is_admin` | `boolean` | `true` for admin users. |

### `Project`

| Field | Type | Description |
| --- | --- | --- |
| `name` | `string` | Project name. |
| `branch` | `string` | Git branch for this variant. |
| `ai_provider` | `string` | AI provider for this variant. |
| `ai_model` | `string` | AI model for this variant. |
| `owner` | `string` | Variant owner username. Legacy ownerless rows use an empty string. |
| `repo_url` | `string` | Repository source string used for generation. This can be a remote Git URL or a server-local absolute path. |
| `status` | `string` | One of `generating`, `ready`, `error`, or `aborted`. |
| `current_stage` | `string \| null` | Current generation stage, or `null`. |
| `last_commit_sha` | `string \| null` | Last generated commit SHA. |
| `last_generated` | `string \| null` | Timestamp of the last successful generation. |
| `page_count` | `integer` | Current page count tracked for the variant. |
| `error_message` | `string \| null` | Latest error or abort message. |
| `plan_json` | `string \| null` | JSON-encoded documentation plan. |
| `created_at` | `string` | Creation timestamp. |
| `updated_at` | `string` | Last update timestamp. |

> **Note:** `current_stage` can be `cloning`, `planning`, `incremental_planning`, `generating_pages`, `validating`, `cross_linking`, `rendering`, `up_to_date`, or `null`. See [Track Generation Progress](track-generation-progress.html) for the stage meanings.

### `ProjectsResponse`

| Field | Type | Description |
| --- | --- | --- |
| `projects` | `Project[]` | Flat list of accessible variants. This is not grouped by project name. |
| `known_models` | `Record<string, string[]>` | Ready model IDs grouped by provider across the server. |
| `known_branches` | `Record<string, string[]>` | Ready branch names grouped by project name. Admins get all ready branches; non-admins get their own ready branches. |

### `User`

| Field | Type | Description |
| --- | --- | --- |
| `id` | `integer` | Numeric user ID. |
| `username` | `string` | Username. |
| `role` | `string` | User role: `admin`, `user`, or `viewer`. |
| `created_at` | `string` | Creation timestamp. |

## Models

### `GET /api/models`

Returns available providers, server defaults, and model IDs seen in ready variants.

**Auth:** None.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| None | — | — | — | This endpoint does not accept parameters. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "providers": string[], "default_provider": string, "default_model": string, "known_models": Record<string, string[]> }` | Returns provider discovery data. |

**Example**
```bash
curl "<SERVER_URL>/api/models"
```

## Auth Routes

### `POST /api/auth/login`

Authenticates a user from a JSON body and sets the `docsfy_session` cookie.

**Auth:** None.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `username` | Body | `string` | — | Username to authenticate. The admin key only works when this value is exactly `admin`. |
| `api_key` | Body | `string` | — | Admin key or user API key. For database users, the key must belong to `username`. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `AuthResponse` | Authenticates the user and sets the `docsfy_session` cookie. |
| `400` | `ErrorResponse` | Invalid JSON body or body is not a JSON object. |
| `401` | `ErrorResponse` | Username and API key did not authenticate. |

**Example**
```bash
curl -i -X POST "<SERVER_URL>/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","api_key":"<ADMIN_KEY>"}'
```

### `POST /api/auth/logout`

Clears the current session cookie and deletes the current session if one exists.

**Auth:** None.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| None | — | — | — | This endpoint does not accept parameters. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "ok": true }` | Deletes the current session if present and clears the `docsfy_session` cookie. |

**Example**
```bash
curl -X POST "<SERVER_URL>/api/auth/logout" \
  --cookie "docsfy_session=<COOKIE>"
```

### `GET /api/auth/me`

Returns the authenticated user identity.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| None | — | — | — | This endpoint does not accept parameters. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `AuthResponse` | Returns the current authenticated user. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl "<SERVER_URL>/api/auth/me" \
  -H "Authorization: Bearer <USER_API_KEY>"
```

### `POST /api/auth/rotate-key`

Rotates the authenticated user's API key.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `new_key` | Body | `string` | Auto-generated | Optional replacement API key. Must be at least 16 characters when supplied. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "username": string, "new_api_key": string }` | Rotates the user's API key, invalidates all sessions for that user, clears the current session cookie, and returns `Cache-Control: no-store`. |
| `400` | `ErrorResponse` | Malformed JSON, non-object body, invalid custom key, or `ADMIN_KEY` admin attempting self-rotation. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

> **Warning:** `new_api_key` is the only copy of the raw key returned by this route.

**Example**
```bash
curl -X POST "<SERVER_URL>/api/auth/rotate-key" \
  -H "Authorization: Bearer <USER_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"new_key":"my-very-secure-custom-password-123"}'
```

## Project Routes

### `GET /api/status`
### `GET /api/projects`

Both paths return the same flat variant list and discovery metadata.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| None | — | — | — | This endpoint does not accept parameters. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `ProjectsResponse` | Returns accessible variants plus known model and branch metadata. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

> **Note:** `projects[]` is a flat list of variants. Use `GET /api/projects/{name}` to retrieve grouped variants for one project name.

**Example**
```bash
curl "<SERVER_URL>/api/status" \
  -H "Authorization: Bearer <USER_API_KEY>"
```

### `GET /api/projects/{name}`

Returns all accessible variants for one project name.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. Must match the stored project name exactly. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "name": string, "variants": Project[] }` | Returns all accessible variants for the project name. |
| `400` | `ErrorResponse` | Invalid project name format. |
| `404` | `ErrorResponse` | No accessible variants found for `name`. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl "<SERVER_URL>/api/projects/my-repo" \
  -H "Authorization: Bearer <USER_API_KEY>"
```

### `POST /api/generate`

Queues a new documentation generation job.

**Auth:** `user` or `admin`.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `repo_url` | Body | `string` | `null` | Remote Git URL. Accepted formats are `http(s)://host/owner/repo(.git)` and `git@host:owner/repo(.git)`. Exactly one of `repo_url` or `repo_path` is required. |
| `repo_path` | Body | `string` | `null` | Absolute server-local path to a Git repository. Exactly one of `repo_url` or `repo_path` is required. Admin only. |
| `ai_provider` | Body | `string` | Server default | AI provider. Valid values are `claude`, `gemini`, and `cursor`. |
| `ai_model` | Body | `string` | Server default | AI model ID. |
| `ai_cli_timeout` | Body | `integer` | Server default | Timeout in seconds for each AI CLI call. Must be greater than `0`. |
| `force` | Body | `boolean` | `false` | Forces a full regeneration and ignores cached output. |
| `branch` | Body | `string` | `main` | Git branch to generate. Slashes are rejected; valid names use letters, digits, `.`, `_`, and `-`. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `202` | `{ "project": string, "status": "generating", "branch": string }` | Creates or updates the variant row and starts background generation. |
| `400` | `ErrorResponse` | Runtime validation failed, such as invalid repository path, non-Git path, unsupported repository target, or missing model after defaults are applied. |
| `403` | `ErrorResponse` | Caller is a `viewer`, or a non-admin attempted to use `repo_path`. |
| `409` | `ErrorResponse` | The same `owner/name/branch/provider/model` variant is already generating. |
| `422` | `ErrorResponse` | Request body failed schema validation. |

> **Note:** The project name is derived from the repository URL basename or the local directory name. Extra body fields such as `project_name` are ignored.

**Example**
```bash
curl -X POST "<SERVER_URL>/api/generate" \
  -H "Authorization: Bearer <USER_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/acme/my-repo.git",
    "ai_provider": "claude",
    "ai_model": "opus",
    "branch": "main",
    "force": false
  }'
```

### `GET /api/projects/{name}/{branch}/{provider}/{model}`

Returns one specific variant.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. |
| `branch` | Path | `string` | — | Variant branch. |
| `provider` | Path | `string` | — | Variant provider. |
| `model` | Path | `string` | — | Variant model. |
| `owner` | Query | `string` | — | Admin-only disambiguation parameter. Required when the same variant exists under multiple owners. Ignored for non-admin requests. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `Project` | Returns the matching variant. |
| `400` | `ErrorResponse` | Invalid project name format. |
| `404` | `ErrorResponse` | Variant not found or not accessible. |
| `409` | `ErrorResponse` | Multiple owners match the same variant and no `owner` was supplied. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl "<SERVER_URL>/api/projects/my-repo/main/claude/opus?owner=alice" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

### `DELETE /api/projects/{name}/{branch}/{provider}/{model}`

Deletes one specific variant.

**Auth:** `user` or `admin`.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. |
| `branch` | Path | `string` | — | Variant branch. |
| `provider` | Path | `string` | — | Variant provider. |
| `model` | Path | `string` | — | Variant model. |
| `owner` | Query | `string` | — | Required for admin requests. Non-admin requests always delete only the caller's own variant. Use an empty value only for legacy ownerless variants. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "deleted": "name/branch/provider/model" }` | Deletes the target variant row and its stored artifacts. |
| `400` | `ErrorResponse` | Invalid project name format, or missing `owner` on an admin request. |
| `404` | `ErrorResponse` | Variant not found. |
| `409` | `ErrorResponse` | Variant is currently generating. Abort it first. |
| `403` | `ErrorResponse` | Caller has read-only access. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl -X DELETE "<SERVER_URL>/api/projects/my-repo/main/claude/opus?owner=alice" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

### `POST /api/projects/{name}/abort`

Aborts the single active generation found for a project name.

**Auth:** `user` or `admin`.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name to search for among active generations. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "aborted": string }` | Cancels the active generation for `name`. |
| `400` | `ErrorResponse` | Invalid project name format. |
| `404` | `ErrorResponse` | No active generation matched `name`. |
| `409` | `ErrorResponse` | More than one active variant matched `name`, or cancellation did not complete cleanly. |
| `403` | `ErrorResponse` | Caller has read-only access. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

> **Note:** This route does not disambiguate by `branch`, `provider`, `model`, or `owner`. Use the branch-specific abort route when more than one active variant can exist.

**Example**
```bash
curl -X POST "<SERVER_URL>/api/projects/my-repo/abort" \
  -H "Authorization: Bearer <USER_API_KEY>"
```

### `POST /api/projects/{name}/{branch}/{provider}/{model}/abort`

Aborts one specific active variant.

**Auth:** `user` or `admin`.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. |
| `branch` | Path | `string` | — | Variant branch. |
| `provider` | Path | `string` | — | Variant provider. |
| `model` | Path | `string` | — | Variant model. |
| `owner` | Query | `string` | — | Admin-only disambiguation parameter. Required when the same active variant exists under multiple owners. Ignored for non-admin requests. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "aborted": "name/branch/provider/model" }` | Cancels the target active generation. |
| `400` | `ErrorResponse` | Invalid project name format. |
| `404` | `ErrorResponse` | No active generation exists for the specified variant. |
| `409` | `ErrorResponse` | Multiple owners matched and no `owner` was supplied, or cancellation is already finishing. |
| `403` | `ErrorResponse` | Caller has read-only access. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl -X POST "<SERVER_URL>/api/projects/my-repo/main/claude/opus/abort?owner=alice" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

### `DELETE /api/projects/{name}`

Deletes all variants for one project name within one owner scope.

**Auth:** `user` or `admin`.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. |
| `owner` | Query | `string` | — | Required for admin requests. Non-admin requests delete only the caller's own variants. Use an empty value only for legacy ownerless variants. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "deleted": string }` | Deletes all variants of `name` for the target owner scope. |
| `400` | `ErrorResponse` | Invalid project name format, or missing `owner` on an admin request. |
| `404` | `ErrorResponse` | No matching variants found. |
| `409` | `ErrorResponse` | At least one targeted variant is still generating. |
| `403` | `ErrorResponse` | Caller has read-only access. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl -X DELETE "<SERVER_URL>/api/projects/my-repo?owner=alice" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

## Admin Routes

### `POST /api/admin/users`

Creates a new database-backed user and returns the raw API key.

**Auth:** Admin only.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `username` | Body | `string` | — | New username. Must be 2-50 characters using letters, digits, `.`, `_`, or `-`. `admin` is reserved. |
| `role` | Body | `string` | `user` | Role for the new user: `admin`, `user`, or `viewer`. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "username": string, "api_key": string, "role": string }` | Creates the user, generates a raw API key, and returns `Cache-Control: no-store`. |
| `400` | `ErrorResponse` | Malformed JSON, non-object body, missing username, invalid username, reserved username, or invalid role. |
| `403` | `ErrorResponse` | Caller is not an admin. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

> **Warning:** `api_key` is the only copy of the raw key returned by this route.

**Example**
```bash
curl -X POST "<SERVER_URL>/api/admin/users" \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","role":"viewer"}'
```

### `DELETE /api/admin/users/{username}`

Deletes a user account.

**Auth:** Admin only.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `username` | Path | `string` | — | Username to delete. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "deleted": string }` | Deletes the user, invalidates their sessions, deletes their owned projects, and removes related access-control entries. |
| `400` | `ErrorResponse` | Attempted to delete the current admin user. |
| `404` | `ErrorResponse` | User not found. |
| `409` | `ErrorResponse` | The user currently has a generation in progress. |
| `403` | `ErrorResponse` | Caller is not an admin. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl -X DELETE "<SERVER_URL>/api/admin/users/alice" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

### `GET /api/admin/users`

Lists all database users.

**Auth:** Admin only.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| None | — | — | — | This endpoint does not accept parameters. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "users": User[] }` | Returns all users without API key hashes. |
| `403` | `ErrorResponse` | Caller is not an admin. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl "<SERVER_URL>/api/admin/users" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

### `POST /api/admin/projects/{name}/access`

Grants a user access to all variants of one project name for one owner.

**Auth:** Admin only.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name to share. |
| `username` | Body | `string` | — | Username receiving access. |
| `owner` | Body | `string` | — | Owner whose project namespace is being shared. Required. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "granted": string, "username": string, "owner": string }` | Creates the access grant if needed. The grant applies to all variants of `name` owned by `owner`. |
| `400` | `ErrorResponse` | Malformed JSON, non-object body, or missing required fields. |
| `404` | `ErrorResponse` | Target user not found, or project name not found for `owner`. |
| `403` | `ErrorResponse` | Caller is not an admin. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

> **Note:** Grants are project-wide for the `(name, owner)` pair, not variant-specific.

**Example**
```bash
curl -X POST "<SERVER_URL>/api/admin/projects/my-repo/access" \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","owner":"alice"}'
```

### `DELETE /api/admin/projects/{name}/access/{username}`

Revokes a user's access to one project name for one owner.

**Auth:** Admin only.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. |
| `username` | Path | `string` | — | Username whose grant will be removed. |
| `owner` | Query | `string` | — | Owner whose project namespace is being updated. Required. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "revoked": string, "username": string, "owner": string }` | Removes the access grant if present. |
| `400` | `ErrorResponse` | Missing `owner`. |
| `403` | `ErrorResponse` | Caller is not an admin. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl -X DELETE "<SERVER_URL>/api/admin/projects/my-repo/access/bob?owner=alice" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

### `GET /api/admin/projects/{name}/access`

Lists usernames with access to one project name for one owner.

**Auth:** Admin only.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. |
| `owner` | Query | `string` | — | Owner whose project namespace is being inspected. Required. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "project": string, "owner": string, "users": string[] }` | Returns the usernames currently granted access for the `(name, owner)` pair. |
| `400` | `ErrorResponse` | Missing `owner`. |
| `403` | `ErrorResponse` | Caller is not an admin. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl "<SERVER_URL>/api/admin/projects/my-repo/access?owner=alice" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

### `POST /api/admin/users/{username}/rotate-key`

Rotates another user's API key.

**Auth:** Admin only.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `username` | Path | `string` | — | Username whose key will be rotated. |
| `new_key` | Body | `string` | Auto-generated | Optional replacement API key. Must be at least 16 characters when supplied. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | `{ "username": string, "new_api_key": string }` | Rotates the user's key, invalidates that user's sessions, and returns `Cache-Control: no-store`. |
| `400` | `ErrorResponse` | Malformed JSON, non-object body, or invalid custom key. |
| `404` | `ErrorResponse` | User not found. |
| `403` | `ErrorResponse` | Caller is not an admin. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

> **Warning:** `new_api_key` is the only copy of the raw key returned by this route.

**Example**
```bash
curl -X POST "<SERVER_URL>/api/admin/users/alice/rotate-key" \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"new_key":"alice-rotated-password-123"}'
```

## Download Routes

### `GET /api/projects/{name}/{branch}/{provider}/{model}/download`

Downloads one specific ready variant as a `.tar.gz` archive.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. |
| `branch` | Path | `string` | — | Variant branch. |
| `provider` | Path | `string` | — | Variant provider. |
| `model` | Path | `string` | — | Variant model. |
| `owner` | Query | `string` | — | Admin-only disambiguation parameter. Required when the same variant exists under multiple owners. Ignored for non-admin requests. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | Binary `application/gzip` | Streams the generated site as a tarball. `Content-Disposition` filename format: `<name>-<branch>-<provider>-<model>-docs.tar.gz`. |
| `400` | `ErrorResponse` | Variant exists but is not `ready`. |
| `404` | `ErrorResponse` | Variant not found, not accessible, or site files are missing. |
| `409` | `ErrorResponse` | Multiple owners match the same variant and no `owner` was supplied. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

**Example**
```bash
curl -L "<SERVER_URL>/api/projects/my-repo/main/claude/opus/download?owner=alice" \
  -H "Authorization: Bearer <ADMIN_KEY>" \
  -o my-repo-main-claude-opus-docs.tar.gz
```

### `GET /api/projects/{name}/download`

Downloads the most recently generated accessible ready variant for one project name.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | Path | `string` | — | Project name. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | Binary `application/gzip` | Streams the latest accessible ready variant as a tarball. `Content-Disposition` filename format: `<name>-docs.tar.gz`. |
| `404` | `ErrorResponse` | No accessible ready variant exists, or the site directory is missing. |
| `409` | `ErrorResponse` | For non-admin callers, multiple accessible owners tied for the newest variant timestamp. |
| `401` | `ErrorResponse` | Missing or invalid authentication. |

> **Note:** This route does not accept `owner`. To target a specific owner, use the variant-specific download route.

**Example**
```bash
curl -L "<SERVER_URL>/api/projects/my-repo/download" \
  -H "Authorization: Bearer <USER_API_KEY>" \
  -o my-repo-docs.tar.gz
```

## Docs Routes

### `GET /docs/{project}/{branch}/{provider}/{model}/{path}`

Serves one file from a specific generated variant.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `project` | Path | `string` | — | Project name. |
| `branch` | Path | `string` | — | Variant branch. |
| `provider` | Path | `string` | — | Variant provider. |
| `model` | Path | `string` | — | Variant model. |
| `path` | Path | `string` | `index.html` | Relative path inside the generated `site/` directory. Nested paths are allowed. A trailing `/` resolves to `index.html`. |
| `owner` | Query | `string` | — | Admin-only disambiguation parameter. Required when the same variant exists under multiple owners. Ignored for non-admin requests. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | File response | Returns the requested generated file. |
| `403` | `ErrorResponse` | `path` escaped the generated site directory. |
| `404` | `ErrorResponse` | Variant not found, not accessible, or file not found. |
| `409` | `ErrorResponse` | Multiple owners match the same variant and no `owner` was supplied. |
| `401` | `ErrorResponse` | Missing or invalid authentication for non-HTML clients. |
| `302` | Redirect | Unauthenticated HTML clients are redirected to `/login`. |

**Example**
```bash
curl "<SERVER_URL>/docs/my-repo/main/claude/opus/index.html?owner=alice" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

### `GET /docs/{project}/{path}`

Serves one file from the most recently generated accessible ready variant for a project name.

**Auth:** Bearer token or `docsfy_session` cookie.

**Parameters**

| Name | In | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `project` | Path | `string` | — | Project name. |
| `path` | Path | `string` | `index.html` | Relative path inside the generated `site/` directory. Nested paths are allowed. A trailing `/` resolves to `index.html`. |

**Returns**

| Status | Body | Effect |
| --- | --- | --- |
| `200` | File response | Returns the requested file from the latest accessible ready variant. |
| `403` | `ErrorResponse` | `path` escaped the generated site directory. |
| `404` | `ErrorResponse` | No accessible ready docs exist, or the file was not found. |
| `409` | `ErrorResponse` | For non-admin callers, multiple accessible owners tied for the newest variant timestamp. |
| `401` | `ErrorResponse` | Missing or invalid authentication for non-HTML clients. |
| `302` | Redirect | Unauthenticated HTML clients are redirected to `/login`. |

> **Note:** This route does not accept `owner`. To target a specific owner and variant, use the variant-specific docs route.

**Example**
```bash
curl "<SERVER_URL>/docs/my-repo/index.html" \
  -H "Authorization: Bearer <USER_API_KEY>"
```

## Related Pages

- [WebSocket Reference](websocket-reference.html)
- [Manage Users, Roles, and Access](manage-users-roles-and-access.html)
- [View, Download, and Publish Docs](view-download-and-publish-docs.html)
- [Generate Documentation](generate-documentation.html)
- [Track Generation Progress](track-generation-progress.html)