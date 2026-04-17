# WebSocket Reference

## Endpoint

### `/api/ws`

**Description:** Real-time endpoint for project sync and generation updates. One connection receives every update visible to the authenticated user. There is no subscribe or filter command.

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `scheme` | `ws` \| `wss` | `wss` on HTTPS, `ws` on HTTP | Transport scheme for the socket URL. |
| `path` | string | `/api/ws` | WebSocket endpoint path. |
| `token` | string | None | Optional query parameter. Accepts the raw `ADMIN_KEY` or a user's API key. No username parameter is used. |
| `docsfy_session` | string | None | Optional cookie. Opaque session token set by `POST /api/auth/login`; `HttpOnly`, `SameSite=Strict`, max age `28800` seconds, `Secure` controlled by `SECURE_COOKIES`. |

```js
// Same-origin browser session
const ws = new WebSocket('wss://docs.example.com/api/ws')

// Direct token auth
const wsWithToken = new WebSocket('wss://docs.example.com/api/ws?token=<API_KEY>')
```

**Return value/effect:**
- Successful connections are accepted and immediately receive a `sync` message.
- Admins receive updates for all variants.
- Other authenticated users receive updates for owned variants plus variants shared with them.
- Access grants and revocations trigger a new `sync` for the affected user.

| Close code | Effect |
| --- | --- |
| `1008` | Authentication failed. |
| `1001` | Heartbeat timeout after 2 missed `pong` replies. |

> **Note:** `/api/ws` authenticates with the `token` query parameter or the `docsfy_session` cookie. It does not read `Authorization` headers.

> **Note:** See [Manage Users, Roles, and Access](manage-users-roles-and-access.html) for access assignment and role details.

> **Warning:** `?token=` places credentials in the URL.

## Message Reference

### `sync`

**Description:** Full replacement snapshot for the authenticated user's visible project list and lookup maps.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | string | `sync` | Message discriminator. |
| `projects` | `Project[]` | `[]` | Visible project variants, sorted by `updated_at` descending. Includes owned variants and any shared variants the user can access. |
| `known_models` | `Record<string, string[]>` | `{}` | Ready model names grouped by provider. Built from ready projects only. |
| `known_branches` | `Record<string, string[]>` | `{}` | Ready branch names grouped by project name. Admins receive all ready branches; non-admins receive owned ready branches only. |

**`sync.projects[]` object**

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | string | n/a | Project name. |
| `branch` | string | `main` | Variant branch. |
| `ai_provider` | string | `""` | Provider name stored on the project record. |
| `ai_model` | string | `""` | Model name stored on the project record. |
| `owner` | string | `""` | Project owner username. |
| `repo_url` | string | n/a | Source repository URL, or the local repository path string when generation used `repo_path`. |
| `status` | string | `generating` | One of `generating`, `ready`, `error`, or `aborted`. |
| `current_stage` | string \| null | `null` | Current stage string, `up_to_date`, or `null`. |
| `last_commit_sha` | string \| null | `null` | Git commit SHA for the variant, when available. |
| `last_generated` | string \| null | `null` | Generation timestamp string in `YYYY-MM-DD HH:MM:SS` format, when available. |
| `page_count` | integer | `0` | Generated page count. |
| `error_message` | string \| null | `null` | Failure or abort text, when available. |
| `plan_json` | string \| null | `null` | Serialized documentation plan JSON string. |
| `created_at` | string | current timestamp | Row creation timestamp. |
| `updated_at` | string | current timestamp | Last update timestamp. |

```json
{
  "type": "sync",
  "projects": [
    {
      "name": "docsfy",
      "branch": "main",
      "ai_provider": "cursor",
      "ai_model": "gpt-5.4-xhigh-fast",
      "owner": "alice",
      "repo_url": "https://github.com/myk-org/docsfy",
      "status": "ready",
      "current_stage": null,
      "last_commit_sha": "abc123def456",
      "last_generated": "2026-04-17 12:34:56",
      "page_count": 14,
      "error_message": null,
      "plan_json": "{\"project_name\":\"docsfy\",\"navigation\":[...]}",
      "created_at": "2026-04-17 12:10:00",
      "updated_at": "2026-04-17 12:34:56"
    }
  ],
  "known_models": {
    "cursor": ["gpt-5.4-xhigh-fast"]
  },
  "known_branches": {
    "docsfy": ["main"]
  }
}
```

**Return value/effect:**
- Sent immediately after a successful connection.
- Sent again after server-side resync events, including terminal status updates, deletes, variant replacement, and access changes.
- Replace local state with the new payload instead of patching individual fields.

> **Warning:** `sync.projects[]` uses `ai_provider` and `ai_model`. `progress` and `status_change` use `provider` and `model`.

### `progress`

