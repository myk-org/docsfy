# Track Generation Progress

Keep each generation in view so you can tell whether docsfy is still working, already finished, or needs intervention. When you can see the current stage in real time, it is much easier to decide whether to wait, inspect a specific run, or stop and retry.

## Prerequisites
- Access to a running docsfy server.
- A signed-in dashboard session or a configured CLI profile with a working key.
- An active run, or a repository you are ready to generate. See [Generate Documentation](generate-documentation.html) for details.

## Quick Example
```shell
docsfy generate https://github.com/org/my-repo --watch
```

This starts a run and keeps the terminal attached to live progress. docsfy prints the project name, branch, status, and generation ID, then streams updates until the run becomes `ready`, `error`, or `aborted`.

> **Note:** `--watch` only attaches when the server returns `generating`. If the command returns `ready` immediately, docsfy decided that variant was already current.

## Step-by-Step
1. Start the run in watch mode.

```shell
docsfy generate https://github.com/org/my-repo --watch
```

Use this when you want one command to submit the job and follow it live in the terminal. See [CLI Command Reference](cli-command-reference.html) for details.

2. Keep the dashboard open while the run is active.

Open the dashboard and select the active run from the list. While the connection stays healthy, the page updates automatically and shows:

- the current status: `Generating`, `Ready`, `Error`, or `Aborted`
- elapsed time while the run is still active
- page count and progress percentage when a plan is available
- the generation ID for later lookup
- an activity log that advances as stages complete

> **Tip:** Copy the generation ID early for long runs. You can use it later with `docsfy status` or `docsfy abort` without retyping the branch, provider, and model.

3. Read the stage names as they change.

The terminal watcher and dashboard activity log use these stage names:

| Stage | What it means |
| --- | --- |
| `cloning` | docsfy is fetching the repository or refreshing its local copy. |
| `analyzing` | docsfy is scanning the codebase to understand its structure. |
| `cataloging_images` | docsfy is cataloging repository images when a `docsfy-images/` directory exists. |
| `planning` | docsfy is building a full documentation plan. |
| `incremental_planning` | docsfy is deciding what to reuse and what to regenerate for an update run. |
| `generating_pages` | docsfy is writing pages and increasing the page count as they finish. |
| `validating` | docsfy is checking generated pages against the codebase and documentation rules. |
| `completeness_check` | docsfy is checking for missing coverage and may add gap pages. |
| `cross_linking` | docsfy is adding and repairing internal page links. |
| `rendering` | docsfy is building the final static documentation site. |
| `up_to_date` | docsfy determined the selected variant already matches the current repository state. |

4. Recheck progress from the CLI whenever you need to.

Use `status` when you want to revisit a run after closing `--watch`, narrow to one exact variant, or jump directly to a copied generation ID.

```shell
docsfy status my-repo
docsfy status my-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
docsfy status a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

The first form shows all visible variants for the project. The filtered form targets one exact variant, and the generation ID form goes straight to a single run.

5. Stop a run if progress shows it should not continue.

If you started the wrong branch, chose the wrong model, or no longer want the active run, stop it from the dashboard or the CLI.

```shell
docsfy abort my-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
docsfy abort a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

When the stop request succeeds, the run changes to `aborted`. You can then start a fresh run with the settings you want.

## Advanced Usage
Use the dashboard for day-to-day monitoring, the CLI watcher for one-off runs, and the WebSocket or JSON output when you need automation.

| Method | Best for | What you get |
| --- | --- | --- |
| Dashboard | Day-to-day monitoring | Live status, progress bar, elapsed time, activity log, and copyable generation ID |
| `docsfy generate --watch` | One-off CLI runs | Submission plus live progress in one terminal session |
| `docsfy status --json` | Scripts and CI checks | Pollable machine-readable status |
| WebSocket `/api/ws` | Custom live integrations | Push updates without polling |

If you want your own live watcher, connect to the same WebSocket the dashboard uses. A signed-in browser session can open it directly because the session cookie is sent automatically:

