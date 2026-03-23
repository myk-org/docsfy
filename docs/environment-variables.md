# Environment Variables

`docsfy` reads its server settings from environment variables. The settings model loads a local `.env` file automatically, and the repository ships `.env.example` with the core runtime options. The provided `docker-compose.yaml` also loads `.env` into the container.

A practical starting point is the shipped `.env.example`:

```dotenv
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

# Development mode: starts Vite dev server on port 5173 alongside FastAPI
# DEV_MODE=true
```

> **Note:** The `docsfy` CLI stores server connection details in `~/.config/docsfy/config.toml` and command-line flags. The variables on this page mostly affect the server/runtime process.

## Quick Reference

| Variable | Default | Required | What it controls |
| --- | --- | --- | --- |
| `ADMIN_KEY` | none | Yes | Built-in admin authentication and the secret used to hash stored user API keys |
| `AI_PROVIDER` | `cursor` | No | Default AI provider when a generation request does not specify one |
| `AI_MODEL` | `gpt-5.4-xhigh-fast` | No | Default AI model when a generation request does not specify one |
| `AI_CLI_TIMEOUT` | `60` | No | Default timeout value passed to AI CLI calls during generation |
| `LOG_LEVEL` | `INFO` | No | Log verbosity |
| `DATA_DIR` | `/data` | No | Root directory for the SQLite database and generated docs |
| `SECURE_COOKIES` | `true` | No | Whether browser session cookies use the `Secure` flag |

## `ADMIN_KEY`

`ADMIN_KEY` is the only required environment variable. The server refuses to start if it is missing or shorter than 16 characters.

From `src/docsfy/main.py`:

```python
if not settings.admin_key:
    logger.error("ADMIN_KEY environment variable is required")
    raise SystemExit(1)

if len(settings.admin_key) < 16:
    logger.error("ADMIN_KEY must be at least 16 characters long")
    raise SystemExit(1)
```

In practice, `ADMIN_KEY` is used in three important ways:

- Sign in as the built-in `admin` user.
- Authenticate admin API requests with `Authorization: Bearer ...`.
- Authenticate WebSocket connections with `/api/ws?token=...`.

It is also more than just an admin password. In `src/docsfy/storage.py`, it is used as the HMAC secret for stored user API-key hashes.

> **Warning:** Changing `ADMIN_KEY` invalidates existing stored user API-key hashes. After rotating it, database-backed users will need new API keys.

> **Note:** `ADMIN_KEY` users cannot rotate their own key through the app. The API explicitly tells you to change the `ADMIN_KEY` environment variable instead.

## `AI_PROVIDER`, `AI_MODEL`, and `AI_CLI_TIMEOUT`

These are server-wide defaults for documentation generation.

- `AI_PROVIDER` defaults to `cursor`.
- `AI_MODEL` defaults to `gpt-5.4-xhigh-fast`.
- `AI_CLI_TIMEOUT` defaults to `60` and must be greater than `0`.

When a generation request does not include its own provider or model, docsfy falls back to these settings. The valid provider names in the codebase are currently `claude`, `gemini`, and `cursor`.

Use these settings when you want a default experience for the whole server, then override provider or model per request when needed.

> **Tip:** Set `AI_PROVIDER` and `AI_MODEL` to the combination you use most often. That keeps the UI and API simpler for everyday use while still allowing explicit overrides for one-off runs.

> **Note:** `AI_CLI_TIMEOUT` is the timeout used when the server calls the provider CLI during generation. It is not a separate environment variable for the `docsfy` client's own HTTP timeout.

## `LOG_LEVEL`

`LOG_LEVEL` defaults to `INFO`.

Use it to make logs quieter or more verbose. The repository's shipped example uses `INFO`, and the tests also set `DEBUG`, which is a good choice when you are troubleshooting startup, authentication, or generation problems.

The application code does not add extra validation for this setting, so use values your logging setup understands.

## `DATA_DIR`

`DATA_DIR` controls where docsfy stores its SQLite database and generated documentation artifacts. By default, everything lives under `/data`.

From `src/docsfy/storage.py`:

```python
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"
```

That means the default layout is:

- database: `DATA_DIR/docsfy.db`
- generated docs and project files: `DATA_DIR/projects/`

The provided Docker Compose setup maps a host directory into that default location:

```yaml
volumes:
  - ./data:/data
env_file:
  - .env
environment:
  - ADMIN_KEY=${ADMIN_KEY}
```

> **Tip:** If you change `DATA_DIR` in Docker, update your volume mount too. Otherwise your database and generated docs may end up inside the container filesystem instead of persistent storage on the host.

> **Note:** When the server runs in a container, any local `repo_path` you send to the API must exist inside the container, not just on your host machine.

## `SECURE_COOKIES`

`SECURE_COOKIES` controls whether the browser session cookie is marked `Secure`. It defaults to `true`, which is the right choice for HTTPS deployments.

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

A few important details come from that code:

- The cookie is always `HttpOnly`.
- The cookie is always `SameSite=Strict`.
- The session lifetime is fixed in code at 8 hours.
- Only the `Secure` attribute is controlled by `SECURE_COOKIES`.

> **Tip:** Set `SECURE_COOKIES=false` only for local plain-HTTP development. Keep it `true` in production and anywhere the app is served over HTTPS.

> **Note:** Tests verify that the `docsfy_session` cookie stores an opaque session token, not the raw API key.

## Development-Only Variables

A few additional environment variables are used for local development or direct process startup.

### `DEV_MODE`

`DEV_MODE=true` is used by the container entrypoint. It installs frontend dependencies, starts the Vite dev server on port `5173`, and runs FastAPI with hot reload.

From `entrypoint.sh`:

```bash
if [ "$DEV_MODE" = "true" ]; then
    echo "DEV_MODE enabled - installing frontend dependencies..."
    cd /app/frontend || exit 1
    npm ci
    echo "Starting Vite dev server on port 5173..."
    npm run dev &
    VITE_PID=$!
    # Forward signals to the background Vite process for clean shutdown
    trap 'kill $VITE_PID 2>/dev/null; wait $VITE_PID 2>/dev/null' SIGTERM SIGINT
    cd /app
    echo "Starting FastAPI with hot reload on port 8000..."
    uv run --no-sync uvicorn docsfy.main:app \
        --host 0.0.0.0 --port 8000 \
        --reload --reload-dir /app/src
```

> **Warning:** `DEV_MODE` is a development convenience, not a production setting.

### `HOST`, `PORT`, and `DEBUG`

If you start the server with the `docsfy-server` console script, `src/docsfy/main.py` reads three more environment variables:

```python
reload = os.getenv("DEBUG", "").lower() == "true"
host = os.getenv("HOST", "127.0.0.1")
port = int(os.getenv("PORT", "8000"))
uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
```

That means:

- `HOST` defaults to `127.0.0.1`
- `PORT` defaults to `8000`
- `DEBUG=true` enables uvicorn reload mode

These are useful when you run `docsfy-server` directly. The Docker entrypoint does not use them; it starts uvicorn explicitly on `0.0.0.0:8000`.

### `API_TARGET`

If you run the frontend dev server separately, `frontend/vite.config.ts` uses `API_TARGET` to decide where `/api`, `/docs`, and `/health` should be proxied. Its default is `http://localhost:8000`.

This is a frontend development variable, not a production server setting.
