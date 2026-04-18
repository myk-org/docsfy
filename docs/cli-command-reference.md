# CLI Command Reference

> **Tip:** For task-oriented command sequences, see [Managing docsfy from the CLI](manage-docsfy-from-the-cli.html).

## Global Command

### `docsfy`

Root command for all CLI operations.

**Syntax:** `docsfy [GLOBAL OPTIONS] <command> [ARGS] [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--server`, `-s` | string | `None` | Server profile name from `~/.config/docsfy/config.toml`. |
| `--host` | string | `None` | Overrides the configured host. Builds the URL as `<scheme>://<host>:<port>`. |
| `--port` | integer | `8000` when `--host` is used | Overrides the port used with `--host`. |
| `--username`, `-u` | string | `None` | Stored connection username. The CLI resolves and stores it, but requests authenticate with the password/API key bearer token. |
| `--password`, `-p` | string | `None` | Password or API key sent as `Authorization: Bearer <value>`. |

> **Note:** Put global options before the subcommand. In `docsfy -p <API_KEY> health`, `-p` means global `--password`. In `docsfy status my-repo -p cursor`, `-p` means command-level `--provider`.


> **Note:** Connection resolution order is: explicit global flags, then `--server`, then `[default].server` in `~/.config/docsfy/config.toml`.


> **Note:** Server-backed commands print `Error: Server redirected to <location>. Check the server URL.` for redirects, or `Error (<status>): <detail>` for HTTP errors, then exit `1`.

```shell
$ docsfy --server prod health
Server: https://docs.example.com
Status: ok
```

**Return value/effect:**
- Running `docsfy` with no arguments prints help.
- If `--host` is used without `--port`, the CLI uses port `8000`.
- If `--host` is used with a selected profile whose URL starts with `http://`, the generated URL keeps `http`; otherwise it uses `https`.
- If no connection can be resolved, the CLI exits `1`.

## Configuration Commands

> **Note:** These commands read and write `~/.config/docsfy/config.toml`. See [Configuration Reference](configuration-reference.html) for the file layout.

### `docsfy config init`

Creates or updates a server profile interactively.

**Syntax:** `docsfy config init`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `Profile name` | prompt/string | `dev` | Profile key written under `servers.<profile>`. |
| `Server URL` | prompt/string | Required | Base docsfy server URL. |
| `Username` | prompt/string | Required | Username stored with the profile. |
| `Password` | prompt/string | Required | Password or API key stored with hidden input. |

```shell
$ docsfy config init
Profile name [dev]: prod
Server URL: https://docs.example.com
Username: admin
Password:
Profile 'prod' saved to /home/alice/.config/docsfy/config.toml
```

**Return value/effect:**
- Writes `~/.config/docsfy/config.toml`.
- Creates `~/.config/docsfy` with owner-only permissions and writes the file with owner read/write only.
- The first saved profile becomes `[default].server`.
- Adding later profiles does not change the existing default automatically.

### `docsfy config show`

Prints the current config file and all saved profiles.

**Syntax:** `docsfy config show`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `—` | `—` | `—` | No positional arguments or command-specific options. |

```shell
$ docsfy config show
Config file: /home/alice/.config/docsfy/config.toml
Default server: dev

[dev] (default)
  URL:      https://docs.example.com
  Username: admin
  Password: se***
```

**Return value/effect:**
- Prints the config file path, default server, and each configured profile.
- Masks passwords as the first 2 characters plus `***`; passwords 2 characters or shorter print as `***`.
- Exits `1` if the config file is missing.
- Exits `1` if the config file exists but is invalid TOML.

### `docsfy config set`

Writes a single dotted config key.

**Syntax:** `docsfy config set <key> <value>`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `key` | string | Required | Dotted config key. Must start with `default.` or `servers.`. |
| `value` | string | Required | Value written to the target key. |
| `default.server` | config key | `None` | Sets the default profile name. |
| `servers.<profile>.url` | config key | `None` | Sets a profile's server URL. |
| `servers.<profile>.username` | config key | `None` | Sets a profile's username. |
| `servers.<profile>.password` | config key | `None` | Sets a profile's password or API key. |

```shell
$ docsfy config set default.server prod
Updated default.server

$ docsfy config set servers.prod.url https://docs.example.com
Updated servers.prod.url
```