```js
const ws = new WebSocket(
  `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws`
)

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data)

  if (msg.type === 'ping') {
    ws.send(JSON.stringify({ type: 'pong' }))
    return
  }

  if (msg.type === 'progress' || msg.type === 'status_change') {
    console.log(msg.name, msg.status, msg.current_stage ?? '', msg.page_count ?? '')
  }
```

A new connection gets an initial `sync` snapshot, then live `progress` and `status_change` events for projects you can access. See [HTTP API and WebSocket Reference](http-api-and-websocket-reference.html) for details.

If you would rather poll than keep a socket open, use JSON output:

```shell
docsfy status my-repo --json
```

> **Note:** Live updates go to admins, the project owner, and users who have been granted access to that project.


> **Tip:** During reruns, `incremental_planning` usually means docsfy is doing a targeted update, while `planning` usually means it fell back to a full plan. See [Regenerate After Code Changes](regenerate-after-code-changes.html) for details.

## Troubleshooting
- `--watch` stops with a timeout: the CLI waits up to 5 minutes for the next WebSocket message. Run `docsfy status my-repo` to confirm whether the job is still active, then reconnect with `--watch` if you still want a live stream.
- `--watch` says it cannot determine the provider or model: rerun with explicit `--provider` and `--model`, or inspect the run first with `docsfy status my-repo`.
- The dashboard is not updating immediately: the browser reconnects automatically, and after repeated socket failures it falls back to polling about every 10 seconds. Keep the page open and refresh your session if you were signed out.
- A rerun finishes almost immediately: if the current stage is `up_to_date`, docsfy decided the selected variant already matches the repository state.
- A rerun is taking as long as a full build: if you expected an incremental update but the stage shows `planning` instead of `incremental_planning`, docsfy is doing a full plan for that run.
- The run ends in `error` or `aborted`: open the selected run, read the error message, and start a new run. See [Run Common CLI Workflows](common-workflow-recipes.html) for details.# Track Generation Progress

Keep each generation in view so you can tell whether docsfy is still working, already finished, or needs intervention. When you can see the current stage in real time, it is much easier to decide whether to wait, inspect a specific run, or stop and retry.

## Prerequisites
- Access to a running docsfy server.
- A signed-in dashboard session or a configured CLI profile with a working key.
- An active run, or a repository you are ready to generate. See [Generate Documentation](generate-documentation.html) for details.

## Quick Example
```shell
docsfy generate https://github.com/org/my-repo --watch
```

This starts a run and keeps the terminal attached to live progress. docsfy prints the project name, branch, status, and generation ID, then streams updates until the run becomes `ready`, `error`, or `aborted`.

> **Note:** `--watch` only attaches when the server returns `generating`. If the command returns `ready` immediately, docsfy decided that variant was already current.

## Step-by-Step
1. Start the run in watch mode.

```shell
docsfy generate https://github.com/org/my-repo --watch
```

Use this when you want one command to submit the job and follow it live in the terminal. See [CLI Command Reference](cli-command-reference.html) for details.

2. Keep the dashboard open while the run is active.

Open the dashboard and select the active run from the list. While the connection stays healthy, the page updates automatically and shows:

- the current status: `Generating`, `Ready`, `Error`, or `Aborted`
- elapsed time while the run is still active
- page count and progress percentage when a plan is available
- the generation ID for later lookup
- an activity log that advances as stages complete

> **Tip:** Copy the generation ID early for long runs. You can use it later with `docsfy status` or `docsfy abort` without retyping the branch, provider, and model.

3. Read the stage names as they change.

The terminal watcher and dashboard activity log use these stage names:

| Stage | What it means |
| --- | --- |
| `cloning` | docsfy is fetching the repository or refreshing its local copy. |
| `analyzing` | docsfy is scanning the codebase to understand its structure. |
| `cataloging_images` | docsfy is cataloging repository images when a `docsfy-images/` directory exists. |
| `planning` | docsfy is building a full documentation plan. |
| `incremental_planning` | docsfy is deciding what to reuse and what to regenerate for an update run. |
| `generating_pages` | docsfy is writing pages and increasing the page count as they finish. |
| `validating` | docsfy is checking generated pages against the codebase and documentation rules. |
| `completeness_check` | docsfy is checking for missing coverage and may add gap pages. |
| `cross_linking` | docsfy is adding and repairing internal page links. |
| `rendering` | docsfy is building the final static documentation site. |
| `up_to_date` | docsfy determined the selected variant already matches the current repository state. |

