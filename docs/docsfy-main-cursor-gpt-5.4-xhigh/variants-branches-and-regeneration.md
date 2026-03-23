# Variants, Branches, and Regeneration

In docsfy, a *variant* is one generated docs set for a specific repository, Git branch, AI provider, and AI model. Generate `main` with one model and `dev` with another, and docsfy treats those as different outputs with their own status, commit SHA, download link, and docs URL.

A few rules matter most:

- Omit `branch` and docsfy uses `main`.
- Omit `ai_provider` or `ai_model` and the server falls back to its configured defaults.
- Non-force runs try hard to reuse what is already known.
- Force runs skip reuse and rebuild from scratch.

## What A Variant Is

Branch, provider, and model are part of the public URL shape. That is why the same repository can have multiple independent variants at once.

Actual URLs used by the app and tests look like this:

```text
/docs/for-testing-only/dev/gemini/gemini-2.5-flash/
/api/projects/for-testing-only/dev/gemini/gemini-2.5-flash
/api/projects/for-testing-only/dev/gemini/gemini-2.5-flash/download
```

Each variant also has its own cache and rendered site on disk. For self-hosted installs, docsfy stores them under a branch/provider/model-specific directory, so `main` and `dev` do not overwrite each other.

> **Warning:** The shorter `/docs/<project>/` and `/api/projects/<name>/download` routes are not branch-pinned. They resolve to the most recently generated ready variant. If you care about a specific branch or model, use the full variant URL.

## Branches

Branch selection is part of the generation request, not an afterthought. In the request model, `branch` defaults to `main`, and `force` defaults to `false`:

```python
force: bool = Field(
    default=False, description="Force full regeneration, ignoring cache"
)
branch: str = Field(
    default=DEFAULT_BRANCH, description="Git branch to generate docs from"
)
```

That is why this real API example from the test plan creates a `main` variant even though it does not send a branch:

```shell
curl -s -X POST http://localhost:8800/api/generate \
  -H "Authorization: Bearer <TEST_USER_PASSWORD>" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/myk-org/for-testing-only","ai_provider":"gemini","ai_model":"gemini-2.5-flash"}'
```

When branch is omitted, the response includes `"branch": "main"`.

Branches are isolated from each other. A ready `main` variant can coexist with a `dev` variant that is still generating, and deleting one branch variant does not remove the other.

> **Warning:** docsfy rejects branch names that contain `/`. Use `release-1.x` instead of `release/1.x`. Branch names must be a single safe path segment because branch is part of the docs URL and API path.

If you request a branch that does not exist, generation fails for that variant and the variant ends in `error`. The branch-specific error is not silently ignored.

> **Tip:** In the web UI, the branch field is a combobox. It can suggest branches docsfy already knows about for that repo, but you can still type a new branch manually.

## Provider And Model Variants

docsfy supports three providers in code: `claude`, `gemini`, and `cursor`. The model name is stored as part of the variant too, so `gemini/gemini-2.5-flash` and `gemini/gemini-2.0-flash` are separate variants even when they point at the same repository and branch.

If you omit provider or model in the API or CLI, the server uses its configured defaults. The default settings in the code are:

```python
class Settings(BaseSettings):
    admin_key: str = ""
    ai_provider: str = "cursor"
    ai_model: str = "gpt-5.4-xhigh-fast"
    ai_cli_timeout: int = Field(default=60, gt=0)
    log_level: str = "INFO"
    data_dir: str = "/data"
```

Those can be overridden with environment variables such as:

```bash
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-pro
AI_CLI_TIMEOUT=120
```

