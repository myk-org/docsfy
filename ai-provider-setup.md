# AI Provider Setup

docsfy supports three AI CLI tools for documentation generation: **Claude Code** (Anthropic), **Gemini CLI** (Google), and **Cursor Agent**. Each provider requires its own credentials and CLI installation. This page covers how to configure credentials for every supported provider.

## Overview

docsfy invokes AI CLIs as subprocesses, passing prompts via stdin. Before generating documentation, docsfy runs a lightweight availability check against the configured provider to verify that credentials are valid and the CLI is reachable.

Set your provider and model in the `.env` file:

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
AI_CLI_TIMEOUT=60
```

The `AI_PROVIDER` value determines which CLI binary and command template docsfy uses:

| `AI_PROVIDER` | Binary | Command Template |
|---------------|--------|-----------------|
| `claude` | `claude` | `claude --model <model> --dangerously-skip-permissions -p` |
| `gemini` | `gemini` | `gemini --model <model> --yolo` |
| `cursor` | `agent` | `agent --force --model <model> --print --workspace <path>` |

> **Note:** Only one provider is active at a time, controlled by the `AI_PROVIDER` environment variable. You only need to configure credentials for the provider you intend to use.

## Anthropic API Key (Claude Code)

The simplest way to use Claude Code is with a direct Anthropic API key.

### Installation

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

### Configuration

Add your API key to the `.env` file:

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The `ANTHROPIC_API_KEY` environment variable is passed directly to the `claude` CLI at runtime.

### Docker Compose

No additional volume mounts are required for direct API key authentication. The key is loaded from the `.env` file:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
```

> **Tip:** You can obtain an API key from the [Anthropic Console](https://console.anthropic.com/). Keep your key secret and never commit it to version control.

## Google Cloud Vertex AI (Claude via Vertex)

If your organization uses Google Cloud, you can access Claude models through Vertex AI instead of using a direct Anthropic API key. This is useful for enterprises that need to route requests through their GCP project for billing, compliance, or access control.

### Prerequisites

- A Google Cloud project with the Vertex AI API enabled
- Claude models enabled in your Vertex AI project
- Google Cloud CLI (`gcloud`) installed and authenticated locally

### Configuration

Set the following environment variables in your `.env` file:

```bash
AI_PROVIDER=claude
AI_MODEL=claude-opus-4-6[1m]

# Enable Vertex AI mode
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project-id
```

| Variable | Description |
|----------|-------------|
| `CLAUDE_CODE_USE_VERTEX` | Set to `1` to enable Vertex AI mode for Claude Code |
| `CLOUD_ML_REGION` | The GCP region where Vertex AI is available (e.g., `us-east5`, `europe-west1`) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Your Google Cloud project ID |

> **Warning:** When `CLAUDE_CODE_USE_VERTEX=1` is set, the `ANTHROPIC_API_KEY` variable is ignored. Authentication is handled entirely through GCP credentials.

### Docker Compose

Vertex AI authentication requires mounting your local Google Cloud credentials into the container as a read-only volume:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
```

The `~/.config/gcloud` directory contains the credential files created by `gcloud auth login` and `gcloud auth application-default login`. The `:ro` suffix mounts the directory as read-only for security.

### Authenticating with GCP

Before starting the container, ensure you have authenticated locally:

```bash
# Authenticate your user account
gcloud auth login

# Set application default credentials (used by client libraries)
gcloud auth application-default login

# Verify the correct project is set
gcloud config set project my-gcp-project-id
```

> **Tip:** For production deployments, consider using a GCP service account instead of user credentials. Place the service account key JSON at a known path and set `GOOGLE_APPLICATION_CREDENTIALS` accordingly.

## Gemini API Key (Gemini CLI)

Google's Gemini CLI provides access to Gemini models for documentation generation.

### Installation

```bash
npm install -g @google/gemini-cli
```

### Configuration

Add your Gemini API key to the `.env` file:

```bash
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The `GEMINI_API_KEY` environment variable is passed to the `gemini` CLI process.

### Docker Compose

No additional volume mounts are required. The key is loaded from the `.env` file:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
```

> **Tip:** You can create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey).

## Cursor API Key (Cursor Agent)

Cursor Agent uses its own CLI binary (`agent`) and workspace-based directory handling.

### Installation

```bash
curl -fsSL https://cursor.com/install | bash
```

### Configuration

Add your Cursor API key to the `.env` file:

```bash
AI_PROVIDER=cursor
AI_MODEL=claude-opus-4-6
CURSOR_API_KEY=cur-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **Note:** Unlike Claude and Gemini, Cursor Agent uses the `--workspace <path>` flag to set the working directory instead of the subprocess `cwd`. This is handled automatically by docsfy's provider configuration (`uses_own_cwd=True`).

### Docker Compose

Cursor Agent requires a volume mount for its configuration directory:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ./cursor:/home/appuser/.config/cursor
```

Create the `cursor/` directory in your project root before starting the container:

```bash
mkdir -p cursor
```

## Complete `.env.example`

Here is the full reference for all AI-related environment variables, as defined in the project's `.env.example`:

```bash
# AI Configuration
AI_PROVIDER=claude                    # Options: claude, gemini, cursor
AI_MODEL=claude-opus-4-6[1m]         # Model identifier for the chosen provider
AI_CLI_TIMEOUT=60                    # Timeout in minutes for AI CLI calls

# Claude - Option 1: Direct API Key
# ANTHROPIC_API_KEY=

# Claude - Option 2: Vertex AI
# CLAUDE_CODE_USE_VERTEX=1
# CLOUD_ML_REGION=
# ANTHROPIC_VERTEX_PROJECT_ID=

# Gemini
# GEMINI_API_KEY=

# Cursor
# CURSOR_API_KEY=

# Logging
LOG_LEVEL=INFO
```

> **Warning:** Never commit your `.env` file to version control. Add `.env` to your `.gitignore` file to prevent accidental exposure of API keys.

## Complete Docker Compose Reference

If you need credentials for multiple providers (e.g., for testing or switching), mount all required volumes:

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
      - ./cursor:/home/appuser/.config/cursor
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Verifying Your Setup

After configuring credentials, start the service and check that the health endpoint responds:

```bash
docker compose up -d
curl http://localhost:8000/health
```

Then trigger a test generation to verify the AI provider is reachable:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/octocat/Hello-World"}'
```

Monitor the generation status:

```bash
curl http://localhost:8000/api/status
```

> **Note:** docsfy runs a lightweight availability check (a simple "Hi" prompt) against the configured provider before starting generation. If credentials are invalid or the CLI is not installed, the generation will fail early with a clear error message.

## Troubleshooting

### Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `claude: command not found` | Claude CLI not installed | Run the install script in your Dockerfile or host |
| `gemini: command not found` | Gemini CLI not installed | Run `npm install -g @google/gemini-cli` |
| `agent: command not found` | Cursor Agent not installed | Run the Cursor install script |
| Authentication error with Vertex AI | GCP credentials not mounted or expired | Re-run `gcloud auth login` and verify the volume mount |
| `ANTHROPIC_API_KEY` ignored | `CLAUDE_CODE_USE_VERTEX=1` is set | Unset `CLAUDE_CODE_USE_VERTEX` to use direct API key |
| Generation timeout | AI CLI taking too long | Increase `AI_CLI_TIMEOUT` (default: 60 minutes) |
