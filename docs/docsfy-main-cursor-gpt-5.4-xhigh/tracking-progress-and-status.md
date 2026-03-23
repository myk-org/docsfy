# Tracking Progress and Status

docsfy shows generation progress live. When you start a run, the server creates or updates a project variant with status `generating`, and the dashboard keeps that variant fresh over `/api/ws`. In normal use, you can stay on the selected variant and watch the badge, page count, and activity log change without refreshing the page.

## What the statuses mean

| Status | Meaning | What you will see |
| --- | --- | --- |
| `generating` | docsfy is still cloning, planning, writing pages, or rendering HTML | A blue pulsing status, live activity log, and an **Abort Generation** button |
| `ready` | The docs finished successfully | **View Documentation**, **Download**, final page count, commit, and last-generated time |
| `error` | The run failed | An error message in the detail view and a regenerate form |
| `aborted` | A user stopped the run | An aborted message in the detail view and a regenerate form |

> **Note:** `ready` can also mean “already up to date.” If the current commit does not require new docs, docsfy finishes immediately as ready and shows a specific up-to-date message.

## Generation stages

Most full runs move through these stages:

1. `cloning`
2. `planning`
3. `generating_pages`
4. `rendering`
5. `ready`

Incremental runs use `incremental_planning` instead of `planning`. That happens when docsfy already has a ready variant, compares commits, and decides which pages actually need to be regenerated.

The dashboard uses those stage names directly when it builds the activity log:

```ts
const stages = ['cloning', 'planning', 'incremental_planning', 'generating_pages', 'rendering']
const currentIdx = stages.indexOf(project.current_stage || '')

if (currentIdx > 2) {
  entries.push({
    id: 'plan',
    type: 'done',
    message: `Planned documentation structure (${totalPages} pages)`,
    timestamp: Date.now(),
  })
} else if (currentIdx === 1) {
  entries.push({ id: 'plan', type: 'active', message: 'Planning documentation structure...', timestamp: Date.now() })
} else if (currentIdx === 2) {
  entries.push({ id: 'plan', type: 'active', message: 'Planning incremental update...', timestamp: Date.now() })
}
```

What each stage means:

- `cloning`: docsfy is preparing the repository source. For remote repositories, that means cloning. For local admin-only repositories, this stage is usually brief because there is no remote clone to perform.
- `planning`: docsfy is building the documentation structure from the repository.
- `incremental_planning`: docsfy is deciding which pages need to change instead of rebuilding everything.
- `generating_pages`: markdown pages are being written or updated.
- `rendering`: the finished page set is being turned into the static HTML site.
- `up_to_date`: a special ready-state marker, not a long-running stage. It means docsfy found nothing new to regenerate.

> **Note:** The progress bar only appears after planning. Before the plan exists, docsfy does not yet know the total number of pages.

## How the dashboard reflects in-flight work

The dashboard loads the current project list once through `/api/projects`, then keeps it fresh with a WebSocket connection to `/api/ws`. That gives you three useful behaviors:

- New runs appear quickly without a manual refresh.
- The sidebar status dot changes as soon as the backend reports new state.
- The detail view updates page counts and log messages while the run is still in flight.

When you start a generation from the dashboard, docsfy immediately switches to that variant view and auto-expands the matching repository and branch in the sidebar. That makes the current run easy to follow without leaving the page.

While a run is active, the server sends `progress` messages with the fields the UI needs for in-flight updates: `current_stage`, `page_count`, `plan_json`, and `error_message`. When a run reaches `ready`, `error`, or `aborted`, the server sends a terminal `status_change` and then a full `sync`, so the whole dashboard stays consistent.

## Understanding page counts

`page_count` is backed by the server, not calculated only in the browser. docsfy updates it as pages are written to the cache:

```py
if project_name:
    from docsfy.storage import update_project_status

    # Count cached pages to get current total
    existing_pages = len(list(cache_dir.glob("*.md")))
    await update_project_status(
        project_name,
        ai_provider,
        ai_model,
        owner=owner,
        status="generating",
        page_count=existing_pages,
        branch=branch,
    )
```

