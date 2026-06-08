# Using the CLI

Manage your docsfy server entirely from the terminal — set up server profiles, generate documentation, monitor progress, download results, and administer users without ever opening a browser.

## Prerequisites

- docsfy installed (`pip install docsfy` or `uv pip install docsfy`)
- A running docsfy server you can reach over the network
- Your username and API key (get these from your server admin)

## Quick Example

Set up a server profile and generate docs in three commands:

```shell
docsfy config init
docsfy generate https://github.com/your-org/your-repo
docsfy download your-repo -o ./docs
```

## Setting Up Server Profiles

Before using any command, configure a connection to your docsfy server. The interactive setup walks you through it:

```shell
docsfy config init
```

You'll be prompted for:

- **Profile name** — a short label like `dev` or `prod` (default: `dev`)
- **Server URL** — full URL including scheme, e.g. `https://docsfy.example.com:8000`
- **Username** — your docsfy username
- **Password** — your API key

The first profile you create automatically becomes the default. Configuration is saved to `~/.config/docsfy/config.toml` with restricted file permissions (owner read/write only).

### Viewing Your Configuration

```shell
docsfy config show
```

```
Config file: /home/you/.config/docsfy/config.toml
Default server: dev

[dev] (default)
  URL:      https://docsfy.example.com:8000
  Username: alice
  Password: dk***
```

Passwords are always masked in output.

### Updating Individual Settings

Change any config value without re-running the full setup:

```shell
docsfy config set servers.dev.url https://new-server.example.com:8000
docsfy config set servers.dev.username bob
docsfy config set default.server prod
```

Keys must start with `default.` or `servers.`.

### Multiple Server Profiles

Run `docsfy config init` again to create additional profiles. Switch between them per-command with `--server`:

```shell
docsfy list --server prod
docsfy generate https://github.com/org/repo --server staging
```

Or change your default:

```shell
docsfy config set default.server prod
```

## Generating Documentation

```shell
docsfy generate https://github.com/your-org/your-repo
```

This submits the repository to the server and starts AI-powered documentation generation. The output confirms the request:

```
Project: your-repo
Branch: main
Status: generating
Generation ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

The server uses its default AI provider and model. To choose a specific provider and model:

```shell
docsfy generate https://github.com/your-org/your-repo --provider gemini --model gemini-2.5-flash
```

### Targeting a Branch

```shell
docsfy generate https://github.com/your-org/your-repo --branch dev
```

> **Note:** Branch names cannot contain slashes. Use hyphens instead (e.g., `release-1.x` instead of `release/1.x`).

### Specifying Repository Type

docsfy auto-detects whether your repo is an app, library, framework, or test suite. Override the detection if needed:

```shell
docsfy generate https://github.com/your-org/your-repo --repo-type library
```

Valid types: `app`, `library`, `framework`, `tests`.

### Forcing Full Regeneration

By default, docsfy performs incremental updates when docs already exist for a repo. Force a complete regeneration with:

```shell
docsfy generate https://github.com/your-org/your-repo --force
```

See [Working with Incremental Updates](incremental-updates.html) for details on how incremental generation works.

### Watching Progress in Real Time

Add `--watch` to stream generation progress directly in your terminal via WebSocket:

```shell
docsfy generate https://github.com/your-org/your-repo --watch
```

```
Project: your-repo
Branch: main
Status: generating
Generation ID: a1b2c3d4-...
Watching generation progress...
[generating] cloning repository
[generating] planning documentation (12 pages)
[generating] generating pages
Generation complete! (12 pages)
```

The command exits automatically when generation finishes, errors out, or is aborted.

## Checking Project Status

### List All Projects

```shell
docsfy list
```

```
NAME          BRANCH  PROVIDER  MODEL              STATUS  OWNER  PAGES  GEN ID
your-repo     main    cursor    gpt-5.4-xhigh-fast ready   alice  12     a1b2c3d4-...
other-repo    dev     gemini    gemini-2.5-flash    ready   bob    8      e5f6a7b8-...
```

Filter by status or provider:

```shell
docsfy list --status ready
docsfy list --provider gemini
```

### Inspect a Specific Project

```shell
docsfy status your-repo
```

```
Project: your-repo
Variants: 2

  main/cursor/gpt-5.4-xhigh-fast
    ID:      a1b2c3d4-e5f6-7890-abcd-ef1234567890
    Status:  ready
    Owner:   alice
    Pages:   12
    Updated: 2026-06-08T14:30:00
    Commit:  abc12345

  dev/gemini/gemini-2.5-flash
    ID:      f9e8d7c6-b5a4-3210-fedc-ba9876543210
    Status:  generating
    Owner:   alice
    Stage:   generating pages
