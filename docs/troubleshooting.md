# Troubleshooting

When something goes wrong, start with the exact message you see in the UI, CLI, or browser network tab. `docsfy` usually passes backend errors through directly, so messages like `Frontend not built`, `Invalid branch name`, `Unauthorized`, or `Variant '...' is already being generated` are usually the shortest path to the fix.

## Quick Triage

- If `/api/*` works but `/` or `/login` does not, this is usually a frontend build problem.
- If a generation fails almost immediately, before cloning starts, this is usually a provider CLI problem.
- If the error mentions `Invalid branch name`, `Remote branch ... not found`, or `does not match expected`, check the branch rules first.
- If you see `already being generated`, `Abort first`, or `Multiple active variants found`, you hit a generation lock or race.
- If you see `401`, repeated redirects to `/login`, or a missing project you expected to see, check authentication, roles, and project access.
- If the dashboard loads but does not update live, check WebSocket connectivity. The browser app can fall back to polling; the CLI `--watch` path cannot.
- The backend health endpoint should return:

```json
{"status":"ok"}
```

## Common Settings To Check

Server-side environment comes from `.env`:

```dotenv
ADMIN_KEY=
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
LOG_LEVEL=INFO
DATA_DIR=/data
SECURE_COOKIES=true
# DEV_MODE=true
```

CLI access comes from `~/.config/docsfy/config.toml`:

```toml
[default]
server = "dev"

[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<your-dev-key>"
```

> **Note:** Browser login and CLI login are different. The browser uses the `docsfy_session` cookie. The CLI sends the configured password/API key as a Bearer token.

> **Warning:** `ADMIN_KEY` is required and must be at least 16 characters long. If it is empty or too short, admin access will not work and the server will not start cleanly.

## Missing Frontend Build

### What it looks like

- Visiting `/`, `/login`, or another SPA route returns a 404.
- The response detail says `Frontend not built. Run: cd frontend && npm run build`.
- The HTML page loads, but `/assets/*` files 404 and the dashboard appears unstyled or broken.
- The API works, but the browser UI does not.

### Why it happens

In production, `docsfy` serves the React app from `frontend/dist`. If `frontend/dist/index.html` is missing, the SPA cannot load at all.

```python
index = _frontend_dist / "index.html"
if index.exists():
    return FileResponse(str(index))
raise HTTPException(
    status_code=404,
    detail="Frontend not built. Run: cd frontend && npm run build",
)
```

The frontend build is defined in `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "test": "vitest run"
  }
}
```

If you deploy with Docker, the image build is supposed to compile the frontend before the runtime image is created:

```dockerfile
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
```

### How to fix it

1. Build the frontend:
   ```shell
   cd frontend
   npm ci
   npm run build
   ```
2. Restart the server after the build finishes.
3. If you are using Docker, rebuild the image so the new `frontend/dist` is copied into the runtime image.
4. If only `/assets/*` is failing, treat that the same way: rebuild the frontend and redeploy the full build output, not just `index.html`.

> **Tip:** If `/api/status` works but `/` does not, the backend is probably fine and only the frontend build is missing.

### Development mode

For local development, this repo can run Vite instead of serving a static build. That is controlled by `DEV_MODE=true`. In that mode the entrypoint runs `npm ci` and starts the Vite dev server automatically.

## Provider CLI Failures

### What it looks like

- A generation switches to `error` almost immediately.
- The error appears before cloning or page generation starts.
- One provider works, but another fails on the same machine.
- You omitted provider/model and the server picked defaults you were not expecting.

### What `docsfy` checks

Before it clones a repository, `docsfy` checks whether the selected provider CLI is available:

```python
cli_flags = ["--trust"] if ai_provider == "cursor" else None
available, msg = await check_ai_cli_available(
    ai_provider, ai_model, cli_flags=cli_flags
)
if not available:
    await update_and_notify(
        gen_key,
        project_name,
        ai_provider,
        ai_model,
        status="error",
        owner=owner,
        branch=branch,
        error_message=msg,
    )
    return
```

Supported providers are fixed in the backend:

```python
VALID_PROVIDERS = ("claude", "gemini", "cursor")
```

### What to check

- Make sure you are using one of the supported provider names: `claude`, `gemini`, or `cursor`.
- If you omitted `ai_provider` or `ai_model`, remember that the server uses its defaults. In this repo those defaults are `cursor` and `gpt-5.4-xhigh-fast`.
- If you are running outside the official container, make sure the provider CLI is installed and available on `PATH`.
- If the provider CLI is installed but slow to start, increase `AI_CLI_TIMEOUT`.

The Docker image expects these CLIs to be installed at build time:

