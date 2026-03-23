# Generating Documentation

`docsfy` turns a Git repository into a static documentation site. It keeps separate outputs for different branches, providers, and models, so the same repository can have multiple documentation variants when you need them.

The project name is taken from the repository URL automatically. For example, `https://github.com/myk-org/for-testing-only` becomes `for-testing-only`.

## Before You Start

- Use a Git remote URL, not a local file path.
- You need write access to start or regenerate documentation.
- `docsfy` accepts normal HTTPS remotes and SSH remotes.

```text
https://github.com/myk-org/for-testing-only
git@github.com:org/repo.git
```

> **Note:** If you use an SSH URL, the server running `docsfy` must already be able to authenticate to that Git host.

> **Warning:** Repository URLs that point to `localhost` or other private-network addresses are rejected. Local `repo_path` generation exists in the API, but it is an admin-only workflow.

## Web App

To start a generation from the dashboard:

1. Open the `New Generation` form.
2. Enter the repository URL.
3. Choose a branch. The field defaults to `main`.
4. Choose a provider: `claude`, `gemini`, or `cursor`.
5. Choose a model from the suggestions, or type one manually.
6. Enable `Force full regeneration` only when you want a clean rebuild.
7. Click `Generate`.

When the request is accepted, the dashboard creates a generating variant and switches to live progress updates. The detail view shows the branch, provider/model, commit SHA, page count, and activity log while the run is in progress.

> **Tip:** The web form remembers the repository URL, branch, and Force checkbox for the current browser session.

> **Note:** Branch suggestions and model suggestions come from completed generations. In-progress or failed variants do not populate those lists.

## CLI

If you use the `docsfy` CLI, point it at your server first:

```bash
docsfy config set server "$DOCSFY_SERVER"
docsfy config set api-key "$DOCSFY_API_KEY"
```

Start a generation:

```bash
docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
```

Generate a specific branch and watch live progress:

```bash
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force --watch
```

`--branch` defaults to `main`. With `--watch`, the CLI follows the run in real time and prints the project name, branch, and current status as soon as the generation starts.

## API

Send a `POST` request to `/api/generate`. The API accepts `repo_url`, `branch`, `ai_provider`, `ai_model`, `ai_cli_timeout`, and `force`.

Replace the bearer token with your own API key and adjust the host if needed:

```bash
curl -s -X POST http://localhost:8800/api/generate \
  -H "Authorization: Bearer <TEST_USER_PASSWORD>" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/myk-org/for-testing-only","ai_provider":"gemini","ai_model":"gemini-2.5-flash"}'
```

A successful request returns `202 Accepted` and starts the generation asynchronously. The response includes the project name, status, and resolved branch. If you omit `branch`, the server resolves it to `main`.

> **Note:** You can also send `ai_cli_timeout` to override the server timeout for a single generation.

## Branches And Models

A documentation variant is scoped by project name, branch, provider, and model. That means `for-testing-only/main/gemini/gemini-2.5-flash` and `for-testing-only/dev/gemini/gemini-2.5-flash` are different variants.

If you do not set a branch, `docsfy` uses `main`. Valid branch examples from the test suite include:

```text
main
dev
v2.0
release-v2.0
v2.0.1
```

> **Warning:** Branch names with `/` are rejected. Use `release-v2.0` instead of `release/v2.0`.

If the selected branch does not exist on the remote, the generation fails during cloning and the variant ends in `error`.

Provider choices are fixed to `claude`, `gemini`, and `cursor`. In the web app, changing the provider updates the model suggestions for that provider. Because the model field is a combobox, you can still type a model name manually when it is not already suggested.

If you omit provider or model in the API or CLI, the server uses its configured defaults. The built-in defaults are:

```env
AI_PROVIDER=cursor
AI_MODEL=gpt-5.4-xhigh-fast
AI_CLI_TIMEOUT=60
```

> **Note:** In the default setup, new generations start from `cursor` and `gpt-5.4-xhigh-fast` unless you choose something else.

> **Warning:** The selected provider and model must be available on the server. If the provider CLI is missing or not authenticated there, the generation fails.

## Force Regeneration

`Force full regeneration` changes how aggressively `docsfy` reuses previous work.

| Force setting | Behavior |
| --- | --- |
| Off | `docsfy` reuses previous successful work when possible. If the commit is unchanged, the run can finish almost immediately as up to date. If only some files changed, `docsfy` can reuse the existing plan and regenerate only affected pages. |
| On | `docsfy` clears the target variant's cached page content, resets progress to `0`, runs a full planning step, and regenerates all pages from scratch. |

Force also matters when you change provider or model on an existing project. Without Force, `docsfy` may reuse the latest successful variant on the same project and branch as a base, and after the new run succeeds it may replace the older provider/model variant. With Force enabled, `docsfy` keeps the existing variant instead of replacing it.

> **Tip:** Use Force when you want a clean rebuild, when you suspect stale cached output, or when you want to keep the current variant and create a second provider/model variant beside it.

> **Note:** When a non-force regenerate finds that the latest generated commit is unchanged, the ready view reports that the documentation is already up to date.

## Track Progress

While a run is active, the dashboard and status pages receive live updates. Common stages include `cloning`, `planning`, `incremental_planning`, `generating_pages`, and `rendering`.

Once the variant reaches `ready`, you can open the generated site or download it as a `.tar.gz` archive. Variant-specific routes follow this pattern:

```text
/docs/for-testing-only/dev/gemini/gemini-2.5-flash/
/api/projects/for-testing-only/dev/gemini/gemini-2.5-flash/download
```

From the CLI, you can inspect the result later with:

```bash
docsfy status for-testing-only
```

> **Note:** Generated docs and download endpoints are authenticated. Open them from a logged-in browser session or an API client that sends a valid bearer token.

> **Warning:** Only one run can be active for the same project, branch, provider, and model at a time. If that exact variant is already generating, a second start request is rejected until the first run finishes or is aborted.
