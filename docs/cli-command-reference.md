# CLI Command Reference

## `docsfy`
**Syntax:** `docsfy [GLOBAL OPTIONS] COMMAND [ARGS]...`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--server`, `-s` | string | none | Use a saved profile from `~/.config/docsfy/config.toml`. |
| `--host` | string | none | Override the profile host. When set, the CLI builds `scheme://host:port`; the scheme comes from the selected profile when available, otherwise `https`. |
| `--port` | integer | `8000` when `--host` is used | Port used with `--host`. |
| `--username`, `-u` | string | none | Override the profile username. |
| `--password`, `-p` | string | none | Override the profile password/API key sent as the bearer token. |

```shell
docsfy --server prod status my-repo
docsfy --host docsfy.example.com --port 443 -u admin -p <API_KEY> health
```

Return value / effect:
- Dispatches to `health`, `config`, `generate`, `list`, `status`, `delete`, `abort`, `download`, `models`, or `admin`.
- With no subcommand, prints help.
- Applies the resolved connection settings to the selected subcommand.

> **Note:** Connection resolution order is explicit CLI flags, then `--server`, then `[default].server` in `~/.config/docsfy/config.toml`, then an error if nothing is configured.

> **Note:** Put global options before the subcommand. After commands such as `status`, `delete`, `abort`, and `download`, `-p` means `--provider`, not API key.

## `docsfy health`
**Syntax:** `docsfy [GLOBAL OPTIONS] health`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| None | - | - | No command-specific parameters or options. Use global connection options before `health`. |

```shell
docsfy --server dev health
docsfy --host localhost --port 8000 -u admin -p <API_KEY> health
```

Return value / effect:
- Calls the server `/health` endpoint.
- Prints `Server: <url>` and `Status: <value>`.
- Exits non-zero if the server is unreachable, returns an HTTP error, or responds with non-JSON content.

## `docsfy config`
`docsfy config` is the CLI configuration command group for `~/.config/docsfy/config.toml`.

| Subcommand | Description |
| --- | --- |
| `docsfy config init` | Create or add a profile interactively. |
| `docsfy config show` | Print saved profiles with masked passwords. |
| `docsfy config set` | Update one dotted key in the config file. |

> **Warning:** `~/.config/docsfy/config.toml` stores raw API keys.

### `docsfy config init`
**Syntax:** `docsfy config init`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `Profile name` | string | `dev` | Profile name stored under `[servers.<profile>]`. |
| `Server URL` | string | none | Full server URL, such as `https://docsfy.example.com`. |
| `Username` | string | none | Username saved with the profile. |
| `Password` | string | none | API key saved in the profile as `password`. Input is hidden. |

```shell
docsfy config init
# Profile name [dev]: prod
# Server URL: https://docsfy.example.com
# Username: admin
# Password: <API_KEY>
```

Return value / effect:
- Creates `~/.config/docsfy/config.toml` if it does not exist.
- Writes the config directory with owner-only permissions and the file with owner read/write permissions.
- Adds `[servers.<profile>]`.
- Sets `[default].server` only when no default profile exists yet.
- Prints `Profile '<profile>' saved to ~/.config/docsfy/config.toml`.

### `docsfy config show`
**Syntax:** `docsfy config show`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| None | - | - | No command-specific parameters or options. |

```shell
docsfy config show
```

Return value / effect:
- Prints the config file path.
- Prints the current default server profile.
- Prints each saved profile with `URL`, `Username`, and a masked `Password`.
- Exits non-zero if the config file is missing or invalid TOML.

### `docsfy config set`
**Syntax:** `docsfy config set KEY VALUE`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `KEY` | string | Required | Dotted config key. Accepted prefixes are `default.` and `servers.`. |
| `VALUE` | string | Required | Value written to the selected key. |

```shell
docsfy config set default.server prod
docsfy config set servers.prod.url https://docsfy.example.com
docsfy config set servers.prod.password <API_KEY>
```

