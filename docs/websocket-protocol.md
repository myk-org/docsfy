# WebSocket Protocol

`/api/ws` is docsfy's real-time update stream. Connect once, authenticate, read the initial `sync` snapshot, then apply live `progress` and `status_change` updates as work continues.

For most clients, the right mental model is simple:

- WebSocket gives you live updates for everything the current user is allowed to see.
- `sync` is the full snapshot and source of truth.
- `progress` and `status_change` are incremental updates for a single variant.
- `ping` / `pong` keeps the connection alive.
- If the socket is unavailable, fall back to polling `GET /api/projects`.

## Endpoint

The built-in frontend connects to the same host as the app and automatically chooses `ws://` or `wss://` based on the page URL:

```ts
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const url = `${protocol}//${window.location.host}/api/ws`
this.ws = new WebSocket(url)
```

That means:

- If you are serving docsfy over HTTPS, use `wss://`.
- If you are serving docsfy over plain HTTP, use `ws://`.
- The official frontend uses a same-origin connection to `/api/ws`.

## Authentication

docsfy supports two WebSocket authentication paths.

### 1. Session cookie

This is the normal browser flow.

1. Log in with `POST /api/auth/login`.
2. docsfy sets the `docsfy_session` cookie.
3. Open `/api/ws` on the same origin.
4. The browser automatically sends the cookie during the WebSocket handshake.

The session cookie is:

- `HttpOnly`
- `SameSite=Strict`
- `Secure` when `SECURE_COOKIES=true`
- an opaque session token, not your raw API key
- valid for 8 hours by default

> **Tip:** For browser-based integrations, prefer the session-cookie flow. It avoids putting API keys in URLs and matches how the official frontend works.

### 2. `?token=` query parameter

You can also authenticate by passing the raw admin key or a user's API key in the WebSocket URL:

`/api/ws?token=<API_KEY>`

This is useful for direct programmatic clients and test clients.

An actual token-authenticated connection from the codebase:

```python
with sync_client.websocket_connect(f"/api/ws?token={TEST_ADMIN_KEY}") as ws:
    data = ws.receive_json()
    assert data["type"] == "sync"
```

> **Warning:** `?token=` puts the credential in the URL. URLs can show up in logs, browser history, and monitoring tools. Prefer the session-cookie flow for browser use.

> **Note:** The REST API accepts `Authorization: Bearer ...`, but `/api/ws` does not read that header. WebSocket auth is handled by the session cookie or the `token` query parameter.

### What happens on auth failure?

If the connection is not authenticated, the server closes it with code `1008` (`policy violation`).

In browser-based tooling, you may see either the `1008` close code or a generic connection error, depending on the client and runtime.

## Connection model

A single WebSocket connection gives you all updates the authenticated user is allowed to receive. There is no subscribe message, room selection, or per-project topic negotiation.

The server behavior is:

1. Authenticate the connection.
2. Accept the WebSocket.
3. Register the connection under the current user.
4. Send an immediate `sync` message.
5. Start the heartbeat loop.
6. Continue sending `progress`, `status_change`, and occasional additional `sync` messages.

The only client message docsfy expects is:

```json
{"type":"pong"}
```

Malformed client messages are ignored, and message types other than `pong` are not used by the server.

Multiple simultaneous connections for the same user are supported, so multiple tabs can all receive the same updates.

### Who receives which updates?

docsfy delivers WebSocket updates to:

- admins
- the project owner
- users who have been granted access to that project

If an admin grants or revokes access, docsfy does not send a special `access_change` event. Instead, it sends a fresh `sync` to the affected user so the client can replace its local state.

## Message reference

| Message | When it is sent | What it contains |
| --- | --- | --- |
| `sync` | Immediately after connect, and whenever the server wants a full resync | Full project snapshot: `projects`, `known_models`, `known_branches` |
| `progress` | While a generation is in progress | Variant identity plus in-flight status and optional progress fields |
| `status_change` | When a variant reaches a terminal state | Variant identity plus final status and optional final metadata |
| `ping` | Heartbeat from server | `{ "type": "ping" }` |
| `pong` | Heartbeat reply from client | `{ "type": "pong" }` |

## `sync`

`sync` is the full replacement payload. When you receive it, you should treat it as the latest authoritative snapshot for the current user.

The official frontend type is:

```ts
export interface SyncMessage {
  type: 'sync'
  projects: Project[]
  known_models: Record<string, string[]>
  known_branches: Record<string, string[]>
}
```

A few important details:

- `projects` is the live list of accessible variants, including `generating`, `ready`, `error`, and `aborted` entries.
- `known_models` is grouped by provider and only includes models from `ready` projects.
- `known_branches` is grouped by project name and only includes branches from `ready` projects.
- `sync` uses the same underlying payload builder as `GET /api/projects`.

> **Tip:** If you already handle the `GET /api/projects` response, you are almost done handling `sync`. The only extra field is `type: "sync"`.

## `progress`

