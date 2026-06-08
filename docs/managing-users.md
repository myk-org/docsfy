# Managing Users and Access Control

Set up user accounts, control who can access your documentation projects, and keep credentials secure by managing roles, project-level permissions, and API key rotation.

## Prerequisites

- A running docsfy server (see [Getting Started with docsfy](quickstart.html))
- The `ADMIN_KEY` environment variable set on the server (at least 16 characters)
- Admin access — either via the `ADMIN_KEY` or a user account with the `admin` role

## Quick Example

Create a user with the CLI in one command:

```bash
docsfy admin users create alice --role user
```

Output:

```
User created: alice
Role: user
API Key: docsfy_aBcDeFgHiJkLmNoPqRsTuVwXyZ...

Save this API key -- it will not be shown again.
```

## Understanding Roles

docsfy has three roles with different permission levels:

| Role | Generate docs | View docs | Manage users | Manage access |
|------|:---:|:---:|:---:|:---:|
| **admin** | ✅ | ✅ | ✅ | ✅ |
| **user** | ✅ | ✅ | ❌ | ❌ |
| **viewer** | ❌ | ✅ | ❌ | ❌ |

- **admin** — Full access including creating/deleting users, granting project access, and rotating API keys.
- **user** — Can generate, view, delete, and download documentation for their own projects. Cannot perform admin operations.
- **viewer** — Read-only access. Can browse documentation shared with them but cannot generate or modify anything.

## Creating Users

### From the Web Dashboard

1. Log in as an admin.
2. Navigate to the **Users** tab in the admin panel.
3. Enter a username, select a role from the dropdown, and click **Create User**.
4. Copy the generated API key immediately — it is shown only once.

### From the CLI

```bash
docsfy admin users create bob --role viewer
```

The `--role` flag accepts `user`, `viewer`, or `admin`. If omitted, it defaults to `user`.

> **Warning:** The API key is displayed only once at creation time. Store it securely — there is no way to retrieve it later. If lost, you must rotate the key.

### Username Rules

- Must be 2–50 characters long
- Must start with a letter or number
- May contain letters, numbers, dots (`.`), hyphens (`-`), and underscores (`_`)
- The username `admin` is reserved and cannot be used

## Listing Users

### CLI

```bash
docsfy admin users list
```

```
USERNAME    ROLE     CREATED
alice       user     2026-06-01 10:30:00
bob         viewer   2026-06-02 14:15:00
carol       admin    2026-06-03 09:00:00
```

Add `--json` for machine-readable output:

```bash
docsfy admin users list --json
```

### Web Dashboard

The **Users** tab shows all users in a table with their username, role, and creation date.

## Granting Project Access

By default, each user can only see projects they own. Admins can share a project with other users by granting access.

### From the Web Dashboard

1. Go to the **Access** tab in the admin panel.
2. Fill in the **Project Name**, **Username**, and **Owner** fields.
3. Click **Grant Access**.

### From the CLI

```bash
docsfy admin access grant my-repo --username bob --owner alice
```

This gives `bob` read access to all variants (branches, providers, models) of the project `my-repo` owned by `alice`.

> **Note:** Both the user and the project must already exist. The grant command validates this and returns an error if either is not found.

## Revoking Project Access

### From the Web Dashboard

1. Go to the **Access** tab.
2. Under **Lookup Access**, enter the project name and owner, then click **List Access**.
3. Click **Revoke** next to the user you want to remove.

### From the CLI

```bash
docsfy admin access revoke my-repo --username bob --owner alice
```

## Listing Project Access

See who has access to a specific project:

```bash
docsfy admin access list my-repo --owner alice
```

```
Project: my-repo
Owner: alice
Users with access: bob, carol
```

Add `--json` for machine-readable output.

## Rotating API Keys

If a key is compromised or a user loses their credentials, rotate their API key. This immediately invalidates the old key and all active sessions for that user.

### Admin Rotating Another User's Key

**CLI:**

```bash
docsfy admin users rotate-key bob
```

```
User: bob
New API Key: docsfy_xYzAbCdEfGhIjKlMnOpQrStUvWxYz...

Save this API key -- it will not be shown again.
```

**Web dashboard:** Click **Change Password** next to the user in the **Users** tab. You can optionally provide a custom key or leave the field empty to auto-generate one.

### Users Rotating Their Own Key

