# Deploying with Docker

Run docsfy as a self-hosted documentation service so your team can generate and browse AI-powered docs from a shared server, with data that survives container restarts.

## Prerequisites

- Docker Engine 20.10+ and Docker Compose v2
- An `ADMIN_KEY` password (minimum 16 characters) — this is your admin login credential
- At least one AI provider CLI credential available to the container (Cursor is pre-installed in the image)

## Quick Example

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
cp .env.example .env
```

Edit `.env` and set your admin password:

```dotenv
ADMIN_KEY=change-this-to-a-16-plus-character-password
```

```bash
docker compose up -d
```

Open `http://localhost:8000/login` and sign in with username `admin` and your `ADMIN_KEY` value.

## Step-by-Step

### 1. Create the environment file

```bash
cp .env.example .env
```

Edit `.env` with your production values:

```dotenv
ADMIN_KEY=change-this-to-a-16-plus-character-password
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
LOG_LEVEL=INFO
DATA_DIR=/data
SECURE_COOKIES=true
```

> **Warning:** `ADMIN_KEY` is required and must be at least 16 characters. The server will refuse to start without it.


> **Note:** Set `SECURE_COOKIES=false` only when running over plain HTTP (e.g., `http://localhost` for local testing). For any HTTPS deployment, keep it `true`.

See [Configuration Reference](configuration-reference.html) for the full list of environment variables.

### 2. Review the Compose file

The project ships a ready-to-use `docker-compose.yaml`:

```yaml
services:
  docsfy:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    env_file:
      - .env
    environment:
      - ADMIN_KEY=${ADMIN_KEY}
    restart: unless-stopped
```

Key points:

- **Port 8000** — the web UI, API, and generated doc sites are all served here.
- **`./data:/data`** — maps the host `data/` directory into the container at `/data`, where the database and generated documentation are stored.
- **`restart: unless-stopped`** — the container restarts automatically after crashes or host reboots (unless you explicitly stop it).

### 3. Build and start

```bash
docker compose up -d --build
```

The multi-stage build compiles the React frontend, the Pi SDK sidecar, and the Python backend into a single image. The first build takes a few minutes; subsequent builds use Docker layer caching.

### 4. Verify the deployment

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok"}
```

The built-in health check also verifies the AI sidecar is running. Check container health status with:

```bash
docker compose ps
```

The `STATUS` column should show `healthy` once both the server and sidecar pass their checks (this can take up to 30 seconds on first start).

### 5. Sign in and start generating

Open `http://localhost:8000/login` in your browser. Sign in with:

- **Username:** `admin`
- **Password:** your `ADMIN_KEY` value

You're now ready to generate documentation. See [Generating Documentation](generating-docs.html) for next steps.

## Persistent Storage

All docsfy state lives under a single directory (`/data` inside the container). The volume mount `./data:/data` ensures this data persists across container restarts, rebuilds, and upgrades.

The data directory contains:

| Path | Contents |
|---|---|
| `/data/docsfy.db` | SQLite database — users, projects, access control, sessions |
| `/data/projects/` | Generated documentation sites, page caches, and build artifacts |

> **Tip:** Back up the `data/` directory to preserve your entire docsfy state — database and all generated docs — in a single copy.

### Using a named Docker volume

If you prefer a named volume instead of a bind mount, replace the volumes section:

```yaml
services:
  docsfy:
    volumes:
      - docsfy-data:/data

volumes:
  docsfy-data:
```

## Environment Variable Reference