**Return value/effect:**
- Writes the updated config file to disk.
- Creates missing nested dictionaries along the dotted key path.
- Accepts any dotted key under `default.` or `servers.` and writes it as-is.
- Exits `1` if the config file is missing.
- Exits `1` if `key` does not start with `default.` or `servers.`.

## Project Commands

> **Note:** `status`, `abort`, `delete`, and `download` accept either a project name or a canonical generation ID (UUID). A generation ID resolves to the exact variant before the command runs.


> **Warning:** `generate`, `abort`, and `delete` require write access. Keys with the `viewer` role receive `403 Write access required.`

### `docsfy health`

Checks whether the configured server responds to `/health`.

**Syntax:** `docsfy health`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `—` | `—` | `—` | No positional arguments or command-specific options. |

```shell
$ docsfy health
Server: https://docs.example.com
Status: ok
```

**Return value/effect:**
- Prints `Server: <resolved-url>`.
- Prints `Status: <status>` when the server returns JSON.
- If the server responds with non-JSON, prints the HTTP status and the first 200 characters of the response body, then exits `1`.
- If the server cannot be reached, prints `Server unreachable: <exception>` and exits `1`.

### `docsfy generate`

Starts documentation generation for a remote Git repository.

**Syntax:** `docsfy generate <repo-url> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `repo-url` | string | Required | Remote Git URL. Accepted forms are `https://host/org/repo(.git)` and `git@host:org/repo(.git)`. Localhost and private-network targets are rejected. |
| `--branch`, `-b` | string | `main` | Branch to generate. Must match `^[a-zA-Z0-9][a-zA-Z0-9._-]*$`; `/` and `..` are rejected. |
| `--provider` | string | `None` | AI provider. Accepted values are `claude`, `gemini`, and `cursor`. If omitted, the server default is used. |
| `--model`, `-m` | string | `None` | AI model name. If omitted, the server default is used. |
| `--force`, `-f` | boolean | `false` | Forces a full regeneration. |
| `--watch`, `-w` | boolean | `false` | After submission, opens a WebSocket and streams progress until completion, failure, or abort. |

```shell
$ docsfy generate https://github.com/acme/my-repo.git --branch dev --provider claude --model sonnet-4 --watch
Project: my-repo
Branch: dev
Status: generating
Generation ID: 123e4567-e89b-12d3-a456-426614174000
Watching generation progress...
[generating] planning
[generating] generating_pages (4 pages)
Generation complete! (12 pages)
```

**Return value/effect:**
- Submits the generation request and prints `Project`, `Branch`, `Status`, and `Generation ID`.
- With `--watch`, the initial summary prints first, then progress messages stream until the run becomes `ready`, `error`, or `aborted`.
- Typical watch messages are `Watching generation progress...`, `[<status>] <stage> (<page_count> pages)`, `Generation complete!`, `Generation failed: ...`, and `Generation was aborted.`.
- If the CLI cannot determine the final provider/model needed for `--watch`, it prints a warning after submission and leaves the generation running.
- Watch failures do not cancel the generation request that was already accepted.

### `docsfy list`

Lists project variants visible to the current key.

**Syntax:** `docsfy list [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--status` | string | `None` | Exact status filter. Current project statuses include `generating`, `ready`, `error`, and `aborted`. |
| `--provider` | string | `None` | Exact AI provider filter. |
| `--json` | boolean | `false` | Prints JSON instead of a table. |

```shell
$ docsfy list --status ready
NAME     BRANCH  PROVIDER  MODEL               STATUS  OWNER  PAGES  GEN ID
-------  ------  --------  ------------------  ------  -----  -----  ------------------------------------
my-repo  main    cursor    gpt-5.4-xhigh-fast  ready   admin  12     123e4567-e89b-12d3-a456-426614174000
```

**Return value/effect:**
- Default output is a table with columns `NAME`, `BRANCH`, `PROVIDER`, `MODEL`, `STATUS`, `OWNER`, `PAGES`, and `GEN ID`.
- `--json` prints a pretty-printed JSON array of project records.
- If no projects match, prints `No projects found.`

### `docsfy status`

Shows one variant or all variants for a project.

