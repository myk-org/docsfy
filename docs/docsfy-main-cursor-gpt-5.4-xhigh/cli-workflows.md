# CLI Workflows

The `docsfy` CLI is the fastest way to work with a running docsfy server from a terminal. Use it to verify connectivity, start documentation generation, inspect variants, download finished sites, and manage users if you have admin access.

## Before You Start

You need:
- A running docsfy server
- A server URL
- An API key

If you use the built-in admin account, the username is `admin` and the API key is the server's `ADMIN_KEY`. If you use a normal account, an admin creates it and gives you the generated API key.

### Save a Reusable CLI Profile

Run the interactive setup once:

```shell
docsfy config init
```

You will be prompted for:

```text
Profile name [dev]:
Server URL: http://localhost:8800
Username: admin
Password:
```

When `docsfy` asks for `Password`, enter your API key.

The CLI stores profiles in `~/.config/docsfy/config.toml`. The structure looks like this:

```toml
[default]
server = "dev"

[servers.dev]
url = "http://localhost:8800"
username = "admin"
password = "<ADMIN_KEY>"
```

Useful follow-up commands:

```shell
docsfy config show
docsfy config set default.server prod
docsfy config set servers.prod.url https://prod.example.com
docsfy config set servers.prod.username admin
```

If you omit `--server`, docsfy uses the profile named in `[default].server`.

> **Note:** `docsfy config show` masks stored passwords, and the CLI writes the config file with owner-only permissions.

> **Tip:** Every command also accepts global connection options: `--server`, `--host`, `--port`, `--username`, and `--password`. For most day-to-day work, a saved profile is more convenient.

### Server Defaults That Affect the CLI

If you run your own server, these values come from the server environment:

```dotenv
ADMIN_KEY=
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
DATA_DIR=/data
SECURE_COOKIES=true
```

If you do not pass `--provider` or `--model` to `docsfy generate`, the server uses its configured `AI_PROVIDER` and `AI_MODEL`.

## Check Server Health

Use `health` first whenever you change config, switch environments, or suspect connectivity issues.

```shell
docsfy health
```

A healthy server responds with output like this:

```text
Server: http://localhost:8800
Status: ok
```

This command is useful for confirming that:
- your CLI is pointing at the server you expect
- the server is reachable
- the server is returning the expected health response

> **Tip:** If you see an error about no configured server, run `docsfy config init` or pass connection flags for a one-off check.

## Generate Documentation

Use `generate` to start a new documentation run for a Git repository.

The CLI takes a Git URL as its argument. HTTPS and SSH URLs are both supported, including forms like `https://github.com/org/repo.git` and `git@github.com:org/repo.git`.

### Start a Standard Generation

The simplest form relies on the server's default AI provider and model:

```shell
docsfy generate https://github.com/org/repo.git
```

If you want to pin the branch, provider, model, and force a full rebuild, use the full form:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force
```

The CLI prints the project name, branch, and initial status. In practice, that means the server accepted the request and queued the work.

Key options:
- `--branch` chooses the Git branch. If you omit it, docsfy uses `main`.
- `--provider` chooses the AI provider. Valid values are `claude`, `gemini`, and `cursor`.
- `--model` chooses the AI model name.
- `--force` skips reuse of existing cached/generated artifacts and does a full regeneration.

> **Warning:** Branch names cannot contain slashes. Use `release-v2.0` or `v2.0`, not `release/v2.0`.

### Watch Live Progress

Add `--watch` to keep the command attached and stream progress as the server works:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force --watch
```

While a generation is running, docsfy can report stages such as:
- `cloning`
- `planning`
- `incremental_planning`
- `generating_pages`
- `rendering`
- `up_to_date`

The watch session exits when the variant reaches a terminal state such as `ready`, `error`, or `aborted`.

> **Tip:** `--watch` is most predictable when you also pass `--provider` and `--model`, especially if your server has default model settings.

### When to Use `--force`

By default, docsfy can reuse existing plans, cached pages, or unchanged artifacts when the target variant is already up to date. Use `--force` when you want a clean full pass.

If you submit the same `project/branch/provider/model` while it is already generating, the server returns a conflict instead of starting a duplicate job.

## List Available Projects

Use `list` when you want a quick overview of everything you can access.

```shell
docsfy list
```

The table includes:
- `NAME`
- `BRANCH`
- `PROVIDER`
- `MODEL`
- `STATUS`
- `OWNER`
- `PAGES`

Each row is a variant, not just a repository name. A single project can appear multiple times if it has multiple branches or model/provider combinations.

Filter by status:

```shell
docsfy list --status ready
```

Filter by provider:

```shell
docsfy list --provider cursor
```

Get machine-readable output:

```shell
docsfy list --json
```

Common status values are `generating`, `ready`, `error`, and `aborted`.

> **Note:** Admins see all projects. Other accounts see their own projects plus any projects that were explicitly shared with them.

## Inspect One Project or One Variant

Use `status` when you want more detail than the list view gives you.

### Show All Variants for a Project

```shell
docsfy status for-testing-only
```

This prints the project name, the number of variants, and then a detail block for each variant. Depending on what exists, you may see fields such as:
- status
- owner
- page count
- last updated time
- short commit SHA
- current stage
- last error

This is the quickest way to answer questions like:
- Did my last run finish?
- Which model produced this version?
- How many pages were generated?
- Is a run still in `planning` or `generating_pages`?

### Filter or Target a Specific Variant