```

Narrow to a specific variant with `--branch`, `--provider`, and `--model`:

```shell
docsfy status your-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
```

### Using Generation IDs

Every command that accepts a project name also accepts a generation ID (UUID). This is useful for scripting when you've captured the ID from a `generate` command:

```shell
docsfy status a1b2c3d4-e5f6-7890-abcd-ef1234567890
docsfy download a1b2c3d4-e5f6-7890-abcd-ef1234567890 -o ./docs
```

The CLI automatically resolves the UUID to the corresponding project, branch, provider, and model.

## Downloading Documentation

Download the generated documentation site as a tar.gz archive:

```shell
docsfy download your-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
```

```
Downloaded to /current/dir/your-repo-main-cursor-gpt-5.4-xhigh-fast-docs.tar.gz
```

### Extracting to a Directory

Use `--output` to extract directly into a folder:

```shell
docsfy download your-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast -o ./docs
```

```
Extracted to ./docs
```

### Flattening the Directory Structure

Archives contain a nested folder. Use `--flatten` to move all files directly into the output directory:

```shell
docsfy download your-repo -b main -p cursor -m gpt-5.4-xhigh-fast -o ./docs --flatten
```

```
Extracted and flattened to ./docs
```

> **Note:** `--flatten` requires `--output`.

## Aborting a Generation

Stop an in-progress generation:

```shell
docsfy abort your-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
```

Or abort by project name (stops any active generation for that project):

```shell
docsfy abort your-repo
```

## Deleting Projects

### Delete a Specific Variant

```shell
docsfy delete your-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
```

You'll be asked to confirm. Skip the prompt in scripts with `--yes`:

```shell
docsfy delete your-repo -b main -p cursor -m gpt-5.4-xhigh-fast --yes
```

### Delete All Variants

```shell
docsfy delete your-repo --all
```

> **Warning:** `--all` deletes every variant across all branches, providers, and models for the named project.

## Checking Available AI Models

See which AI providers and models are available on the server:

```shell
docsfy models
```

```
Provider: claude
  claude-sonnet-4-20250514
  claude-opus-4-20250514

Provider: gemini
  gemini-2.5-flash
  gemini-2.5-pro

Provider: cursor (default)
  gpt-5.4-xhigh-fast  (default)
  gpt-5.4-xhigh
```

Filter by provider:

```shell
docsfy models --provider gemini
```

## Checking Server Health

Verify connectivity to your docsfy server:

```shell
docsfy health
```

```
Server: https://docsfy.example.com:8000
Status: ok
```

## Admin Commands

Admin commands require an account with the `admin` role. See [Managing Users and Access Control](managing-users.html) for the full workflow.

### Managing Users

```shell
# List all users
docsfy admin users list

# Create a user (role: user, viewer, or admin)
docsfy admin users create alice --role user

# Rotate a user's API key
docsfy admin users rotate-key alice

# Delete a user
docsfy admin users delete alice --yes
```

When creating a user or rotating a key, the new API key is displayed once. Save it immediately — it cannot be retrieved later.

### Managing Project Access

```shell
# List who has access to a project
docsfy admin access list my-project --owner alice

# Grant access
docsfy admin access grant my-project --username bob --owner alice

# Revoke access
docsfy admin access revoke my-project --username bob --owner alice
```

## Advanced Usage

### JSON Output

Most commands support `--json` for machine-readable output, useful in scripts and CI pipelines:

```shell
docsfy list --json
docsfy status your-repo --json
docsfy models --json
docsfy admin users list --json
```

### Overriding Connection Settings per Command

Override any profile setting for a single command without changing your config:

```shell
docsfy list --host docsfy.staging.local --port 9000 --username admin --password my-key
```

The priority order is:

1. Explicit CLI flags (`--host`, `--port`, `--username`, `--password`)
2. Named server profile (`--server prod`)
3. Default profile from config
4. Error if nothing is configured

### CI/CD Integration

In CI environments where interactive `config init` isn't practical, pass credentials directly:

```shell
docsfy generate https://github.com/org/repo \
  --host docsfy.internal.com \
  --port 8000 \
  --username "$DOCSFY_USER" \
  --password "$DOCSFY_API_KEY" \
  --branch "$CI_BRANCH" \
  --force \
  --watch
```

Or create the config file programmatically before running commands. See [Common Workflow Recipes](recipes-common-workflows.html) for complete CI/CD patterns.

### Admin Operations on Other Users' Projects

Admins can operate on any user's projects by specifying `--owner`:

```shell
docsfy status some-project --owner alice
docsfy delete some-project --all --owner alice --yes
docsfy download some-project -b main -p cursor -m gpt-5.4-xhigh-fast --owner alice -o ./docs
```

## Troubleshooting

**"No server configured" error**
Run `docsfy config init` to create your first server profile, or pass `--host` and `--password` directly.

**"Server profile 'X' not found"**
Check available profiles with `docsfy config show`. Profile names are case-sensitive.

**"Error: Server redirected"**
Your server URL may be missing the correct scheme or port. Verify the URL in `docsfy config show` matches your server's actual address.

**"Specify --branch, --provider, and --model together"**
When targeting a specific variant for status, download, delete, or abort, all three flags must be provided together. Use `docsfy status <project>` first to see available variants.

**WebSocket timeout with --watch**
The `--watch` flag times out after 5 minutes of inactivity. For long-running generations, use `docsfy status <project>` to poll instead.

For the full list of every flag and option, see [CLI Command Reference](cli-reference.html). For server-side configuration, see [Configuration Reference](configuration-reference.html).

## Related Pages

- [CLI Command Reference](cli-reference.html)
- [Getting Started with docsfy](quickstart.html)
- [Configuration Reference](configuration-reference.html)
- [Common Workflow Recipes](recipes-common-workflows.html)
- [Managing Projects and Variants](managing-projects.html)