**Syntax:** `docsfy status <name-or-generation-id> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | Required | Project name or canonical generation ID. A generation ID resolves the exact variant and owner automatically. |
| `--branch`, `-b` | string | `None` | Branch filter. When combined with `--provider` and `--model`, selects one exact variant. |
| `--provider`, `-p` | string | `None` | Provider filter. When combined with `--branch` and `--model`, selects one exact variant. |
| `--model`, `-m` | string | `None` | Model filter. When combined with `--branch` and `--provider`, selects one exact variant. |
| `--owner` | string | `None` | Admin-only owner disambiguation for exact variant lookups. Ignored when listing all variants for a project. |
| `--json` | boolean | `false` | Prints JSON instead of human-readable output. |

```shell
$ docsfy status my-repo
Project: my-repo
Variants: 2

  main/cursor/gpt-5.4-xhigh-fast
    ID:      123e4567-e89b-12d3-a456-426614174000
    Status:  ready
    Owner:   admin
    Pages:   12
    Updated: 2026-04-18T10:00:00
    Commit:  abcdef12
```

**Return value/effect:**
- With all of `--branch`, `--provider`, and `--model`, prints one exact variant.
- Otherwise, prints all matching variants for the project after applying any filters.
- Human-readable output shows `ID`, `Status`, `Owner`, and any available `Pages`, `Updated`, `Commit`, `Stage`, and `Error` fields.
- Commit SHAs are truncated to the first 8 characters.
- `--json` prints either a single variant object or `{"name": "<project>", "variants": [...]}`.
- If no variants match, prints `No variants found for '<name>'.`

### `docsfy abort`

Aborts an active generation.

**Syntax:** `docsfy abort <name-or-generation-id> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | Required | Project name or canonical generation ID. A generation ID resolves the exact variant and owner automatically. |
| `--branch`, `-b` | string | `None` | Branch of the variant to abort. Must be used together with `--provider` and `--model`. |
| `--provider`, `-p` | string | `None` | Provider of the variant to abort. Must be used together with `--branch` and `--model`. |
| `--model`, `-m` | string | `None` | Model of the variant to abort. Must be used together with `--branch` and `--provider`. |
| `--owner` | string | `None` | Admin-only owner disambiguation for exact variant aborts. Ignored by project-wide abort. |

```shell
$ docsfy abort my-repo -b main -p cursor -m gpt-5.4-xhigh-fast
Aborted generation for 'my-repo/main/cursor/gpt-5.4-xhigh-fast'.
```

**Return value/effect:**
- With no variant selector, aborts one active generation by project name.
- With all of `--branch`, `--provider`, and `--model`, aborts that exact variant.
- If only some of the variant selectors are provided, exits `1` with an error.
- Successful output is `Aborted generation for '<target>'.`
- Project-wide aborts can return HTTP `409` when multiple active variants exist for the same project name.

### `docsfy delete`

Deletes one variant or all variants for a project.

**Syntax:** `docsfy delete <name-or-generation-id> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | Required | Project name or canonical generation ID. A generation ID resolves the exact variant and owner automatically. |
| `--branch`, `-b` | string | `None` | Branch of the variant to delete. Required for exact variant deletion unless `--all` is used. |
| `--provider`, `-p` | string | `None` | Provider of the variant to delete. Required for exact variant deletion unless `--all` is used. |
| `--model`, `-m` | string | `None` | Model of the variant to delete. Required for exact variant deletion unless `--all` is used. |
| `--owner` | string | `None` | Project owner. Required for admin deletions. |
| `--all` | boolean | `false` | Deletes all variants of the project. Cannot be combined with variant selectors. |
| `--yes`, `-y` | boolean | `false` | Skips the confirmation prompt. |

> **Warning:** This removes the selected database record(s) and deletes the corresponding on-disk project directory, including cached pages and rendered site output.

```shell
$ docsfy delete my-repo -b main -p cursor -m gpt-5.4-xhigh-fast --yes
Deleted variant 'my-repo/main/cursor/gpt-5.4-xhigh-fast'.

