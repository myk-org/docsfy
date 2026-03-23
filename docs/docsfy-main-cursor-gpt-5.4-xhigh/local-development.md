# Local Development

`docsfy` has two useful local workflows:

| Workflow | Best for | Open in your browser |
|---|---|---|
| Split development | React UI work, fast feedback, hot reload | `http://localhost:5173` |
| Built-SPA check | Production-like checks, backend serving the UI itself | `http://localhost:8000` |

In split development, FastAPI runs on port `8000` and Vite runs on port `5173`. You use the Vite URL in the browser, and Vite proxies API, docs, health, and WebSocket traffic back to FastAPI.

In built-SPA mode, FastAPI serves the built frontend from `frontend/dist`, so you only use port `8000`.

## Prerequisites

- Python `3.12+`. `pyproject.toml` sets `requires-python = ">=3.12"`.
- `uv` for Python commands.
- Node and npm for the frontend. The Docker image builds the SPA with Node `20`, so matching that locally is the safest option.
- A writable data directory for the database and generated docs.

## Where settings go

Not every setting is loaded the same way, which matters for local development.

- Put app settings such as `ADMIN_KEY`, `DATA_DIR`, `SECURE_COOKIES`, `AI_PROVIDER`, and `AI_MODEL` in the repo root `.env`.
- Pass backend launcher settings such as `DEBUG`, `HOST`, and `PORT` in the shell when starting `docsfy-server`.
- Pass `API_TARGET` in the shell when starting the Vite dev server.
- `DEV_MODE` is handled by `entrypoint.sh`, so it matters for container startup, not for a host-local `uv run docsfy-server`.

The app settings loader in `src/docsfy/config.py` reads `.env` automatically:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

The backend launcher in `src/docsfy/main.py` reads `DEBUG`, `HOST`, and `PORT` directly from the process environment:

```python
def run() -> None:
    import uvicorn

    reload = os.getenv("DEBUG", "").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("docsfy.main:app", host=host, port=port, reload=reload)
```

## Configure `.env`

Start from the values in `.env.example`:

```env
# Required: Admin password (minimum 16 characters)
ADMIN_KEY=

# AI provider and model defaults
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

For host-local development, the most important changes are:

- Set `ADMIN_KEY` to a real value with at least 16 characters.
- Change `SECURE_COOKIES=false` if you are using plain `http://localhost`.
- Consider changing `DATA_DIR` to something writable and local to the repo, such as `./data`, instead of the container-oriented default `/data`.

> **Warning:** With `SECURE_COOKIES=true`, browser login over plain local HTTP will not persist because the session cookie is marked `secure`.

> **Note:** The login screen expects username `admin` and the `ADMIN_KEY` value from your environment.

## Run the backend locally

From the repo root, start the backend with `docsfy-server`:

```bash
DEBUG=true uv run docsfy-server
```

That gives you:

- FastAPI on `127.0.0.1:8000` by default
- automatic reload when `DEBUG=true`
- the `/health` endpoint at `http://localhost:8000/health`

If you need the backend to listen on a different interface or port, pass `HOST` and `PORT` in the shell when you start it.

> **Tip:** `DEBUG` is not read from `.env` by `docsfy-server`. Set it in the shell when you launch the backend.

## Run the frontend locally

The frontend scripts in `frontend/package.json` are:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "test": "vitest run"
}
```

Start the frontend from `frontend/`:

```bash
cd frontend
npm ci
npm run dev
```

Then open `http://localhost:5173`.

This is the best workflow for day-to-day UI development because Vite handles hot reload and the browser stays on the frontend dev server.

## How the Vite proxy changes the workflow

When Vite is running, the browser still uses paths like `/api/...`, `/docs/...`, and `/api/ws`. The difference is that Vite forwards those requests to the backend for you.

In `frontend/vite.config.ts`:

