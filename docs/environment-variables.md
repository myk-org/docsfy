# Environment Variables

`docsfy` uses environment variables for server startup, authentication, storage, default AI behavior, and local development. In normal usage, put the core server settings in a repo-root `.env` file. The settings model reads that file automatically, and the provided `docker-compose.yaml` passes it into the container too.

> **Note:** The `docsfy` CLI stores server URL and credentials in `~/.config/docsfy/config.toml` or CLI flags such as `--host`, `--port`, `--username`, and `--password`. The variables on this page mainly affect the server process, the container entrypoint, and the frontend development server.

A practical starting point is the shipped `.env.example`:

```dotenv
# Required: Admin password (minimum 16 characters)
ADMIN_KEY=

# AI provider and model defaults
# (pydantic_settings reads these case-insensitively)
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60

# Data directory for database and generated docs
DATA_DIR=/data

# Cookie security (set to false for local HTTP development)
SECURE_COOKIES=true

# Development mode: starts Vite dev server on port 5173 alongside FastAPI
# DEV_MODE=true
```

If you use the included Compose setup, the container reads the same `.env` file:

```yaml
env_file:
  - .env
environment:
  - ADMIN_KEY=${ADMIN_KEY}
```

## Quick Reference

### Core Server Settings

| Variable | Default | Required | What it controls |
| --- | --- | --- | --- |
| `ADMIN_KEY` | none | Yes | Built-in admin authentication and the secret used to hash stored user API keys |
| `AI_PROVIDER` | `cursor` | No | Default AI provider when a generation request does not specify one |
| `AI_MODEL` | `gpt-5.4-xhigh-fast` | No | Default AI model when a generation request does not specify one |
| `AI_CLI_TIMEOUT` | `60` | No | Default timeout value passed to provider CLI calls |
| `DATA_DIR` | `/data` | No | Root directory for the SQLite database and generated documentation artifacts |
| `SECURE_COOKIES` | `true` | No | Whether the browser session cookie uses the `Secure` flag |

### Launcher And Development Settings

| Variable | Default | Used by | What it controls |
| --- | --- | --- | --- |
| `HOST` | `127.0.0.1` | `docsfy-server` | Backend bind host when you run the packaged server entrypoint directly |
| `PORT` | `8000` | `docsfy-server` | Backend bind port when you run the packaged server entrypoint directly |
| `DEBUG` | unset | `docsfy-server` | Enables Uvicorn reload when set to `true` |
| `DEV_MODE` | unset | `entrypoint.sh` | Starts Vite and FastAPI reload together inside the container |
| `API_TARGET` | `http://localhost:8000` | Vite dev server | Proxy target for `/api`, `/docs`, `/health`, and WebSocket traffic during frontend development |

## How `docsfy` Reads These Values

Most server settings come from `src/docsfy/config.py`:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admin_key: str = ""
    ai_provider: str = "cursor"
    ai_model: str = "gpt-5.4-xhigh-fast"
    ai_cli_timeout: int = Field(default=60, gt=0)
    data_dir: str = "/data"
    secure_cookies: bool = True  # Set to False for local HTTP dev
```

That means:

- Core server settings are loaded from `.env` or the process environment.
- Extra keys in `.env` do not break the settings loader because it uses `extra="ignore"`.
- `HOST`, `PORT`, `DEBUG`, `DEV_MODE`, and `API_TARGET` are separate. They are read directly by the launcher, the container entrypoint, or Vite instead of this settings model.

```mermaid
flowchart TD
    A["`.env` or process environment"] --> B["`Settings` in `src/docsfy/config.py`"]
    B --> C["Startup validates `ADMIN_KEY`"]
    B --> D["Generation defaults: `AI_PROVIDER`, `AI_MODEL`, `AI_CLI_TIMEOUT`"]
    B --> E["Storage root: `DATA_DIR`"]
    B --> F["Browser cookie security: `SECURE_COOKIES`"]

    G["Shell environment"] --> H["`docsfy-server` launcher"]
    H --> I["`HOST`, `PORT`, `DEBUG`"]

    J["Container environment"] --> K["`entrypoint.sh`"]
    K --> L["`DEV_MODE=true` starts Vite on `5173` and FastAPI reload on `8000`"]

    M["Frontend dev shell environment"] --> N["`frontend/vite.config.ts`"]
    N --> O["`API_TARGET` proxies `/api`, `/docs`, `/health`, and `/api/ws`"]
```

## `ADMIN_KEY`

`ADMIN_KEY` is the one setting you must provide before the server can start. `docsfy` checks it during application startup and exits if it is missing or too short:

```python
settings = get_settings()
if not settings.admin_key:
    logger.error("ADMIN_KEY environment variable is required")
    raise SystemExit(1)

if len(settings.admin_key) < 16:
    logger.error("ADMIN_KEY must be at least 16 characters long")
    raise SystemExit(1)