You can pass one or two filters, such as `--branch dev`, to narrow the printed list.

If you know the exact branch, provider, and model, pass all three together:

```shell
docsfy status for-testing-only --branch dev --provider gemini --model gemini-2.5-flash
```

That returns the detail for a single variant instead of the whole project.

### Use `--owner` When Admin Disambiguation Matters

If you are an admin and the same project or variant exists under multiple owners, add `--owner` when you want one specific match:

```shell
docsfy status shared-name --branch main --provider claude --model opus --owner alice
```

For a plain `docsfy status PROJECT`, you usually do not need `--owner` because docsfy shows all matching variants and includes the owner in the output.

For scripts:

```shell
docsfy status for-testing-only --json
```

`list --json` returns an array of variants. `status --json` returns either a project wrapper or a single variant object, depending on whether you fully specify `--branch`, `--provider`, and `--model`.

## Abort In-Progress Work

Use `abort` to stop a generation that is still running.

### Abort by Project Name

If there is only one active variant for that project, this is the simplest form:

```shell
docsfy abort my-repo
```

### Abort a Specific Variant

If more than one variant is active, target the exact one:

```shell
docsfy abort for-testing-only --branch main --provider gemini --model gemini-2.5-flash
```

For variant-specific aborts, pass `--branch`, `--provider`, and `--model` together. Admins can also add `--owner` when the same variant exists under more than one owner.

After aborting, confirm the result with:

```shell
docsfy status for-testing-only
```

> **Warning:** Plain `docsfy abort PROJECT` fails when multiple active variants match that name. In that case, rerun the command with `--branch`, `--provider`, and `--model`.

> **Note:** `abort` is a write action. `viewer` accounts can inspect and download docs, but they cannot generate, abort, or delete variants.

## Download Generated Artifacts

Use `download` to pull the generated static site to your machine.

### Download the Default Ready Variant

```shell
docsfy download test-repo
```

This downloads the most recently generated `ready` variant you can access and saves it in the current directory as:

```text
test-repo-docs.tar.gz
```

### Download One Exact Variant

If you want a specific branch/provider/model combination, specify it explicitly:

```shell
docsfy download test-repo --branch main --provider claude --model opus
```

That saves the archive using this pattern:

```text
<name>-<branch>-<provider>-<model>-docs.tar.gz
```

For exact-variant downloads, pass `--branch`, `--provider`, and `--model` together.

### Extract Directly into a Directory

Add `--output` to extract the archive immediately instead of keeping the `.tar.gz` file:

```shell
docsfy download test-repo --branch main --provider claude --model opus --output ./site
```

If `./site` does not exist yet, docsfy creates it for you.

> **Note:** `docsfy download PROJECT` chooses the newest ready variant available to you. If you care about the exact branch or model, pass `--branch`, `--provider`, and `--model`.

> **Warning:** Downloads only work for `ready` variants. If a run is still `generating`, or ended in `error` or `aborted`, check `docsfy status` first.

## Admin Workflows

The `admin` command group is for user and access management.

### List Users

```shell
docsfy admin users list
```

For scripts:

```shell
docsfy admin users list --json
```

The table includes each user's username, role, and creation time.

### Create a User

```shell
docsfy admin users create cli-test-user --role user
```

Valid roles are:
- `admin`
- `user`
- `viewer`

A successful create prints the new API key. Autogenerated keys use the `docsfy_...` format.

> **Warning:** Save the generated API key when you create or rotate a user. The CLI does not show it again later.

> **Note:** `viewer` is the read-only role. Viewers can inspect and download docs they can access, but they cannot start or stop generations.

Usernames have a few practical rules:
- `admin` is reserved
- names must be 2 to 50 characters long
- letters, numbers, dots, hyphens, and underscores are allowed

### Rotate a User's Key

Generate a new key automatically:

```shell
docsfy admin users rotate-key alice
```

For automation:

```shell
docsfy admin users rotate-key alice --json
```

If you want to set a custom key yourself, use `--new-key`. Custom keys must be at least 16 characters long.

Rotating a key invalidates that user's existing sessions, so they will need to authenticate again with the new key.

> **Note:** The built-in `admin` account is controlled by the server's `ADMIN_KEY` environment variable, not by `admin users rotate-key`.

### Delete a User

```shell
docsfy admin users delete cli-test-user --yes
```

Without `--yes`, docsfy prompts for confirmation.

You cannot delete your own account, and a delete is blocked while that user still has an active generation in progress.

### View Who Can Access a Project

```shell
docsfy admin access list my-repo --owner admin
```

This shows the usernames that currently have access to that project for that owner.

### Grant Access to a Project

```shell
docsfy admin access grant my-repo --username alice --owner admin
```

### Revoke Access

```shell
docsfy admin access revoke my-repo --username alice --owner admin
```

> **Note:** Access grants are owner-scoped and project-wide. In other words, you grant access to all variants of `my-repo` owned by `admin`, not just one branch or model.

## Common CLI Errors

- `No server configured`: run `docsfy config init`, or pass connection options such as `--server`.
- `Write access required`: the authenticated account is a `viewer`.
- `Variant not ready`: the target variant is not in `ready` state yet. Use `docsfy status PROJECT`.
- `Multiple active variants found; use the branch-specific abort endpoint.`: rerun `docsfy abort` with `--branch`, `--provider`, and `--model`.
- `Multiple owners found for this variant, please specify owner`: rerun the exact-variant command with `--owner`.
- `No projects found.`: the account has no owned projects and no granted access yet.
