# Projects API

docsfy stores generated documentation as **project variants**. A variant is one combination of:

- project name
- branch
- AI provider
- AI model
- owner

That design is what makes the Projects API useful: the same repository can exist multiple times at once for different branches, models, and users.

## Quick Reference
| Route | Purpose | Best for |
| --- | --- | --- |
| `GET /api/status` | List all visible variants | Dashboard-style listings |
| `GET /api/projects` | Alias for `/api/status` | Same payload as `/api/status` |
| `GET /api/projects/{name}` | List all visible variants for one project name | Variant browsing |
| `POST /api/generate` | Start a generation run | New docs or regeneration |
| `GET /api/projects/{name}/{branch}/{provider}/{model}` | Fetch one exact variant | Precise status/detail lookups |
| `POST /api/projects/{name}/abort` | Abort by project name | Convenience abort when only one run matches |
| `POST /api/projects/{name}/{branch}/{provider}/{model}/abort` | Abort one exact variant | Precise aborts |
| `DELETE /api/projects/{name}/{branch}/{provider}/{model}` | Delete one variant | Cleanup for one exact build |
| `DELETE /api/projects/{name}` | Delete all variants for one owner-scoped project | Bulk cleanup |
| `GET /api/projects/{name}/{branch}/{provider}/{model}/download` | Download one ready variant as `.tar.gz` | Deterministic downloads |
| `GET /api/projects/{name}/download` | Download the latest ready accessible variant | Convenience downloads |
| `GET /docs/{project}/{branch}/{provider}/{model}/{path:path}` | Serve generated HTML for one exact variant | Stable docs links |
| `GET /docs/{project}/{path:path}` | Serve generated HTML for the latest ready accessible variant | Convenience docs links |

> **Note:** `GET /api/status` and `GET /api/projects` are aliases. Both call the same handler and return the same payload.

## Authentication And Permissions

All project API routes and all `/docs/*` routes are authenticated.

- API clients use `Authorization: Bearer <API_KEY>`.
- Browsers use the `docsfy_session` cookie after logging in.
- `admin` and `user` can generate and abort.
- `viewer` is read-only.

> **Note:** Unauthenticated browser requests to `/docs/*` are redirected to `/login`. API-style requests get `401 Unauthorized`.

> **Warning:** `viewer` users can list projects, inspect variants, download ready docs, and open `/docs/*`, but write routes return `403 Write access required.`

## Runtime Settings

These defaults affect how the Projects API behaves:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admin_key: str = ""  # Required — validated at startup
    ai_provider: str = "cursor"
    ai_model: str = "gpt-5.4-xhigh-fast"
    ai_cli_timeout: int = Field(default=60, gt=0)
    log_level: str = "INFO"
    data_dir: str = "/data"
    secure_cookies: bool = True  # Set to False for local HTTP dev
```

Environment variables override these values, and `.env` is loaded automatically.

Practical implications:

- `ADMIN_KEY` is required, and startup fails without it.
- If you omit `ai_provider` or `ai_model` in `POST /api/generate`, the server defaults are used.
- `ai_cli_timeout` defaults to `60`.
- Browser auth assumes secure cookies unless you disable them for local HTTP development.

## Variant Identity And Branch-Aware URLs

The most precise routes include all four variant selectors:

- `{name}`
- `{branch}`
- `{provider}`
- `{model}`

That is the stable format to use when you want predictable behavior.

The test suite uses branch-aware URLs like these:

```python
response = await client.get("/api/projects/test-repo/v2.0/claude/opus")
response = await client.get("/docs/test-repo/v2.0/claude/opus/index.html")
response = await client.get("/api/projects/test-repo/v2.0/claude/opus/download")
```

> **Warning:** The convenience routes `GET /docs/{project}/...` and `GET /api/projects/{name}/download` are **not** pinned to `main`. They return the newest ready variant you can access, regardless of branch, provider, or model.

## Listing Projects And Variants

Use `GET /api/status` or `GET /api/projects` to get the visible project list. The payload also includes `known_models` and `known_branches`, which the web UI uses for suggestions.

The frontend types describe the response like this:

```ts
export interface Project {
  name: string
  branch: string
  ai_provider: string
  ai_model: string
  owner: string
  repo_url: string
  status: ProjectStatus
  current_stage: string | null
  last_commit_sha: string | null
  last_generated: string | null
  page_count: number
  error_message: string | null
  plan_json: string | null
  created_at: string
  updated_at: string
}