A real CLI example from the repository's E2E plan looks like this:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force --watch
```

One important behavior is easy to miss: on a non-force run, docsfy does not only look at the exact same provider/model variant. It chooses the freshest ready variant on the same branch as a baseline, even if that baseline was generated with a different provider or model.

That baseline reuse works like this:

- If the baseline is a different provider/model variant and the requested commit is the same, docsfy can copy the existing artifacts directly and mark the new variant as up to date.
- If the commit changed, docsfy can still copy the baseline's cached content, reuse unchanged pages, and regenerate only what needs attention.
- After the new variant is ready, docsfy removes the reused baseline only when that baseline was a different provider/model variant.
- If you use `force`, docsfy does not do that replacement. The old variant stays, and the new one is built from scratch.

> **Tip:** If you want two provider/model outputs to coexist side by side for comparison, use `force` when creating the second one. A non-force provider/model switch may replace the baseline variant after the new one succeeds.

> **Note:** In the current UI, the "Regenerate Documentation" panel keeps the selected variant's branch. It lets you change provider, model, and `force`. To generate a different branch, start a new generation for that branch.

## How docsfy Decides Whether To Regenerate

On a non-force run, docsfy follows a simple sequence:

1. Pick a previous ready variant on the same branch as the baseline.
2. Compare the baseline commit SHA with the requested commit SHA.
3. If needed, fetch just enough Git history to diff the old and new commits.
4. Decide whether nothing changed, whether only some pages need updates, or whether a full rebuild is safer.

Here is the practical outcome:

| Situation | What docsfy does |
| --- | --- |
| Same commit SHA as the baseline | Marks the variant `ready` with `current_stage="up_to_date"` and skips planning and page generation |
| Different commit SHA, but Git diff shows no changed files | Treats the docs as up to date and skips regeneration |
| Different commit SHA, changed files, saved plan is available | Runs the incremental pipeline |
| `force=true` or no usable baseline/diff/plan | Falls back to a full regeneration from scratch |

An up-to-date run still ends in `ready`. The difference is that the stage is `up_to_date`, and the ready view in the UI shows "Documentation is already up to date."

## Incremental Updates

Incremental regeneration is not just "rerun everything faster." It is a diff-driven workflow.

When docsfy can take the incremental path, it:

- computes a Git diff between the previous and current commit,
- keeps the existing documentation plan when possible,
- asks an incremental planner which page slugs are affected,
- reuses cached pages that were not touched,
- updates only the pages that need changes.

Remote repositories are cloned shallowly first. When docsfy needs a diff, it fetches just enough history to reach the previous commit. If that fetch fails, incremental mode is abandoned and docsfy rebuilds fully.

The incremental planner can return three useful outcomes:

- `[]`: no page content needs to change, so cached pages are reused.
- A subset like `["introduction", "configuration"]`: only those pages are revisited.
- `["all"]`: every page is revisited, but the existing plan is still reused.

If the incremental planner fails or returns invalid output, docsfy treats that as `["all"]` rather than guessing.

That last case is important. If the incremental planner cannot safely narrow the change down, docsfy does **not** automatically re-plan the entire docs site. Instead, it keeps the old plan and revisits every page under that plan.

For page-level updates, docsfy uses a patch-style format instead of rewriting the whole page. This example is from the test suite:

```json
{
  "updates": [
    {
      "old_text": "## Configuration\n\nOld settings.\n",
      "new_text": "## Configuration\n\nNew settings.\n"
    }
  ]
}
```

That lets docsfy surgically replace only the changed block in an existing page. Unchanged pages stay cached, and even changed pages can often be updated without rewriting the rest of the document.

Incremental updates also preserve doc structure when they can. The repository's E2E tests verify that after an incremental run, the saved `plan_json` can remain unchanged while page content updates to the new commit.

## When docsfy Falls Back To A Full Regeneration

A full regeneration of the whole variant happens when docsfy cannot trust the incremental path.

Whole-variant full regeneration happens when:

- you select `Force full regeneration` in the UI,
- you pass `--force` in the CLI,
- you send `"force": true` in the API request,
- there is no usable previous ready variant to compare against,
- docsfy cannot fetch the previous commit needed for diffing a shallow clone,
- `git diff` fails,
- there is no saved plan to reuse,
- the saved `plan_json` exists but cannot be parsed,
- copying baseline artifacts during a provider/model switch fails.

When docsfy does a full regeneration, it clears stale cached page files first so removed pages do not linger on disk or show up in the rendered site by accident.

There is also a smaller, page-level fallback inside an otherwise incremental run. If an individual page update cannot be safely applied, docsfy regenerates just that page in full. That happens when:

- the incremental page response is not valid JSON,
- an `old_text` block is missing from the existing page,
- an `old_text` block appears more than once and is not unique,
- patch blocks overlap,
- the AI call for that page fails.

So there are really three levels of fallback:

- no work at all because the variant is already up to date,
- incremental run with selective page updates,
- full regeneration of one page or of the whole variant when safety checks fail.

## What You Will See While It Runs

While a generation is in progress, the main `status` value is one of:

- `generating`
- `ready`
- `error`
- `aborted`

During `generating`, docsfy also tracks a more specific `current_stage`. The stages used in code are:

- `cloning`
- `incremental_planning`
- `planning`
- `generating_pages`
- `rendering`
- `up_to_date`

On a forced full regeneration, docsfy resets the page count to `0` before rebuilding. Once the plan is ready, the UI can show progress as generated pages count up toward the total pages in the plan.

If you use the CLI with `--watch`, or the web dashboard, those stage changes are how you can tell whether docsfy is taking the fast incremental path or doing a full rebuild.

## Practical Examples

Generate a specific branch and model from the CLI:

```shell
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force --watch
```

Start a generation through the API and let branch default to `main`:

```shell
curl -s -X POST http://localhost:8800/api/generate \
  -H "Authorization: Bearer <TEST_USER_PASSWORD>" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/myk-org/for-testing-only","ai_provider":"gemini","ai_model":"gemini-2.5-flash"}'
```

Open or download an exact variant instead of "whatever is latest":

```text
/docs/for-testing-only/dev/gemini/gemini-2.5-flash/
/api/projects/for-testing-only/dev/gemini/gemini-2.5-flash/download
```

> **Tip:** When you bookmark docs, automate downloads, or share links with teammates, prefer the full variant URL. That keeps the result stable even after someone generates a newer branch or model for the same repository.
