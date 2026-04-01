# Installation

docsfy has two parts:

- a Python application that provides the API, generation engine, and CLI
- a React frontend that `docsfy-server` serves from `frontend/dist`

If you only want the CLI to talk to an existing docsfy server, you can skip the frontend build on your machine. If you want the full local web UI, install both the Python and frontend dependencies.

## Prerequisites

You will need:

- Python 3.12 or newer
- `uv` for Python dependency management
- Node.js and npm for the frontend build
- Git
- one supported AI provider CLI if you plan to generate docs: `claude`, `gemini`, or `cursor`
- Chromium plus Mermaid CLI (`mmdc`) if you want local generation to match the container's Mermaid diagram support

The project metadata defines the Python version requirement and the two console entry points:

```toml
[project]
requires-python = ">=3.12"

[project.scripts]
docsfy-server = "docsfy.main:run"
docsfy = "docsfy.cli.main:main"
```

> **Note:** The repository’s container build uses Python 3.12 and Node 20, so Node 20 is a safe choice for local frontend work too.

If you want local generation to match the container's Mermaid diagram support, install Chromium and Mermaid CLI (`mmdc`) too. The runtime image does that with:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
  bash \
  git \
  curl \
  nodejs \
  npm \
  chromium \
  && rm -rf /var/lib/apt/lists/*

# Puppeteer config for mermaid-cli (must be set before npm install)
ENV PUPPETEER_EXECUTABLE_PATH="/usr/bin/chromium"
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD="true"

# Configure npm for non-root global installs and install Gemini CLI + mermaid-cli
RUN mkdir -p /home/appuser/.npm-global \
  && npm config set prefix '/home/appuser/.npm-global' \
  && npm install -g @google/gemini-cli @mermaid-js/mermaid-cli@11
```

## Install Python dependencies

From the repository root, install the Python environment with `uv`:

```bash
uv sync --frozen --no-dev
```

That matches the runtime install used by the project’s container build and gives you the `docsfy` and `docsfy-server` commands inside the project environment.

If you do not want to activate the environment manually, you can run the commands through `uv`:

```bash
uv run docsfy --help
uv run docsfy-server
```

> **Note:** If you only need the CLI as a client for an already-running server, this Python install is enough.

## Install frontend dependencies

The frontend lives in `frontend/` and uses Vite. Install its dependencies with npm, then build the static assets:

```bash
cd frontend
npm ci
npm run build
```

The available frontend scripts are defined in `frontend/package.json`:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "test": "vitest run"
}
```

`npm run build` creates the files that `docsfy-server` serves for the browser UI.

If you are actively working on the frontend, you can also run the Vite dev server:

```bash
cd frontend
npm run dev
```

> **Tip:** The Vite dev server listens on `0.0.0.0:5173` and proxies `/api`, `/docs`, and `/health` to `http://localhost:8000` by default. If your backend is running somewhere else, set `API_TARGET` before starting `npm run dev`.

> **Warning:** Build the frontend before starting `docsfy-server` if you want the browser UI. The server only mounts `/assets` when those build artifacts already exist, so if you build the frontend after the server is already running, restart the server.

## Create your `.env` file

`docsfy-server` reads settings from a `.env` file in the repository root. The checked-in example is:

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

At minimum, set `ADMIN_KEY` to a strong value with 16 or more characters.

> **Warning:** `docsfy-server` exits at startup if `ADMIN_KEY` is missing or shorter than 16 characters.

> **Tip:** For local development over plain `http://localhost`, set `SECURE_COOKIES=false`. Otherwise browser login cookies will be marked secure and will not work over HTTP.

> **Note:** `DATA_DIR` defaults to `/data`, which matches the container setup. For a local source checkout, point it at a writable location if you do not want to use `/data`.

## Start `docsfy-server`

Once the Python environment, frontend build, and `.env` file are ready, start the server:

```bash
uv run docsfy-server
```

By default, the server binds to `127.0.0.1:8000`. You can override that with environment variables:

```bash
HOST=0.0.0.0 PORT=8000 DEBUG=true uv run docsfy-server
```

`DEBUG=true` enables reload mode for local backend development.

> **Note:** Generation jobs require the matching provider CLI to be installed. docsfy supports `claude`, `gemini`, and `cursor`, and checks that the selected provider CLI is available before it starts generating pages.

## Configure the `docsfy` CLI

`docsfy` is the client entry point. It talks to a running server and stores connection profiles in `~/.config/docsfy/config.toml`.

The easiest setup path is the interactive config command:

```bash
uv run docsfy config init
uv run docsfy health
```

For a first local setup, use:

- server URL: `http://localhost:8000`
- username: `admin`
- password: your `ADMIN_KEY`

The example config file in the repository looks like this:

```toml
[default]
server = "dev"

[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<your-dev-key>"
```

This file contains the server URL plus the credential the CLI will send as a Bearer token. For the built-in local admin account, that token is your `ADMIN_KEY`.

> **Warning:** `~/.config/docsfy/config.toml` contains credentials. Keep it private.

> **Tip:** The example config recommends `chmod 600 ~/.config/docsfy/config.toml`, and `docsfy config init` writes the file with owner-only permissions automatically.

## The two installed commands

After installation, the two commands you will use most are:

- `docsfy-server` to run the FastAPI application
- `docsfy` to configure a server profile, check health, start generations, inspect status, and manage projects or users

From a repository checkout, the most reliable way to invoke them is through `uv run`:

```bash
uv run docsfy-server
uv run docsfy health
```

If `uv run docsfy health` reports an `ok` status, your local installation is ready to use.


## Related Pages

- [Docker and Compose Quickstart](docker-quickstart.html)
- [Environment Variables](environment-variables.html)
- [AI Provider Setup](ai-provider-setup.html)
- [Local Development](local-development.html)
- [First Run Quickstart](first-run-quickstart.html)