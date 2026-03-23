# Docker and Compose Quickstart

`docsfy` includes a ready-to-use `Dockerfile` and `docker-compose.yaml`. The provided setup builds the app from this repository, stores runtime data in `./data`, and publishes the web UI on `http://localhost:8000`.

## Quick start

1. Create a `.env` file by copying `.env.example`.
2. Set `ADMIN_KEY` to a strong value with at least 16 characters.
3. If you are running locally over plain `http://localhost:8000`, set `SECURE_COOKIES=false`.
4. Start the app from the repository root:

```bash
docker compose up --build
```

5. Open `http://localhost:8000`.
6. Sign in with username `admin` and the same value you set for `ADMIN_KEY`.

The shipped `.env.example` looks like this:

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

> **Warning:** `ADMIN_KEY` is required. The app exits at startup if it is missing or shorter than 16 characters.

> **Warning:** For a normal local browser-based quickstart, change `SECURE_COOKIES` to `false`. With the default `true`, the login cookie is marked secure and will not work correctly on plain `http://localhost:8000`.

> **Note:** `AI_PROVIDER` and `AI_MODEL` set the defaults for new generations. The supported providers in the codebase are `claude`, `gemini`, and `cursor`.

## What the provided Compose setup does

These are the key parts of `docker-compose.yaml`:

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

In practice, that means:

- Docker Compose builds the image locally from the repository's `Dockerfile`.
- Port `8000` is published by default.
- Your local `./data` directory is mounted into `/data` inside the container.
- The container reads environment settings from `.env`.
- The service restarts automatically unless you stop it manually.

> **Tip:** The first build can take a while. The Dockerfile builds the frontend, installs Python dependencies, and installs the provider CLIs during the image build.

## Persistent data

The application stores its database and project data under `DATA_DIR`, which defaults to `/data`:

```python
DB_PATH = Path(os.getenv("DATA_DIR", "/data")) / "docsfy.db"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
PROJECTS_DIR = DATA_DIR / "projects"
```

Because Compose mounts `./data:/data`, the container's storage shows up on your host as:

- `./data/docsfy.db` for the SQLite database
- `./data/projects/` for generated docs and project artifacts

Generated site output is stored under this layout:

`./data/projects/<owner>/<project>/<branch>/<provider>/<model>/site`

> **Tip:** Recreating the container does not erase your database or generated documentation as long as `./data` stays in place.

> **Warning:** If you change `DATA_DIR` in `.env`, also change the container-side mount target in `docker-compose.yaml`. The provided setup assumes `DATA_DIR=/data` together with `./data:/data`.

## Exposed ports and health check

The Dockerfile exposes the main app port and the optional frontend dev port:

```dockerfile
EXPOSE 8000
# Vite dev server (DEV_MODE only)
EXPOSE 5173

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
```

What this means:

- `8000` is the main application port. In the default Compose setup, this is the port you use.
- `5173` is only relevant when you enable frontend development mode.
- Container health is checked with `GET /health` on port `8000`.

> **Note:** The default setup serves the built frontend from the FastAPI app on port `8000`. You only need port `5173` when you want Vite hot reloading.

## Development mode

The repository also includes a built-in development mode. When `DEV_MODE=true`, `entrypoint.sh` changes how the container starts:

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

To use this mode:

- Set `DEV_MODE=true` in `.env`.
- Uncomment `# - "5173:5173"` in `docker-compose.yaml`.
- Uncomment `# - ./frontend:/app/frontend` in `docker-compose.yaml` if you want frontend hot reload from your local checkout.

When dev mode is enabled, the Vite server runs on `5173` and the backend still runs on `8000`. The frontend dev server proxies `/api`, `/docs`, and `/health` to `http://localhost:8000`.

> **Tip:** Leave `DEV_MODE` off unless you are actively editing the frontend. For normal local usage, the default `8000` setup is simpler.

## Common gotchas

- The container exits immediately: check that `ADMIN_KEY` is set and is at least 16 characters long.
- You can log in, but the UI behaves like you are not signed in: set `SECURE_COOKIES=false` for plain local HTTP.
- Data is not persisting where you expect: confirm that `docker-compose.yaml` still mounts `./data:/data` and that `DATA_DIR` is still `/data`.