$ docsfy delete my-repo --all --yes
Deleted all variants of 'my-repo'.
```

**Return value/effect:**
- Without `--yes`, prompts before deleting.
- If the prompt is declined, prints `Aborted.` and exits `0`.
- Exact variant deletion prints `Deleted variant '<name>/<branch>/<provider>/<model>'.`
- `--all` prints `Deleted all variants of '<name>'.`
- If no exact variant selector is provided and `--all` is not used, exits `1`.
- If `name` is a generation ID and `--all` is used, the CLI resolves it to the project name and prints a warning before deleting all variants.

### `docsfy download`

Downloads generated docs as a tarball or extracts them into a directory.

**Syntax:** `docsfy download <name-or-generation-id> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | Required | Project name or canonical generation ID. A generation ID resolves the exact variant and owner automatically. |
| `--branch`, `-b` | string | `None` | Branch of the variant to download. Must be used together with `--provider` and `--model`. |
| `--provider`, `-p` | string | `None` | Provider of the variant to download. Must be used together with `--branch` and `--model`. |
| `--model`, `-m` | string | `None` | Model of the variant to download. Must be used together with `--branch` and `--provider`. |
| `--owner` | string | `None` | Admin-only owner disambiguation for exact variant downloads. Ignored by project-wide default download. |
| `--output`, `-o` | path/string | `None` | Output directory to extract into. If omitted, the CLI saves a `.tar.gz` archive in the current directory. |

```shell
$ docsfy download my-repo -b main -p cursor -m gpt-5.4-xhigh-fast --output ./site
Extracted to site

$ docsfy download my-repo
Downloaded to /work/my-repo-docs.tar.gz
```

**Return value/effect:**
- With all of `--branch`, `--provider`, and `--model`, downloads that exact ready variant.
- With no variant selector, downloads the latest accessible ready variant.
- Without `--output`, saves an archive named `<name>-docs.tar.gz` or `<name>-<branch>-<provider>-<model>-docs.tar.gz` in the current directory.
- With `--output`, creates the target directory if needed, extracts the archive there, and prints `Extracted to <dir>`.
- If only some variant selectors are provided, exits `1`.
- Variant-specific downloads return HTTP `400` if the selected variant is not `ready`.

### `docsfy models`

Lists valid providers and server-known model names.

**Syntax:** `docsfy models [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--provider`, `-P` | string | `None` | Restricts output to one provider. Current providers are `claude`, `gemini`, and `cursor`. |
| `--json`, `-j` | boolean | `false` | Prints JSON instead of human-readable output. |

```shell
$ docsfy models
Provider: claude
  sonnet-4

Provider: gemini
  (no models used yet)

Provider: cursor (default)
  gpt-5.4-xhigh-fast  (default)
```

**Return value/effect:**
- Plain-text output prints one section per provider.
- The default provider is marked with `(default)`.
- The default model under the default provider is marked with `  (default)`.
- Providers with no ready models print `  (no models used yet)`.
- `--json` prints the server payload; filtered JSON still includes `default_provider` and `default_model`.
- Unknown providers print `Unknown provider: <provider>` and exit `1`.

## Admin Commands

> **Warning:** All `admin` commands require an admin API key. Non-admin keys receive `403 Admin access required.`

### `docsfy admin users list`

Lists all users.

**Syntax:** `docsfy admin users list [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `--json` | boolean | `false` | Prints JSON instead of a table. |

```shell
$ docsfy admin users list
USERNAME  ROLE   CREATED
--------  -----  -------------------
alice     user   2026-04-18T09:00:00
bob       admin  2026-04-18T09:30:00
```

**Return value/effect:**
- Default output is a table with columns `USERNAME`, `ROLE`, and `CREATED`.
- `CREATED` is printed as the first 19 characters of the timestamp.
- `--json` prints a pretty-printed JSON array of user records.
- If no users exist, prints `No users found.`

### `docsfy admin users create`

Creates a user and prints the API key once.

**Syntax:** `docsfy admin users create <username> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `username` | string | Required | Username to create. Must match `^[a-zA-Z0-9][a-zA-Z0-9._-]{1,49}$`. The name `admin` is reserved. |
| `--role`, `-r` | string | `user` | User role. Accepted values are `admin`, `user`, and `viewer`. |
| `--json` | boolean | `false` | Prints JSON instead of human-readable output. |