export interface ProjectsResponse {
  projects: Project[]
  known_models: Record<string, string[]>
  known_branches: Record<string, string[]>
}
```

Use `GET /api/projects/{name}` when you want all visible variants for one project name. The response shape is:

- `name`: the project name
- `variants`: every accessible variant for that project

For non-admin users, this endpoint merges:

- variants you own
- variants another owner explicitly shared with you

If nothing visible matches, the server returns `404`.

## Starting Generation

Use `POST /api/generate` to start a new run.

The request schema is defined like this:

```python
class GenerateRequest(BaseModel):
    repo_url: str | None = Field(
        default=None, description="Git repository URL (HTTPS or SSH)"
    )
    repo_path: str | None = Field(default=None, description="Local git repository path")
    ai_provider: Literal["claude", "gemini", "cursor"] | None = None
    ai_model: str | None = None
    ai_cli_timeout: int | None = Field(default=None, gt=0)
    force: bool = Field(
        default=False, description="Force full regeneration, ignoring cache"
    )
    branch: str = Field(
        default=DEFAULT_BRANCH, description="Git branch to generate docs from"
    )

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        if "/" in v:
            msg = (
                f"Invalid branch name: '{v}'. Branch names cannot contain slashes "
                "— use hyphens instead (e.g., release-1.x)."
            )
            raise ValueError(msg)
