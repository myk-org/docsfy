# Configuration Reference

This page documents every configuration knob for the docsfy server, CLI, and Docker deployment. Each setting lists its name, type, default, valid values, and a concrete example.

## Server Environment Variables

The docsfy server reads its configuration from environment variables (or an `.env` file in the working directory). Settings are loaded by `pydantic_settings` — variable names are **case-insensitive**.

| Variable | Type | Default | Description |
|---|---|---|---|
| `ADMIN_KEY` | `string` | *(none — required)* | Master admin password. Must be at least 16 characters. Used for admin login, API key HMAC hashing, and initial authentication. |
| `AI_PROVIDER` | `string` | `cursor` | Default AI provider for documentation generation. |
| `AI_MODEL` | `string` | `gpt-5.4-xhigh-fast` | Default AI model for documentation generation. |
| `AI_CLI_TIMEOUT` | `integer` | `60` | Timeout in seconds for each AI CLI call. Must be greater than 0. |
| `LOG_LEVEL` | `string` | `INFO` | Python logging level. |
| `DATA_DIR` | `string` | `/data` | Root directory for the SQLite database and generated documentation files. |
| `SECURE_COOKIES` | `boolean` | `true` | Set session cookies with the `Secure` flag. Set to `false` for local HTTP development. |
| `MAX_CONCURRENT_PAGES` | `integer` | `10` | Maximum number of AI calls to run in parallel during page generation and validation. Must be greater than 0. |
| `PORT` | `integer` | `8000` | TCP port the uvicorn server listens on. |
| `HOST` | `string` | `127.0.0.1` | Bind address for the uvicorn server. |
| `DEBUG` | `string` | *(unset)* | When `true`, starts uvicorn with `--reload` for hot reloading. |
| `SIDECAR_PORT` | `integer` | `9100` | TCP port the Pi SDK HTTP sidecar listens on. Set by the container entrypoint. |
| `DEV_MODE` | `string` | *(unset)* | When `true`, the entrypoint installs frontend dependencies, starts a Vite dev server on port `5173`, recompiles the sidecar TypeScript, and runs uvicorn with `--reload`. |

### Example `.env` file

```env
ADMIN_KEY=my-very-long-secret-key-here
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
LOG_LEVEL=INFO
DATA_DIR=/data
SECURE_COOKIES=true
MAX_CONCURRENT_PAGES=10
```

> **Warning:** `ADMIN_KEY` is required. The server will exit immediately at startup if it is empty or shorter than 16 characters.


> **Note:** Rotating `ADMIN_KEY` invalidates all existing user API key hashes. Every user must regenerate their API key after an `ADMIN_KEY` change.

### Valid AI Providers

| Provider | Value |
|---|---|
| Claude | `claude` |
| Gemini | `gemini` |
| Cursor | `cursor` |

See [Configuring AI Providers](configuring-ai-providers.html) for provider setup details.

### Valid Log Levels

`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Data Directory Layout

All persistent state lives under `DATA_DIR` (default `/data`).

```
<DATA_DIR>/
├── docsfy.db                  # SQLite database
└── projects/
    └── <owner>/
        └── <project>/
            └── <branch>/
                └── <provider>/
                    └── <model>/
                        ├── cache/pages/   # Cached page markdown
                        └── site/          # Rendered HTML site
```

- `<owner>` is the username of the project creator (`_default` when empty).
- `<branch>` defaults to `main`.
- `<provider>` and `<model>` identify the AI variant used for generation.

## CLI Configuration File

The CLI stores server profiles in a TOML file at:

```
~/.config/docsfy/config.toml
```

The file is created with permissions `600` (owner read/write only).

### File Structure

```toml
# Default server profile to use when --server is not specified
[default]
server = "dev"