Return value / effect:
- Updates one config value and prints `Updated <KEY>`.
- Creates missing intermediate tables on the path to `KEY`.
- Exits non-zero if the config file does not exist.
- Exits non-zero if `KEY` does not start with `default.` or `servers.`.

> **Warning:** `docsfy config set` writes the TOML key directly. It does not verify that a referenced profile exists.

## Project Commands
> **Note:** `generate`, `delete`, and `abort` require a `user` or `admin` account. `list`, `status`, `download`, and `models` are read-oriented commands.

### `docsfy generate`
**Syntax:** `docsfy [GLOBAL OPTIONS] generate REPO_URL [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `REPO_URL` | string | Required | Remote Git URL. Accepted forms include `https://host/org/repo`, `https://host/org/repo.git`, `git@host:org/repo`, and `git@host:org/repo.git`. |
| `--branch`, `-b` | string | `main` | Git branch to generate. Branch names cannot contain `/`. |
| `--provider` | string | server default | AI provider. Valid values in this codebase are `claude`, `gemini`, and `cursor`. |
| `--model`, `-m` | string | server default | AI model name. |
| `--force`, `-f` | boolean | `false` | Force a full regeneration instead of reusing cached artifacts. |
| `--watch`, `-w` | boolean | `false` | Stream live generation progress over WebSocket after the request starts. |

```shell
docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force --watch
```

Return value / effect:
- Starts generation and prints `Project`, `Branch`, and `Status`.
- Uses the repository name as the stored project name for later commands.
- With `--watch`, prints progress updates until the variant reaches `ready`, `error`, or `aborted`.
- Exits non-zero on validation, HTTP, or WebSocket errors.

> **Note:** When `--provider` or `--model` is omitted, the server default is used. In this repository, the code defaults are `cursor` and `gpt-5.4-xhigh-fast`, but deployments can override them.

> **Tip:** When using `--watch`, pass both `--provider` and `--model` so the CLI can subscribe to the exact variant immediately.

> **Warning:** The CLI `generate` command accepts remote Git URLs only. Local filesystem paths are not a CLI argument.

> **Warning:** Repository URLs that target `localhost` or private-network addresses are rejected by the server.

### `docsfy list`
**Syntax:** `docsfy [GLOBAL OPTIONS] list [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--status` | string | all statuses | Filter by stored status value. The codebase uses `generating`, `ready`, `error`, and `aborted`. |
| `--provider` | string | all providers | Filter by AI provider. |
| `--json` | boolean | `false` | Output JSON instead of the table view. |

```shell
docsfy list --status ready --provider cursor
docsfy list --json
```

Return value / effect:
- Prints a table with `NAME`, `BRANCH`, `PROVIDER`, `MODEL`, `STATUS`, `OWNER`, and `PAGES`.
- `--json` outputs an array of project/variant objects.
- Includes projects the user owns and projects shared with the user.
- Prints `No projects found.` when nothing matches.