```

The web app sends generation requests like this:

```ts
await api.post('/api/generate', {
  repo_url: submittedRepoUrl,
  branch: submittedBranch,
  ai_provider: submittedProvider,
  ai_model: submittedModel,
  force: submittedForce,
})
```

A real API example from the branch-support test omits `branch`, so the server falls back to the default:

```shell
curl -s -X POST http://localhost:8800/api/generate -H "Authorization: Bearer <TEST_USER_PASSWORD>" -H "Content-Type: application/json" -d '{"repo_url":"https://github.com/myk-org/for-testing-only","ai_provider":"gemini","ai_model":"gemini-2.5-flash"}'
```

When accepted, the response is `202 Accepted` and includes:

- `project`: inferred from the repository URL or local path
- `status`: `generating`
- `branch`: the resolved branch value

### Request Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `repo_url` | Yes, unless `repo_path` is used | Remote Git URL. HTTPS and `git@host:org/repo.git` SSH-style URLs are accepted. |
| `repo_path` | Yes, unless `repo_url` is used | Absolute local Git repo path. Admin-only. Must exist and contain `.git`. |
| `ai_provider` | No | `claude`, `gemini`, or `cursor`. Defaults to server config if omitted. |
| `ai_model` | No | Model name. Defaults to server config if omitted. |
| `ai_cli_timeout` | No | Positive integer timeout for the AI CLI. |
| `force` | No | If `true`, ignore cache and do a full regeneration. |
| `branch` | No | Git branch to generate from. Defaults to `main`. |

> **Warning:** Branch names cannot contain `/`. `release/v2.0` is rejected; use a single path segment such as `release-v2.0`.

> **Warning:** `repo_path` is admin-only, must be absolute, and the checked-out local branch must match the `branch` you send.

> **Warning:** docsfy rejects repository URLs that point at `localhost`, private IP ranges, or other non-public network addresses.

### Generation Lifecycle

The stored `status` is one of:

- `generating`
- `ready`
- `error`
- `aborted`

While `status` is `generating`, `current_stage` can move through stages such as:

- `cloning`
- `incremental_planning`
- `planning`
- `generating_pages`
- `rendering`
- `up_to_date`

Related fields such as `page_count`, `plan_json`, `last_commit_sha`, and `error_message` are updated as the run progresses.

> **Tip:** If the same `owner/name/branch/provider/model` is already generating, the server returns `409`. Wait for it to finish, abort it, or change the variant.

## Looking Up One Variant

Use `GET /api/projects/{name}/{branch}/{provider}/{model}` when you need one exact variant.

This returns the full variant record, including:

- `status`
- `current_stage`
- `page_count`
- `last_commit_sha`
- `plan_json`
- `owner`

This is the safest route to use when:

- the same repo has multiple branches
- the same repo has multiple providers or models
- multiple owners may have matching variants

If the variant is not visible to the caller, docsfy returns `404` rather than exposing whether it exists under another owner.

## Aborting Generation

There are two abort routes.

### `POST /api/projects/{name}/abort`

This is a convenience route. It looks for an active run by project name only.

Use it when there is exactly one active run for that project name. If more than one active variant matches, the server returns `409` and tells you to use the branch-specific abort route.

### `POST /api/projects/{name}/{branch}/{provider}/{model}/abort`

This is the precise route. It targets one exact variant and is the safer choice for scripts, admin tools, and multi-owner installs.

The UI uses the variant-specific abort route like this:

```ts
await api.post(
  `/api/projects/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/abort?owner=${encodeURIComponent(project.owner)}`
)
```

A successful abort marks the variant as:

- `status: aborted`
- `error_message: "Generation aborted by user"`

## Deleting Variants

There are two delete routes.

### `DELETE /api/projects/{name}/{branch}/{provider}/{model}`

Deletes one exact variant.

### `DELETE /api/projects/{name}`

Deletes all variants for that project name within one owner scope.

The UI builds owner-scoped delete URLs like this:

```ts
await api.delete(
  `/api/projects/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}?owner=${encodeURIComponent(project.owner)}`
)
```

```ts
for (const owner of owners) {
  await api.delete(`/api/projects/${name}?owner=${encodeURIComponent(owner)}`)
}
```

Delete behavior is owner-aware:

- non-admin users can delete only their own variants
- admins must include `?owner=username` on delete routes
- if a matching variant is still generating, delete returns `409` and you must abort first

> **Warning:** Admin delete routes require `?owner=...` even when the path already includes `name`, `branch`, `provider`, and `model`.

> **Note:** Legacy pre-owner records can still be targeted with `?owner=` (empty string).

## Downloading Generated Docs

There are two download routes.

### `GET /api/projects/{name}/{branch}/{provider}/{model}/download`

Downloads one ready variant as a `.tar.gz` archive.

Rules:

- the variant must resolve successfully
- its status must be `ready`
- the rendered site directory must exist

The response is `application/gzip`, and the filename format is:

- variant-specific: `name-branch-provider-model-docs.tar.gz`

### `GET /api/projects/{name}/download`

Downloads the newest ready variant you can access for that project name.

Rules:

- it is not pinned to `main`
- it is not pinned to one provider or model
- it chooses the latest ready accessible variant
- the archive filename format is `name-docs.tar.gz`

> **Tip:** Use the variant-specific download route whenever branch, provider, model, or owner matters. The project-level download route is a convenience shortcut.

## Serving Generated Docs Over HTTP

docsfy can serve the generated HTML directly.

### Variant-Specific Docs

Use:

- `GET /docs/{project}/{branch}/{provider}/{model}/{path:path}`

Examples exercised by the test suite:

- `/docs/test-repo/main/claude/opus/index.html`
- `/docs/test-repo/main/claude/opus/introduction.html`
- `/docs/test-repo/v2.0/claude/opus/index.html`

A trailing slash works because docsfy treats an empty path as `index.html`.

### Latest Accessible Docs

Use:

- `GET /docs/{project}/{path:path}`

This is the convenience route that serves the newest ready accessible variant for that project name.

The implementation makes that behavior explicit:

```python
@app.get("/docs/{project}/{path:path}")
async def serve_docs(
    request: Request, project: str, path: str = "index.html"
) -> FileResponse:
    """Serve the most recently generated variant."""
    if request.state.is_admin:
        latest = await get_latest_variant(project)
    else:
        latest = await _resolve_latest_accessible_variant(
            request.state.username, project
        )