# Server profiles — add as many as needed
[servers.<profile-name>]
url = "<server-url>"
username = "<username>"
password = "<api-key>"
```

### Keys Reference

| Key | Type | Required | Description |
|---|---|---|---|
| `default.server` | `string` | No | Name of the profile to use by default when `--server` is not passed. |
| `servers.<name>.url` | `string` | Yes | Full URL of the docsfy server (e.g. `https://docsfy.example.com`). |
| `servers.<name>.username` | `string` | Yes | Username for authentication. |
| `servers.<name>.password` | `string` | Yes | API key or admin password. |

> **Tip:** Valid key prefixes for `docsfy config set` are `default.` and `servers.` only.

### Example

```toml
[default]
server = "dev"

[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<your-dev-key>"

[servers.prod]
url = "https://docsfy.example.com"
username = "admin"
password = "<your-prod-key>"
```

### CLI Config Commands

#### `docsfy config init`

Interactive setup that prompts for profile name, server URL, username, and password. Creates the config file if it doesn't exist, or adds a new profile.

```bash
docsfy config init
```

```
Profile name [dev]: prod
Server URL: https://docsfy.example.com
Username: admin
Password: ********
Profile 'prod' saved to /home/user/.config/docsfy/config.toml
```

#### `docsfy config show`

Displays all profiles with masked passwords.

```bash
docsfy config show
```

```
Config file: /home/user/.config/docsfy/config.toml
Default server: dev

[dev] (default)
  URL:      http://localhost:8000
  Username: admin
  Password: my***
```

#### `docsfy config set`

Set a single configuration key.

```bash
docsfy config set default.server prod
docsfy config set servers.dev.url https://new-server.com
docsfy config set servers.staging.password new-api-key
```

See [Using the CLI](using-the-cli.html) for the full CLI setup workflow and [CLI Command Reference](cli-reference.html) for all commands.

### CLI Connection Resolution

When the CLI connects to a server, parameters are resolved in this priority order (highest first):

1. Explicit CLI flags (`--host`, `--port`, `--username`, `--password`)
2. Named server profile from `--server` flag
3. Default server profile from `[default].server` in config
4. Error if nothing is configured

| CLI Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--server` | `-s` | `string` | *(from config)* | Server profile name to use. |
| `--host` | | `string` | *(from profile)* | Server hostname. Overrides the profile URL. |
| `--port` | | `integer` | `8000` | Server port. Used with `--host`. |
| `--username` | `-u` | `string` | *(from profile)* | Username for authentication. |
| `--password` | `-p` | `string` | *(from profile)* | API key or password. |

```bash
# Use config default
docsfy list

# Use a named profile
docsfy --server prod list

# Override host and port
docsfy --host myserver --port 9000 -u admin -p my-key list
```

> **Note:** When `--host` is used with a profile, the scheme is preserved from the profile URL. Without a profile, the scheme defaults to `https`.

## Docker Compose Configuration

### Compose File Reference

```yaml
services:
  docsfy:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
      # - "5173:5173"  # Uncomment for DEV_MODE
    volumes:
      - ./data:/data
      # - ./frontend:/app/frontend  # Uncomment for frontend hot reload
    env_file:
      - .env
    environment:
      - ADMIN_KEY=${ADMIN_KEY}
      # - DEV_MODE=true
    restart: unless-stopped
