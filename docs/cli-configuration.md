# CLI Configuration

`docsfy` keeps its CLI connection settings in a TOML file in your home directory. You can save multiple servers there, choose one as the default, and override any part of the connection from the command line when you need a one-off change.

> **Note:** This page is about the CLI profile file in your home directory. It is separate from the server's own environment settings.

## Where the file lives

The CLI reads:

`~/.config/docsfy/config.toml`

Create it with:

```shell
docsfy config init
```

If the file does not exist, commands that need a server connection will fail until you either create the file or pass connection settings on the command line.

When `docsfy config init` writes the config, it creates the directory with owner-only permissions and writes the file as owner-read/write only.

> **Warning:** `~/.config/docsfy/config.toml` contains API keys. Keep it private.

## File format

The repository includes this example in `config.toml.example`:

```toml
# docsfy CLI configuration
# Copy to ~/.config/docsfy/config.toml or run: docsfy config init
#
# SECURITY: This file contains passwords. Keep it private:
#   chmod 600 ~/.config/docsfy/config.toml

# Default server to use when --server is not specified
[default]
server = "dev"

# Server profiles -- add as many as you need
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

How to read this file:

- `[default].server` chooses which saved profile is used when you do not pass `--server`.
- Each `[servers.<name>]` table defines one server profile.
- A profile has three fields: `url`, `username`, and `password`.

> **Note:** This file does not store a default AI provider or model. If you omit `--provider` or `--model` on `docsfy generate`, the server uses its own configured defaults.

## Creating and updating profiles

`docsfy config init` is the easiest way to create a profile. It prompts for:

- `Profile name`
- `Server URL`
- `Username`
- `Password`

A few details matter:

- If you press Enter at `Profile name`, the default name is `dev`.
- On the first run, the created profile also becomes the default server.
- If you run `docsfy config init` again later, it adds another profile but keeps the existing default.

To inspect the current file:

```shell
docsfy config show
```

`config show` prints the config file path, shows which profile is the default, lists every saved profile, and masks the password in its output.

To update values in place, use `config set`. These are real examples from the codebase tests:

```shell
docsfy config set default.server prod
docsfy config set servers.dev.url https://new-server.com
docsfy config set servers.dev.password new-password
```

`config set` only accepts keys that start with `default.` or `servers.`. It also requires the config file to exist already, so run `docsfy config init` at least once first.

> **Warning:** `docsfy config set default.server prod` updates the TOML value, but it does not verify that `servers.prod` exists. If the default points to a missing profile, later commands will fail when they try to use it.

> **Tip:** Use `docsfy config init` to create a complete new profile. Use `docsfy config set` when you just want to change one value.

## How default server selection works

The CLI resolves connection settings in this order:

1. Explicit command-line flags: `--host`, `--port`, `--username`, `--password`
2. The profile named by `--server` / `-s`
3. The profile named by `[default].server`
4. If none of those resolves to a server, the command exits with an error

In practice, that means:

- `--server` lets you temporarily switch to a different saved profile.
- If you do not pass `--server`, the CLI uses `[default].server`.
- If you have no saved config yet, you can still connect by passing enough command-line flags directly.
- If you name a profile that does not exist, the CLI exits and shows the available profile names.

## Global override flags

These are global connection options:

- `--server`, `-s`: choose a saved server profile
- `--host`: override the host from the saved profile
- `--port`: override the port
- `--username`, `-u`: override the username
- `--password`, `-p`: override the password/API key

Use them before the subcommand. This is a real test example:

```shell
docsfy --host myhost --port 9000 -u admin -p key health
```

A few override rules are worth knowing:

- If you use `--host` without `--port`, the CLI uses port `8000`.
- If you override only one field, the rest still come from the selected profile.
- If you override `--host`, the CLI rebuilds the URL from the host and port.
- When a selected profile URL starts with `http://`, overriding only the host keeps `http`.
- If there is no profile URL to borrow a scheme from, `--host` defaults to `https`.

> **Tip:** For local development, save your dev profile with an `http://...` URL. Then a host-only override keeps `http` instead of switching to `https`.

## Credentials and authentication

Each profile stores both `username` and `password`, but the CLI authenticates API requests with the `password` field as a Bearer token.

This is the exact client setup from the code:

```python
# username is stored for display/debugging; auth uses password as Bearer token
self.username = username
self.password = password
self._client = httpx.Client(
    base_url=self.server_url,
    headers={"Authorization": f"Bearer {self.password}"},
    timeout=30.0,
    follow_redirects=False,
)
```

What that means for you:

- Treat `password` as the API key for that server.
- The `username` field is still stored in the profile and shown by `docsfy config show`.
- The same saved API key is also used for `docsfy generate --watch`, which connects to the WebSocket progress endpoint.

If you rotate a user's API key on the server, update the matching `password` value in `~/.config/docsfy/config.toml`.

## Troubleshooting

If a config-related command fails, these are the most common causes:

- `Config not found`: run `docsfy config init`.
- `No server configured`: set `[default].server`, use `--server`, or pass `--host` and credentials directly.
- `Server profile '...' not found`: fix the `--server` value or your `[default].server` setting.
- TOML parse error: fix the syntax in `~/.config/docsfy/config.toml` and run the command again.


## Related Pages

- [CLI Workflows](cli-workflows.html)
- [CLI Command Reference](cli-command-reference.html)
- [Installation](installation.html)
- [Authentication and Roles](authentication-and-roles.html)
- [Authentication API](auth-api.html)