```

The UI builds variant-specific docs and download links like this:

```ts
const docsUrl = `/docs/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/?owner=${encodeURIComponent(project.owner)}`
const downloadUrl = `/api/projects/${project.name}/${project.branch}/${project.ai_provider}/${project.ai_model}/download?owner=${encodeURIComponent(project.owner)}`
```

> **Warning:** `/docs/{project}/...` is a latest-variant shortcut, not a branch shortcut. If you need `main`, `dev`, or a specific provider/model, use the full variant-specific docs route.

## Owner Scoping And Shared Access

Owner scoping is part of the API design.

A few rules matter in practice:

- `owner` is part of variant identity
- project access grants are scoped by both project name and project owner
- non-admin users cannot use `?owner=` to jump into another owner's namespace
- admins can use `?owner=` to disambiguate or target a specific owner's variant

This matters most when the same project name exists under multiple owners.

### What Shared Access Means

If an admin grants you access to another user's project:

- the project appears in your listings
- its variants are merged into `GET /api/projects/{name}`
- you can view ready docs and download them
- if your role is `user` or `admin`, you can abort accessible active runs
- you still cannot delete another user's variants unless you are an admin

### When Admins Should Use `?owner=`

Use `?owner=username` on:

- `GET /api/projects/{name}/{branch}/{provider}/{model}` when the same variant may exist under multiple owners
- `POST /api/projects/{name}/{branch}/{provider}/{model}/abort`
- `GET /api/projects/{name}/{branch}/{provider}/{model}/download`
- `GET /docs/{project}/{branch}/{provider}/{model}/...`
- all admin delete routes

> **Tip:** In multi-user installations, prefer variant-specific URLs plus `?owner=` instead of generic latest routes.

### When `?owner=` Does Not Solve It

The project-level convenience routes are intentionally broad:

- `POST /api/projects/{name}/abort` matches by project name only
- `GET /api/projects/{name}/download` chooses the newest ready accessible variant
- `GET /docs/{project}/...` chooses the newest ready accessible variant

If you need a deterministic owner, branch, provider, or model, use the variant-specific route instead.

## Common Responses And Failure Modes

| Status | When You Should Expect It |
| --- | --- |
| `200` | Successful list, lookup, delete, abort, download, or docs fetch |
| `202` | `POST /api/generate` accepted and queued |
| `400` | Invalid request data, invalid branch name, unsupported repo URL, admin delete without `?owner=`, or variant download before the variant is `ready` |
| `401` | Missing or invalid authentication |
| `403` | Write route called by a `viewer`, or a blocked file access attempt under `/docs/*` |
| `404` | Project/variant not found, not visible to the caller, no active generation, missing rendered file, or no ready docs available |
| `409` | Duplicate generation, multiple matching active abort targets, multiple owners matching a variant, or delete attempted while generation is still running |

A few especially important cases:

- inaccessible variants often return `404`, not `403`, so docsfy does not leak whether another owner's variant exists
- `POST /api/projects/{name}/abort` returns `409` if more than one active variant shares that project name
- delete routes return `409` if generation is still in progress for the target

## Practical Usage Pattern

Use these defaults:

- want everything you can see: `GET /api/status`
- want all variants for one project name: `GET /api/projects/{name}`
- want one exact variant: `GET /api/projects/{name}/{branch}/{provider}/{model}`
- want predictable docs links: `GET /docs/{project}/{branch}/{provider}/{model}/`
- want predictable downloads: `GET /api/projects/{name}/{branch}/{provider}/{model}/download`
- want a convenience shortcut to the newest ready docs: `GET /docs/{project}/`
- want to stop a specific run: `POST /api/projects/{name}/{branch}/{provider}/{model}/abort`
- want to clean up one owner's project as admin: use the delete routes with `?owner=username`

If you remember only one rule, make it this: when branch, provider, model, or owner matters, use the full variant-specific route. Generic project-level routes are shortcuts to **latest accessible**, not shortcuts to **main**.