```

### Compose Options

| Key | Type | Default | Description |
|---|---|---|---|
| `services.docsfy.ports` | `list` | `["8000:8000"]` | Port mappings. Add `5173:5173` when `DEV_MODE=true`. |
| `services.docsfy.volumes` | `list` | `["./data:/data"]` | Persistent storage. Add `./frontend:/app/frontend` for development. |
| `services.docsfy.env_file` | `list` | `[".env"]` | Path to the environment file. |
| `services.docsfy.environment.ADMIN_KEY` | `string` | `${ADMIN_KEY}` | Admin key passed from shell or `.env`. |
| `services.docsfy.environment.DEV_MODE` | `string` | *(commented)* | Set to `true` for development mode. |
| `services.docsfy.restart` | `string` | `unless-stopped` | Container restart policy. |

### Container DEV_MODE

When `DEV_MODE=true`, the container entrypoint:

1. Runs `npm ci` and starts the Vite dev server on port `5173`
2. Recompiles sidecar TypeScript from source
3. Starts uvicorn with `--reload --reload-dir /app/src`

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

> **Note:** When `DEV_MODE` is not `true`, the container serves the prebuilt frontend from `frontend/dist`.

See [Deploying with Docker](deployment.html) for production deployment patterns.

### Container Ports

| Port | Protocol | Default | Description |
|---|---|---|---|
| `8000` | TCP | `8000` | FastAPI server (uvicorn). Controlled by `PORT` env var. |
| `5173` | TCP | `5173` | Vite development server. Only active when `DEV_MODE=true`. |
| `9100` | TCP | `9100` | Pi SDK sidecar (internal). Controlled by `SIDECAR_PORT` env var. |

### Health Check

The container health check probes both the server and the sidecar:

```
curl -f http://localhost:${PORT:-8000}/health
curl -f http://localhost:${SIDECAR_PORT:-9100}/health
```

- **Interval:** 30 seconds
- **Timeout:** 10 seconds
- **Start period:** 30 seconds
- **Retries:** 3

## Session and Authentication Constants

These values are compiled into the server and cannot be changed via environment variables.

| Constant | Value | Description |
|---|---|---|
| Session TTL | `28800` seconds (8 hours) | Duration before a session cookie expires. |
| Minimum API key length | `16` characters | Minimum length for `ADMIN_KEY` and user API keys. |
| Session cookie name | `docsfy_session` | Name of the HTTP-only session cookie. |
| Cookie `SameSite` | `strict` | Cookie SameSite policy. |
| Cookie `HttpOnly` | `true` | Cookie cannot be accessed by JavaScript. |
| API key prefix | `docsfy_` | Generated API keys start with this prefix. |
| Valid user roles | `admin`, `user`, `viewer` | Assignable roles for user accounts. |

See [Managing Users and Access Control](managing-users.html) for role descriptions.

## Git Operation Timeouts

Internal timeouts for git subprocess calls. These are compiled constants in `repository.py`.

| Operation | Timeout | Description |
|---|---|---|
| Clone | 300 seconds | `git clone --depth 1` of a remote repository. |
| Fetch | 120 seconds | `git fetch --depth=1` to deepen a shallow clone for diffing. |
| Diff | 60 seconds | `git diff --stat --patch` between two commits. |
| Name listing | 30 seconds | `git diff --name-only` to list changed files. |
| Cat-file / rev-parse | 10 seconds | `git cat-file`, `git rev-parse` for commit SHA and branch detection. |

## GenerateRequest Defaults

When submitting a generation request (via API or CLI), these defaults apply to omitted fields.

| Field | Type | Default | Valid Values | Description |
|---|---|---|---|---|
| `ai_provider` | `string` | Server default (`cursor`) | `claude`, `gemini`, `cursor` | AI provider. |
| `ai_model` | `string` | Server default (`gpt-5.4-xhigh-fast`) | *(provider-specific)* | AI model. |
| `ai_cli_timeout` | `integer` | `60` | > 0 | Per-call AI timeout in seconds. |
| `branch` | `string` | `main` | `^[a-zA-Z0-9][a-zA-Z0-9._-]*$` | Git branch to generate docs from. Slashes are **not** allowed. |
| `force` | `boolean` | `false` | `true`, `false` | Force full regeneration, ignoring cache. |
| `repo_type` | `string` | *(auto-detected)* | `app`, `tests`, `library`, `framework` | Repository type hint for prompt selection. |

> **Warning:** Branch names cannot contain `/` characters. Use hyphens instead (e.g. `release-1.x` rather than `release/1.x`).

See [Generating Documentation](generating-docs.html) for generation workflows and [REST API Reference](api-reference.html) for the `POST /api/generate` endpoint.

## Generation Stages

A generation run progresses through these stages in order. The `current_stage` field reflects the active stage in status responses and WebSocket messages.

| Stage | Description |
|---|---|
| `cloning` | Cloning the git repository (or reading the local path). |
| `analyzing` | Building the code knowledge graph with Graphify. |
| `planning` | AI plans the documentation structure (full generation). |
| `incremental_planning` | AI plans which pages need updates (incremental generation). |
| `generating_pages` | AI generates markdown content for each page. |
| `validating` | AI validates pages for stale references and completeness. |
| `completeness_check` | Verifying all planned pages were generated. |
| `cross_linking` | AI adds cross-reference links between related pages. |
| `rendering` | Converting markdown to HTML and building the static site. |

## Prompt Constraints

Internal limits applied during AI prompt construction.

| Constant | Value | Description |
|---|---|---|
| Max diff length | 30,000 characters | Diff content is truncated beyond this limit before being passed to the incremental planner. |
| Max file char cap (code graph) | 20,000 characters | Per-file character limit during code graph semantic extraction. |

## WebSocket Constants

Internal constants for the WebSocket connection (`/api/ws`).

| Constant | Value | Description |
|---|---|---|
| Heartbeat interval | 30 seconds | Server sends a ping frame at this interval. |
| Pong timeout | 10 seconds | Maximum wait for a pong response before marking a missed pong. |
| Max missed pongs | 2 | Connection is closed after this many consecutive missed pongs. |

## Frontend Constants

Client-side timing constants defined in `frontend/src/lib/constants.ts`.

| Constant | Value | Description |
|---|---|---|
| `TOAST_DEFAULT_MS` | 4000 ms | Default toast notification duration. |
| `TOAST_ERROR_MS` | 6000 ms | Error toast notification duration. |
| `WS_HEARTBEAT_INTERVAL_MS` | 30000 ms | Client-side WebSocket heartbeat interval. |
| `WS_RECONNECT_MAX_DELAY_MS` | 30000 ms | Maximum delay between WebSocket reconnection attempts. |
| `WS_POLLING_FALLBACK_MS` | 10000 ms | Polling interval when WebSocket is unavailable. |
| `SIDEBAR_MIN_WIDTH` | 180 px | Minimum sidebar width in the dashboard. |
| `SIDEBAR_MAX_WIDTH` | 500 px | Maximum sidebar width in the dashboard. |
| `SIDEBAR_DEFAULT_WIDTH` | 256 px | Default sidebar width in the dashboard. |

## Project Database Schema

The composite primary key for project variants:

```
PRIMARY KEY (name, branch, ai_provider, ai_model, owner)
```

| Column | Type | Default | Description |
|---|---|---|---|
| `name` | `TEXT` | *(required)* | Repository name. |
| `branch` | `TEXT` | `main` | Git branch. |
| `ai_provider` | `TEXT` | `''` | AI provider used. |
| `ai_model` | `TEXT` | `''` | AI model used. |
| `owner` | `TEXT` | `''` | Username of the project creator. |
| `generation_id` | `TEXT` | *(auto-generated UUID)* | Unique identifier for the generation run. |
| `repo_url` | `TEXT` | *(required)* | Git repository URL. |
| `status` | `TEXT` | `generating` | Current status: `generating`, `ready`, `error`, `aborted`. |
| `current_stage` | `TEXT` | `NULL` | Active generation stage (see Generation Stages above). |
| `last_commit_sha` | `TEXT` | `NULL` | SHA of the commit used for the last generation. |
| `last_generated` | `TIMESTAMP` | `NULL` | Timestamp of last successful generation. |
| `page_count` | `INTEGER` | `0` | Number of generated documentation pages. |
| `error_message` | `TEXT` | `NULL` | Error description when status is `error`. |
| `plan_json` | `TEXT` | `NULL` | JSON-serialized documentation plan. |
| `repo_type` | `TEXT` | `NULL` | Detected or specified repository type. |
| `total_cost_usd` | `REAL` | `NULL` | Total AI generation cost in USD. |

## Related Pages

- [Deploying with Docker](deployment.html)
- [Configuring AI Providers](configuring-ai-providers.html)
- [CLI Command Reference](cli-reference.html)
- [Using the CLI](using-the-cli.html)
- [Generating Documentation](generating-docs.html)