### `docsfy status`
**Syntax:** `docsfy [GLOBAL OPTIONS] status NAME [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `NAME` | string | Required | Stored project name, such as `for-testing-only`. |
| `--branch`, `-b` | string | all branches | Filter by branch. When combined with `--provider` and `--model`, targets one exact variant. |
| `--provider`, `-p` | string | all providers | Filter by provider. When combined with `--branch` and `--model`, targets one exact variant. |
| `--model`, `-m` | string | all models | Filter by model. When combined with `--branch` and `--provider`, targets one exact variant. |
| `--owner` | string | none | Owner disambiguation for exact variant lookups. |
| `--json` | boolean | `false` | Output JSON instead of plain text. |

```shell
docsfy status for-testing-only
docsfy status for-testing-only --branch main --provider cursor --model gpt-5 --json
```

Return value / effect:
- With only `NAME`, prints all accessible variants for that project.
- With `--branch`, `--provider`, and `--model` together, prints one exact variant.
- Plain text output can include `Status`, `Owner`, `Pages`, `Updated`, short `Commit`, `Stage`, and `Error`.
- `--json` outputs either `{ "name": NAME, "variants": [...] }` or a single variant object.
- Prints `No variants found for '<NAME>'.` when filters remove every result.

> **Note:** `--owner` is used only when `--branch`, `--provider`, and `--model` are all present. It does not change the broad project view.

> **Tip:** `status` accepts partial filters. `--branch` alone, `--provider` alone, and other partial combinations are valid.

### `docsfy delete`
**Syntax:** `docsfy [GLOBAL OPTIONS] delete NAME [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `NAME` | string | Required | Stored project name. |
| `--branch`, `-b` | string | none | Variant branch. Must be used with `--provider` and `--model` for exact variant deletion. |
| `--provider`, `-p` | string | none | Variant provider. Must be used with `--branch` and `--model` for exact variant deletion. |
| `--model`, `-m` | string | none | Variant model. Must be used with `--branch` and `--provider` for exact variant deletion. |
| `--owner` | string | none | Required for admin delete requests. Ignored for non-admin users. |
| `--all` | boolean | `false` | Delete all variants for the project within one owner scope. |
| `--yes`, `-y` | boolean | `false` | Skip the confirmation prompt. |

```shell
docsfy delete for-testing-only --branch dev --provider gemini --model gemini-2.0-flash --yes
docsfy delete my-repo --all --yes
```

Return value / effect:
- Deletes one exact variant when `--branch`, `--provider`, and `--model` are all present.
- Deletes all variants for one project/owner scope when `--all` is set.
- Prompts for confirmation unless `--yes` is used.
- Prints `Deleted variant '<name>/<branch>/<provider>/<model>'.` or `Deleted all variants of '<name>'.`
- Exits non-zero if the target is missing, still generating, or invalidly specified.

> **Warning:** Use either `--all` or the full variant selector. Do not combine them.

> **Warning:** Admin deletes require `--owner`, even when the branch, provider, and model are fully specified.

### `docsfy abort`
**Syntax:** `docsfy [GLOBAL OPTIONS] abort NAME [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `NAME` | string | Required | Stored project name. |
| `--branch`, `-b` | string | none | Variant branch. Must be supplied together with `--provider` and `--model` for exact variant aborts. |
| `--provider`, `-p` | string | none | Variant provider. Must be supplied together with `--branch` and `--model` for exact variant aborts. |
| `--model`, `-m` | string | none | Variant model. Must be supplied together with `--branch` and `--provider` for exact variant aborts. |
| `--owner` | string | none | Owner disambiguation for exact variant aborts. |

```shell
docsfy abort my-repo
docsfy abort for-testing-only --branch main --provider gemini --model gemini-2.5-flash
```

Return value / effect:
- With only `NAME`, aborts the single active generation for that project name.
- With the full selector, aborts that exact variant.
- Prints `Aborted generation for '<name>'.` or `Aborted generation for '<name>/<branch>/<provider>/<model>'.`
- Successful aborts transition the variant to `aborted`.
- Exits non-zero if the target is not generating, ambiguously specified, or unavailable.

> **Warning:** Project-level abort fails when more than one active variant matches the same project name.

> **Note:** `--owner` only affects fully qualified variant aborts. It does not change project-level aborts.

### `docsfy download`
**Syntax:** `docsfy [GLOBAL OPTIONS] download NAME [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `NAME` | string | Required | Stored project name. |
| `--branch`, `-b` | string | none | Variant branch. Must be supplied together with `--provider` and `--model` for exact variant downloads. |
| `--provider`, `-p` | string | none | Variant provider. Must be supplied together with `--branch` and `--model` for exact variant downloads. |
| `--model`, `-m` | string | none | Variant model. Must be supplied together with `--branch` and `--provider` for exact variant downloads. |
| `--owner` | string | none | Owner disambiguation for exact variant downloads. |
| `--output`, `-o` | string | none | Extract into a directory instead of saving a `.tar.gz` archive in the current directory. |

```shell
docsfy download my-repo
docsfy download my-repo --branch main --provider cursor --model gpt-5 --output ./site
```

Return value / effect:
- With no variant selector, downloads the latest ready variant visible to the user.
- With the full selector, downloads that exact variant.
- Without `--output`, saves an archive in the current directory.
- With `--output`, creates the directory if needed, downloads to a temporary archive, and extracts the archive there.
- Prints `Downloaded to <path>` or `Extracted to <dir>`.

Archive naming:
- Project-level download: `<project>-docs.tar.gz`
- Exact variant download: `<project>-<branch>-<provider>-<model>-docs.tar.gz`

> **Warning:** Only `ready` variants can be downloaded.

> **Warning:** Use all three variant selectors together or omit all three.

> **Note:** `--owner` only affects fully qualified variant downloads. It does not change project-level downloads.

### `docsfy models`
**Syntax:** `docsfy [GLOBAL OPTIONS] models [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--provider`, `-P` | string | all providers | Filter to one provider. Valid providers in this codebase are `claude`, `gemini`, and `cursor`. |
| `--json`, `-j` | boolean | `false` | Output JSON instead of plain text. |

```shell
docsfy models
docsfy models --provider cursor --json
```

Return value / effect:
- Plain text output groups known models under each provider.
- Marks the current default provider and default model with `(default)`.
- Shows `(no models used yet)` for providers with no completed ready variants.
- `--json` outputs `{ "providers": [...], "default_provider": "...", "default_model": "...", "known_models": {...} }`.
- With `--provider`, output is filtered to one provider. In JSON mode, `default_provider` and `default_model` remain present even when the provider list is filtered.
- Exits non-zero for an unknown provider.

> **Note:** `known_models` is built from ready variants only.

## `docsfy admin`
`docsfy admin` is the admin-only command group.

| Group | Subcommands |
| --- | --- |
| `docsfy admin users` | `list`, `create`, `delete`, `rotate-key` |
| `docsfy admin access` | `list`, `grant`, `revoke` |

> **Warning:** All `admin ...` commands require admin credentials.

### `docsfy admin users list`
**Syntax:** `docsfy [GLOBAL OPTIONS] admin users list [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--json` | boolean | `false` | Output JSON instead of the table view. |

```shell
docsfy admin users list
docsfy admin users list --json
```

Return value / effect:
- Prints a table with `USERNAME`, `ROLE`, and `CREATED`.
- `--json` outputs an array of user objects with `id`, `username`, `role`, and `created_at`.
- Prints `No users found.` when the user list is empty.

### `docsfy admin users create`
**Syntax:** `docsfy [GLOBAL OPTIONS] admin users create USERNAME [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `USERNAME` | string | Required | Username to create. Must be 2-50 characters, start with an alphanumeric character, and use only alphanumerics, `.`, `_`, or `-`. |
| `--role`, `-r` | string | `user` | User role. Valid values are `admin`, `user`, and `viewer`. |
| `--json` | boolean | `false` | Output JSON instead of plain text. |

```shell
docsfy admin users create alice --role viewer
docsfy admin users create alice --role user --json
```

Return value / effect:
- Creates the user account.
- Plain text output prints `User created`, `Role`, and `API Key`.
- `--json` outputs `{ "username": "...", "api_key": "...", "role": "..." }`.
- Exits non-zero for invalid usernames, duplicate usernames, reserved usernames, or invalid roles.

> **Warning:** The username `admin` is reserved.

> **Warning:** The API key is shown once. Save it immediately.

### `docsfy admin users delete`
**Syntax:** `docsfy [GLOBAL OPTIONS] admin users delete USERNAME [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `USERNAME` | string | Required | Username to delete. |
| `--yes`, `-y` | boolean | `false` | Skip the confirmation prompt. |

```shell
docsfy admin users delete alice --yes
```

Return value / effect:
- Prompts for confirmation unless `--yes` is used.
- Deletes the user account.
- Deletes that user's sessions, owned projects, and related access grants.
- Prints `Deleted user '<username>'.` on success.
- Exits non-zero when the user is missing or cannot be deleted.

> **Warning:** You cannot delete your own admin account.

> **Warning:** A user cannot be deleted while one of their generations is still in progress.

### `docsfy admin users rotate-key`
**Syntax:** `docsfy [GLOBAL OPTIONS] admin users rotate-key USERNAME [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `USERNAME` | string | Required | Username whose API key will be rotated. |
| `--new-key` | string | auto-generated key | Set a specific replacement API key. Custom keys must be at least 16 characters long. |
| `--json` | boolean | `false` | Output JSON instead of plain text. |

```shell
docsfy admin users rotate-key alice
docsfy admin users rotate-key alice --new-key "my-very-secure-custom-password-123" --json
```

Return value / effect:
- Generates a new API key when `--new-key` is omitted.
- Uses the supplied key when `--new-key` is present and valid.
- Invalidates the user's existing sessions.
- Plain text output prints `User` and `New API Key`.
- `--json` outputs `{ "username": "...", "new_api_key": "..." }`.

> **Warning:** The new API key is shown once. Save it immediately.

### `docsfy admin access list`
**Syntax:** `docsfy [GLOBAL OPTIONS] admin access list PROJECT [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `PROJECT` | string | Required | Stored project name. |
| `--owner` | string | Required | Owner whose project access list should be shown. |
| `--json` | boolean | `false` | Output JSON instead of plain text. |

```shell
docsfy admin access list my-repo --owner admin
docsfy admin access list my-repo --owner admin --json
```

Return value / effect:
- Prints the project name, owner, and current access list.
- Prints `No access grants.` when the list is empty.
- `--json` outputs `{ "project": "...", "owner": "...", "users": [...] }`.

> **Note:** Access grants are project-level and owner-scoped. One grant covers all variants of that project for the specified owner.

### `docsfy admin access grant`
**Syntax:** `docsfy [GLOBAL OPTIONS] admin access grant PROJECT [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `PROJECT` | string | Required | Stored project name. |
| `--username` | string | Required | Username to grant access to. |
| `--owner` | string | Required | Owner whose project will be shared. |

```shell
docsfy admin access grant my-repo --username alice --owner admin
```

Return value / effect:
- Grants the named user access to the project for the specified owner.
- The grant applies to all variants of that project for that owner.
- Prints `Granted '<username>' access to '<project>' (owner: <owner>).`
- Exits non-zero if the user does not exist or the project does not exist for that owner.

### `docsfy admin access revoke`
**Syntax:** `docsfy [GLOBAL OPTIONS] admin access revoke PROJECT [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `PROJECT` | string | Required | Stored project name. |
| `--username` | string | Required | Username whose access will be removed. |
| `--owner` | string | Required | Owner whose project access grant will be removed. |

```shell
docsfy admin access revoke my-repo --username alice --owner admin
```

Return value / effect:
- Removes the named user's access grant for that project and owner.
- Prints `Revoked '<username>' access to '<project>' (owner: <owner>).`

## Shared Exit Behavior

| Condition | Effect |
| --- | --- |
| HTTP `4xx` / `5xx` | Prints `Error (<status>): <detail>` to stderr and exits non-zero. |
| HTTP redirect | Prints a redirect error and exits non-zero. |
| `health` connection failure | Prints `Server unreachable: ...` and exits non-zero. |
| `generate --watch` WebSocket timeout or close | Prints an error to stderr and exits non-zero. |
| Confirmation declined | Prints `Aborted.` and exits without changing server state. |

Commands with JSON output:
- `docsfy list`
- `docsfy status`
- `docsfy models`
- `docsfy admin users list`
- `docsfy admin users create`
- `docsfy admin users rotate-key`
- `docsfy admin access list`

## Related Pages

- [Manage docsfy from the CLI](manage-docsfy-from-the-cli.html)
- [Generate Documentation](generate-documentation.html)
- [Track Generation Progress](track-generation-progress.html)
- [View, Download, and Publish Docs](view-download-and-publish-docs.html)
- [Manage Users, Roles, and Access](manage-users-roles-and-access.html)