```

In practice, `ADMIN_KEY` is used for all of these:

- Browser login as the built-in `admin` user
- Bearer authentication for admin API requests
- `?token=` authentication on `/api/ws`
- The HMAC secret for stored user API keys

That last point matters because database-backed users depend on it too. In `src/docsfy/storage.py`, user API keys are hashed with `ADMIN_KEY`:

```python
secret = hmac_secret or os.getenv("ADMIN_KEY", "")
if not secret:
    msg = "ADMIN_KEY environment variable is required for key hashing"
    raise RuntimeError(msg)
return hmac.new(secret.encode(), key.encode(), hashlib.sha256).hexdigest()
```

> **Warning:** Rotating `ADMIN_KEY` invalidates existing database-backed user API keys. After you change it, those users will need new API keys.

> **Note:** The built-in admin username is always `admin`. The `/api/auth/rotate-key` endpoint does not rotate `ADMIN_KEY`; for that case the API explicitly tells you to change the environment variable itself.

## Default AI Settings: `AI_PROVIDER`, `AI_MODEL`, And `AI_CLI_TIMEOUT`

These are server-wide defaults for documentation generation. They are used when a generate request does not provide its own provider, model, or timeout.

The generate API resolves defaults this way in `src/docsfy/api/projects.py`:

```python
settings = get_settings()
ai_provider = gen_request.ai_provider or settings.ai_provider
ai_model = gen_request.ai_model or settings.ai_model

