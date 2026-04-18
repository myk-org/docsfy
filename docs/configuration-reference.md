# Configuration Reference

Server runtime settings are loaded from environment variables. CLI profiles are stored in `~/.config/docsfy/config.toml`.

## Admin and Server Settings
### Server environment variables
Settings loaded during application startup and request handling.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `ADMIN_KEY` | string | `""` | Required built-in admin secret. The built-in admin username is `admin`. Startup fails if this value is empty or shorter than 16 characters. |
| `AI_PROVIDER` | string | `cursor` | Default provider used when a generation request omits `ai_provider`. Accepted values: `claude`, `gemini`, `cursor`. |
| `AI_MODEL` | string | `gpt-5.4-xhigh-fast` | Default model used when a generation request omits `ai_model`. |
| `AI_CLI_TIMEOUT` | integer | `60` | Positive timeout value passed to AI CLI calls when a generation request omits `ai_cli_timeout`. |
| `MAX_CONCURRENT_PAGES` | integer | `10` | Maximum parallel AI CLI calls during page generation and validation. Must be greater than `0`. |
| `DATA_DIR` | path | `/data` | Base directory for `docsfy.db` and generated project artifacts. |
| `SECURE_COOKIES` | boolean | `true` | Controls the `Secure` flag on the `docsfy_session` cookie. |

```dotenv
ADMIN_KEY=<ADMIN_KEY>
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
MAX_CONCURRENT_PAGES=10
DATA_DIR=/data
SECURE_COOKIES=true
```

Effect: `ADMIN_KEY` enables built-in admin access and is also used as the HMAC secret for stored user API keys. `AI_PROVIDER`, `AI_MODEL`, and `AI_CLI_TIMEOUT` apply when a generation request omits those fields. `DATA_DIR` changes the runtime storage root. `SECURE_COOKIES` changes whether browser sessions require HTTPS.

> **Warning:** Changing `ADMIN_KEY` invalidates existing stored user API keys.


> **Note:** On plain `http://localhost`, browser sessions do not persist unless `SECURE_COOKIES=false`.

### `docsfy-server`
Direct launcher environment read by `docsfy.main.run()`.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `HOST` | string | `127.0.0.1` | Bind host used by `docsfy-server`. |
| `PORT` | integer | `8000` | Bind port used by `docsfy-server`. |
| `DEBUG` | string | unset | When set to `true`, starts uvicorn with reload enabled. |

```bash
HOST=0.0.0.0 PORT=9000 DEBUG=true docsfy-server
```

Effect: Starts the server on the requested interface and port. `DEBUG=true` enables backend autoreload.

> **Note:** The checked-in container entrypoint does not use `HOST`, `PORT`, or `DEBUG`; it always starts uvicorn on `0.0.0.0:8000`.

## Sessions and Storage
### `docsfy_session`
Browser session cookie used for authenticated UI and WebSocket traffic.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | `docsfy_session` | Cookie name. |
| `value` | string | generated | Opaque session token. The raw API key is not stored in the cookie. |
| `HttpOnly` | boolean | `true` | Browser JavaScript cannot read the cookie. |
| `SameSite` | string | `strict` | Same-site policy. |
| `Secure` | boolean | `true` | Controlled by `SECURE_COOKIES`. |
| `Max-Age` | integer | `28800` | Session lifetime in seconds. |
| `server storage` | string | SHA-256 hash | The `sessions` table stores a SHA-256 hash of the token, not the raw token. |

```http
Set-Cookie: docsfy_session=<token>; HttpOnly; SameSite=strict; Max-Age=28800; Secure
```

Effect: Authenticates browser requests until logout, expiry, or API key rotation. Logout and user key rotation delete the current session.

### Runtime storage layout
Files and directories rooted under `DATA_DIR`.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `DATA_DIR/docsfy.db` | file | `/data/docsfy.db` | SQLite database containing projects, users, access grants, and sessions. |
| `DATA_DIR/projects/` | directory | `/data/projects/` | Root directory for generated variants. |
| `DATA_DIR/projects/<owner-or-_default>/<project>/<branch>/<provider>/<model>/` | directory | derived | Per-variant working directory. Empty owners are stored as `_default`. |
| `.../plan.json` | file | derived | Saved documentation plan for the variant. |
| `.../site/` | directory | derived | Rendered static site served under `/docs/...`. |
| `.../cache/pages/` | directory | derived | Cached page markdown used for regeneration. |

