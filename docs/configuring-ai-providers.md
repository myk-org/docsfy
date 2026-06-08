# Configuring AI Providers

Choose which AI provider and model generates your documentation, tune timeouts, and verify that the Pi SDK sidecar — the service that routes all AI calls — is running correctly.

## Prerequisites

- A running docsfy server (see [Deploying with Docker](deployment.html))
- The Pi SDK sidecar started automatically (bundled in the Docker image)

## Quick Example

Set your default provider and model in the `.env` file:

```bash
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-20250514
AI_CLI_TIMEOUT=90
```

Restart the server, and every new generation request will use Claude by default.

## Available Providers

docsfy supports three AI providers:

| Provider | Description |
|----------|-------------|
| `claude` | Anthropic's Claude models |
| `gemini` | Google's Gemini models |
| `cursor` | Cursor agent models (default) |

## Setting Server Defaults

The server-wide default provider and model are configured through environment variables. These apply when a user does not specify a provider or model in their generation request.

```bash
# .env
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
```

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `cursor` | Default AI provider for new generations |
| `AI_MODEL` | `gpt-5.4-xhigh-fast` | Default model within the chosen provider |
| `AI_CLI_TIMEOUT` | `60` | Seconds before an individual AI call times out |

> **Note:** Environment variables override any config file values. See [Configuration Reference](configuration-reference.html) for the complete list of settings.

## Choosing a Provider Per Generation

You can override the server default on each generation request — from the dashboard or the CLI.

### From the Web Dashboard

1. Open the dashboard and click **New Generation**.
2. Select a provider from the **Provider** dropdown (`claude`, `gemini`, or `cursor`).
3. Choose a model from the **Model** dropdown, which auto-populates with models available for the selected provider.
4. Click **Generate**.

> **Tip:** The model list is discovered automatically from the sidecar. If the dropdown is empty, the sidecar may not be running — see [Troubleshooting](#troubleshooting) below.

### From the CLI

```bash
docsfy generate https://github.com/org/repo \
  --provider claude \
  --model claude-sonnet-4-20250514 \
  --branch main
```

When `--provider` or `--model` are omitted, the server defaults apply.

## Listing Available Models

See which providers and models the server currently supports.

### CLI

```bash
docsfy models
```

Sample output:

```
Provider: claude
  claude-sonnet-4-20250514
  claude-opus-4-20250514

Provider: gemini
  gemini-2.5-pro

Provider: cursor (default)
  gpt-5.4-xhigh-fast  (default)
```

Filter to a single provider:

```bash
docsfy models --provider gemini
```

Get machine-readable output:

```bash
docsfy models --json
```

For full CLI flag details, see [CLI Command Reference](cli-reference.html).

## How the Pi SDK Sidecar Works

All AI calls from docsfy are routed through the **Pi SDK sidecar**, a lightweight Node.js service that runs alongside the main server. You do not call AI providers directly — the sidecar handles provider routing, authentication, and model discovery.

The flow for every generation:

1. docsfy server receives a generate request with a provider and model.
2. The server sends AI prompts to the sidecar over HTTP on `localhost`.
3. The sidecar routes the call to the correct provider (Claude, Gemini, or Cursor).
4. Responses flow back through the sidecar to the server.

> **Note:** The sidecar starts automatically when using Docker. The entrypoint script launches it in the background, waits for it to be healthy, and then starts the docsfy server. If the sidecar dies, the container shuts down.

### Sidecar Port

The sidecar listens on port **9100** by default. Override it with the `SIDECAR_PORT` environment variable:

```bash
SIDECAR_PORT=9200
```

### Health Check

Both the docsfy server and sidecar have health endpoints. The Docker health check verifies both:

```bash
# Check the main server
curl http://localhost:8000/health

# Check the sidecar
curl http://localhost:9100/health
```

## Advanced Usage

### Parallel Page Generation

docsfy generates multiple documentation pages in parallel. Control the concurrency level with:

```bash
MAX_CONCURRENT_PAGES=10
```

This limits how many simultaneous AI calls run during page generation and validation. Lower this if you hit provider rate limits; raise it for faster generation on providers with high rate limits.

### Multiple Variants

Each combination of **project + branch + provider + model** creates a separate documentation variant. You can generate docs for the same repository using different providers to compare output quality:

```bash
docsfy generate https://github.com/org/repo --provider claude --model claude-sonnet-4-20250514
docsfy generate https://github.com/org/repo --provider gemini --model gemini-2.5-pro
```

Both variants are stored independently and accessible at their own URLs:

```
/docs/{project}/{branch}/{provider}/{model}/
```

See [Managing Projects and Variants](managing-projects.html) for listing, inspecting, and deleting variants.

### Switching Providers for an Existing Project

To regenerate an existing project's docs with a different provider, simply submit a new generation with the desired provider and model. The new variant is stored alongside the old one — nothing is overwritten.

To force a complete regeneration with the same provider (ignoring incremental update logic), add the `--force` flag:

```bash
docsfy generate https://github.com/org/repo --provider cursor --force
```

See [Working with Incremental Updates](incremental-updates.html) for details on when incremental vs. full regeneration applies.

## Troubleshooting

**Model dropdown is empty in the dashboard**

The sidecar may not be running or reachable. Check its health:

```bash
curl http://localhost:9100/health
```

If the sidecar is down, restart the container. The entrypoint script automatically starts it.

**"Sidecar not available" error during generation**

docsfy checks sidecar availability before starting each generation. If the sidecar is unreachable, the generation fails immediately with an error status. Verify the sidecar is healthy and that `SIDECAR_PORT` matches in both the server and sidecar configuration.

**AI calls timing out**

Increase the timeout:

```bash
AI_CLI_TIMEOUT=120
```

This sets the per-call timeout in seconds. Complex codebases may need longer timeouts for planning and page generation steps.

**Generation is slow**

- Increase `MAX_CONCURRENT_PAGES` to allow more parallel AI calls (default: `10`).
- Check whether your provider has rate limits that are being hit.
- Consider switching to a faster model for large repositories.

## Related Pages

- [Deploying with Docker](deployment.html)
- [Configuration Reference](configuration-reference.html)
- [Generating Documentation](generating-docs.html)
- [Working with Incremental Updates](incremental-updates.html)
- [Managing Projects and Variants](managing-projects.html)