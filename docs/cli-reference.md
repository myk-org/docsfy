# CLI Command Reference

The `docsfy` CLI manages documentation generation, project lifecycle, and server administration from the terminal. It communicates with a running docsfy server over HTTP and WebSocket.

> **Note:** The CLI requires a running docsfy server. See [Getting Started with docsfy](quickstart.html) for initial setup, or [Using the CLI](using-the-cli.html) for profile configuration walkthrough.

## Global Options

Every `docsfy` command accepts these options. They apply **before** any subcommand.

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--server` | `-s` | `string` | Config default | Server profile name from `~/.config/docsfy/config.toml` |
| `--host` | | `string` | From profile | Server host (overrides profile URL) |
| `--port` | | `int` | `8000` | Server port (used with `--host`) |
| `--username` | `-u` | `string` | From profile | Username for authentication |
| `--password` | `-p` | `string` | From profile | API key for authentication |

**Resolution priority** (highest to lowest):

1. Explicit CLI flags (`--host`, `--port`, `--username`, `--password`)
2. Server profile specified by `--server`
3. Default server profile from config `[default].server`
4. Error if nothing is configured

```bash
# Use the default profile
docsfy list

# Use a named profile
docsfy --server prod list

# Override host and credentials inline
docsfy --host myserver.example.com --port 8000 -u admin -p <API_KEY> list
```

> **Tip:** Run `docsfy config init` to set up a profile so you don't need to pass credentials on every command. See [Configuration Reference](configuration-reference.html) for the config file format.

---

## `docsfy generate`

Generate documentation for a Git repository. Submits a generation request to the server and optionally watches progress in real time via WebSocket.

```
docsfy generate <REPO_URL> [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `REPO_URL` | `string` | Yes | Git repository URL (HTTPS or SSH) |

### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--branch` | `-b` | `string` | `main` | Git branch to generate docs from |
| `--provider` | | `string` | Server default | AI provider (`claude`, `gemini`, `cursor`) |
| `--model` | `-m` | `string` | Server default | AI model name |
| `--repo-type` | `-t` | `string` | Auto-detected | Repository type: `app`, `tests`, `library`, `framework` |
| `--force` | `-f` | `bool` | `false` | Force full regeneration, ignoring cache |
| `--watch` | `-w` | `bool` | `false` | Watch generation progress via WebSocket |

### Output

Prints project name, branch, status, and generation ID to stdout. With `--watch`, streams progress updates to stderr until generation completes or fails.

```
Project: my-project
Branch: main
Status: generating
Generation ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Examples

```bash
# Basic generation with defaults
docsfy generate https://github.com/org/repo

# Generate for a specific branch and provider
docsfy generate https://github.com/org/repo -b dev --provider claude -m claude-sonnet-4-20250514

# Force full regeneration and watch progress
docsfy generate https://github.com/org/repo -f -w

# Specify repository type explicitly
docsfy generate https://github.com/org/repo -t library

# SSH URL
docsfy generate git@github.com:org/repo.git -b release-1.x
```

> **Note:** Branch names cannot contain slashes. Use hyphens instead (e.g., `release-1.x` instead of `release/1.x`). Branch validation pattern: `^[a-zA-Z0-9][a-zA-Z0-9._-]*$`

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Generation submitted (or completed, with `--watch`) |
| `1` | Invalid repo type, generation error, WebSocket failure, or server error |

---

## `docsfy list`

List all projects visible to the authenticated user.

```
docsfy list [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--status` | `string` | None | Filter by status: `ready`, `generating`, `error`, `aborted` |
| `--provider` | `string` | None | Filter by AI provider |
| `--json` | `bool` | `false` | Output as JSON instead of table |

### Output (table)

```
NAME          BRANCH  PROVIDER  MODEL                  STATUS  OWNER  PAGES  GEN ID
----------    ------  --------  ---------------------  ------  -----  -----  ------
my-project    main    cursor    gpt-5.4-xhigh-fast     ready   admin  12     a1b2c3d4-...
other-repo    dev     claude    claude-sonnet-4-20250514        ready   admin  8      e5f6a7b8-...
```

### Examples

```bash
# List all projects
docsfy list

# List only ready projects
docsfy list --status ready

# List projects using Claude
docsfy list --provider claude

# Get machine-readable output
docsfy list --json
```

### JSON Output Structure

```json
[
  {
    "name": "my-project",
    "branch": "main",
    "ai_provider": "cursor",
    "ai_model": "gpt-5.4-xhigh-fast",
    "status": "ready",
    "owner": "admin",
    "page_count": 12,
    "generation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
]
```

---

## `docsfy status`

Show the status of a project and its variants. Accepts either a project name or a generation ID (UUID).

```
docsfy status <NAME> [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `NAME` | `string` | Yes | Project name or generation ID (UUID) |

### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--branch` | `-b` | `string` | None | Filter by branch |
| `--provider` | `-p` | `string` | None | Filter by provider |
| `--model` | `-m` | `string` | None | Filter by model |
| `--owner` | | `string` | None | Project owner (for admin disambiguation) |
| `--json` | | `bool` | `false` | Output as JSON |

### Behavior

- If `--branch`, `--provider`, and `--model` are all specified, returns a single variant's detail.
- Otherwise, returns all matching variants for the project.
- UUID arguments are resolved to project name/branch/provider/model via the server API.

### Output

```
Project: my-project
Variants: 2

  main/cursor/gpt-5.4-xhigh-fast
    ID:      a1b2c3d4-e5f6-7890-abcd-ef1234567890
    Status:  ready
    Owner:   admin
    Pages:   12
    Updated: 2026-06-08T10:30:00
    Commit:  abc12345

  dev/claude/claude-sonnet-4-20250514
    ID:      f9e8d7c6-b5a4-3210-fedc-ba0987654321
    Status:  generating
    Owner:   admin
    Stage:   generating_pages
```

### Examples

```bash
# Show all variants for a project
docsfy status my-project

# Show a specific variant
docsfy status my-project -b main -p cursor -m gpt-5.4-xhigh-fast

# Look up by generation ID
docsfy status a1b2c3d4-e5f6-7890-abcd-ef1234567890

# JSON output for scripting
docsfy status my-project --json
```

---

## `docsfy delete`

Delete a project or a specific variant. Requires confirmation unless `--yes` is passed.

```
docsfy delete <NAME> [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `NAME` | `string` | Yes | Project name or generation ID (UUID) |

### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--branch` | `-b` | `string` | None | Branch of variant to delete |
| `--provider` | `-p` | `string` | None | Provider of variant to delete |
| `--model` | `-m` | `string` | None | Model of variant to delete |
| `--owner` | | `string` | None | Project owner (required for admin) |
| `--all` | | `bool` | `false` | Delete all variants of the project |
| `--yes` | `-y` | `bool` | `false` | Skip confirmation prompt |

### Behavior

- To delete a **specific variant**: specify `--branch`, `--provider`, and `--model` together.
- To delete **all variants**: use `--all`.
- `--all` and `--branch`/`--provider`/`--model` are mutually exclusive.
- Without `--all` or the full variant triple, the command exits with an error.

### Examples

```bash
# Delete a specific variant
docsfy delete my-project -b main -p cursor -m gpt-5.4-xhigh-fast

# Delete all variants (skip confirmation)
docsfy delete my-project --all -y

# Delete by generation ID
docsfy delete a1b2c3d4-e5f6-7890-abcd-ef1234567890 -y

# Admin deleting another user's project
docsfy delete my-project --all --owner otheruser -y
```

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Deletion successful or aborted by user |
| `1` | Missing required options, invalid arguments, or server error |

---

## `docsfy abort`

Abort an active documentation generation.

```
docsfy abort <NAME> [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `NAME` | `string` | Yes | Project name or generation ID (UUID) |

### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--branch` | `-b` | `string` | None | Branch of variant to abort |
| `--provider` | `-p` | `string` | None | Provider of variant to abort |
| `--model` | `-m` | `string` | None | Model of variant to abort |
| `--owner` | | `string` | None | Project owner (required for admin) |

### Behavior

- Specify `--branch`, `--provider`, and `--model` together to abort a specific variant.
- Omit all three to abort by project name (server selects the active generation).
- Providing only some of the three variant selectors is an error.

### Examples

```bash
# Abort by project name
docsfy abort my-project

# Abort a specific variant
docsfy abort my-project -b main -p cursor -m gpt-5.4-xhigh-fast

# Abort by generation ID
docsfy abort a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## `docsfy download`

Download generated documentation as a `.tar.gz` archive or extract it directly to a directory.

```
docsfy download <NAME> [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `NAME` | `string` | Yes | Project name or generation ID (UUID) |

### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--branch` | `-b` | `string` | None | Branch of variant to download |
| `--provider` | `-p` | `string` | None | Provider of variant to download |
| `--model` | `-m` | `string` | None | Model of variant to download |
| `--owner` | | `string` | None | Project owner (for admin disambiguation) |
| `--output` | `-o` | `string` | None | Output directory to extract to |
| `--flatten` | | `bool` | `false` | Flatten extracted directory structure into output dir |

### Behavior

- Without `--output`: saves a `.tar.gz` file to the current directory.
- With `--output`: extracts the archive to the specified directory.
- `--flatten` moves all files from the archive's top-level subdirectory into `--output` directly. Requires `--output`.
- Specify `--branch`, `--provider`, and `--model` together for a specific variant, or omit all three for the default variant.

### Archive Naming

| Variant specified | Archive filename |
|---|---|
| No | `{name}-docs.tar.gz` |
| Yes | `{name}-{branch}-{provider}-{model}-docs.tar.gz` |

### Examples

```bash
# Download archive to current directory
docsfy download my-project

# Download a specific variant
docsfy download my-project -b main -p cursor -m gpt-5.4-xhigh-fast

# Extract to a directory
docsfy download my-project -o ./docs-output

# Extract and flatten (no nested subdirectory)
docsfy download my-project -o ./docs-output --flatten

# Download by generation ID
docsfy download a1b2c3d4-e5f6-7890-abcd-ef1234567890 -o ./docs
```

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Download or extraction successful |
| `1` | Missing required options, `--flatten` without `--output`, or server error |

---

## `docsfy models`

List available AI providers and their models from the server.

```
docsfy models [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--provider` | `-P` | `string` | None | Filter by a specific provider |
| `--json` | `-j` | `bool` | `false` | Output as JSON |

### Output

```
Provider: cursor (default)
  gpt-5.4-xhigh-fast  (default)
  gpt-4.1-mini

Provider: claude
  claude-sonnet-4-20250514

Provider: gemini
  gemini-2.5-pro
```

### Examples

```bash
# List all providers and models
docsfy models

# Show only Claude models
docsfy models -P claude

# JSON output
docsfy models --json
```

### JSON Output Structure

```json
{
  "providers": ["claude", "gemini", "cursor"],
  "default_provider": "cursor",
  "default_model": "gpt-5.4-xhigh-fast",
  "available_models": {
    "cursor": [{"id": "gpt-5.4-xhigh-fast"}, {"id": "gpt-4.1-mini"}],
    "claude": [{"id": "claude-sonnet-4-20250514"}],
    "gemini": [{"id": "gemini-2.5-pro"}]
  }
}
```

---

## `docsfy health`

Check if the docsfy server is reachable.

```
docsfy health
```

### Output

```
Server: https://myserver.example.com:8000
Status: ok
```

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Server is healthy |
| `1` | Server unreachable or returned non-JSON response |

### Example

```bash
docsfy --server prod health
```

---

## `docsfy config`

Manage CLI configuration profiles stored in `~/.config/docsfy/config.toml`. See [Configuration Reference](configuration-reference.html) for the full file format.

### `docsfy config init`

Interactive setup that creates a server profile.

```
docsfy config init
```

Prompts for:

| Prompt | Default | Description |
|---|---|---|
| Profile name | `dev` | Name for this server profile |
| Server URL | — | Full URL (e.g., `https://myserver.example.com:8000`) |
| Username | — | Your username |
| Password | — | Your API key (input hidden) |

If no default profile exists, the new profile is automatically set as the default.

```bash
$ docsfy config init
Profile name [dev]: prod
Server URL: https://docs.example.com:8000
Username: admin
Password: ****
Profile 'prod' saved to /home/user/.config/docsfy/config.toml
```

### `docsfy config show`

Display all server profiles with masked passwords.

```
docsfy config show
```

```
Config file: /home/user/.config/docsfy/config.toml
Default server: dev

[dev] (default)
  URL:      http://localhost:8000
  Username: admin
  Password: ad***

[prod]
  URL:      https://docs.example.com:8000
  Username: deployer
  Password: dk***
```

### `docsfy config set`

Set a single configuration value by dotted key path.

```
docsfy config set <KEY> <VALUE>
```

| Argument | Type | Required | Description |
|---|---|---|---|
| `KEY` | `string` | Yes | Dotted config key |
| `VALUE` | `string` | Yes | Value to set |

Valid key prefixes: `default.` and `servers.`

```bash
# Change the default profile
docsfy config set default.server prod

# Update a profile URL
docsfy config set servers.dev.url http://localhost:9000

# Update credentials
docsfy config set servers.prod.username deployer
docsfy config set servers.prod.password <API_KEY>
```

> **Warning:** The config file stores credentials in plain text with `0600` permissions. The directory is set to `0700`. Do not commit this file to version control.

---

## `docsfy admin`

Administrative commands for user and access management. Requires admin-level authentication.

### `docsfy admin users list`

List all users on the server.

```
docsfy admin users list [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--json` | `bool` | `false` | Output as JSON |

**Table output:**

```
USERNAME  ROLE   CREATED
--------  -----  -------------------
admin     admin  2026-06-01T00:00:00
alice     user   2026-06-05T14:30:22
bob       viewer 2026-06-07T09:15:00
```

### `docsfy admin users create`

Create a new user account.

```
docsfy admin users create <USERNAME> [OPTIONS]
```

| Argument / Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `USERNAME` (arg) | | `string` | — | Username to create |
| `--role` | `-r` | `string` | `user` | User role: `admin`, `user`, `viewer` |
| `--json` | | `bool` | `false` | Output as JSON |

```bash
$ docsfy admin users create alice --role user
User created: alice
Role: user
API Key: dk_a1b2c3d4e5f6...

Save this API key -- it will not be shown again.
```

> **Warning:** The API key is displayed only once. Store it securely.

### `docsfy admin users delete`

Delete a user account.

```
docsfy admin users delete <USERNAME> [OPTIONS]
```

| Argument / Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `USERNAME` (arg) | | `string` | — | Username to delete |
| `--yes` | `-y` | `bool` | `false` | Skip confirmation prompt |

```bash
docsfy admin users delete alice -y
```

### `docsfy admin users rotate-key`

Rotate a user's API key. Generates a new key (or sets a custom one) and invalidates the old key.

```
docsfy admin users rotate-key <USERNAME> [OPTIONS]
```

| Argument / Option | Type | Default | Description |
|---|---|---|---|
| `USERNAME` (arg) | `string` | — | Username whose key to rotate |
| `--new-key` | `string` | Auto-generated | Custom API key (generated if omitted) |
| `--json` | `bool` | `false` | Output as JSON |

```bash
$ docsfy admin users rotate-key alice
User: alice
New API Key: dk_f6e5d4c3b2a1...

Save this API key -- it will not be shown again.
```

---

### `docsfy admin access list`

List users who have been granted access to a project.

```
docsfy admin access list <PROJECT> --owner <OWNER> [OPTIONS]
```

| Argument / Option | Type | Required | Default | Description |
|---|---|---|---|---|
| `PROJECT` (arg) | `string` | Yes | — | Project name |
| `--owner` | `string` | Yes | — | Project owner |
| `--json` | `bool` | No | `false` | Output as JSON |

```bash
$ docsfy admin access list my-project --owner admin
Project: my-project
Owner: admin
Users with access: alice, bob
```

### `docsfy admin access grant`

Grant a user access to all variants of a project.

```
docsfy admin access grant <PROJECT> --username <USER> --owner <OWNER>
```

| Argument / Option | Type | Required | Description |
|---|---|---|---|
| `PROJECT` (arg) | `string` | Yes | Project name |
| `--username` | `string` | Yes | Username to grant access |
| `--owner` | `string` | Yes | Project owner |

```bash
docsfy admin access grant my-project --username alice --owner admin
```

### `docsfy admin access revoke`

Revoke a user's access to a project.

```
docsfy admin access revoke <PROJECT> --username <USER> --owner <OWNER>
```

| Argument / Option | Type | Required | Description |
|---|---|---|---|
| `PROJECT` (arg) | `string` | Yes | Project name |
| `--username` | `string` | Yes | Username to revoke access |
| `--owner` | `string` | Yes | Project owner |

```bash
docsfy admin access revoke my-project --username alice --owner admin
```

---

## Generation ID Resolution

Many commands accept a **generation ID** (UUID) in place of a project name. When a UUID is detected, the CLI resolves it to the full variant coordinates (name, branch, provider, model, owner) via the `/api/projects/by-id/{id}` endpoint.

UUID format: canonical hyphenated form `8-4-4-4-12` (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

Commands that support generation ID lookup: `status`, `delete`, `abort`, `download`.

```bash
# These are equivalent (if the UUID maps to my-project/main/cursor/gpt-5.4-xhigh-fast)
docsfy status a1b2c3d4-e5f6-7890-abcd-ef1234567890
docsfy status my-project -b main -p cursor -m gpt-5.4-xhigh-fast
```

> **Tip:** Copy the generation ID from `docsfy generate` or `docsfy list` output to use with other commands.

---

## Output Formats

All listing and status commands support two output formats:

| Format | Flag | Description |
|---|---|---|
| Table | *(default)* | Human-readable, column-aligned table |
| JSON | `--json` | Machine-readable JSON for scripting and piping |

```bash
# Pipe JSON output to jq
docsfy list --json | jq '.[].name'

# Use in shell scripts
STATUS=$(docsfy status my-project --json | jq -r '.variants[0].status')
```

---

## Common Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Error (invalid input, server error, authentication failure, connection refused) |

All error messages are printed to **stderr**. Successful data output goes to **stdout**, making it safe to pipe output while still seeing errors.

---

## Related Pages

- [Using the CLI](using-the-cli.html) — Setup walkthrough, authentication, and workflow examples
- [Configuration Reference](configuration-reference.html) — Config file format, environment variables, and server settings
- [REST API Reference](api-reference.html) — The HTTP endpoints that the CLI communicates with
- [Managing Projects and Variants](managing-projects.html) — Conceptual overview of projects, branches, and variants
- [Managing Users and Access Control](managing-users.html) — User roles and access control concepts
- [Configuring AI Providers](configuring-ai-providers.html) — Available providers, models, and selection details

## Related Pages

- [Using the CLI](using-the-cli.html)
- [REST API Reference](api-reference.html)
- [Configuration Reference](configuration-reference.html)
- [Managing Users and Access Control](managing-users.html)
- [Managing Projects and Variants](managing-projects.html)