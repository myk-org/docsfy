# AI Provider Setup

`docsfy` does not call Anthropic, Google, or Cursor APIs directly. Instead, it runs locally installed AI CLIs from the backend, so provider setup happens on the machine running `docsfy-server`.

The supported provider names are:

- `claude`
- `gemini`
- `cursor`

Provider and model are part of each generated variant, alongside the project name and branch. That is why the same repository can have separate outputs for different providers, models, or branches.

## What `docsfy` Expects

For each provider you want to use, `docsfy` expects the matching external CLI to be installed and usable by the server process:

- `claude`: Claude Code CLI
- `gemini`: Google Gemini CLI
- `cursor`: Cursor Agent CLI

If you use the included Docker image, all three are installed during the image build:

```dockerfile
# Install Claude Code CLI (installs to ~/.local/bin)
RUN /bin/bash -o pipefail -c "curl -fsSL https://claude.ai/install.sh | bash"

# Install Cursor Agent CLI (installs to ~/.local/bin)
RUN /bin/bash -o pipefail -c "curl -fsSL https://cursor.com/install | bash"

# Configure npm for non-root global installs and install Gemini CLI
RUN mkdir -p /home/appuser/.npm-global \
  && npm config set prefix '/home/appuser/.npm-global' \
  && npm install -g @google/gemini-cli
```

The container is then configured so those CLIs are available to the runtime user:

```dockerfile
USER appuser

ENV PATH="/home/appuser/.local/bin:/home/appuser/.npm-global/bin:${PATH}"
ENV HOME="/home/appuser"
```

If you are not using Docker, install the equivalent CLIs yourself on the host where `docsfy-server` runs, and make sure they are on `PATH` for that server user.

> **Warning:** A provider showing up in the UI does not mean it is actually ready to use. The provider list is fixed, but real availability is checked when generation starts.

## Authentication Expectations

There are two separate kinds of authentication in a `docsfy` deployment:

1. `docsfy` server auth, which controls access to the app and API
2. Provider CLI auth, which allows Claude, Gemini, or Cursor to actually generate documentation

The `docsfy` CLI config is only for talking to your `docsfy` server:

```toml
[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<your-dev-key>"
```

That `password` is your `docsfy` API key, not a Claude, Gemini, or Cursor credential.

The server environment is the same story: it configures defaults, not provider logins. The example environment file contains provider defaults and timeout settings, but no provider-specific secrets:

```dotenv
# AI provider and model defaults
# (pydantic_settings reads these case-insensitively)
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
```

`docsfy` does not define its own Claude, Gemini, or Cursor auth variables. The underlying provider CLI must already be authenticated in the environment where `docsfy-server` runs.

For container deployments, that means the authenticated CLI state must be available to the runtime user shown in the Dockerfile: `appuser` with `HOME=/home/appuser`.

> **Note:** The repository installs the provider binaries, but it does not automate provider login. Complete each provider CLI's normal authentication flow separately, then make sure that authenticated state is available to the same user that runs `docsfy-server`.

## Default Provider, Model, and Timeout

If you do not send `ai_provider` and `ai_model` in an API request, `docsfy` falls back to its configured defaults. The shipped defaults are:

- Provider: `cursor`
- Model: `gpt-5.4-xhigh-fast`
- CLI timeout: `60` seconds

Those values come from environment variables:

```dotenv
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
```

You can override them per generation through the API or the `docsfy` CLI.

An example from the repository's CLI tests uses an explicit Gemini model:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
```

The API uses the same fields:

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -X POST "$SERVER/api/generate" \
  -d "{\"repo_url\":\"https://github.com/myk-org/for-testing-only\",\"ai_provider\":\"gemini\",\"ai_model\":\"gemini-2.5-flash\",\"force\":true}"
```

> **Note:** `ADMIN_KEY` in the example above authenticates you to `docsfy`. It does not log the provider CLI into Claude, Gemini, or Cursor.

## How Provider and Model Availability Affect Generation

### Providers are validated, models are not hardcoded

`docsfy` validates the provider name against the supported set of `claude`, `gemini`, and `cursor`.

Model handling is looser: the backend only requires a non-empty model string. It does not keep its own authoritative catalog of valid provider models. In practice, the provider CLI is the source of truth.