```text
/data/docsfy.db
/data/projects/alice/my-repo/main/claude/opus/plan.json
/data/projects/alice/my-repo/main/claude/opus/site/index.html
/data/projects/alice/my-repo/main/claude/opus/cache/pages/introduction.md
```

Effect: `init_db()` creates `docsfy.db` and `projects/` if they do not exist. Generated docs, cached pages, and saved plans are read from and written to this tree.

> **Note:** Branch, provider, and model values become path segments. Path traversal values such as `/`, `\`, `..`, or leading `.` are rejected.

## Ports and Containers
### Default ports
Network ports used by the checked-in launchers and development tools.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `8000` | TCP port | `8000` | Application server, REST API, docs serving, and `/health`. |
| `5173` | TCP port | `5173` | Vite development server used by `npm run dev` and container `DEV_MODE=true`. |

```text
http://localhost:8000/
http://localhost:5173/
```

Effect: `8000` is the application port in direct runs and container runs. `5173` is only used for frontend development.

> **Note:** The container image exposes both `8000` and `5173` and uses `curl -f http://localhost:8000/health` as its health check.

### `docker-compose.yaml`
Checked-in Compose service definition for containerized runs.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `services.docsfy.build.context` | path | `.` | Build context used for the image. |
| `services.docsfy.build.dockerfile` | path | `Dockerfile` | Dockerfile used for the build. |
| `services.docsfy.ports[0]` | string | `"8000:8000"` | Maps the backend port to the host. |
| `services.docsfy.ports[1]` | string | commented | Optional `"5173:5173"` mapping for Vite development mode. |
| `services.docsfy.volumes[0]` | string | `"./data:/data"` | Persists database and generated docs on the host. |
| `services.docsfy.volumes[1]` | string | commented | Optional `"./frontend:/app/frontend"` bind mount for live frontend development. |
| `services.docsfy.env_file` | path | `.env` | Loads environment variables into the container. |
| `services.docsfy.environment.ADMIN_KEY` | string | `${ADMIN_KEY}` | Passes the admin secret into the container environment. |
| `services.docsfy.environment.DEV_MODE` | string | commented | Optional development mode toggle. |
| `services.docsfy.restart` | string | `unless-stopped` | Container restart policy. |

```yaml
services:
  docsfy:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
      # - "5173:5173"
    volumes:
      - ./data:/data
      # - ./frontend:/app/frontend
    env_file:
      - .env
    environment:
      - ADMIN_KEY=${ADMIN_KEY}
      # - DEV_MODE=true
    restart: unless-stopped
```

Effect: Builds the local image and runs the server with persistent storage at `./data`. Uncommenting the development lines enables frontend hot-reload access from the host.

> **Warning:** `ADMIN_KEY` must resolve to a non-empty value of at least 16 characters or the application exits during startup.


> **Note:** If you change `DATA_DIR`, update the container-side volume target so it matches the new storage root.

## CLI Profiles
### `~/.config/docsfy/config.toml`
Local CLI profile file used by `docsfy`.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `path` | path | `~/.config/docsfy/config.toml` | CLI profile file. |
| `directory mode` | file mode | `0700` | Permission mode applied to `~/.config/docsfy/` when the CLI writes it. |
| `file mode` | file mode | `0600` | Permission mode applied to `config.toml` when the CLI writes it. |
| `[default].server` | string | unset | Default profile name used when `--server` is omitted. |
| `[servers.<name>].url` | string | unset | Base URL for the named server profile. |
| `[servers.<name>].username` | string | unset | Username stored with the profile. |
| `[servers.<name>].password` | string | unset | API key stored with the profile and used as the CLI Bearer token. |

```toml
[default]
server = "dev"

[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<API_KEY>"
```

Effect: The CLI resolves connection details from this file before running commands. The stored `password` value is sent as the Bearer token for API requests.

> **Warning:** `password` is stored verbatim in `config.toml`.


> **Note:** `username` is stored with the profile, but CLI authentication uses the password/API key as the Bearer token.

### `docsfy config init`
Interactive profile creation.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `Profile name` | prompt | `dev` | Profile name written under `[servers.<name>]`. |
| `Server URL` | prompt | none | Base URL for the target server. |
| `Username` | prompt | none | Username stored with the profile. |
| `Password` | prompt | none | API key stored with the profile. Input is hidden. |

```text
$ docsfy config init
Profile name [dev]: dev
Server URL: http://localhost:8000
Username: admin
Password:
Profile 'dev' saved to ~/.config/docsfy/config.toml
```

