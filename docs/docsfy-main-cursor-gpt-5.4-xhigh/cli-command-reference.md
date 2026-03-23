# CLI Command Reference

`docsfy` is the command-line client for a running docsfy server. You use it to save connection profiles, start documentation generation, inspect existing outputs, download generated sites, and perform admin-only user and access management.

In docsfy, a _variant_ is one `project / branch / provider / model` combination. In admin or shared-access setups, the same project name can exist under different owners, which is why some commands also support `--owner`.

Permissions at a glance:
- `list`, `status`, and `download` are read-oriented commands for projects you own or have been granted access to.
- `generate`, `delete`, and `abort` require a `user` or `admin` account.
- `admin ...` commands require admin access.

Examples on this page are taken from the repository's CLI tests and sample config.

## Command Summary

| Command | What it does |
| --- | --- |
| `config` | Manage saved server profiles in `~/.config/docsfy/config.toml` |
| `generate` | Start documentation generation for a Git repository |
| `list` | Show accessible projects and variants |
| `status` | Show detailed status for one project or one exact variant |
| `delete` | Delete a single variant or all variants of a project |
| `abort` | Stop an active generation run |
| `download` | Download a generated docs site as a tarball, or extract it to a directory |
| `admin users ...` | List, create, delete, and rotate user API keys |
| `admin access ...` | Grant, revoke, and inspect project access for other users |

## Global Connection Options

All commands share the same connection options. The CLI resolves them in this order:

1. Explicit CLI flags such as `--host`, `--username`, and `--password`
2. A named profile selected with `--server`
3. The default profile from `[default].server` in `~/.config/docsfy/config.toml`
4. An error if nothing is configured

| Option | Meaning |
| --- | --- |
| `--server`, `-s` | Use a named server profile from the config file |
| `--host` | Override the host from the selected profile |
| `--port` | Override the port when `--host` is used |
| `--username`, `-u` | Override the configured username |
| `--password`, `-p` | Override the configured password/API key |

> **Note:** In CLI config and flags, the field is named `password`, but for docsfy this value is your API key.

> **Note:** Global options go before the subcommand. That matters because `-p` is reused: before the subcommand it means API key, but after commands like `status`, `delete`, `abort`, and `download` it means `--provider`.

> **Tip:** If you use `--host`, the CLI builds a full URL from host and port. The port defaults to `8000`, and the scheme comes from the selected profile when available; otherwise it defaults to `https`.

## `config`

`docsfy config` manages the CLI config file at `~/.config/docsfy/config.toml`.

A sample config from the repository:

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

[servers.staging]
url = "https://staging.docsfy.example.com"
username = "deployer"
password = "<your-staging-key>"
```

> **Warning:** This file contains credentials. The CLI writes it with owner-only permissions, and you should keep it private.

### `config init`

`docsfy config init` is the interactive setup flow. It prompts for:

- Profile name, defaulting to `dev`
- Server URL
- Username
- Password/API key

If you are creating the first profile, it also becomes the default server. If you add another profile later, the existing default stays in place until you change it.

```shell
docsfy config init
```

### `config show`

`docsfy config show` prints the config file path, the current default profile, and each saved profile with its password/API key masked.

```shell
docsfy config show
```

### `config set`

`docsfy config set` writes nested TOML keys directly.

```shell
docsfy config set default.server prod
docsfy config set servers.dev.url https://new-server.com
```

Use it when you want to switch the default profile or update individual fields without re-running `config init`.

> **Note:** `config set` expects dotted keys such as `default.server`, `servers.dev.url`, and `servers.dev.username`. It does not use shorthand keys like `server` or `api-key`.

## `generate`

`docsfy generate` starts documentation generation for a remote Git repository.

The project name used by later commands is derived from the repository name. For example:

- `https://github.com/myk-org/for-testing-only` becomes `for-testing-only`
- `https://github.com/org/my-repo.git` becomes `my-repo`
- `git@github.com:org/repo.git` becomes `repo`