```dockerfile
RUN /bin/bash -o pipefail -c "curl -fsSL https://claude.ai/install.sh | bash"
RUN /bin/bash -o pipefail -c "curl -fsSL https://cursor.com/install | bash"
RUN mkdir -p /home/appuser/.npm-global \
  && npm config set prefix '/home/appuser/.npm-global' \
  && npm install -g @google/gemini-cli

ENV PATH="/home/appuser/.local/bin:/home/appuser/.npm-global/bin:${PATH}"
```

> **Warning:** Provider failures happen before cloning. If a run fails instantly, check provider installation, authentication, and `AI_PROVIDER`/`AI_MODEL` first, not just the repo URL.

> **Note:** The `cursor` provider is handled slightly differently: `docsfy` automatically adds `--trust` when it checks and calls the CLI.

## Branch Validation And Branch Mismatch

### What it looks like

- The request is rejected immediately with `Invalid branch name`.
- A remote run fails with a clone error such as `Remote branch ... not found`.
- A local path run fails because the checked-out branch does not match what you asked for.

### What counts as a valid branch

`docsfy` defaults to `main` and validates branch names before generation starts:

```python
@field_validator("branch")
@classmethod
def validate_branch(cls, v: str) -> str:
    if "/" in v:
        msg = (
            f"Invalid branch name: '{v}'. Branch names cannot contain slashes "
            "— use hyphens instead (e.g., release-1.x)."
        )
        raise ValueError(msg)
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", v):
        msg = f"Invalid branch name: '{v}'"
        raise ValueError(msg)
    if ".." in v:
        msg = f"Invalid branch name: '{v}'"
        raise ValueError(msg)
    return v
```

That means:

- Valid: `main`, `dev`, `release-1.x`, `v2.0.1`
- Invalid: `release/v2.0`, `.hidden`, `../etc/passwd`

The slash rule exists because the branch is part of URLs like `/docs/<project>/<branch>/<provider>/<model>/...`.

### Remote repository branch problems

Remote repositories are cloned with `git clone --depth 1`, and `docsfy` passes the branch if you supplied one. If that branch does not exist upstream, you will get a clone failure such as:

- `Clone failed: fatal: Remote branch 'nonexistent' not found`

### Local repository branch problems

When you generate from `repo_path`, `docsfy` checks the current branch of that working tree. If it does not match the branch you requested, it fails with an error like:

- `Branch 'main' does not match expected 'v2.0'`

### How to fix it

- Use the exact branch name that exists in Git.
- Replace slashes with hyphens when you need a branch that can safely live inside a `docsfy` URL.
- If you are using `repo_path`, either check out the requested branch first or change the branch value you send.
- If you omit the branch entirely, `docsfy` uses `main`.

Actual CLI syntax for a branch-specific run looks like this:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force
```

## Generation Conflicts And Stuck Runs

### What it looks like

- `Variant 'project/branch/provider/model' is already being generated`
- `Cannot delete 'project/provider/model' while generation is in progress. Abort first.`
- `Multiple active variants found; use the branch-specific abort endpoint.`
- `Abort still in progress ... Please retry shortly.`
- A run that was `generating` becomes `error` after a restart.

### Why it happens

`docsfy` prevents two jobs from generating the same owner/project/branch/provider/model at the same time:

```python
gen_key = f"{owner}/{project_name}/{branch}/{ai_provider}/{ai_model}"
async with _gen_lock:
    if gen_key in _generating:
        raise HTTPException(
            status_code=409,
            detail=f"Variant '{project_name}/{branch}/{ai_provider}/{ai_model}' is already being generated",
        )
