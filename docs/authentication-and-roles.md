# Authentication and Roles

`docsfy` uses one authentication model across the web UI, API, and CLI:

- The built-in bootstrap admin signs in as `admin` with the `ADMIN_KEY` environment variable.
- Everyone else is a database-backed user with a role of `viewer`, `user`, or `admin`.
- The browser exchanges a username + API key for a session cookie.
- API and CLI clients can send the same API key directly as a Bearer token.

> **Tip:** In the web UI, the field is labeled **Password**, but the backend and CLI call the same secret an **API key**. They are the same credential.

## Two kinds of admin access

There are two ways to have admin privileges in `docsfy`:

1. The built-in `admin` account, configured from `ADMIN_KEY`
2. A database-backed user whose role is `admin`

They can both use the admin panel and admin API. The main difference is credential management: database-backed admins can rotate their own keys through the app, while the built-in `admin` account is rotated by changing `ADMIN_KEY`.

## Built-in admin login

The built-in admin account is how you bootstrap a new deployment. It is not created from the admin panel and it is not looked up in the `users` table. Instead, the server reads `ADMIN_KEY` from the environment at startup, and login grants admin access only when the username is exactly `admin`.

From `.env.example`:

```env
# Required: Admin password (minimum 16 characters)
ADMIN_KEY=

# Data directory for database and generated docs
DATA_DIR=/data

# Cookie security (set to false for local HTTP development)
SECURE_COOKIES=true
```

From `src/docsfy/api/auth.py`:

```python
# Check admin -- username must be "admin" and key must match
if username == "admin" and hmac.compare_digest(api_key, settings.admin_key):
    is_admin = True
    authenticated = True
    role = "admin"
else:
    # Check user key -- verify username matches the key's owner
    user = await get_user_by_key(api_key)
    if user and user["username"] == username:
        authenticated = True
        role = str(user.get("role", "user"))
        if role == "admin":
            is_admin = True
```

The server also validates `ADMIN_KEY` on startup. If it is missing or shorter than 16 characters, `docsfy` exits instead of starting with a broken auth setup.

> **Warning:** The username `admin` is reserved. You cannot create a database-backed user named `admin`, `Admin`, or `ADMIN`.

## Database-backed users

Admins can create additional users from the admin panel or the CLI. These users are stored in the SQLite database under `DATA_DIR`, with a role of `viewer`, `user`, or `admin`.

Raw API keys are not stored in the database. Instead, `docsfy` stores a keyed HMAC hash of the API key, and auto-generated keys use a `docsfy_` prefix.

From `src/docsfy/storage.py`:

```python
def hash_api_key(key: str, hmac_secret: str = "") -> str:
    """Hash an API key with HMAC-SHA256 for storage.

    Uses ADMIN_KEY as the HMAC secret so that even if the source is read,
    keys cannot be cracked without the environment secret.
    """
    # NOTE: ADMIN_KEY is used as the HMAC secret. Rotating ADMIN_KEY will
    # invalidate all existing api_key_hash values, requiring all users to
    # regenerate their API keys.
    secret = hmac_secret or os.getenv("ADMIN_KEY", "")
    if not secret:
        msg = "ADMIN_KEY environment variable is required for key hashing"
        raise RuntimeError(msg)
    return hmac.new(secret.encode(), key.encode(), hashlib.sha256).hexdigest()


def generate_api_key() -> str:
    """Generate a random API key."""
    return f"docsfy_{secrets.token_urlsafe(32)}"
```

In practice, that means:

- When a user is created or their key is rotated, the raw key is shown once and should be saved immediately.
- If you lose a key, rotate it. The server cannot show you the old one.
- Auto-generated keys start with `docsfy_`.
- If you change `ADMIN_KEY`, existing database-backed user keys stop matching until those users are issued new keys.

> **Note:** The admin UI and CLI both treat newly created or rotated credentials as one-time secrets: save them when they are shown.

## Browser login and session cookies

The browser does not send your API key on every request after login. Instead, it exchanges `username` + `api_key` for a session cookie and then uses that cookie for normal browsing.

From `frontend/src/pages/LoginPage.tsx`:

```ts
await api.post<AuthResponse>('/api/auth/login', {
  username,
  api_key: password,
})
```

From `src/docsfy/storage.py`:

```python
SESSION_TTL_SECONDS = 28800  # 8 hours
```

From `src/docsfy/api/auth.py`:

```python
response.set_cookie(
    "docsfy_session",
    session_token,
    httponly=True,
    samesite="strict",
    secure=settings.secure_cookies,
    max_age=SESSION_TTL_SECONDS,
)
```

What that means in practice:

- The cookie name is `docsfy_session`.
- Sessions last 8 hours.
- The cookie is `HttpOnly`, so browser JavaScript cannot read it directly.
- The cookie uses `SameSite=Strict`.
- The `Secure` flag is controlled by `SECURE_COOKIES`.
- Logout deletes the server-side session and clears the cookie.

The session token is opaque; it is not the raw API key. If a user is deleted or their key is rotated, their existing sessions stop working.

When you browse protected docs without a valid session, `docsfy` redirects HTML requests for `/docs/...` to `/login`. Protected API requests return `401 Unauthorized`.

> **Note:** `SECURE_COOKIES=true` is the default and is the right setting for HTTPS deployments. For local HTTP development, set `SECURE_COOKIES=false` or the browser will not send the cookie back.

## CLI and API clients

CLI and other non-browser clients usually skip the login endpoint and send the API key directly as a Bearer token.

From `config.toml.example`:

```toml
[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<your-dev-key>"
```

From `src/docsfy/cli/client.py`:

```python
self._client = httpx.Client(
    base_url=self.server_url,
    headers={"Authorization": f"Bearer {self.password}"},
    timeout=30.0,
    follow_redirects=False,
)
```