Common options:
- `--branch`, `-b`: Git branch to generate from. Defaults to `main`.
- `--provider`: AI provider. Valid values in this codebase are `claude`, `gemini`, and `cursor`.
- `--model`, `-m`: AI model name.
- `--force`, `-f`: Force a full regeneration instead of reusing cached artifacts.
- `--watch`, `-w`: Stream live generation progress.

Examples:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force --watch
```

What you can expect:
- The CLI prints the derived project name, resolved branch, and initial status.
- With `--watch`, it listens for live progress updates such as `cloning`, `planning`, `incremental_planning`, `generating_pages`, and `rendering`.
- Final statuses are `ready`, `error`, or `aborted`.

> **Tip:** `generate` takes a repository URL, but `status`, `delete`, `abort`, and `download` use the derived project name. For `https://github.com/myk-org/for-testing-only`, that name is `for-testing-only`.

> **Note:** If you omit `--provider` or `--model`, the server default is used. In this codebase the current defaults are `cursor` and `gpt-5.4-xhigh-fast`, but deployments can override them.

> **Tip:** When using `--watch`, pass both `--provider` and `--model` explicitly so the CLI can subscribe to the exact variant immediately.

> **Warning:** Branch names cannot contain slashes. Use names like `release-1.x`, not `release/1.x`.

> **Warning:** The CLI `generate` command expects a Git repository URL, not a local filesystem path. The validated URL shapes are standard HTTPS remotes like `https://github.com/org/repo.git` and SSH remotes like `git@github.com:org/repo.git`.

## `list`

`docsfy list` shows the accessible projects and variants in a table. The table includes these columns:

- `NAME`
- `BRANCH`
- `PROVIDER`
- `MODEL`
- `STATUS`
- `OWNER`
- `PAGES`

Examples:

```shell
docsfy list
docsfy list --status ready
docsfy list --provider cursor
docsfy list --json
```

Use `--status` and `--provider` to narrow the result set before printing. In practice, project statuses used by the codebase are `generating`, `ready`, `error`, and `aborted`.

For non-admin users, `list` includes projects you own plus projects that have been shared with you. For admins, it shows everything.

## `status`

`docsfy status` shows detailed information for one project.

With just the project name, it shows all matching variants you can access. If you provide `--branch`, `--provider`, and `--model` together, it fetches one exact variant instead.

Examples:

```shell
docsfy status for-testing-only
docsfy status my-repo -b main -p cursor -m gpt-5
```

Useful fields in the output include:
- Status
- Owner
- Page count
- Last generated time
- Short commit SHA
- Current stage
- Error message, when present

> **Note:** `--owner` is mainly useful for admins when you are querying one fully qualified variant and need to disambiguate between multiple owners.

> **Tip:** If you want one exact variant, provide all three selectors together: `--branch`, `--provider`, and `--model`.

## `delete`

`docsfy delete` removes either one exact variant or every variant for a project.

Common options:
- `--branch`, `-b`: Variant branch
- `--provider`, `-p`: Variant provider
- `--model`, `-m`: Variant model
- `--owner`: Project owner, required for admin deletion of someone else's project
- `--all`: Delete all variants for the project
- `--yes`, `-y`: Skip the confirmation prompt

Examples:

```shell
docsfy delete for-testing-only --branch dev --provider gemini --model gemini-2.0-flash --yes
docsfy delete my-repo --all --yes
```

If you leave off `--yes`, the CLI asks for confirmation before deleting anything.

> **Warning:** Use either `--all` or the full variant selector (`--branch`, `--provider`, and `--model`). Do not combine them.

> **Warning:** The server refuses deletion while generation is in progress. Abort the running variant first, then retry the delete.

## `abort`

`docsfy abort` stops an active generation run.

You can use it in two ways:
- By project name alone, if there is only one active generation for that project
- By exact variant, using `--branch`, `--provider`, and `--model`

