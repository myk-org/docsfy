# Deployment and Runtime

docsfy is easiest to operate as a single container with a persistent `/data` volume. The provided image already bundles the FastAPI backend, the built React frontend, Git, and the AI provider CLIs it expects at runtime.

For a production deployment, plan for:
- one writable data volume, usually mounted at `/data`
- one strong `ADMIN_KEY`
- outbound access to your Git host and the AI services used by your chosen provider CLI
- HTTPS plus WebSocket support on `/api/ws`
- a single app instance unless you add your own distributed coordination

## Minimal Container Deployment

The repository already includes a working `docker-compose.yaml`:

```yaml
services:
  docsfy:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
      # Uncomment for development (DEV_MODE=true)
      # - "5173:5173"
    volumes:
      - ./data:/data
      # Uncomment for development (hot reload)
      # - ./frontend:/app/frontend
    env_file:
      - .env
    environment:
      # WARNING: ADMIN_KEY must be set in your .env file or shell environment.
      # An empty ADMIN_KEY will cause the application to reject all admin requests.
      - ADMIN_KEY=${ADMIN_KEY}
      # Uncomment for development
      # - DEV_MODE=true
    restart: unless-stopped
```

In production, the most important part is the `./data:/data` mount. Without persistent storage, user accounts, sessions, project metadata, and generated documentation disappear when the container is replaced.

> **Note:** This repository ships a `Dockerfile` and `docker-compose.yaml`, but it does not include in-repo GitHub Actions workflows, Helm charts, or Kubernetes manifests. If you deploy to another platform, you will supply that platform-specific automation yourself.

## Entrypoint Modes

The container always starts through `entrypoint.sh`, and that script has two modes:

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
else
    exec uv run --no-sync uvicorn docsfy.main:app \
        --host 0.0.0.0 --port 8000
