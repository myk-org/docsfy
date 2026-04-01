# Introduction

`docsfy` is an AI-powered documentation generator for Git repositories. You give it a repo, a branch, and an AI provider/model, and it produces a polished static documentation site that you can browse in the web app, automate through the HTTP API, download as an archive, or manage from the CLI.

It is built for teams that want documentation to stay close to the codebase. Instead of relying on a long README or manually maintained pages, docsfy explores the repository itself, plans a documentation structure, writes markdown pages, renders them into HTML, and keeps track of each generated output as a distinct documentation variant.

## What docsfy does

- Generates documentation from Git repositories over HTTPS or SSH, and can also work from a local Git checkout when an admin provides a filesystem path.
- Tracks documentation as variants, so the same repository can have separate outputs for different branches, AI providers, AI models, and owners.
- Serves the latest or a specific variant through authenticated `/docs/...` routes, and can also package the generated site as a downloadable `.tar.gz`.
- Supports incremental refreshes: if the repository has not changed, docsfy can mark a variant as already up to date; if only part of the repo changed, it can regenerate only the affected pages.
- Runs a post-generation pipeline that can validate generated pages against the repository, add related-page cross-links, detect a project version for the site footer, and pre-render Mermaid diagrams to SVG when Mermaid CLI is available on the server.
- Produces a human-friendly static site and companion `llms.txt` / `llms-full.txt` files for AI-oriented consumption.

## Who it is for

- Self-hosters and platform admins who want a shared, authenticated documentation service for a team.
- Developers and technical writers who want fast first-pass docs generated directly from a repository.
- Internal users who only need read access to published documentation through the web app or generated site.
- Teams that need docs scoped by branch, model, or owner instead of a single global “latest” build.

docsfy has three built-in roles:

- `admin` can see everything, manage users, rotate user keys, and grant or revoke access to projects.
- `user` can generate, regenerate, abort, download, and delete their own documentation variants.
- `viewer` is read-only for docs and project listings, but can still sign in and rotate their own password/API key.

> **Note:** In docsfy, the “password” a user types into the web app or stores in the CLI config is an API key. The built-in admin uses `ADMIN_KEY`, and regular users get per-user keys created by an admin.

Admins see every project. Non-admin users see only projects they own or projects that have been explicitly shared with them.

## One Repository, Many Variants

A core docsfy idea is that documentation is not just “for a repo.” It is for a specific combination of:

- repository name
- branch
- AI provider
- AI model
- owner

That is why the dashboard groups a repository into branches and then into provider/model variants, and why the API has both “latest variant” routes and fully variant-specific routes.

> **Warning:** Branch names cannot contain `/`. Use names like `release-1.x` instead of `release/1.x`.

## The Main Workflows

### Web App

The web app is the easiest way to use docsfy day to day.

- Sign in at `/login` with a username and password/API key.
- Browse your accessible repositories in a sidebar project tree grouped by repository, branch, and provider/model variant. If you are an admin, same-named repositories stay separated by owner.
- Start a new generation by entering a repository URL, branch, provider, model, and optional force flag.
- Watch progress live in the selected variant view as docsfy moves through cloning, planning, page generation, validation, cross-linking, and rendering.
- Open the finished documentation in the browser, download it, regenerate it with different model settings, abort a run, or delete a variant.
- If you are an admin, create users and manage access to shared projects without leaving the dashboard.

The frontend sends generation requests with this exact shape:

```typescript
await api.post('/api/generate', {
  repo_url: submittedRepoUrl,
  branch: submittedBranch,
  ai_provider: submittedProvider,
  ai_model: submittedModel,
  force: submittedForce,
})
```

A normal browser-based workflow looks like this:

1. Sign in.
2. Click `New Generation`.
3. Enter a Git URL such as `https://github.com/myk-org/for-testing-only`.
4. Pick a branch and model.
5. Wait for the variant to move to `ready`.
6. Open or download the generated docs.

The app uses WebSocket updates for real-time status and falls back to polling if the socket is unavailable.

> **Tip:** Leave `Force full regeneration` off for normal refreshes. That lets docsfy reuse cached pages and skip work when a variant is already current.

### HTTP API

If you want automation, CI integration, or your own frontend, the HTTP API exposes the same core operations as the web app.

- `POST /api/generate` starts a new generation and returns immediately with a `202` response.
- `GET /api/projects` and `GET /api/status` return the projects you can access, plus known models and known branches.
- `GET /api/projects/{name}` returns all accessible variants for a repository.
- `GET /api/projects/{name}/{branch}/{provider}/{model}` returns one specific variant.
- `POST /api/projects/{name}/abort` and `POST /api/projects/{name}/{branch}/{provider}/{model}/abort` stop active runs.
- `GET /api/projects/{name}/download` and the variant-specific download route return the generated site as `application/gzip`.
- `/api/admin/...` routes handle user and access management for admins.
- `/api/auth/...` routes handle login, logout, “who am I”, and key rotation.

The app serves generated sites through two route shapes:

