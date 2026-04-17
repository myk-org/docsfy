# Configuration Reference

Server settings come from environment variables. CLI profiles live in `~/.config/docsfy/config.toml`. See [Install and Run docsfy Without Docker](install-and-run-docsfy-without-docker.html) for startup steps and [CLI Command Reference](cli-command-reference.html) for CLI syntax.

## `.env`-Backed Server Settings
### `.env`
Environment file used by the server settings model.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `path` | path | `.env` | UTF-8 file loaded by the server settings model. |
| `encoding` | string | `utf-8` | Encoding used when reading `.env`. |
| `extra keys` | behavior | `ignored` | Unknown keys do not fail settings loading. |

```dotenv
ADMIN_KEY=<ADMIN_KEY>
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
DATA_DIR=/data
SECURE_COOKIES=true
```

Effect: Supplies the settings-model fields used during application startup and request handling.

> **Note:** `HOST`, `PORT`, `DEBUG`, `DEV_MODE`, and `API_TARGET` are read directly from the process environment, not from the settings model.

### Authentication settings
Admin authentication and browser cookie security.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `ADMIN_KEY` | string | `""` | Required admin secret. Used for admin login, admin Bearer auth, and HMAC hashing of stored user API keys. Startup validation requires at least 16 characters. |
| `SECURE_COOKIES` | boolean | `true` | Controls the `Secure` flag on the `docsfy_session` cookie. |

```dotenv
ADMIN_KEY=<ADMIN_KEY>
SECURE_COOKIES=true
```

Effect: `ADMIN_KEY` must be present for the server to start. `SECURE_COOKIES` changes whether browsers send the session cookie only over HTTPS.

> **Warning:** Changing `ADMIN_KEY` invalidates existing stored user API keys.

### Generation settings
Server-side defaults used when a generation omits provider, model, or timeout, plus the parallel page limit.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `AI_PROVIDER` | enum | `cursor` | Default AI provider. Accepted values: `claude`, `gemini`, `cursor`. |
| `AI_MODEL` | string | `gpt-5.4-xhigh-fast` | Default AI model name. |
| `AI_CLI_TIMEOUT` | integer | `60` | Positive timeout value passed to provider CLI calls when no request-specific value is supplied. |
| `MAX_CONCURRENT_PAGES` | integer | `10` | Maximum parallel AI CLI calls during page generation and validation. Must be greater than `0`. |

```dotenv
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
AI_CLI_TIMEOUT=120
MAX_CONCURRENT_PAGES=4
```

Effect: Request-specific provider, model, and timeout values override `AI_PROVIDER`, `AI_MODEL`, and `AI_CLI_TIMEOUT`. `MAX_CONCURRENT_PAGES` remains the server-side concurrency cap.

### Storage and logging settings
Runtime storage root and log verbosity.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `DATA_DIR` | path | `/data` | Base directory for `docsfy.db` and per-variant project files. |
| `LOG_LEVEL` | string | `INFO` | Logger level string used by the server. |

```dotenv
DATA_DIR=/srv/docsfy-data
LOG_LEVEL=DEBUG
```

Effect: `DATA_DIR` changes where the database and generated artifacts are stored. `LOG_LEVEL` changes server log verbosity.

## Direct Process Environment
### `docsfy-server` launcher variables
Variables read directly by the `docsfy-server` console entry point.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `HOST` | string | `127.0.0.1` | Bind host used by `docsfy-server`. |
| `PORT` | integer | `8000` | Bind port used by `docsfy-server`. |
| `DEBUG` | string | unset | Set to `true` to start uvicorn with reload enabled. |

```bash
HOST=0.0.0.0 PORT=9000 DEBUG=true docsfy-server
```

Effect: Starts the direct server entry point on the requested host and port, with reload enabled only when `DEBUG=true`.

> **Note:** The checked-in container entrypoint does not read `HOST` or `PORT`; it always starts uvicorn on `0.0.0.0:8000`.

### Container and frontend development variables
Variables used by `entrypoint.sh` and the Vite development server.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `DEV_MODE` | string | unset | When set to `true`, the container entrypoint runs `npm ci`, starts Vite on `5173`, and starts uvicorn with reload on `8000`. |
| `API_TARGET` | URL | `http://localhost:8000` | Backend target used by the Vite dev proxy for `/api`, `/docs`, and `/health`. WebSocket proxying is enabled for `/api`. |
| `vite host` | string | `0.0.0.0` | Fixed Vite development bind host. |
| `vite port` | integer | `5173` | Fixed Vite development port. |

```yaml
services:
  docsfy:
    ports:
      - "8000:8000"
      - "5173:5173"
    environment:
      - DEV_MODE=true
```

```bash
API_TARGET=http://localhost:8000 npm run dev
```

Effect: Enables split frontend/backend development and points the Vite proxy at the chosen backend.