```ts
const API_TARGET = process.env.API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
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

The frontend code is written around same-origin browser requests:

```ts
const response = await fetch(`${path}`, config)
```

And the WebSocket client connects back to the current browser host:

```ts
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const url = `${protocol}//${window.location.host}/api/ws`
this.ws = new WebSocket(url)
```

In practice, that means:

- Use `http://localhost:5173` in the browser while Vite is running.
- API requests still reach FastAPI on port `8000` through the proxy.
- WebSocket updates still work in local development because the `/api` proxy enables `ws: true`.
- Generated docs under `/docs/...` still open correctly because Vite also proxies `/docs`.

> **Tip:** If your backend is not running on `http://localhost:8000`, set `API_TARGET` in the shell before starting `npm run dev`.

## When to build the SPA

You only need `npm run build` when FastAPI itself should serve the frontend from `frontend/dist`.

That includes:

- checking the backend-served UI on port `8000`
- running without Vite
- building the production container image

FastAPI serves the built SPA from `frontend/dist` in `src/docsfy/main.py`:

```python
_frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

_assets_dir = _frontend_dist / "assets"
if _assets_dir.exists():
    app.mount(
        "/assets", StaticFiles(directory=str(_assets_dir)), name="frontend-assets"
    )

@app.get("/{path:path}")
async def spa_catch_all(path: str) -> FileResponse:
    if path.startswith(("api/", "docs/")) or path in ("api", "docs"):
        raise HTTPException(status_code=404, detail="Not found")
    index = _frontend_dist / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(
        status_code=404,
        detail="Frontend not built. Run: cd frontend && npm run build",
    )
```

Build it with:

```bash
cd frontend
npm run build
```

After that, `uv run docsfy-server` can serve the app directly on port `8000`.

> **Note:** You do not need to build the SPA for normal React development on port `5173`. `npm run dev` is enough.

The Docker build already does this for you. In `Dockerfile`:

```dockerfile
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

COPY --chown=appuser:0 --from=frontend-builder /app/frontend/dist /app/frontend/dist
```

So a normal non-dev container run already has a built `frontend/dist`.

## What `DEV_MODE` does

`DEV_MODE` is handled by `entrypoint.sh`. It changes how the container starts:

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

- Vite starts on port `5173`
- FastAPI starts on port `8000`
- the backend uses `--reload`
- you should browse to `http://localhost:5173`

Without `DEV_MODE`:

- only FastAPI starts
- the container expects a built `frontend/dist`
- you browse to `http://localhost:8000`

> **Warning:** If you are running the app directly on your host, `DEV_MODE=true` does not start Vite for you. Start the backend and frontend as separate processes instead.

## Using `DEV_MODE` with `docker-compose`

The sample `docker-compose.yaml` already shows the pieces needed for container-based development:

```yaml
services:
  docsfy:
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
      - ADMIN_KEY=${ADMIN_KEY}
      # Uncomment for development
      # - DEV_MODE=true
```

For container-based frontend development:

1. Enable `DEV_MODE=true`.
2. Expose port `5173`.
3. Bind-mount `./frontend:/app/frontend`.
4. Open `http://localhost:5173`.

> **Warning:** The sample compose file only comments in a frontend bind mount. `entrypoint.sh` enables backend reload with `--reload --reload-dir /app/src`, but host-side Python edits will only hot-reload if the container can also see updated `src/` files.

> **Tip:** If you plan to change backend Python code often, host-local development is the simpler workflow unless you also add a backend source bind mount to your container setup.

## Quick reference

- React/UI work: run the backend on `8000`, run Vite on `5173`, and browse to `http://localhost:5173`.
- Backend-served UI check: build the SPA with `npm run build`, then browse to `http://localhost:8000`.
- `DEV_MODE` is for the container entrypoint workflow.
- The Vite proxy is what makes `/api`, `/docs`, `/health`, and `/api/ws` work from `http://localhost:5173` without extra CORS setup.
