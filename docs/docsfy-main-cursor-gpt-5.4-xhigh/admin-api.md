## Authentication

All routes under `\`/api/admin\`` require admin privileges. docsfy recognizes two kinds of admin credentials:

- the built-in `admin` account, authenticated with the `ADMIN_KEY` environment variable
- a database-backed user created with role `admin`

For scripts and automation, send the key as `Authorization: Bearer <token>`. For browser-based admin flows, log in through `POST /api/auth/login`; successful logins set an `HttpOnly` `docsfy_session` cookie with `SameSite=strict`, an 8-hour lifetime, and a `secure` flag controlled by `SECURE_COOKIES`.

The server-side auth settings come directly from `.env.example`:

```1:17:.env.example
# Required: Admin password (minimum 16 characters)
ADMIN_KEY=

# AI provider and model defaults
# (pydantic_settings reads these case-insensitively)
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60

# Logging
LOG_LEVEL=INFO

# Data directory for database and generated docs
DATA_DIR=/data

# Cookie security (set to false for local HTTP development)
SECURE_COOKIES=true
```

> **Warning:** `ADMIN_KEY` is not just the built-in admin password. docsfy also uses it as the HMAC secret for stored user API keys, so changing `ADMIN_KEY` invalidates every existing database-backed user key.

> **Tip:** If you are testing over plain `http://` on localhost, set `SECURE_COOKIES=false` or browser login sessions will not persist.

The bundled `docsfy` CLI uses the same Bearer-token model under the hood. The admin commands live under `docsfy admin users ...` and `docsfy admin access ...`.

## Quick Reference

| Route | Purpose |
|---|---|
| `GET /api/admin/users` | List database-backed users |
| `POST /api/admin/users` | Create a user and return a one-time API key |
| `DELETE /api/admin/users/{username}` | Delete a user, their sessions, grants, and owned projects |
| `POST /api/admin/users/{username}/rotate-key` | Generate or set a new API key for a user |
| `POST /api/admin/projects/{name}/access` | Grant access to a project owned by a specific user |
| `GET /api/admin/projects/{name}/access?owner=<owner>` | List usernames with access to that project |
| `DELETE /api/admin/projects/{name}/access/{username}?owner=<owner>` | Revoke access from a user |

Common status codes:

- `200`: request succeeded
- `400`: malformed JSON, missing required fields, invalid role, invalid username, or too-short custom key
- `401`: no valid Bearer token or session cookie
- `403`: authenticated, but not an admin
- `404`: target user or project was not found
- `409`: delete was blocked because the user currently has a generation in progress

## User Management

### Create A User

Use `POST /api/admin/users` to create a database-backed account.

Request body:

- `username`: required
- `role`: optional, defaults to `user`

Valid roles are:

- `admin`: full admin privileges
- `user`: normal read/write project operations
- `viewer`: read-only access; can sign in and view granted docs, but cannot generate or delete projects

Username rules are strict:

- 2 to 50 characters
- letters and digits first
- `.` `_` and `-` are allowed
- `admin` is reserved, case-insensitively

The admin API tests exercise user creation like this:

```80:89:tests/test_api_admin.py
response = await admin_client.post(
    "/api/admin/users",
    json={"username": "testuser", "role": "user"},
)
assert response.status_code == 200
data = response.json()
assert data["username"] == "testuser"
assert data["role"] == "user"
assert data["api_key"].startswith("docsfy_")
assert response.headers.get("cache-control") == "no-store"
```

A successful response includes:

- `username`
- `role`
- `api_key`

The returned `api_key` is the raw secret. docsfy stores only a hash in the database.

> **Warning:** Treat the returned `api_key` as a one-time secret. `GET /api/admin/users` does not return raw keys later.

> **Note:** The built-in `admin` account is not a database user. You will not see it in `GET /api/admin/users`, and you cannot create another user named `admin`.

### List Users

Use `GET /api/admin/users` to retrieve the current database-backed user list.

Each entry includes:

- `id`
- `username`
- `role`
- `created_at`

This route intentionally does not return `api_key` or `api_key_hash`.

### Delete A User

Use `DELETE /api/admin/users/{username}` to permanently remove a user.

Important behavior:

- the request is rejected if you try to delete the account you are currently authenticated as
- the request returns `404` if the user does not exist
- the request returns `409` if that user currently has a generation in progress
- all sessions for that user are invalidated
- project-access grants for that user are removed
- access entries for projects owned by that user are removed
- projects owned by that user are deleted

> **Warning:** Deleting a user is destructive. In docsfy, this is more than removing a login: it also removes the user's owned projects and related access-control entries.

### Rotate A User Key

Use `POST /api/admin/users/{username}/rotate-key` to replace a user's API key.