That means:

- If the model name is valid and your account can use it, generation can proceed.
- If the model name is wrong, unavailable, or not allowed for your current provider login, the provider CLI will fail and the variant will move to `error`.

### Availability is checked before generation work begins

Before `docsfy` starts cloning or rendering, it checks whether the selected provider CLI is available for the requested provider/model pair.

If that check fails, the run does not continue as a successful generation. In the UI or status output, you will see the project move into an error state with the message returned from the availability check.

> **Warning:** Installing a CLI binary is not enough. The CLI must also be usable non-interactively by the server user, with access to the model you selected.

### The model picker is historical, not live discovery

The UI's model suggestions come from previously completed `ready` variants. In other words, a model appears in the picker because it has already succeeded on this `docsfy` server before.

This has a few important consequences:

- A fresh installation may have an empty model list.
- A newly released model will not appear automatically.
- A model may still appear in the list even if your current provider login no longer has access to it.

The UI still lets you type a model manually. That matters because the backend requires a non-empty model, and new or first-time models often need to be entered by hand before they can become suggested values later.

> **Tip:** If the model dropdown is empty, type the model name you want to use and run a generation once. After a successful `ready` run, that model becomes part of the server's remembered model list.

## Cursor-Specific Behavior

`docsfy` treats all three providers similarly, with one Cursor-specific behavior: when `cursor` is selected, it automatically adds Cursor's `--trust` flag before invoking the CLI.

You do not need a separate `docsfy` setting for that.

## Switching Providers or Models

Provider and model are not just labels. They affect how `docsfy` stores and reuses work.

Each variant is scoped by:

- project name
- branch
- provider
- model
- owner

That means the same repository can have separate variants such as:

- `main / gemini / gemini-2.5-flash`
- `main / claude / opus`
- `dev / cursor / gpt-5.4-xhigh-fast`

This is why variant-specific URLs and downloads include the branch, provider, and model.

### Non-force runs can reuse work from another provider/model

When you regenerate without `force`, `docsfy` can reuse the newest ready variant as a base, even if that base was created by a different provider or model.

The repository tests cover two important cases:

- Same commit: `docsfy` can copy the existing cached pages and rendered site directly instead of regenerating everything.
- New commit: `docsfy` can reuse the previous plan and keep unchanged cached pages, only regenerating the parts that need updates.

This makes provider and model switching much faster, especially when you are comparing outputs for the same repository.

> **Note:** On a non-force run for the same commit, the older ready variant from another provider/model can be replaced once the new one is ready.

### `force` disables cross-provider reuse

If you want a full fresh run for the selected provider/model, use `force=true` or `--force`.

With `force`, `docsfy` does not reuse another provider's cached output, and the older variant is left in place.

> **Tip:** Use `--force` when you want to compare providers side by side without automatic replacement.

## Practical Setup Checklist

Use this checklist when bringing up a new server:

- Set `ADMIN_KEY` so you can access the `docsfy` API and UI.
- Decide on default `AI_PROVIDER`, `AI_MODEL`, and `AI_CLI_TIMEOUT`.
- Install the Claude, Gemini, and/or Cursor CLI on the machine running `docsfy-server`.
- Make sure the server user can execute those CLIs from `PATH`.
- Authenticate each provider CLI outside of `docsfy`.
- Confirm that the authenticated state is available to the same user that runs `docsfy-server`.
- Run a first generation with an explicit provider and model.
- Verify that successful runs start populating the model suggestions you expect.

## Troubleshooting

If provider setup is wrong, the most common symptoms are:

- A generation starts and then quickly moves to `error`: the provider CLI is probably missing, logged out, or denied access to the requested model.
- The provider is selectable in the UI but generation fails immediately: provider visibility in the UI does not guarantee runtime availability.
- The model you want is not listed: type it manually.
- A model still appears in the picker but now fails: remembered models reflect past successful runs, not current provider entitlements.
- Provider calls are timing out: raise `AI_CLI_TIMEOUT` globally, or send `ai_cli_timeout` on the request.

When in doubt, test the provider CLI directly in the same environment, as the same user, and with the same `HOME` that `docsfy-server` uses.