That has a few important consequences:

- The page count you see is the number of pages currently available for that variant.
- The total used for the progress bar comes from the saved plan (`plan_json`).
- Full regenerations reset the count to `0` so stale pages do not make the progress look ahead of reality.
- Incremental regenerations can start above `0` because unchanged cached pages are reused immediately.

> **Tip:** If an incremental run starts at `3 of 8 pages`, that usually means docsfy reused the other five cached pages and only needed to regenerate the remaining ones.

> **Note:** A run can show all pages counted while the badge still says `Generating`. That usually means page writing is complete and docsfy is in the final `rendering` stage. The docs are only finished when the status changes to `Ready`.

## Ready, Error, and Aborted

### Ready

A successful run ends in `ready`. The dashboard then shows:

- the final page count
- the commit SHA for the generated docs
- the last-generated timestamp
- buttons to view or download the generated site

If the selected commit is unchanged, docsfy still ends in `ready`, but the detail view shows **Documentation is already up to date.**

### Error

A run ends in `error` if docsfy cannot finish, for example because the AI CLI is unavailable, planning fails, or another exception stops the job. The detail view shows the backend `error_message`, and the regenerate section defaults to **Force full regeneration** so you can retry cleanly.

> **Warning:** If the server restarts while a variant is still `generating`, docsfy automatically converts that variant to `error` with the message `Server restarted during generation`. This prevents stale runs from looking permanently in progress.

### Aborted

A run ends in `aborted` when a user stops it from the generating view. The detail view keeps the variant visible, shows the abort message, and offers regeneration or deletion.

> **Note:** docsfy does not let you delete a variant while it is actively generating. Abort it first, then delete it if you no longer need it.

## WebSocket Behavior and Fallback

If you are logged into the browser UI, live updates work automatically through the same session. The server sends an initial `sync`, then periodic heartbeats and progress messages.

The current server heartbeat settings are:

```py
_WS_HEARTBEAT_INTERVAL = 30
_WS_PONG_TIMEOUT = 10
_WS_MAX_MISSED_PONGS = 2
```

On the frontend, docsfy reconnects up to three times with backoff. If that still fails, it falls back to polling `/api/projects` instead of leaving the dashboard stale:

```ts
private attemptReconnect(): void {
  if (this.reconnectAttempts >= this.maxReconnectAttempts) {
    console.debug('[WS] Falling back to polling')
    this.startPolling()
    return
  }
  const delay = this.getBackoffDelay()
  this.reconnectAttempts++
  console.debug('[WS] Reconnecting, attempt', this.reconnectAttempts)
  this.reconnectTimer = setTimeout(() => this.connect(true), delay)
}

private startPolling(): void {
  if (this.pollingTimer) return
  this.pollingTimer = setInterval(async () => {
    try {
      const data = await api.get<ProjectsResponse>('/api/projects')
      const syncMessage: WebSocketMessage = {
        type: 'sync' as const,
        projects: data.projects,
        known_models: data.known_models,
        known_branches: data.known_branches,
      }
      this.handlers.forEach(handler => handler(syncMessage))
    } catch {
      /* ignore polling errors */
    }
  }, WS_POLLING_FALLBACK_MS)
}
```

With the current frontend defaults, that fallback polling happens every 10 seconds.

> **Tip:** `docsfy generate --watch` uses the same WebSocket progress feed from the CLI, so you can follow stage and page-count updates in the terminal as well.

## Day-to-Day Workflow

In practice, tracking a run is simple:

1. Start the generation.
2. Stay on the selected variant while docsfy moves through cloning, planning, page generation, and rendering.
3. Watch the activity log and progress bar once the plan is available.
4. Open or download the docs when the badge turns `Ready`.
5. If the run fails or is aborted, read the message in the detail view and regenerate from there.

If you keep one rule in mind, the UI is easy to read: a run is only complete when the status changes to `Ready`. Until then, the dashboard is showing you live progress toward that final state.