Request body:

- empty JSON object to generate a new random key
- or `{ "new_key": "..." }` to set a custom key

Custom keys must be at least 16 characters long.

The auth tests cover an admin-set custom key like this:

```908:919:tests/test_auth.py
custom = "admin-chosen-password-long"
resp = await admin_client.post(
    "/api/admin/users/admin-custom-target/rotate-key",
    json={"new_key": custom},
)
assert resp.status_code == 200
assert resp.json()["new_api_key"] == custom

# Verify the custom key works
user = await get_user_by_key(custom)
assert user is not None
assert user["username"] == "admin-custom-target"
```

A successful response includes:

- `username`
- `new_api_key`

This response is sent with `Cache-Control: no-store`, and all existing sessions for that user are invalidated.

If the target user does not exist, the route returns `404`.

> **Note:** There is currently no separate admin endpoint for changing a user's role after creation. Roles are assigned when the user is created.

## Project Access Administration

Project sharing in docsfy is grant-based. An admin can give one user access to a project owned by another user without transferring ownership.

Access is scoped by:

- project name
- project owner

Access is not scoped by:

- branch
- AI provider
- AI model

That means one grant covers every variant of that project for that owner.

> **Note:** In these endpoints, `owner` means the project owner's username, not the admin making the request.

A granted user sees shared projects through the normal project listing and docs routes. Their role still matters: a `viewer` with a grant can open docs, but remains read-only.

### Grant Access

Use `POST /api/admin/projects/{name}/access`.

Request body:

- `username`: required
- `owner`: required

Before creating the grant, docsfy verifies that:

- the target user exists
- the project exists for the specified owner

The route implementation shows the exact validation and response shape:

```127:143:src/docsfy/api/admin.py
# Validate user exists
user = await get_user_by_username(username)
if not user:
    raise HTTPException(status_code=404, detail=f"User '{username}' not found")
# Validate project exists for the specified owner
variants = await list_variants(name, owner=project_owner)
if not variants:
    raise HTTPException(
        status_code=404,
        detail=f"Project '{name}' not found for owner '{project_owner}'",
    )
await grant_project_access(name, username, project_owner=project_owner)
await notify_access_change(username)
logger.info(
    f"[AUDIT] Admin '{request.state.username}' granted '{username}' access to '{name}' (owner: '{project_owner}')"
)
return {"granted": name, "username": username, "owner": project_owner}
```

Use this route when you want a user to see a project they do not own, including all of that project's variants for the chosen owner.

### Look Up Current Access

Use `GET /api/admin/projects/{name}/access?owner=<owner>` to see who currently has access to a project.

The response shape is:

- `project`
- `owner`
- `users`

`users` is a username list, ordered alphabetically.

This is the admin access-lookup endpoint exposed by the API today. It is project-centric: there is no separate admin route that lists every grant for a given user.

### Revoke Access

Use `DELETE /api/admin/projects/{name}/access/{username}?owner=<owner>` to remove a grant.

The response includes:

- `revoked`
- `username`
- `owner`

You must still provide `owner`, because grants are stored per project-owner pair.

This route is effectively idempotent for automation. It always returns the same summary object and does not distinguish between "grant was present and removed" and "grant was already absent."

> **Tip:** Grant and revoke operations trigger a sync update for the affected user, so connected dashboards usually reflect the change without a manual refresh.

## Related Auth Endpoints

A few non-admin auth routes matter when you are operating the Admin API.

### Log In

Use `POST /api/auth/login` with JSON:

- `username`
- `api_key`

For the built-in admin account, `username` must be exactly `admin` and `api_key` must match `ADMIN_KEY`.

For database-backed users, the username must match the owner of the supplied API key.

A successful login returns:

- `username`
- `role`
- `is_admin`

It also sets the `docsfy_session` cookie for browser use.

### Check Current Identity

Use `GET /api/auth/me` to verify who the server thinks you are. It returns:

- `username`
- `role`
- `is_admin`

This is the quickest way to confirm whether a token is being treated as built-in admin, database admin, normal user, or viewer.

### Log Out

Use `POST /api/auth/logout` to clear the current session cookie and delete the matching server-side session record.

### Self-Service Key Rotation

Use `POST /api/auth/rotate-key` when a database-backed user needs to rotate their own key.

This route accepts the same optional `new_key` field as the admin rotate route. On success, it:

- returns `username` and `new_api_key`
- sends `Cache-Control: no-store`
- deletes the current session cookie
- invalidates the user's existing sessions, so they must log in again with the new key

> **Warning:** The built-in `admin` account cannot use `POST /api/auth/rotate-key`. Manage that credential by changing `ADMIN_KEY` in your deployment instead.