fi
```

### Production mode

With `DEV_MODE` unset, the container runs one Uvicorn process on `0.0.0.0:8000`. This is the normal deployment mode.

### Development mode

With `DEV_MODE=true`, the container starts:
- FastAPI with hot reload on port `8000`
- the Vite frontend dev server on port `5173`

The frontend dev server is configured for container-friendly access and proxies API traffic back to FastAPI:

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

Use port `8000` in production. Use port `5173` only when you intentionally want the development workflow.

If you run docsfy outside the container, the packaged `docsfy-server` entrypoint calls `docsfy.main:run` and uses:
- `HOST`, default `127.0.0.1`
- `PORT`, default `8000`
- `DEBUG=true` to enable reload

That is separate from the container entrypoint. The container always binds `0.0.0.0:8000` itself.

## Required Runtime Configuration

The server reads its settings from environment variables, with built-in `.env` support. The example in `.env.example` is:

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

The production-critical settings are:

- `ADMIN_KEY`
  Required. The application exits at startup if it is missing or shorter than 16 characters.
- `DATA_DIR`
  Defaults to `/data`. This is where docsfy keeps its SQLite database and generated artifacts.
- `SECURE_COOKIES`
  Defaults to `true`, which is what you want behind HTTPS.
- `AI_PROVIDER`, `AI_MODEL`, `AI_CLI_TIMEOUT`
  Set the server defaults for generation requests when the caller does not provide them explicitly.
- `LOG_LEVEL`
  Controls backend log verbosity.

> **Warning:** `ADMIN_KEY` is more than just the admin login secret. docsfy also uses it as the HMAC secret for stored user API keys. Rotating `ADMIN_KEY` invalidates existing user API keys, so users will need new keys after the change.

> **Tip:** Leave `SECURE_COOKIES=true` in production. Only set it to `false` for plain-HTTP local development.

## What The Running Service Does

A single FastAPI application serves all of these:

- the React SPA at `/`, `/login`, and other client-side routes
- the JSON API under `/api/*`
- generated documentation under `/docs/*`
- the public health endpoint at `/health`
- the WebSocket endpoint at `/api/ws`

A few practical details matter in production:

- The SPA shell itself is served without server-side auth, and the frontend handles login state client-side.
- API routes and generated docs are authenticated.
- Unauthenticated browser requests for `/docs/...` are redirected to `/login`.
- Unauthenticated API requests return `401`.
- Variant-specific docs live at `/docs/<project>/<branch>/<provider>/<model>/...`.
- `/docs/<project>/...` resolves to the latest ready variant the current user is allowed to access.

The frontend uses root-relative URLs such as `/api`, `/docs`, `/assets`, `/health`, and `/api/ws`. The simplest deployment is therefore one host at the site root.

> **Tip:** If you put docsfy behind a reverse proxy or ingress, make sure `/api/ws` supports WebSocket upgrades. The browser uses WebSockets for live generation updates and only falls back to polling after reconnect attempts fail.

## Persistent Storage

docsfy stores its durable state in a SQLite database plus per-project directories under `DATA_DIR`:

```python
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"

def get_project_dir(
    name: str,
    ai_provider: str = "",
    ai_model: str = "",
    owner: str = "",
    branch: str = DEFAULT_BRANCH,
) -> Path:
    safe_owner = _validate_owner(owner)
    return (
        PROJECTS_DIR
        / safe_owner
        / _validate_name(name)
        / branch
        / ai_provider
        / ai_model
    )
```

In practice, that means you should expect this layout:

- `DATA_DIR/docsfy.db`
  Stores users, sessions, projects, access grants, and generation metadata.
- `DATA_DIR/projects/<owner>/<project>/<branch>/<provider>/<model>/plan.json`
  Stores the current documentation plan.
- `DATA_DIR/projects/<owner>/<project>/<branch>/<provider>/<model>/cache/pages/*.md`
  Stores cached page markdown used for incremental regeneration.
- `DATA_DIR/projects/<owner>/<project>/<branch>/<provider>/<model>/site/`
  Stores the rendered static site that docsfy serves and downloads.

The rendered `site/` directory includes the published HTML plus supporting files such as:
- `index.html`
- one `*.html` file per page
- one `*.md` file per page
- `search-index.json`
- `llms.txt`
- `llms-full.txt`
- `assets/`
- `.nojekyll`

Remote Git checkouts are not persistent. docsfy clones remote repositories into a temporary directory, generates the docs, and then deletes that clone. Only the SQLite data, cached markdown, plan JSON, and rendered site stay on disk.

Downloads are also temporary. When someone requests a download, docsfy creates a `tar.gz` archive from the rendered `site/` directory, streams it to the client, and removes the temporary archive afterward.

## Runtime Behavior

### Generation lifecycle

A generation request becomes an in-process background task. The normal flow is:

1. create or update the project row with status `generating`
2. check that the selected AI CLI is available
3. clone the remote repo or open the local repo path
4. run `planning` or `incremental_planning`
5. generate page markdown into the cache
6. render the static site into `site/`
7. mark the variant `ready`

At runtime, you will see a mix of terminal statuses and current stages:

- terminal statuses: `ready`, `error`, `aborted`
- in-progress stages: `cloning`, `planning`, `incremental_planning`, `generating_pages`, `rendering`, `up_to_date`

docsfy also tries to avoid unnecessary work:

- remote repos are shallow-cloned first
- old history is fetched only if needed for diff-based regeneration
- cached page markdown is reused when incremental generation is possible
- `force=true` clears cached page output and forces a full regeneration
- provider/model variants can sometimes reuse existing artifacts for the same repo and branch

### Local repositories vs remote repositories

The generate API supports two source types:

- `repo_url` for a normal remote Git repository
- `repo_path` for an existing local Git checkout

`repo_path` is intentionally restricted. It must be an absolute path, it must contain a `.git` directory, and only admins can use it. For most hosted deployments, `repo_url` is the normal choice.

### Live updates and sessions

The browser uses `/api/ws` for live project updates. The server sends a heartbeat ping every 30 seconds, waits up to 10 seconds for a pong, and closes the connection after repeated missed pongs.

The frontend also has a fallback path: if WebSocket reconnect attempts keep failing, it switches to polling `/api/projects`.

Browser login uses a `docsfy_session` cookie with these runtime characteristics:

- `HttpOnly`
- `SameSite=Strict`
- `Secure` when `SECURE_COOKIES=true`
- 8-hour lifetime

The CLI does not use browser sessions. It authenticates with Bearer tokens and can hit the same server endpoints directly.

> **Note:** Expired browser sessions stop working immediately, but expired session rows are only cleaned from the database during application startup. Long-running instances may accumulate old session rows until the next restart.

> **Warning:** Generation jobs are not externalized to a queue or worker service. They live in the app process in an in-memory task registry. If the process restarts, active generations are lost. On the next startup, docsfy marks any leftover `generating` rows as `error` with the message `Server restarted during generation`.

> **Warning:** Out of the box, docsfy is a single-instance deployment model. Active generation tracking and WebSocket connection state are both in memory, and the repository only ships SQLite storage. If you scale beyond one app instance, you will need your own strategy for shared job coordination, routing, and storage semantics.

## Health Checks

docsfy exposes a very small health endpoint:

```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

The container image uses that endpoint directly:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

This is a good fit for container liveness or readiness probes because it tells you whether the web process is up and serving requests.

If you configure the CLI, `docsfy health` checks the same endpoint.

> **Note:** `/health` is intentionally lightweight. It does not verify SQLite writes, outbound Git access, or AI provider CLI availability. Treat it as a process health check, not a full dependency check.

## Non-Root Execution

The container is built to run as a non-root user by default:

```dockerfile
RUN useradd --create-home --shell /bin/bash -g 0 appuser \
  && mkdir -p /data \
  && chown appuser:0 /data \
  && chmod -R g+w /data

# Switch to non-root user for runtime
USER appuser

# Ensure CLIs are in PATH
ENV PATH="/home/appuser/.local/bin:/home/appuser/.npm-global/bin:${PATH}"
# Set HOME for OpenShift compatibility (random UID has no passwd entry)
ENV HOME="/home/appuser"
```

That gives you a few useful guarantees:

- the normal runtime user is `appuser`, not `root`
- `/data` is writable without running the container as root
- the image is prepared for OpenShift-style arbitrary UIDs in group `0`
- the CLI tools installed into the home directory remain reachable through `PATH`

The Dockerfile also makes `/app` and the `appuser` home directory group-writable for OpenShift compatibility, so platforms that override the UID still have a better chance of working without image changes.

> **Tip:** Whatever platform you use, make sure the mounted `DATA_DIR` is writable by the UID and GID that will actually run the process. If the volume is read-only or owned by the wrong user/group, docsfy will not be able to initialize its database or write generated sites.

## Container Expectations

The provided runtime image is intentionally not a minimal Python-only image. It includes the tools docsfy needs while it is running:

- `git` for cloning and diffing repositories
- `bash`, `curl`, `nodejs`, and `npm`
- provider CLIs installed at image build time:
  - Claude Code CLI
  - Cursor CLI
  - Gemini CLI

That has two practical consequences:

- the selected provider CLI must still be available on `PATH` at runtime
- the container needs outbound network access to both your Git host and the provider services used by that CLI

If you build your own image or run docsfy outside the provided container, keep these requirements in place:

- install `git`
- install the AI provider CLIs you plan to support
- make sure the frontend is already built into `frontend/dist` unless you are intentionally running `DEV_MODE=true`
- keep a writable `DATA_DIR`
- keep WebSocket support available at `/api/ws`

If a required AI CLI is missing, docsfy does not silently degrade. The generation request fails and the variant is marked `error`.