```python
@app.get("/docs/{project}/{branch}/{provider}/{model}/{path:path}")
@app.get("/docs/{project}/{path:path}")
```

That gives you two useful access patterns:

- a fully specific docs URL such as `/docs/for-testing-only/dev/gemini/gemini-2.5-flash/`
- a short `/docs/{project}/` URL that serves the most recently generated accessible variant

> **Note:** Browser access to `/docs/...` follows the same authentication rules as the rest of docsfy. If you want to publish the generated site somewhere else, use the download workflow and deploy the static files separately.

### Generated Sites

Every successful generation produces a static documentation site, not just an entry in the dashboard.

The generated site includes:

- a landing page and per-page HTML files
- a sidebar with grouped navigation
- in-page table of contents when a page has headings
- built-in search backed by `search-index.json`
- dark/light theme switching
- copy buttons and language labels on code blocks
- callout styling for blockquotes such as `> **Note:**`, `> **Warning:**`, and `> **Tip:**`
- previous/next navigation between pages
- detected version info in the footer when docsfy can find a version in project metadata or Git tags
- Mermaid diagrams pre-rendered to SVG when Mermaid CLI is available on the server
- AI-suggested `## Related Pages` sections when docsfy finds useful cross-page links
- `llms.txt` and `llms-full.txt` alongside the human-facing site

In practice, that means a finished docsfy build can be used in two different ways:

- as an authenticated site served directly by docsfy under `/docs/...`
- as a downloadable archive you unpack and host anywhere static HTML is accepted

Because docsfy writes a `.nojekyll` file into the output, the generated site is also friendly to GitHub Pages-style static hosting.

### CLI

The `docsfy` CLI is the terminal-first interface to the same server. It is useful for scripting, quick checks, and admin tasks.

The package exposes two entry points:

- `docsfy-server` starts the FastAPI application
- `docsfy` talks to a running server

A real CLI generation example from the repository’s test plans looks like this:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
```

Common CLI workflows include:

- `docsfy config init` to save a server profile
- `docsfy health` to verify the server is reachable
- `docsfy list` to see all visible projects
- `docsfy status <project>` to inspect variants
- `docsfy download <project> ...` to pull down generated docs
- `docsfy abort <project> ...` to stop an active generation
- `docsfy admin users ...` and `docsfy admin access ...` for admin-only management

If you want live terminal feedback, `docsfy generate` also supports `--watch`, which listens to the same WebSocket progress stream the web app uses and prints stage changes such as `cloning`, `planning`, `generating_pages`, `validating`, `cross_linking`, and `rendering`.

The CLI config file is a small TOML profile store:

```toml
[default]
server = "dev"

[servers.dev]
url = "http://localhost:8000"
username = "admin"
password = "<your-dev-key>"
```

> **Note:** The CLI calls the credential field `password`, but it is the same API key/admin key used elsewhere in docsfy.

## Configuration At A Glance

A minimal server setup starts with environment variables. The repository ships this example:

```dotenv
# Required: Admin password (minimum 16 characters)
ADMIN_KEY=

# AI provider and model defaults
# (pydantic_settings reads these case-insensitively)
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60

# Logging
LOG_LEVEL=INFO

# Data directory for database and generated docs
DATA_DIR=/data

# Cookie security (set to false for local HTTP development)
SECURE_COOKIES=true
```

Those settings tell docsfy:

- who the built-in admin is
- which AI provider/model to use by default
- where to store the database and generated sites
- whether session cookies should be marked `Secure`

> **Warning:** `ADMIN_KEY` is required, and both admin and custom user keys must be at least 16 characters long.

The provided Compose setup keeps deployment simple: it reads `.env`, exposes port `8000`, and persists generated output under `./data` mapped to `/data`.

> **Note:** The provided Docker build installs the Claude, Cursor, and Gemini CLIs inside the container, plus Chromium and Mermaid CLI (`mmdc`) for diagram rendering. If you use the containerized setup, that is the easiest way to start with all three supported providers and Mermaid diagram rendering in generated sites.

## Things To Know Before You Start

- Remote repository generation accepts standard HTTPS and SSH Git URLs.
- Local repository generation is supported through `repo_path`, but it is restricted to admins.
- The server defaults to the `cursor` provider and `gpt-5.4-xhigh-fast` model unless you override them.
- The “latest docs” route for a project serves the most recently generated accessible variant, not necessarily the only variant that exists.
- Admins can share access to a project owned by one user with other users or viewers without copying the generated files.

If you want the shortest path to value, start the server, create or obtain a key, generate one repository from the web app or CLI, and then decide whether your team prefers to work from the dashboard, the API, the downloaded static site, or all three.


## Related Pages

- [Architecture and Runtime](architecture-and-runtime.html)
- [First Run Quickstart](first-run-quickstart.html)
- [Projects, Variants, and Ownership](projects-variants-and-ownership.html)
- [Generating Documentation](generating-documentation.html)
- [CLI Workflows](cli-workflows.html)