## Default Variant Setting
### `branch`
Default branch used by variant records and filesystem layout when no branch is supplied.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `branch` | string | `main` | Default branch value. It is stored in the database primary key, used in variant URLs, and included in per-variant directory paths. Valid values must match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$`; `/` and `..` are rejected. |

```text
Valid:   release-1.x
Invalid: release/1.x
Default: main
```

Effect: Omitted branch values resolve to `main`.

> **Tip:** Use hyphens instead of slashes in branch names.

## Data Locations
### Runtime storage layout
Persistent files stored under `DATA_DIR`.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `DATA_DIR/docsfy.db` | file | `/data/docsfy.db` | SQLite database containing project metadata, users, project access rules, and hashed sessions. |
| `DATA_DIR/projects/` | directory | `/data/projects/` | Root directory for generated variants. |
| `DATA_DIR/projects/<owner-or-_default>/<project>/<branch>/<provider>/<model>/` | directory | derived | Per-variant root directory. `_default` is used when the owner is empty. |
| `.../site/` | directory | derived | Rendered static site files served under `/docs/...`. |
| `.../cache/pages/` | directory | derived | Cached page markdown used for regeneration. |

```text
/data/projects/alice/my-repo/main/claude/opus/site/index.html
/data/projects/alice/my-repo/main/claude/opus/cache/pages/introduction.md
```

Effect: `docsfy` creates `docsfy.db` and the `projects/` tree under `DATA_DIR` and uses these paths as the authoritative runtime storage location.

### Docker Compose volume
Default host-to-container storage mapping in the checked-in `docker-compose.yaml`.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `host path` | path | `./data` | Host directory mounted into the container. |
| `container path` | path | `/data` | Container path used by the server's default `DATA_DIR`. |
| `env_file` | path | `.env` | Compose file loaded into the container for server settings. |

```yaml
services:
  docsfy:
    volumes:
      - ./data:/data
    env_file:
      - .env
```

Effect: Persists the database and generated docs on the host across container restarts.

> **Note:** If you change `DATA_DIR`, update the volume mount to point at the new container path.

## Browser Session Cookie
### `docsfy_session`
Browser session cookie set on login.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | `docsfy_session` | Cookie name. |
| `value` | string | generated | Opaque session token returned on login. |
| `HttpOnly` | boolean | `true` | Client-side JavaScript cannot read the cookie. |
| `SameSite` | string | `strict` | Same-site cookie policy. |
| `Secure` | boolean | `true` | Controlled by `SECURE_COOKIES`. |
| `Max-Age` | integer | `28800` | Session lifetime in seconds (8 hours). |

```http
Set-Cookie: docsfy_session=<token>; HttpOnly; SameSite=strict; Max-Age=28800; Secure
```

Effect: Authenticates protected browser requests and WebSocket connections while the session is valid. The cookie stores an opaque token; the `sessions` table stores a SHA-256 hash of that token. The cookie is deleted on logout and after API key rotation.

> **Warning:** On plain `http://localhost`, browser logins do not persist unless `SECURE_COOKIES=false`.

## CLI Profiles
### `~/.config/docsfy/config.toml`
Local CLI profile file used by `docsfy`.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `directory` | path | `~/.config/docsfy/` | CLI config directory. |
| `file` | path | `~/.config/docsfy/config.toml` | CLI profile file. |
| `[default].server` | string | none | Default profile name used when `--server` is omitted. |
| `[servers.<name>].url` | string | none | Base URL for a named server profile. |
| `[servers.<name>].username` | string | none | Username stored with the profile for connection resolution and display. |
| `[servers.<name>].password` | string | none | API key stored with the profile and sent as the CLI Bearer token. |

```toml
[default]
server = "dev"

[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<API_KEY>"
```

Effect: The CLI loads this file to resolve server URL and credentials for commands that connect to a docsfy server. The stored `password` value is what the CLI sends as the Bearer token.

> **Warning:** `password` is stored verbatim in `config.toml`; the CLI relies on file permissions rather than encryption.
> **Note:** The CLI creates `~/.config/docsfy/` with owner-only permissions and writes `config.toml` with owner read/write only.
> **Tip:** `docsfy config set` accepts keys under `default.` and `servers.`.

### Connection resolution
Resolution order used by the CLI when building a server connection.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--server` | CLI flag | none | Selects a named profile from `[servers]`. |
| `--host` | CLI flag | none | Overrides the host portion of the resolved URL. If the selected profile URL begins with `http://`, the CLI keeps `http`; otherwise it uses `https`. |
| `--port` | CLI flag | `8000` when `--host` is set | Overrides or supplies the port for `--host`. |
| `--username` | CLI flag | none | Overrides the resolved username. |
| `--password` | CLI flag | none | Overrides the resolved API key. |
| `[default].server` | config key | none | Fallback profile when `--server` is omitted. |

```bash
docsfy --server prod health
docsfy --host docsfy.example.com --port 8443 -u admin -p <API_KEY> health
```

Effect: Resolution order is CLI flags, then the named profile, then `[default].server`. If no connection can be resolved, or if the selected profile does not exist, the CLI exits with an error. See [CLI Command Reference](cli-command-reference.html) for command syntax.

## Related Pages

- [Install and Run docsfy Without Docker](install-and-run-docsfy-without-docker.html)
- [Configure AI Providers](configure-ai-providers.html)
- [Manage docsfy from the CLI](manage-docsfy-from-the-cli.html)
- [CLI Command Reference](cli-command-reference.html)
- [Fix Setup and Generation Problems](fix-setup-and-generation-problems.html)