This is why the same secret works in both places:

- In the web UI, you type it into the Password field and receive a session cookie.
- In the CLI, it is stored as `password` in `~/.config/docsfy/config.toml` and sent as a Bearer token.

The CLI configuration code writes that file with owner-only permissions.

> **Warning:** `~/.config/docsfy/config.toml` contains real credentials. Keep it private.

## Roles and permissions

### `viewer`

A `viewer` is read-only.

- Can sign in.
- Can view docs they own or docs an admin shared with them.
- Can download docs they are allowed to view.
- Can rotate their own API key.
- Cannot generate, regenerate, abort, or delete documentation.
- Cannot access the admin panel.

### `user`

A `user` is a normal write-enabled account.

- Can do everything a `viewer` can do.
- Can generate docs from remote repository URLs.
- Can regenerate, abort, and delete their own variants.
- Can see their own projects plus any projects explicitly shared with them.
- Cannot access the admin panel.
- Cannot use local filesystem `repo_path` generation; that is admin-only.

### `admin`

An `admin` has global visibility and user-management access.

- Can do everything a `user` can do.
- Can see all projects across all owners.
- Can access the admin panel.
- Can create and delete users.
- Can rotate any user's API key.
- Can grant and revoke project access.
- Can generate from local filesystem paths (`repo_path`).

> **Note:** Database-backed admins and the built-in `admin` account get the same admin permissions. The difference is rotation behavior: database-backed admins can rotate their own key in the app, while the built-in `admin` account is rotated by changing `ADMIN_KEY`.

> **Tip:** Role checks are enforced on the server, not just hidden in the UI. For example, `viewer` write requests are rejected even if someone manually calls the API.

## Shared access is owner-scoped

By default, non-admin users only see their own projects. Admins can grant access to another user's project, but the grant is scoped to both the project name and the owner.

That owner scoping matters because two different users can generate docs for repositories with the same name. A grant to Alice's `for-testing-only` project does not automatically grant Bob's `for-testing-only` project.

From `frontend/src/components/admin/AccessPanel.tsx`:

```ts
await api.post(`/api/admin/projects/${encodeURIComponent(grantProject.trim())}/access`, {
  username: grantUsername.trim(),
  owner: grantOwner.trim(),
})
```

A grant applies to all variants of that project name for that owner. Revoking access removes those shared views again, and the restriction is enforced on direct URLs too, not just in the dashboard.

In practice:

- Admins see everything.
- Non-admins see their own projects.
- Non-admins also see projects listed in their access grants.
- If a user does not have access, project details, downloads, and docs URLs return `404` rather than leaking that the project exists.

> **Tip:** When an admin grants access, always use the correct owner. If multiple users generated the same repo name, the owner determines which copy is shared.

## Key rotation

Database-backed users can rotate their own keys. Admins can also rotate keys on behalf of other users.

From `src/docsfy/storage.py`:

```python
async def rotate_user_key(username: str, custom_key: str | None = None) -> str:
    """Generate or set a new API key for a user. Returns the raw new key."""
    if custom_key:
        validate_api_key(custom_key)
        raw_key = custom_key
    else:
        raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET api_key_hash = ? WHERE username = ?",
            (key_hash, username),
        )
        if cursor.rowcount == 0:
            msg = f"User '{username}' not found"
            raise ValueError(msg)
        # Invalidate all existing sessions for this user
        await db.execute("DELETE FROM sessions WHERE username = ?", (username,))
        await db.commit()
    return raw_key
```

From `src/docsfy/api/auth.py`:

```python
response = JSONResponse(
    content={"username": username, "new_api_key": new_key},
    headers={"Cache-Control": "no-store"},
)
response.delete_cookie(
    "docsfy_session",
    httponly=True,
    samesite="strict",
    secure=settings.secure_cookies,
)
```

Rotation behaves like this:

- `POST /api/auth/rotate-key` rotates the current database-backed user's key.
- `POST /api/admin/users/{username}/rotate-key` lets an admin rotate another user's key.
- If you send `new_key`, it must be at least 16 characters long.
- If you omit `new_key`, `docsfy` generates a new `docsfy_...` key.
- The old key stops working immediately.
- All active sessions for that user are invalidated.
- The self-service browser flow clears the current session cookie, so the user must log in again with the new key.
- Rotation responses use `Cache-Control: no-store` because they contain sensitive credentials.

`viewer` users can rotate their own keys just like `user` users. Database-backed admins can too.

> **Warning:** The built-in `admin` account cannot use the rotate-key endpoint. If you are logged in as `admin` via `ADMIN_KEY`, rotate that credential by changing the `ADMIN_KEY` environment variable and restarting the server.

> **Warning:** Rotating `ADMIN_KEY` is a global event for database-backed users, because their stored API-key hashes are derived from it. Plan to reissue or rotate user keys after changing `ADMIN_KEY`.

## Practical guidance

Use the built-in `admin` account to bootstrap the system, then create database-backed users for day-to-day access.

A good pattern is:

- Keep `ADMIN_KEY` for break-glass access and initial administration.
- Create named database users for humans and service accounts.
- Give read-only people the `viewer` role.
- Give day-to-day writers the `user` role.
- Grant project access explicitly when someone needs to see another owner's docs.
- Rotate lost or exposed keys instead of trying to recover them, because raw keys are not stored.

If you keep those rules in mind, `docsfy`'s auth model stays simple: one secret per account, role-based permissions on top, and short-lived browser sessions for the UI.


## Related Pages

- [Authentication API](auth-api.html)
- [User and Access Management](user-and-access-management.html)
- [Security Considerations](security-considerations.html)
- [Projects, Variants, and Ownership](projects-variants-and-ownership.html)
- [Admin API](admin-api.html)