```shell
$ docsfy admin users create alice --role viewer
User created: alice
Role: viewer
API Key: docsfy_TfM8Qn1x...

Save this API key -- it will not be shown again.
```

**Return value/effect:**
- Creates the user and generates a new API key.
- Auto-generated API keys start with `docsfy_`.
- Default output prints `User created`, `Role`, `API Key`, and `Save this API key -- it will not be shown again.`
- `--json` prints an object with `username`, `api_key`, and `role`.

### `docsfy admin users delete`

Deletes a user.

**Syntax:** `docsfy admin users delete <username> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `username` | string | Required | Username to delete. |
| `--yes`, `-y` | boolean | `false` | Skips the confirmation prompt. |

```shell
$ docsfy admin users delete alice --yes
Deleted user 'alice'.
```

**Return value/effect:**
- Without `--yes`, prompts before deleting.
- If the prompt is declined, prints `Aborted.` and exits `0`.
- Successful output is `Deleted user '<username>'.`
- Deletion removes the user record, invalidates sessions, deletes owned projects, removes access-control entries, and removes the user's project directory if it exists.
- The current admin account cannot delete itself.
- Deletion is blocked while that user has an active generation.

### `docsfy admin users rotate-key`

Rotates a user's API key.

**Syntax:** `docsfy admin users rotate-key <username> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `username` | string | Required | Username whose API key will be rotated. |
| `--new-key` | string | `None` | Custom API key. If omitted, the server generates one. Custom keys must be at least 16 characters long. |
| `--json` | boolean | `false` | Prints JSON instead of human-readable output. |

```shell
$ docsfy admin users rotate-key alice
User: alice
New API Key: docsfy_JvQk9L2...

Save this API key -- it will not be shown again.
```

**Return value/effect:**
- Generates a new API key unless `--new-key` is supplied.
- Invalidates all existing sessions for that user.
- Default output prints `User`, `New API Key`, and `Save this API key -- it will not be shown again.`
- `--json` prints an object with `username` and `new_api_key`.

### `docsfy admin access list`

Lists all users who can access a project.

**Syntax:** `docsfy admin access list <project> --owner <owner> [OPTIONS]`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project` | string | Required | Project name. |
| `--owner` | string | Required | Project owner whose access grants will be listed. |
| `--json` | boolean | `false` | Prints JSON instead of human-readable output. |

```shell
$ docsfy admin access list my-repo --owner admin
Project: my-repo
Owner: admin
Users with access: alice, bob
```

**Return value/effect:**
- Default output prints `Project`, `Owner`, and either `Users with access: ...` or `No access grants.`
- `--json` prints an object with `project`, `owner`, and `users`.

### `docsfy admin access grant`

Grants a user access to all variants of a project owned by a specific user.

**Syntax:** `docsfy admin access grant <project> --username <username> --owner <owner>`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project` | string | Required | Project name. |
| `--username` | string | Required | Username to grant access to. |
| `--owner` | string | Required | Owner of the project being shared. |

```shell
$ docsfy admin access grant my-repo --username alice --owner admin
Granted 'alice' access to 'my-repo' (owner: admin).
```

**Return value/effect:**
- Successful output is `Granted '<username>' access to '<project>' (owner: <owner>).`
- The target user must exist.
- The project must exist for the specified owner.
- Duplicate grants are ignored by the server.

### `docsfy admin access revoke`

Revokes a user's access to a project.

**Syntax:** `docsfy admin access revoke <project> --username <username> --owner <owner>`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project` | string | Required | Project name. |
| `--username` | string | Required | Username to revoke access from. |
| `--owner` | string | Required | Owner of the project whose grant will be removed. |

```shell
$ docsfy admin access revoke my-repo --username alice --owner admin
Revoked 'alice' access to 'my-repo' (owner: admin).
```

**Return value/effect:**
- Successful output is `Revoked '<username>' access to '<project>' (owner: <owner>).`
- Removes the matching access-control entry if it exists.

## Related Pages

- [Managing docsfy from the CLI](manage-docsfy-from-the-cli.html)
- [Configuration Reference](configuration-reference.html)
- [Configuring AI Providers and Models](configure-ai-providers-and-models.html)
- [Tracking Generation Progress](track-generation-progress.html)
- [Viewing and Downloading Docs](view-and-download-docs.html)