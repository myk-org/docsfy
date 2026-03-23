# Authentication API

docsfy supports two authentication styles:

- Bearer-token auth for CLI tools, scripts, and direct API calls
- Session-cookie auth for the built-in browser UI after a successful login

The same secret appears under different names depending on the client. In the login JSON body it is sent as `api_key`; in direct API requests it is sent as a Bearer token; in the UI it is entered in a password field and exchanged for a browser session.

Actual examples from the codebase:

```28:33:frontend/src/pages/LoginPage.tsx
    try {
      await api.post<AuthResponse>('/api/auth/login', {
        username,
        api_key: password,
      })
      navigate(intendedPath)
```

```15:25:src/docsfy/cli/client.py
    def __init__(self, server_url: str, username: str, password: str) -> None:
        self.server_url = server_url.rstrip("/")
        # username is stored for display/debugging; auth uses password as Bearer token
        self.username = username
        self.password = password
        self._client = httpx.Client(
            base_url=self.server_url,
            headers={"Authorization": f"Bearer {self.password}"},
            timeout=30.0,
            follow_redirects=False,
        )
```

> **Note:** If you are automating docsfy, you usually do not need to call `POST /api/auth/login` first. Send `Authorization: Bearer <api-key>` on protected requests instead.

## How Authentication Works

For protected routes, docsfy checks the `Authorization` header first and falls back to the `docsfy_session` cookie. This applies to `/api/*` and `/docs/*`.

```118:133:src/docsfy/main.py
        # 1. Check Authorization header (API clients)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            logger.debug(f"Auth middleware: Bearer token auth for '{path}'")
            token = auth_header[7:]
            if token == settings.admin_key:
                is_admin = True
                username = "admin"
            else:
                user = await get_user_by_key(token)

        # 2. Check session cookie (browser) -- opaque session token
        if not user and not is_admin:
            session_token = request.cookies.get("docsfy_session")
            if session_token:
                logger.debug(f"Auth middleware: session cookie auth for '{path}'")
```

A successful browser login creates an HttpOnly `docsfy_session` cookie. The cookie is `SameSite=Strict`, its `Secure` flag follows the `secure_cookies` setting, and its lifetime is 8 hours. The cookie value is an opaque session token, not your raw API key.

```64:80:src/docsfy/api/auth.py
        session_token = await create_session(username, is_admin=is_admin)
        response = JSONResponse(
            content={
                "username": username,
                "role": role,
                "is_admin": is_admin,
            }
        )
        response.set_cookie(
            "docsfy_session",
            session_token,
            httponly=True,
            samesite="strict",
            secure=settings.secure_cookies,
            max_age=SESSION_TTL_SECONDS,
        )
        return response
```

The React frontend sends that cookie automatically on same-origin requests, so browser code does not need to read or store the session token itself.

> **Tip:** Session-cookie auth is designed for the built-in same-origin web UI. For CLI tools, scripts, and other non-browser clients, use Bearer-token auth.

Unauthenticated requests behave differently depending on what you are calling:

- `/api/*` returns `401` with `{"detail": "Unauthorized"}`
- HTML requests to `/docs/*` are redirected to `/login`
- `/api/ws` uses the same auth model, but WebSocket clients pass a Bearer-style token as `?token=<api-key>` or rely on the session cookie

## Endpoint Reference

### POST `/api/auth/login`

Creates a browser session from a username/API-key pair.

- Auth required: No
- Request body: JSON object with `username` and `api_key`
- Success: `200 OK`, returns `username`, `role`, and `is_admin`, and sets the `docsfy_session` cookie
- Errors: `400` for malformed JSON or non-object bodies, `401` for invalid credentials
- Roles: `role` can be `admin`, `user`, or `viewer`
- Admin flag: `is_admin` is `true` for the built-in `admin` user and for database-backed users whose role is `admin`

Special login rules:

- The built-in admin login requires `username` to be exactly `admin`
- That built-in admin password is the server's `ADMIN_KEY`
- Database users must send the username that owns the API key they are using

