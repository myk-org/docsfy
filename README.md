# docsfy

AI-powered documentation generator that creates polished static HTML docs from GitHub repositories using Claude, Gemini, or Cursor CLI.

[**Documentation**](https://myk-org.github.io/docsfy-docs/) | [**GitHub**](https://github.com/myk-org/docsfy)

## Architecture

- **React SPA** -- Single-page web UI with sidebar project tree, inline generation progress, and admin panels
- **WebSocket** -- Real-time generation progress streamed to the browser (no polling)
- **CLI** -- Full-featured `docsfy` command for scripting and terminal workflows
- **FastAPI backend** -- REST API with JWT authentication

Entry points:

| Command | Description |
|---|---|
| `docsfy` | CLI tool for generating docs, managing projects, and admin tasks |
| `docsfy-server` | Starts the FastAPI web server with the React UI |

## Documentation

Full documentation is available at [https://myk-org.github.io/docsfy-docs/](https://myk-org.github.io/docsfy-docs/)

## Quick Start

### Web UI

```bash
# Clone and configure
git clone https://github.com/myk-org/docsfy.git
cd docsfy
cp .env.example .env
# Edit .env -- set ADMIN_KEY (minimum 16 characters)

# Run
docker compose up

# Open the web UI
open http://localhost:8000         # macOS
# xdg-open http://localhost:8000   # Linux
# start http://localhost:8000      # Windows
```

Log in with admin credentials, add a GitHub repository URL, and watch generation progress in real time via WebSocket.

### CLI

```bash
# Install
pip install docsfy

# Initialize CLI config
docsfy config init
# Edit ~/.config/docsfy/config.toml with server URL and credentials

# Generate docs for a repository
docsfy generate https://github.com/org/repo

# List projects
docsfy projects list

# View generation status
docsfy projects status org/repo
```

### API

```bash
# Authenticate
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<ADMIN_KEY>"}' | jq -r .access_token)

# Generate docs
curl -X POST http://localhost:8000/api/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/repo"}'

# List projects
curl http://localhost:8000/api/projects \
  -H "Authorization: Bearer $TOKEN"
```

## Configuration

### Server (.env)

See `.env.example` for all available environment variables.

### CLI (~/.config/docsfy/config.toml)

See `config.toml.example` for the CLI configuration format.

## License

Apache-2.0