Non-admin users can rotate their own key through the API. This clears their current session — they must log in again with the new key.

> **Warning:** The built-in `admin` account (authenticated via `ADMIN_KEY`) cannot rotate keys through the API. Change the `ADMIN_KEY` environment variable and restart the server instead.

### Custom API Keys

You can supply a custom key instead of auto-generating one:

```bash
docsfy admin users rotate-key bob --new-key "my-custom-secure-key-here"
```

Custom keys must be at least 16 characters long.

## Deleting Users

### From the CLI

```bash
docsfy admin users delete carol
```

You will be prompted for confirmation. Add `--yes` to skip:

```bash
docsfy admin users delete carol --yes
```

### From the Web Dashboard

Click **Delete** next to the user in the **Users** tab and confirm the action.

### What Happens When a User Is Deleted

- All active sessions for the user are invalidated immediately
- All projects owned by the user are deleted from the database
- All project files on disk belonging to the user are removed
- All access grants (both granted to and granted by the user) are cleaned up
- A user cannot be deleted while one of their projects has a generation in progress

> **Warning:** User deletion is permanent and cannot be undone. All of their projects and generated documentation will be lost.

## The Admin Account

docsfy has a special built-in admin identity that authenticates with the `ADMIN_KEY` environment variable:

- **Username:** `admin`
- **Credentials:** The value of the `ADMIN_KEY` environment variable
- This account always has full admin privileges
- It cannot be deleted or have its key rotated through the API — change the `ADMIN_KEY` env var and restart the server

You can also create additional users with the `admin` role. These behave identically to the built-in admin for authorization purposes, but their keys are managed through the normal user management workflow.

> **Warning:** Changing the `ADMIN_KEY` environment variable invalidates **all** existing user API key hashes (since `ADMIN_KEY` is used as the HMAC secret for key hashing). After rotating `ADMIN_KEY`, you must rotate every user's API key as well.

## Advanced Usage

### Sessions and Timeouts

- Browser sessions last 8 hours and are stored as HTTP-only cookies
- Rotating a user's API key invalidates all their active sessions
- Expired sessions are cleaned up automatically when the server starts

### Connecting the CLI to a Server

Before running admin commands, configure the CLI with a server profile:

```bash
docsfy config init
```

You'll be prompted for a profile name, server URL, username, and password (API key). See [Using the CLI](using-the-cli.html) for complete setup instructions.

You can also pass credentials directly:

```bash
docsfy --host myserver.example.com --username admin --password $ADMIN_KEY admin users list
```

### JSON Output

All CLI admin commands support `--json` for scripting:

```bash
docsfy admin users create ci-bot --role user --json
```

```json
{
  "username": "ci-bot",
  "api_key": "docsfy_aBcDeFgHiJkLmNoPqRsTuVwXyZ...",
  "role": "user"
}
```

### Access Control Model

docsfy uses an ownership-based access model:

- Every project is owned by the user who generated it
- Owners always have full access to their own projects
- Admins can see and manage all projects regardless of ownership
- Access grants are scoped by **project name + project owner** — granting access gives the user visibility into all variants (branches, AI providers, models) of that project
- When all variants of a project are deleted, associated access grants are automatically cleaned up

## Troubleshooting

**"Username 'admin' is reserved"** — You cannot create a user with the username `admin`. Choose a different name and assign the `admin` role instead.

**"Cannot delete your own account"** — An admin cannot delete the account they are currently logged in with. Have another admin delete it, or use a different admin account.

**"Cannot delete user while generation is in progress"** — Wait for any active documentation generation jobs owned by that user to complete, or abort them first. See [Managing Projects and Variants](managing-projects.html) for how to abort a generation.

**"ADMIN_KEY users cannot rotate keys"** — If you are logged in using the `ADMIN_KEY` environment variable (as the built-in `admin` account), you cannot rotate your key through the API. Update the `ADMIN_KEY` environment variable on the server and restart it.

**"API key must be at least 16 characters long"** — Custom API keys provided via `--new-key` must be at least 16 characters. Use a longer key or omit the flag to auto-generate one.

## Related Pages

- [Getting Started with docsfy](quickstart.html)
- [Using the CLI](using-the-cli.html)
- [CLI Command Reference](cli-reference.html)
- [REST API Reference](api-reference.html)
- [Managing Projects and Variants](managing-projects.html)