> **Note:** The UI labels this field as "Password", but the API field name is still `api_key`.

### POST `/api/auth/logout`

Clears the current browser session.

- Auth required: No
- Request body: none
- Success: `200 OK` with `{ok: true}`
- Side effect: if the request includes `docsfy_session`, docsfy deletes the stored session and clears the cookie in the response
- Bearer-token note: this does not revoke API keys or disable Bearer-token access

> **Note:** Bearer-token auth is stateless. Rotating a key, not logging out, is how you invalidate it.

### GET `/api/auth/me`

Returns the identity attached to the current request. This is the current-user endpoint used by the dashboard to confirm who is signed in.

- Auth required: Yes, via Bearer token or session cookie
- Success: `200 OK` with `username`, `role`, and `is_admin`
- Error: `401 Unauthorized` if the request has no valid token or session

Use this endpoint to:

- confirm that a token or session is still valid
- determine the active role
- decide whether to show admin-only features

### POST `/api/auth/rotate-key`

Rotates the current user's own API key. In the UI, this is exposed as **Change Password**, but it is rotating the same underlying secret used for Bearer auth.

- Auth required: Yes, via Bearer token or session cookie
- Request body: empty body or `{}` to auto-generate a new key, or `{ "new_key": "..." }` to set a custom one
- Success: `200 OK` with `username` and `new_api_key`
- Response headers: includes `Cache-Control: no-store`
- Errors: `400` for malformed JSON, non-object JSON, short custom keys, or built-in `ADMIN_KEY` admins; `401 Unauthorized` if the request is not authenticated

The dashboard's change-password flow calls this endpoint and then sends the user back to `/login`:

```340:348:frontend/src/pages/DashboardPage.tsx
    try {
      const body = newPassword ? { new_key: newPassword } : {}
      const data = await api.post<{ new_api_key: string }>('/api/auth/rotate-key', body)
      await modalAlert({
        title: 'Password Changed',
        message: `Your new password is: ${data.new_api_key}\n\nSave it — you'll need it to log in again.`,
      })
      wsManager.disconnect()
      navigate('/login')
```

What happens after rotation:

- The old API key stops working immediately
- All existing sessions for that user are invalidated
- The current `docsfy_session` cookie is deleted
- You must log in again with the new key
- The returned `new_api_key` is the value you need to save for future logins and API calls

> **Warning:** Custom keys must be at least 16 characters long.

> **Warning:** Users signed in as the built-in `admin` account with `ADMIN_KEY` cannot use this endpoint. Change the server's `ADMIN_KEY` instead.

## Configuration

docsfy reads settings from `.env`. The auth-related settings that matter most are:

- `ADMIN_KEY`, which is required at startup and must be at least 16 characters long
- `secure_cookies`, which defaults to `True` and should be set to `False` for local HTTP development without HTTPS

```9:22:src/docsfy/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admin_key: str = ""  # Required — validated at startup
    ai_provider: str = "cursor"
    ai_model: str = "gpt-5.4-xhigh-fast"
    ai_cli_timeout: int = Field(default=60, gt=0)
    log_level: str = "INFO"
    data_dir: str = "/data"
    secure_cookies: bool = True  # Set to False for local HTTP dev
```

If you run docsfy with Docker Compose, `ADMIN_KEY` is passed through from `.env`.

> **Warning:** If `secure_cookies` stays enabled on plain HTTP local development, the browser will not send the session cookie and login will appear not to stick.

> **Warning:** Changing `ADMIN_KEY` is a broader operational change than rotating the built-in admin password. It is also used as the HMAC secret for stored user API keys, so rotating it invalidates existing user keys.

## Practical Takeaways

- Use Bearer tokens for CLI and automation.
- Use `POST /api/auth/login` only when you want a browser session.
- Use `GET /api/auth/me` to check who the current request is authenticated as.
- Use `POST /api/auth/rotate-key` to invalidate an existing user key and issue a new one.
- Use `POST /api/auth/logout` only to clear browser sessions; it does not revoke Bearer tokens.
