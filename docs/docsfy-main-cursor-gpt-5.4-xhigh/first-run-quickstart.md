# First Run Quickstart

`docsfy` is a FastAPI service with a built-in React UI. On a first run, the simplest flow is: set `ADMIN_KEY`, start the service, sign in as the built-in `admin`, create any extra users you need, and launch a first generation against a real Git repository.

## What You Need

- One admin secret for `ADMIN_KEY`
- A remote Git repository URL over HTTPS or SSH
- One usable AI provider: `claude`, `gemini`, or `cursor`
- Docker and Docker Compose if you want the quickest startup path

The shipped `.env.example` shows the core runtime settings:

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

# Development mode: starts Vite dev server on port 5173 alongside FastAPI
# DEV_MODE=true
```

> **Warning:** `docsfy` will exit on startup if `ADMIN_KEY` is missing or shorter than 16 characters.

> **Warning:** For plain `http://localhost` development, set `SECURE_COOKIES=false`. With secure cookies enabled, the browser will not keep the login session on HTTP.

## 1. Start The Service

The included `docker-compose.yaml` is the fastest first-run path. It exposes port `8000`, loads your `.env`, and keeps the database plus generated documentation under `./data`:

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
```

From the repository root:

1. Copy `.env.example` to `.env`.
2. Set a real `ADMIN_KEY`.
3. If you are using plain local HTTP, set `SECURE_COOKIES=false`.
4. Run `docker compose up`.
5. Open `http://localhost:8000/health` and confirm the service returns `{"status":"ok"}`.

> **Tip:** The first build can take a little while. The container image builds the frontend and installs the bundled Claude, Cursor, and Gemini CLIs.

> **Tip:** If you run `docsfy-server` directly instead of using the container, build the frontend first. In production mode the backend serves `frontend/dist`, and without it the app returns: `Frontend not built. Run: cd frontend && npm run build`.

## 2. Sign In As Admin

Open `http://localhost:8000/login` and use:

- Username: `admin`
- Password: your `ADMIN_KEY`

The built-in admin account comes from environment configuration, not from the users table.

> **Note:** The web UI calls this value a password. The API and CLI use the same secret as an API key or Bearer token.

> **Note:** `admin` is a reserved username. Do not try to create a normal user named `admin`.

After sign-in, you land on the dashboard. As an admin you can start generations, view every project, open the `Users` panel, and manage sharing from the `Access` panel.

## 3. Create Users If You Need Them

If you are the only operator, you can skip this section and start generating as `admin`.

If other people will use the system, create named accounts from the `Users` panel. `docsfy` supports three roles:

| Role | Best used for | Can generate | Can manage users/access |
| --- | --- | --- | --- |
| `admin` | full operators | Yes | Yes |
| `user` | day-to-day doc generation | Yes | No |
| `viewer` | read-only access | No | No |

For a first non-admin account, choose `user`.

> **Warning:** Generated passwords/API keys are shown once when a user is created or rotated. Save them before you dismiss the message.

If you prefer the CLI, the repository already exercises commands like these:

```shell
docsfy admin users list
docsfy admin users create cli-test-user --role user
```

> **Note:** Projects belong to the account that starts the generation. If one user creates docs and another user needs to see them, grant access from the `Access` panel after the project exists.

## 4. Start Your First Documentation Generation

From the dashboard, click `New Generation` and fill in:

- `Repository URL`: a remote Git URL over HTTPS or SSH
- `Branch`: `main` is the default
- `Provider`: `claude`, `gemini`, or `cursor`
- `Model`: the model you want for that provider
- `Force full regeneration`: leave this off for a true first run

A good first test target is the same repository used in this project’s own test plans: `https://github.com/myk-org/for-testing-only`.

The CLI test plan uses this exact command:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
```

If you want to stay in the UI, the same values make a good first run:

- Repository URL: `https://github.com/myk-org/for-testing-only`
- Branch: `main`
- Provider/model: either your configured defaults, or a known working pair such as `gemini` / `gemini-2.5-flash`

If you do not override the server defaults, `docsfy` falls back to:

- Provider: `cursor`
- Model: `gpt-5.4-xhigh-fast`

> **Note:** Branch names cannot contain `/`. Use names like `main`, `dev`, or `release-1.x`.

After you click `Generate`, `docsfy` creates a project variant immediately and runs the job in the background. In the dashboard you should see:

- A new project entry in the sidebar
- Status `Generating`
- Real-time progress updates
- Activity log stages such as `cloning`, `planning`, `generating_pages`, and `rendering`

When the run finishes, the detail view shows:

- `Ready` status
- Page count
- Last generated time
- Last commit SHA
- `View Documentation`
- `Download`

> **Tip:** The direct docs URL includes the project, branch, provider, and model: `/docs/<project>/<branch>/<provider>/<model>/`. The shorter `/docs/<project>/` route serves the latest ready variant you can access.

## 5. Optional: Connect The CLI To The Same Server

If you have the `docsfy` CLI installed locally, create a reusable connection profile. The example `config.toml` included in this repo looks like this:

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

You can create a local profile interactively and then test it:

```shell
docsfy config init
docsfy health
```

For the built-in admin account, the CLI `password` field is your `ADMIN_KEY`. For a normal user, it is that user’s API key or password.

> **Warning:** `~/.config/docsfy/config.toml` contains credentials. Keep it private.

## 6. If The First Run Fails

If a project moves to `Error`, open the variant detail view and read the error message shown there. On a first run, the usual causes are:

- `ADMIN_KEY` is missing or too short
- `SECURE_COOKIES` is still `true` while you are using plain `http://localhost`
- The selected AI provider is not usable in that runtime environment
- The repository URL is invalid or unreachable
- The signed-in account is a `viewer`, which is read-only and cannot generate

> **Note:** The Docker image installs the Claude Code CLI, Cursor Agent CLI, and Gemini CLI at build time. That gives you the binaries, but the provider you choose still needs to be usable in that environment or generation will fail early.

Once your first run succeeds, the next practical step is to create named `user` accounts for everyday work and keep the built-in `admin` account for setup, access control, and recovery.