task = asyncio.create_task(
    _run_generation(
        repo_url=gen_request.repo_url,
        repo_path=gen_request.repo_path,
        project_name=project_name,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_cli_timeout=gen_request.ai_cli_timeout
        or settings.ai_cli_timeout,
```

The supported provider names in the current codebase are defined in `src/docsfy/models.py`:

```python
VALID_PROVIDERS = ("claude", "gemini", "cursor")
```

What each setting does:

- `AI_PROVIDER` sets the default provider for new generations.
- `AI_MODEL` sets the default model name for that provider.
- `AI_CLI_TIMEOUT` sets the default timeout value passed to provider CLI calls.
- `AI_CLI_TIMEOUT` must be greater than `0`, because the settings model uses `Field(default=60, gt=0)`.

A few practical details matter here:

- You can still override provider and model per request through the API or CLI.
- `docsfy` validates the provider name against `claude`, `gemini`, and `cursor`.
- The model is provider-specific; after defaults are resolved, `docsfy` only requires that it not be empty.
- When the selected provider is `cursor`, generation code adds `--trust` when invoking the CLI.

> **Tip:** Set `AI_PROVIDER` and `AI_MODEL` to the combination you use most often. That keeps routine runs simple, while still allowing one-off overrides.

> **Note:** `AI_CLI_TIMEOUT` affects the provider CLI calls made by the server. It does not change the `docsfy` CLI’s own HTTP client timeout, which is a separate hardcoded `30.0` in `src/docsfy/cli/client.py`.

## `DATA_DIR`

`DATA_DIR` controls where `docsfy` stores durable runtime data. By default, that is `/data`.

From `src/docsfy/storage.py`:

```python
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"
```

Project variants are then stored under owner, project, branch, provider, and model directories:

```python
return (
    PROJECTS_DIR
    / safe_owner
    / _validate_name(name)
    / branch
    / ai_provider
    / ai_model
)
```

In practice, the on-disk layout looks like this:

- `DATA_DIR/docsfy.db`
  Stores users, sessions, projects, access grants, and generation metadata.
- `DATA_DIR/projects/<owner>/<project>/<branch>/<provider>/<model>/plan.json`
  Stores the current documentation plan.
- `DATA_DIR/projects/<owner>/<project>/<branch>/<provider>/<model>/cache/pages/*.md`
  Stores cached page markdown used for incremental regeneration.
- `DATA_DIR/projects/<owner>/<project>/<branch>/<provider>/<model>/site/`
  Stores the rendered static site that `docsfy` serves and downloads.

The included Compose setup is wired to the default path:

```yaml
volumes:
  - ./data:/data
env_file:
  - .env
```

So with the default configuration, your host machine ends up with:

- `./data/docsfy.db`
- `./data/projects/`

> **Warning:** If you change `DATA_DIR`, also change the container mount target. The provided Compose file assumes `DATA_DIR=/data` together with `./data:/data`.

> **Tip:** The mounted directory must be writable by the runtime user. The provided image is already prepared for `/data`, so keeping the default is the simplest container deployment.

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

This tells you a lot about the browser session behavior:

- The cookie name is `docsfy_session`.
- It is always `HttpOnly`.
- It is always `SameSite=Strict`.
- Its lifetime is fixed in code by `SESSION_TTL_SECONDS = 28800`, which is 8 hours.
- `SECURE_COOKIES` controls only the `Secure` flag.

The test suite also verifies that the cookie stores an opaque session token, not the raw API key.

This setting matters for more than just page loads. Browser-side API requests use same-origin credentials, and browser WebSocket auth can also use the same `docsfy_session` cookie.

> **Warning:** If you are running over plain local HTTP, leave `SECURE_COOKIES=false` during development. With `true`, the browser will not send the secure cookie back over `http://`, so login can appear not to stick.

> **Tip:** Keep `SECURE_COOKIES=true` anywhere the app is served over HTTPS.

> **Note:** The session lifetime itself is not configurable by environment variable in the current codebase. Only the `Secure` flag is.

## `HOST`, `PORT`, And `DEBUG`

These three variables are read directly by the packaged backend launcher in `src/docsfy/main.py`:

```python
def run() -> None:
    import uvicorn

    reload = os.getenv("DEBUG", "").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
```

They only affect runs that use the `docsfy-server` entrypoint.

What they do:

- `HOST` changes the bind address and defaults to `127.0.0.1`.
- `PORT` changes the bind port and defaults to `8000`.
- `DEBUG=true` enables Uvicorn reload mode.

A subtle but important detail: these are not part of the `Settings` model above. They are read directly from the process environment.

> **Tip:** If you launch `docsfy-server` directly, set `HOST`, `PORT`, and `DEBUG` in the shell or service manager that starts the process.

> **Note:** The provided container entrypoint does not use these variables. It starts Uvicorn explicitly on `0.0.0.0:8000`.

## `DEV_MODE`

`DEV_MODE` is handled by `entrypoint.sh`, so it is a container startup switch rather than a normal app setting.

From `entrypoint.sh`:

```bash
if [ "$DEV_MODE" = "true" ]; then
    echo "DEV_MODE enabled - installing frontend dependencies..."
    cd /app/frontend || exit 1
    npm ci
    echo "Starting Vite dev server on port 5173..."
    npm run dev &
    VITE_PID=$!
    trap 'kill $VITE_PID 2>/dev/null; wait $VITE_PID 2>/dev/null' SIGTERM SIGINT
    cd /app
    echo "Starting FastAPI with hot reload on port 8000..."
    uv run --no-sync uvicorn docsfy.main:app \
        --host 0.0.0.0 --port 8000 \
        --reload --reload-dir /app/src
else
    exec uv run --no-sync uvicorn docsfy.main:app \
        --host 0.0.0.0 --port 8000
fi
```

With `DEV_MODE=true` inside the container:

- The entrypoint runs `npm ci`
- Vite starts on port `5173`
- FastAPI still runs on port `8000`
- The backend uses `--reload`

Without `DEV_MODE`:

- Only FastAPI starts
- The container serves the already-built frontend on port `8000`

The sample Compose file already shows the related toggles:

```yaml
ports:
  - "8000:8000"
  # Uncomment for development (DEV_MODE=true)
  # - "5173:5173"
volumes:
  - ./data:/data
  # Uncomment for development (hot reload)
  # - ./frontend:/app/frontend
environment:
  - ADMIN_KEY=${ADMIN_KEY}
  # Uncomment for development
  # - DEV_MODE=true
```

> **Warning:** `DEV_MODE` is a development convenience, not a production setting.

> **Note:** If you run `docsfy-server` directly on your host, `DEV_MODE` does nothing because `entrypoint.sh` is not involved.

## `API_TARGET`

`API_TARGET` is only used when you run the frontend dev server with Vite.

From `frontend/vite.config.ts`:

```ts
const API_TARGET = process.env.API_TARGET || 'http://localhost:8000'

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        ws: true,
      },
      '/docs': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/health': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
```

This is what makes the split development workflow work cleanly:

- Open the browser at `http://localhost:5173`
- Let Vite proxy `/api`, `/docs`, and `/health` to the backend
- Let the `/api` proxy carry WebSocket traffic too because `ws: true` is enabled

If your backend is not running on `http://localhost:8000`, this is the variable to change for frontend development.

> **Tip:** `API_TARGET` is a frontend-development variable only. It does not affect the built frontend served by FastAPI and it does not change the backend’s own bind address.

## What Most Deployments Actually Need

For a normal deployment, the settings that matter most are:

- `ADMIN_KEY`
- `AI_PROVIDER`
- `AI_MODEL`
- `AI_CLI_TIMEOUT`
- `DATA_DIR`
- `SECURE_COOKIES`

For local frontend development, add:

- `DEV_MODE` if you want the container to run Vite for you
- `API_TARGET` if Vite should proxy to a backend other than `http://localhost:8000`

For direct host-local backend launches with `docsfy-server`, add:

- `HOST`
- `PORT`
- `DEBUG`

If you set only one thing first, set `ADMIN_KEY`. That is the one environment variable the server cannot run without.


## Related Pages

- [Installation](installation.html)
- [Local Development](local-development.html)
- [Deployment and Runtime](deployment-and-runtime.html)
- [Authentication and Roles](authentication-and-roles.html)
- [AI Provider Setup](ai-provider-setup.html)