**Description:** Variant-scoped in-flight update while generation is still running.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | string | `progress` | Message discriminator. |
| `name` | string | n/a | Project name. |
| `branch` | string | `main` | Variant branch. |
| `provider` | string | n/a | AI provider for the active variant. |
| `model` | string | n/a | AI model for the active variant. |
| `owner` | string | n/a | Project owner username. |
| `status` | string | `generating` | Current run status. The current backend sends `generating` for this message type. |
| `current_stage` | string | Not sent | Current generation stage. |
| `page_count` | integer | Not sent | Generated page count so far. |
| `plan_json` | string \| null | Not sent | Serialized documentation plan JSON string. |
| `error_message` | string \| null | Not sent | In-flight error detail, when supplied by the backend. |

**`current_stage` values**

| Value | Description |
| --- | --- |
| `cloning` | Repository clone or local repository load has started. |
| `planning` | Full planning is running. |
| `incremental_planning` | Incremental planner is deciding which pages to regenerate. |
| `generating_pages` | Page generation is running. |
| `validating` | Post-generation validation is running. |
| `cross_linking` | Cross-linking and internal-link fixes are running. |
| `rendering` | Static site rendering is running. |

```json
{
  "type": "progress",
  "name": "docsfy",
  "branch": "main",
  "provider": "cursor",
  "model": "gpt-5.4-xhigh-fast",
  "owner": "alice",
  "status": "generating",
  "current_stage": "generating_pages",
  "page_count": 3,
  "plan_json": "{\"project_name\":\"docsfy\",\"navigation\":[...]}"
}
```

**Return value/effect:**
- Apply this message to the variant identified by `name`, `branch`, `provider`, `model`, and `owner`.
- During `generating_pages`, `page_count` increments as pages are generated.
- During later stages, `page_count` carries the generated page total.
- `plan_json` is a JSON string, not a parsed object.

> **Tip:** Match `progress` messages by `name`, `branch`, `provider`, `model`, and `owner`.

### `status_change`

**Description:** Variant-scoped terminal update.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | string | `status_change` | Message discriminator. |
| `name` | string | n/a | Project name. |
| `branch` | string | `main` | Variant branch. |
| `provider` | string | n/a | AI provider for the variant. |
| `model` | string | n/a | AI model for the variant. |
| `owner` | string | n/a | Project owner username. |
| `status` | string | n/a | Terminal status. One of `ready`, `error`, or `aborted`. |
| `page_count` | integer | Not sent | Final generated page count, when available. |
| `last_generated` | string \| null | Not sent | Completion timestamp in `YYYY-MM-DD HH:MM:SS` format. Sent on `ready`. |
| `last_commit_sha` | string \| null | Not sent | Commit SHA for the completed or reused variant, when available. |
| `error_message` | string \| null | Not sent | Failure or abort text, when available. |

**`status` values**

| Value | Description |
| --- | --- |
| `ready` | Generation completed successfully or the variant was reused as current. |
| `error` | Generation failed. |
| `aborted` | Generation was cancelled or aborted by the user. |

```json
{
  "type": "status_change",
  "name": "docsfy",
  "branch": "main",
  "provider": "cursor",
  "model": "gpt-5.4-xhigh-fast",
  "owner": "alice",
  "status": "ready",
  "page_count": 14,
  "last_generated": "2026-04-17 12:34:56",
  "last_commit_sha": "abc123def456"
}
```

**Return value/effect:**
- Emitted only for `ready`, `error`, and `aborted`.
- Every `status_change` is followed by a fresh `sync`.
- When a variant is reused without regeneration, the terminal message still uses `status: "ready"`. The following `sync.projects[]` record may show `current_stage: "up_to_date"`.

## Heartbeat

### `ping`

**Description:** Server heartbeat probe.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | string | `ping` | Heartbeat message sent by the server. |

```json
{
  "type": "ping"
}
```

**Return value/effect:**
- Sent every `30` seconds.
- The server waits `10` seconds for the matching `pong`.

### `pong`

**Description:** Client heartbeat reply.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | string | `pong` | Heartbeat reply sent by the client. |

```json
{
  "type": "pong"
}
```

**Return value/effect:**
- Resets the missed-heartbeat counter for the current connection.
- After `2` missed `pong` replies, the server closes the socket with code `1001`.
- Client messages other than valid JSON `{"type":"pong"}` are ignored.

## Related Pages

- [Track Generation Progress](track-generation-progress.html)
- [HTTP API Reference](http-api-reference.html)
- [Manage Users, Roles, and Access](manage-users-roles-and-access.html)
- [Fix Setup and Generation Problems](fix-setup-and-generation-problems.html)
- [Manage docsfy from the CLI](manage-docsfy-from-the-cli.html)