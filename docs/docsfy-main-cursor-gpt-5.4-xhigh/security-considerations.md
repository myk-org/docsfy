# Security Considerations

docsfy is designed for authenticated, internal-style documentation hosting rather than anonymous public uploads. It protects its API and generated docs with credential checks, reduces credential exposure in storage, rejects risky repository inputs, and sanitizes AI-generated HTML before it is rendered.

## What matters most
- Protect `ADMIN_KEY` like a root credential. It is required at startup and must be at least 16 characters long.
- Keep `SECURE_COOKIES=true` in production so browser sessions are sent only over HTTPS.
- Prefer individual database-backed users over sharing the built-in `admin` credential.
- Use remote repository URLs for normal workflows. Local `repo_path` access is intentionally admin-only.
- Review generated documentation before publishing it outside your team, even though docsfy sanitizes the rendered HTML.

## Authentication and access control

With a small set of public exceptions such as `/health`, login/logout, and the frontend login route, docsfy treats `/api/*` and `/docs/*` as authenticated surfaces.

It supports two main authentication flows:

- Browser flow: log in once, receive a `docsfy_session` cookie, and let the frontend send that cookie on same-origin requests.
- API or CLI flow: send `Authorization: Bearer <API_KEY>` on each request.

The built-in `admin` login is special. It is not a normal database user. It only authenticates when the username is literally `admin` and the submitted secret matches `ADMIN_KEY`. Database-backed users are looked up by API key and carry one of three roles: `admin`, `user`, or `viewer`.

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

Write access is enforced server-side. Viewers can read but cannot generate or delete docs.

From `src/docsfy/api/projects.py`:

```python
def _require_write_access(request: Request) -> None:
    """Raise 403 if user is a viewer (read-only)."""
    if request.state.role not in ("admin", "user"):
        raise HTTPException(
            status_code=403,
            detail="Write access required.",
        )
```

Access grants are owner-scoped. If one owner shares `my-repo`, that does not automatically expose another owner's `my-repo`. When a non-admin requests a project they should not see, docsfy often returns `404 Not found` instead of `403`, which helps avoid leaking whether that project exists.

For browser HTML requests to `/docs/*`, unauthenticated users are redirected to `/login`. Programmatic requests get `401 Unauthorized` JSON instead. The WebSocket endpoint follows the same model: it accepts either a session cookie or a token, and the built-in frontend uses the cookie-based path after login.

> **Note:** In the UI and CLI config, this secret may be shown as a "password", but for database-backed users it is the same underlying API key used for authenticated API requests.

> **Tip:** For day-to-day administration, prefer a database-backed user with role `admin`. That account can rotate its own key. The built-in `admin` login is tied directly to `ADMIN_KEY`.

## API keys and session cookies

docsfy does not store user API keys in plaintext. The `users` table keeps only `api_key_hash`, and that hash is an HMAC-SHA256 digest keyed by `ADMIN_KEY`.

From `src/docsfy/storage.py`:

```python
def hash_api_key(key: str, hmac_secret: str = "") -> str:
    """Hash an API key with HMAC-SHA256 for storage.

    Uses ADMIN_KEY as the HMAC secret so that even if the source is read,
    keys cannot be cracked without the environment secret.
    """
    secret = hmac_secret or os.getenv("ADMIN_KEY", "")
    if not secret:
        msg = "ADMIN_KEY environment variable is required for key hashing"
        raise RuntimeError(msg)
    return hmac.new(secret.encode(), key.encode(), hashlib.sha256).hexdigest()
```

In practice, that means:

- The raw API key is not recoverable from the database.
- Creating or rotating a key is the moment when the raw value must be saved.
- Generated keys use a random `docsfy_...` format.
- Custom replacement keys must be at least 16 characters long.
- Creating or rotating a key returns `Cache-Control: no-store` so browsers and proxies should not cache the raw value.
- Rotating a user's key invalidates that user's active sessions.

Browser sessions use a separate opaque token. docsfy generates a random session token, stores only its SHA-256 hash in the `sessions` table, and sends the raw token as an `HttpOnly` cookie.

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

That gives you:

- `HttpOnly`: JavaScript cannot read the session cookie.
- `SameSite=Strict`: the cookie is not intended for cross-site use.
- `Secure`: controlled by `SECURE_COOKIES`, and should stay enabled in production.
- An 8-hour lifetime by default.