| Variable | Default | Description |
|---|---|---|
| `ADMIN_KEY` | *(required)* | Admin password (minimum 16 characters) |
| `AI_PROVIDER` | `cursor` | Default AI provider (`claude`, `gemini`, or `cursor`) |
| `AI_MODEL` | `gpt-5.4-xhigh-fast` | Default AI model |
| `AI_CLI_TIMEOUT` | `60` | Timeout in seconds for each AI CLI call |
| `MAX_CONCURRENT_PAGES` | `10` | Maximum parallel AI calls during generation |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATA_DIR` | `/data` | Path inside the container for database and docs |
| `SECURE_COOKIES` | `true` | Set to `false` for HTTP-only deployments |
| `PORT` | `8000` | Server listen port |
| `SIDECAR_PORT` | `9100` | Internal AI sidecar port (rarely needs changing) |

See [Configuration Reference](configuration-reference.html) for details on every setting, and [Configuring AI Providers](configuring-ai-providers.html) for provider-specific setup.

## Advanced Usage

### Changing the exposed port

To run docsfy on a different host port, change the port mapping in `docker-compose.yaml`:

```yaml
ports:
  - "3000:8000"
```

Then access the service at `http://localhost:3000`. The internal `PORT` variable should stay at `8000` unless you have a specific reason to change it.

### Placing behind a reverse proxy

For production HTTPS deployments, put a reverse proxy (nginx, Caddy, Traefik) in front of docsfy. A minimal nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name docs.example.com;

    ssl_certificate     /etc/ssl/certs/docs.example.com.pem;
    ssl_certificate_key /etc/ssl/private/docs.example.com.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support for real-time generation updates
    location /api/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

> **Note:** Keep `SECURE_COOKIES=true` (the default) when serving over HTTPS. The WebSocket endpoint at `/api/ws` requires the `Upgrade` and `Connection` headers to be forwarded.

### Tuning generation performance

For servers with more CPU and memory, increase parallel AI calls:

```dotenv
MAX_CONCURRENT_PAGES=20
AI_CLI_TIMEOUT=120
```

For constrained environments, reduce concurrency:

```dotenv
MAX_CONCURRENT_PAGES=4
```

### Development mode

For local development with hot reload, uncomment the dev options in `docker-compose.yaml`:

```yaml
services:
  docsfy:
    ports:
      - "8000:8000"
      - "5173:5173"
    volumes:
      - ./data:/data
      - ./frontend:/app/frontend
    environment:
      - ADMIN_KEY=${ADMIN_KEY}
      - DEV_MODE=true
```

This starts the Vite dev server on port 5173 alongside the FastAPI backend with auto-reload. Edit frontend files on your host and see changes immediately.

### Upgrading docsfy

```bash
git pull
docker compose up -d --build
```

Your data in `./data` is preserved across rebuilds. The database schema automatically migrates on startup when needed.

> **Tip:** Run `docker compose down` before upgrading if you want a clean restart, but this is not required — `up --build` replaces the running container in place.

## Troubleshooting

- **Container exits immediately** — Check logs with `docker compose logs docsfy`. The most common cause is a missing or too-short `ADMIN_KEY`.

- **Health check fails** — The health check probes both the server (`/health` on port 8000) and the AI sidecar (port 9100). Run `docker compose logs docsfy | grep sidecar` to check if the sidecar started successfully. It can take up to 30 seconds on first boot.

- **Browser login redirects back to `/login`** — If you're accessing over plain HTTP, set `SECURE_COOKIES=false` in `.env` and restart the container.

- **Permission denied on `./data`** — The container runs as a non-root user (UID 1000, GID 0). Ensure the host `data/` directory is writable:
  ```bash
  mkdir -p data && chmod 775 data
  ```

- **Generation fails with provider errors** — Verify your AI provider is configured correctly. See [Configuring AI Providers](configuring-ai-providers.html) for provider-specific requirements.

- **Out of disk space** — Generated documentation and page caches accumulate in `./data/projects/`. Delete old projects through the web dashboard or API to free space. See [Managing Projects and Variants](managing-projects.html) for cleanup options.

## Related Pages

- [Getting Started with docsfy](quickstart.html)
- [Configuration Reference](configuration-reference.html)
- [Configuring AI Providers](configuring-ai-providers.html)
- [Managing Projects and Variants](managing-projects.html)
- [Generating Documentation](generating-docs.html)