Effect: Creates or updates the named profile. If `[default].server` is not already set, it is set to the new profile name. If a default already exists, `init` adds the new profile without changing the current default.

### `docsfy config show`
Profile inspection command.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `command-specific options` | none | none | This command has no command-specific flags. |

```bash
docsfy config show
```

Effect: Prints the config file path, default profile, saved profiles, and masked passwords. Passwords are displayed as `***` or the first two characters followed by `***`.

### `docsfy config set`
Nested value update command.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `key` | string | none | Nested key to update. Must start with `default.` or `servers.`. |
| `value` | string | none | Value written to the target key. |

```bash
docsfy config set default.server prod
docsfy config set servers.prod.url https://docsfy.example.com
docsfy config set servers.prod.password <API_KEY>
```

Effect: Updates `config.toml` in place. Missing nested tables are created automatically.

> **Tip:** CLI connection resolution only reads `[default].server`, `servers.<name>.url`, `servers.<name>.username`, and `servers.<name>.password`.

### `docsfy` global connection options
Global options accepted before any CLI command.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--server`, `-s` | string | unset | Selects a named profile from `[servers]`. |
| `--host` | string | unset | Overrides the resolved host. If the selected profile URL starts with `http://`, the CLI keeps `http`; otherwise it uses `https`. |
| `--port` | integer | `8000` when `--host` is used | Port used with `--host`. |
| `--username`, `-u` | string | profile value | Overrides the resolved username. |
| `--password`, `-p` | string | profile value | Overrides the resolved API key. |

```bash
docsfy --server prod health
docsfy --host myhost --port 9000 -u admin -p <API_KEY> health
```

Effect: Resolution order is explicit CLI flags, then the `--server` profile, then `[default].server`. If no connection can be resolved, or the named profile does not exist, the CLI exits with an error.

## Local Development
### Frontend development proxy
Vite development server settings from `frontend/vite.config.ts`.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `API_TARGET` | URL | `http://localhost:8000` | Backend target for Vite proxying. |
| `server.host` | string | `0.0.0.0` | Vite bind host. |
| `server.port` | integer | `5173` | Vite bind port. |
| `proxy./api` | route | enabled | Proxies API requests to `API_TARGET`. WebSocket proxying is enabled. |
| `proxy./docs` | route | enabled | Proxies docs asset requests to `API_TARGET`. |
| `proxy./health` | route | enabled | Proxies health checks to `API_TARGET`. |

```bash
cd frontend
API_TARGET=http://localhost:8000 npm run dev
```

Effect: Starts Vite on `5173` and forwards API, docs, health, and WebSocket traffic to the backend target.

### Container `DEV_MODE`
Development mode handled by `entrypoint.sh`.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `DEV_MODE` | string | unset | When `true`, the entrypoint runs `npm ci`, starts Vite in the background, and starts uvicorn with `--reload --reload-dir /app/src`. |
| `backend bind` | host:port | `0.0.0.0:8000` | Fixed backend bind used by the container entrypoint. |
| `frontend bind` | port | `5173` | Vite port used in development mode. |
| `frontend mount` | path | commented in Compose | Optional `./frontend:/app/frontend` bind mount for live frontend changes. |

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
      - DEV_MODE=true
```

Effect: Starts the backend and Vite together inside the container. Backend code reloads from `/app/src`. Frontend live changes require the frontend bind mount.

> **Note:** When `DEV_MODE` is not `true`, the container serves the prebuilt frontend from `frontend/dist`.


> **Note:** If `frontend/dist/index.html` is missing and Vite is not running, non-API routes return `404` with `Frontend not built. Run: cd frontend && npm run build`.

## Related Pages

- See [Install and Run docsfy Without Docker](install-and-run-docsfy-without-docker.html) for details.
- See [Managing docsfy from the CLI](manage-docsfy-from-the-cli.html) for details.
- See [CLI Command Reference](cli-command-reference.html) for details.
- See [Fixing Setup and Generation Problems](fix-setup-and-generation-problems.html) for details.

## Related Pages

- [Install and Run docsfy Without Docker](install-and-run-docsfy-without-docker.html)
- [Managing docsfy from the CLI](manage-docsfy-from-the-cli.html)
- [CLI Command Reference](cli-command-reference.html)
- [Configuring AI Providers and Models](configure-ai-providers-and-models.html)
- [Fixing Setup and Generation Problems](fix-setup-and-generation-problems.html)