4. Recheck progress from the CLI whenever you need to.

Use `status` when you want to revisit a run after closing `--watch`, narrow to one exact variant, or jump directly to a copied generation ID.

```shell
docsfy status my-repo
docsfy status my-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
docsfy status a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

The first form shows all visible variants for the project. The filtered form targets one exact variant, and the generation ID form goes straight to a single run.

5. Stop a run if progress shows it should not continue.

If you started the wrong branch, chose the wrong model, or no longer want the active run, stop it from the dashboard or the CLI.

```shell
docsfy abort my-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
docsfy abort a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

When the stop request succeeds, the run changes to `aborted`. You can then start a fresh run with the settings you want.

## Advanced Usage
Use the dashboard for day-to-day monitoring, the CLI watcher for one-off runs, and the WebSocket or JSON output when you need automation.

| Method | Best for | What you get |
| --- | --- | --- |
| Dashboard | Day-to-day monitoring | Live status, progress bar, elapsed time, activity log, and copyable generation ID |
| `docsfy generate --watch` | One-off CLI runs | Submission plus live progress in one terminal session |
| `docsfy status --json` | Scripts and CI checks | Pollable machine-readable status |
| WebSocket `/api/ws` | Custom live integrations | Push updates without polling |

If you want your own live watcher, connect to the same WebSocket the dashboard uses. A signed-in browser session can open it directly because the session cookie is sent automatically:

```js
const ws = new WebSocket(
  `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws`
)

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data)

  if (msg.type === 'ping') {
    ws.send(JSON.stringify({ type: 'pong' }))
    return
  }

  if (msg.type === 'progress' || msg.type === 'status_change') {
    console.log(msg.name, msg.status, msg.current_stage ?? '', msg.page_count ?? '')
  }
}
```

A new connection gets an initial `sync` snapshot, then live `progress` and `status_change` events for projects you can access. See [HTTP API and WebSocket Reference](http-api-and-websocket-reference.html) for details.

If you would rather poll than keep a socket open, use JSON output:

```shell
docsfy status my-repo --json
```

> **Note:** Live updates go to admins, the project owner, and users who have been granted access to that project.


> **Tip:** During reruns, `incremental_planning` usually means docsfy is doing a targeted update, while `planning` usually means it fell back to a full plan. See [Regenerate After Code Changes](regenerate-after-code-changes.html) for details.

## Troubleshooting
- `--watch` stops with a timeout: the CLI waits up to 5 minutes for the next WebSocket message. Run `docsfy status my-repo` to confirm whether the job is still active, then reconnect with `--watch` if you still want a live stream.
- `--watch` says it cannot determine the provider or model: rerun with explicit `--provider` and `--model`, or inspect the run first with `docsfy status my-repo`.
- The dashboard is not updating immediately: the browser reconnects automatically, and after repeated socket failures it falls back to polling about every 10 seconds. Keep the page open and refresh your session if you were signed out.
- A rerun finishes almost immediately: if the current stage is `up_to_date`, docsfy decided the selected variant already matches the repository state.
- A rerun is taking as long as a full build: if you expected an incremental update but the stage shows `planning` instead of `incremental_planning`, docsfy is doing a full plan for that run.
- The run ends in `error` or `aborted`: open the selected run, read the error message, and start a new run. See [Run Common CLI Workflows](common-workflow-recipes.html) for details.

## Related Pages

- [Generate Documentation](generate-documentation.html)
- [Run Common CLI Workflows](common-workflow-recipes.html)
- [HTTP API and WebSocket Reference](http-api-and-websocket-reference.html)
- [Manage Projects and Variants](manage-projects-and-variants.html)
- [Regenerate After Code Changes](regenerate-after-code-changes.html)