```

The same lock also protects delete and abort operations from racing against active generation.

### How to fix it

- If you started the same variant twice, wait for the first run to finish or abort it.
- If you only know the project name but more than one variant is active, abort the exact variant instead of aborting by name.
- If abort says it is still in progress, wait a moment and retry.
- If abort says the job already finished, refresh status before trying again.
- If the server restarted during generation, start a new run. `docsfy` intentionally marks orphaned `generating` jobs as `error` with the message `Server restarted during generation`.

Useful CLI commands:

```shell
docsfy status for-testing-only
docsfy abort for-testing-only --branch main --provider gemini --model gemini-2.5-flash
```

> **Tip:** `--force` clears cached generation artifacts, but it does not bypass the active-generation lock.

## Access, Login, And Permission Problems

### What the status codes usually mean

- `401 Unauthorized`: you are not authenticated, your API key is wrong, or your browser session expired.
- `403 Admin access required`: you reached an admin-only endpoint.
- `403 Write access required.`: your account is `viewer`, so you can read but not generate, abort, or delete.
- `404 Not found`: the project may exist, but you do not own it and have not been granted access. `docsfy` intentionally hides inaccessible projects behind a 404 instead of exposing them with a 403.

### Browser and CLI behave differently

- Browser requests to `/docs/*` redirect to `/login` when you are not signed in.
- API and CLI requests return JSON `401` responses instead.
- The login page shows `Invalid username or password` for bad credentials, and `Unable to connect to server` for connection failures.

Admin login is always username `admin` with the admin password.

### Session cookie problems

The browser session cookie is created like this:

```python
response.set_cookie(
    "docsfy_session",
    session_token,
    httponly=True,
    samesite="strict",
    secure=settings.secure_cookies,
    max_age=SESSION_TTL_SECONDS,
)
```

> **Warning:** If you run `docsfy` on plain `http://localhost` with `SECURE_COOKIES=true`, login can appear to work and then immediately bounce back to `/login` because the browser will not send a secure cookie over plain HTTP.

For local HTTP development, set `SECURE_COOKIES=false`.

### Role and access restrictions

- `viewer` users can view projects they own or were granted, but they cannot generate or delete.
- `repo_path` generation is admin-only. Non-admin users get `Local repo path access requires admin privileges`.
- If you are using a local repository path, you can also see:
  - `Repository path does not exist: '...'`
  - `Not a git repository (no .git directory): '...'`

### Shared project access

Project sharing is owner-specific. If the wrong owner was used when access was granted, the user still will not see the project.

The CLI commands for access management are:

```shell
docsfy admin access list <project> --owner <owner>
docsfy admin access grant <project> --username <user> --owner <owner>
docsfy admin access revoke <project> --username <user> --owner <owner>
```

If the same project name and variant exist under more than one owner, you can also see ambiguity errors such as:

- `Multiple owners found for this variant, please specify owner`
- `Multiple owners found for this variant (...). Contact an admin to resolve the ambiguity.`

In that case, use the correct owner explicitly or ask an admin to clean up the ambiguous access.

### CLI auth checks

If the CLI is failing, start with:

```shell
docsfy config show
```

If the CLI reports a redirect such as `Error: Server redirected to /login. Check the server URL.`, verify the `url`, `username`, and `password` in `~/.config/docsfy/config.toml`.

## WebSocket Connectivity And Live Updates

### What it looks like

- The dashboard loads, but live status updates never appear.
- The CLI `--watch` command prints `WebSocket connection failed: ...`.
- The CLI prints `WebSocket connection closed unexpectedly.` or `Timed out waiting for progress update.`.
- Browser dev tools show `/api/ws` closing with code `1008`.

### How it works

- The browser connects to `/api/ws`.
- The server accepts either a valid `docsfy_session` cookie or `?token=<api-key>`.
- On connect, the server sends an initial `sync` payload.
- The server sends `ping` every 30 seconds, expects `pong` within 10 seconds, and closes after 2 missed pongs.
- Unauthenticated WebSocket connections are closed with code `1008`.

In the browser, `docsfy` retries the WebSocket 3 times and then falls back to polling `/api/projects` every 10 seconds.

> **Tip:** If the dashboard stops updating instantly but still refreshes within about 10 seconds, the polling fallback is probably working exactly as designed.

### Local development and proxies

The Vite dev server is already configured to proxy WebSockets to the backend:

```ts
'/api': {
  target: API_TARGET,
  changeOrigin: true,
  ws: true,
}
```

If you are running behind another proxy or load balancer, make sure it preserves WebSocket upgrade requests for `/api/ws`.

### CLI `--watch` specifics

The CLI derives its WebSocket URL from your configured server URL. That means a bad `url` in `~/.config/docsfy/config.toml` can break `--watch` even if the generation itself still starts.

A real `--watch` example from this repo's test plan is:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force --watch
```

If `--watch` fails, rerun without it and use `docsfy status <project>` while you fix the network or proxy issue. The browser app has polling fallback; the CLI watch path does not.

### What to check

- If the close code is `1008`, log in again or use a valid API key/token.
- If the site is served over HTTPS, the browser will use `wss://` automatically.
- If you are using Vite dev mode, make sure the dev server is running and port `5173` is exposed.
- If you are using a reverse proxy, confirm it supports WebSocket upgrades for `/api/ws`.
- If the dashboard works but updates are delayed, wait for the 10-second polling interval before assuming it is stuck.

If none of the sections above fits, capture the exact error text, the provider, model, branch, whether you were using the browser or CLI, and whether `/health` returned `{"status":"ok"}`. Those details usually identify the failing layer very quickly.