`progress` is sent while work is still running. This is how docsfy reports that a generation has started and how far it has gotten.

The server builds the message like this:

```python
message: dict[str, Any] = {
    "type": "progress",
    "name": project_name,
    "branch": branch,
    "provider": provider,
    "model": model,
    "owner": owner,
    "status": status,
}
if current_stage is not None:
    message["current_stage"] = current_stage
if page_count is not None:
    message["page_count"] = page_count
if plan_json is not None:
    message["plan_json"] = plan_json
if error_message is not None:
    message["error_message"] = error_message
```

In practice:

- `status` will be `generating`
- `current_stage` can move through `cloning`, `planning`, `incremental_planning`, `generating_pages`, and `rendering`
- `page_count` increases as pages are generated
- `plan_json` can appear before page generation finishes, so clients can show planned structure early
- `error_message` can appear if there is an in-flight problem worth surfacing

`plan_json` is a serialized JSON string, not an already-parsed object.

One subtle but important point: the transition into generation is reported as `progress`, not `status_change`.

## `status_change`

`status_change` is used for terminal states only. In the current backend, that means:

- `ready`
- `error`
- `aborted`

The message always includes the variant identity:

- `name`
- `branch`
- `provider`
- `model`
- `owner`
- `status`

It may also include:

- `page_count`
- `last_generated`
- `last_commit_sha`
- `error_message`

After a terminal `status_change`, the server also triggers a full `sync`. That gives clients a fast single-variant update first, followed by a full consistency pass.

> **Note:** `sync.projects` uses `ai_provider` and `ai_model` because it contains full `Project` records. Incremental WebSocket messages use `provider` and `model`. The official frontend maps between those field names when applying updates.

## Matching updates to a variant

When you receive `progress` or `status_change`, match them using the full variant identity:

- `name`
- `branch`
- `provider`
- `model`
- `owner`

That is the safest way to distinguish:

- different branches of the same repo
- different providers or models for the same repo
- different owners who generated the same repo name

## Heartbeat: `ping` and `pong`

The server sends heartbeat pings on a fixed interval:

```python
_WS_HEARTBEAT_INTERVAL = 30
_WS_PONG_TIMEOUT = 10
_WS_MAX_MISSED_PONGS = 2
```

That means:

- the server sends `{"type": "ping"}` every 30 seconds
- the client should reply with `{"type": "pong"}`
- the server waits up to 10 seconds for each pong
- after 2 missed pongs, the server closes the connection with code `1001`

The official frontend handles heartbeat like this:

```ts
if (isPingMessage(parsed)) {
  this.ws?.send(JSON.stringify({ type: 'pong' }))
  return
}
```

If you are writing your own client, implement the same behavior. You do not need to send periodic pings yourself unless your environment requires it for other reasons.

## Polling fallback

WebSocket is the preferred path, but docsfy's frontend is designed to keep working if the socket is unavailable.

The built-in behavior is:

- reconnect after non-normal closes
- try up to 3 reconnects
- use exponential backoff
- fall back to polling `GET /api/projects` every 10 seconds
- stop polling once WebSocket reconnects successfully

The actual fallback code converts the polling result into a synthetic `sync` message:

```ts
const data = await api.get<ProjectsResponse>('/api/projects')
const syncMessage: WebSocketMessage = {
  type: 'sync' as const,
  projects: data.projects,
  known_models: data.known_models,
  known_branches: data.known_branches,
}
this.handlers.forEach(handler => handler(syncMessage))
```

In the current frontend, the reconnect timing is effectively:

- attempt 1 after 1 second
- attempt 2 after 2 seconds
- attempt 3 after 4 seconds
- then polling every 10 seconds

> **Tip:** Treat `GET /api/projects` as the official fallback for `/api/ws`. If your client can already apply `sync`, you can reuse that same code path for polling recovery.

The dashboard also does a best-effort HTTP refresh if it receives an incremental update for a variant it does not yet have locally. That helps clients recover from edge cases where a new variant exists on the server before the local list has caught up.

## Configuration that affects WebSocket behavior

The most relevant environment settings are:

```env
# Required: Admin password (minimum 16 characters)
ADMIN_KEY=

# Cookie security (set to false for local HTTP development)
SECURE_COOKIES=true
```

`SECURE_COOKIES` matters for browser-based WebSocket auth because the official frontend relies on the `docsfy_session` cookie.

- In production, leave `SECURE_COOKIES=true` and use HTTPS/WSS.
- For local plain-HTTP development, docsfy lets you disable the `Secure` flag if needed.

## Practical client checklist

- Open one connection to `/api/ws` per active client session.
- Authenticate with the session cookie or `?token=<API_KEY>`.
- Treat the first `sync` as your initial state.
- Use `name + branch + provider + model + owner` to match incremental updates.
- Reply to every `ping` with `pong`.
- Fall back to `GET /api/projects` if the socket cannot stay connected.

If you follow that pattern, your client will behave the same way as docsfy's official frontend.