Examples:

```shell
docsfy abort my-repo
docsfy abort for-testing-only --branch main --provider gemini --model gemini-2.5-flash
```

When the abort succeeds, the variant ends up in `aborted` status.

> **Tip:** If more than one active variant exists for the same project name, the project-level form is ambiguous. In that case, retry with `--branch`, `--provider`, and `--model`. Admins may also need `--owner` for someone else's variant.

## `download`

`docsfy download` fetches generated documentation for a project.

You can use it in two modes:
- Without variant selectors: download the latest ready variant you can access
- With `--branch`, `--provider`, and `--model`: download one exact variant

Common options:
- `--branch`, `-b`: Variant branch
- `--provider`, `-p`: Variant provider
- `--model`, `-m`: Variant model
- `--owner`: Useful for admins when downloading a specific variant owned by someone else
- `--output`, `-o`: Extract into a directory instead of saving a tarball in the current directory

Example:

```shell
docsfy download my-repo -b main -p cursor -m gpt-5
```

Archive naming:
- Exact variant download: `<project>-<branch>-<provider>-<model>-docs.tar.gz`
- Project-level download: `<project>-docs.tar.gz`

When you pass `--output`, the CLI creates the directory if needed, downloads the archive to a temporary file, and extracts it there.

> **Tip:** If a project has multiple variants, or if you are an admin working across multiple owners, prefer the fully qualified form with `--branch`, `--provider`, and `--model` so you know exactly which archive you are getting.

> **Warning:** Only ready variants can be downloaded.

## `admin`

All `admin` subcommands require admin credentials.

### `admin users`

`admin users` manages docsfy accounts. Valid roles are:
- `admin`
- `user`
- `viewer`

Examples:

```shell
docsfy admin users list
docsfy admin users create cli-test-user --role user
docsfy admin users delete cli-test-user --yes
docsfy admin users rotate-key alice
```

What each subcommand does:
- `list`: Show all users in a table, or JSON with `--json`
- `create`: Create a user and print the generated API key; `--role` defaults to `user`
- `delete`: Delete a user; prompts unless you pass `--yes`
- `rotate-key`: Rotate a user's API key; use `--new-key` to provide your own key, or omit it to generate one automatically

Practical details:
- Usernames must be 2-50 characters, start with an alphanumeric character, and may include `.`, `_`, and `-`
- The username `admin` is reserved
- Deleting a user also removes their sessions, owned projects, and related access grants
- Rotating a key invalidates that user's existing sessions

> **Warning:** `create` and `rotate-key` show the API key only once. Save it immediately.

> **Warning:** You cannot delete your own admin account, and the server blocks deleting a user while they have a generation in progress.

### `admin access`

`admin access` manages project sharing. Access is project-level and owner-scoped, which means a grant applies to all variants of that project for that owner.

Examples:

```shell
docsfy admin access list my-repo --owner admin
docsfy admin access grant my-repo --username alice --owner admin
docsfy admin access revoke my-repo --username alice --owner admin
```

What each subcommand does:
- `list`: Show which users currently have access to a project; supports `--json`
- `grant`: Give a user access to a project owned by a specific owner
- `revoke`: Remove that access again

> **Note:** `--owner` is required on all `admin access` commands, because project sharing is scoped to a specific owner.

## JSON Output and Exit Behavior

Commands that support `--json`:
- `docsfy list`
- `docsfy status`
- `docsfy admin users list`
- `docsfy admin users create`
- `docsfy admin users rotate-key`
- `docsfy admin access list`

When scripting:
- `docsfy list --json` returns an array of project objects
- `docsfy status --json` returns either one variant object or a `{name, variants}` object, depending on whether you fully qualified the variant
- HTTP and API failures are printed as `Error (<status>): ...` and return a non-zero exit code
- If you decline a confirmation prompt, the CLI prints `Aborted.` and exits without making changes