The frontend is wired to use same-origin credentials instead of reading or managing the cookie itself. From `frontend/src/lib/api.ts`:

```ts
const config: RequestInit = {
  ...options,
  credentials: 'same-origin',
  redirect: 'manual',
  headers,
}
```

Start from the shipped `.env.example` settings:

```env
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

If you use the CLI, remember that the config file contains the raw password or API key. The sample `config.toml.example` calls this out directly:

```toml
# docsfy CLI configuration
# Copy to ~/.config/docsfy/config.toml or run: docsfy config init
#
# SECURITY: This file contains passwords. Keep it private:
#   chmod 600 ~/.config/docsfy/config.toml

# Default server to use when --server is not specified
[default]
server = "dev"

# Server profiles -- add as many as you need
[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<your-dev-key>"
```

`docsfy config init` reinforces this by writing the config directory and file with owner-only permissions.

> **Warning:** Rotating `ADMIN_KEY` does more than change the built-in admin login. Because it is also the HMAC secret for user API-key hashes, existing database-backed API keys stop matching until new keys are issued.

> **Tip:** Leave `SECURE_COOKIES=true` in production. Set it to `false` only for local HTTP development.

## Repository URLs, SSRF protection, and path validation

docsfy validates repository inputs in more than one place.

### Repository URL shape

The request model only accepts a narrow set of remote Git URL forms, and local paths must be absolute.

From `src/docsfy/models.py`:

```python
@field_validator("repo_url")
@classmethod
def validate_repo_url(cls, v: str | None) -> str | None:
    if v is None:
        return v
    https_pattern = r"^https?://[\w.\-]+/[\w.\-]+/[\w.\-]+(\.git)?$"
    ssh_pattern = r"^git@[\w.\-]+:[\w.\-]+/[\w.\-]+(\.git)?$"
    if not re.match(https_pattern, v) and not re.match(ssh_pattern, v):
        msg = f"Invalid git repository URL: '{v}'"
        raise ValueError(msg)
    return v
```

Practical implications:

- Current remote URL validation is intentionally strict. It expects `host/org/repo`-style paths.
- Bare local filesystem paths are not accepted as `repo_url`.
- `repo_path` must be absolute.
- Local repository generation is admin-only and must point to a directory that exists and contains `.git`.

Branch names are also validated because they are used in URLs and on disk. Slashes, leading dots, and `..` are rejected. Use `release-1.x`, not `release/1.x`.

### SSRF protection for remote repositories

Before cloning a remote repository, docsfy rejects repository URLs that point at localhost, private addresses, or DNS names that resolve to private addresses.

From `src/docsfy/api/projects.py`:

```python
if not hostname:
    # Reject bare paths like /srv/repo.git or ../repo that have
    # no scheme and no hostname -- they are local filesystem refs.
    raise HTTPException(
        status_code=400,
        detail="Repository URL must include a hostname. Bare local paths are not allowed.",
    )
# Check for localhost
if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
    raise HTTPException(
        status_code=400,
        detail="Repository URL must not target localhost or private networks",
    )
# Check if hostname is an IP address in private range
try:
    addr = ipaddress.ip_address(hostname)
    if not addr.is_global:
        raise HTTPException(
            status_code=400,
            detail="Repository URL must not target localhost or private networks",
        )
except ValueError:
    # hostname is a DNS name - resolve and check
    try:
        loop = asyncio.get_event_loop()
        resolved = await loop.run_in_executor(
            None,
            socket.getaddrinfo,
            hostname,
            None,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
        for _family, _socktype, _proto, _canonname, sockaddr in resolved:
            ip_str = sockaddr[0]
            addr = ipaddress.ip_address(ip_str)
            if not addr.is_global:
                raise HTTPException(
                    status_code=400,
                    detail="Repository URL resolves to a private network address",
                )
```

This protects against common SSRF mistakes, such as accidentally pointing docsfy at:

- `localhost`
- `127.0.0.1`
- `0.0.0.0`
- private RFC1918 or non-global IPs
- DNS names that resolve to internal addresses

The code also passes the repository URL to Git after `--`, which prevents the URL from being interpreted as a Git CLI option.

> **Note:** The SSRF protection is intentionally basic. The code explicitly recommends adding network or firewall controls for stronger protection against cases such as DNS rebinding.

### Filesystem safety

docsfy also validates the names it turns into directory names and filenames.

From `src/docsfy/storage.py`:

```python
if not branch:
    msg = "branch is required for project directory paths"
    raise ValueError(msg)
if not ai_provider or not ai_model:
    msg = "ai_provider and ai_model are required for project directory paths"
    raise ValueError(msg)
# Sanitize path segments to prevent traversal
for segment_name, segment in [
    ("branch", branch),
    ("ai_provider", ai_provider),
    ("ai_model", ai_model),
]:
    if (
        "/" in segment
        or "\\" in segment
        or ".." in segment
        or segment.startswith(".")
    ):
        msg = f"Invalid {segment_name}: '{segment}'"
        raise ValueError(msg)
```

There are similar checks for project names, owners, and generated page slugs. Invalid slugs are rejected before docsfy writes cache files or output pages.

When serving built docs, docsfy also verifies that the requested file stays inside the generated site directory.

From `src/docsfy/main.py`:

```python
file_path = site_dir / path
try:
    file_path.resolve().relative_to(site_dir.resolve())
except ValueError as exc:
    raise HTTPException(status_code=403, detail="Access denied") from exc
if not file_path.exists() or not file_path.is_file():
    raise HTTPException(status_code=404, detail="File not found")
```

That containment check is important because it prevents `..`-style path traversal from escaping the generated docs directory.

## Sanitizing AI-generated HTML

docsfy does not blindly trust the HTML that comes out of the markdown rendering step. After converting markdown to HTML, it sanitizes the result before inserting it into the page template.

From `src/docsfy/renderer.py`:

```python
# Remove script tags and content
html = re.sub(
    r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
)
# Remove iframe, object, embed, form tags
for tag in ["iframe", "object", "embed", "form"]:
    html = re.sub(
        rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    html = re.sub(rf"<{tag}[^>]*/>", "", html, flags=re.IGNORECASE)
# Remove event handler attributes
html = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', "", html, flags=re.IGNORECASE)
html = re.sub(r"\s+on\w+\s*=\s*\S+", "", html, flags=re.IGNORECASE)

def _sanitize_url_attr(match: re.Match) -> str:
    attr = match.group(1)  # href or src
    quote = match.group(2)  # " or '
    url = match.group(3)  # the URL value
    clean_url = url.strip()
    if clean_url.startswith(("http://", "https://", "#", "/", "mailto:")):
        return match.group(0)  # Keep as-is
    return f"{attr}={quote}#{quote}"
```

In practice, that means:

- `<script>` content is removed.
- `<iframe>`, `<object>`, `<embed>`, and `<form>` elements are removed.
- Inline event handlers such as `onclick=` and `onerror=` are stripped.
- Unsafe `href` and `src` values such as `javascript:` or `data:` are rewritten to `#`.
- Safe URL shapes such as `https://...`, `/relative-path`, `#anchor`, and `mailto:` are preserved.

Template rendering adds another layer. Jinja autoescaping is enabled for HTML templates, and only the already-sanitized page body is marked safe for insertion.

From `src/docsfy/templates/page.html`:

```html
{{ content | safe }}
```

That ordering is the important part: sanitize first, then render.

Other dynamic UI text is also handled conservatively. For example, search result titles and snippets in `src/docsfy/static/search.js` are inserted with DOM `textContent`, not as raw HTML.

> **Warning:** Sanitization greatly reduces XSS risk, but it is not a substitute for reviewing generated documentation before publishing it to a wider audience. AI-generated docs can still contain misleading instructions, bad links, or content you would not want to ship unchanged.

## Deployment notes

A few defaults are worth knowing when you deploy docsfy:

- `docsfy-server` binds to `127.0.0.1` by default when run directly, which is a safer local default.
- The provided container image drops to a non-root `appuser` at runtime.
- `docker-compose.yaml` reads `ADMIN_KEY` from `.env` instead of hardcoding it into the compose file.

For most deployments, a good baseline is simple:

- Keep `ADMIN_KEY` in the environment, never in git.
- Serve docsfy over HTTPS.
- Leave `SECURE_COOKIES=true`.
- Use per-user accounts and roles instead of sharing the built-in admin secret.
- Review generated docs before publishing them outside your trusted audience.
