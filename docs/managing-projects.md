# Managing Projects and Variants

You want to view, inspect, download, stop, or clean up the documentation projects docsfy has generated — and manage the individual branch/provider/model **variants** within each project.

## Prerequisites

- A running docsfy server with at least one generated project
- The `docsfy` CLI installed and configured (see [Getting Started with docsfy](quickstart.html)), **or** access to the web dashboard
- A user account with appropriate permissions (viewers can list and download; users and admins can delete and abort)

## Quick Example

List all your projects in one command:

```
docsfy list
```

```
NAME              BRANCH  PROVIDER  MODEL                    STATUS  OWNER   PAGES  GEN ID
for-testing-only  main    cursor    gpt-5.4-xhigh-fast      ready   alice   12     a1b2c3d4-...
my-app            main    claude    claude-sonnet-4-0        ready   alice   8      e5f6a7b8-...
my-app            dev     gemini    gemini-2.5-pro           error   alice   0      c9d0e1f2-...
```

## Understanding Projects and Variants

A **project** corresponds to a Git repository (e.g., `my-app`). Each project can have multiple **variants** — one for every combination of:

- **Branch** (e.g., `main`, `dev`, `release-1.x`)
- **AI provider** (e.g., `claude`, `gemini`, `cursor`)
- **AI model** (e.g., `gpt-5.4-xhigh-fast`, `claude-sonnet-4-0`)

Each variant is identified by a unique **Generation ID** (UUID), which you can use interchangeably with the project name in most CLI commands.

## Listing Projects

### CLI

```
docsfy list
```

Filter by status or provider:

```
docsfy list --status ready
docsfy list --provider claude
```

Get machine-readable output:

```
docsfy list --json
```

### Web Dashboard

Log in to the dashboard. The project tree on the left groups variants by repository, then by branch. Click any variant to see its details in the right panel.

## Inspecting a Project

### CLI

View all variants of a project:

```
docsfy status my-app
```

Inspect a specific variant by providing branch, provider, and model:

```
docsfy status my-app --branch main --provider cursor --model gpt-5.4-xhigh-fast
```

You can also look up a variant by its Generation ID:

```
docsfy status a1b2c3d4-5678-9abc-def0-123456789abc
```

The output shows key details about each variant:

```
Project: my-app
Variants: 2

  main/cursor/gpt-5.4-xhigh-fast
    ID:      a1b2c3d4-5678-9abc-def0-123456789abc
    Status:  ready
    Owner:   alice
    Pages:   12
    Updated: 2026-06-07 14:30:00
    Commit:  abc1234d

  dev/gemini/gemini-2.5-pro
    ID:      e5f6a7b8-9012-3456-7890-abcdef012345
    Status:  error
    Owner:   alice
    Error:   AI provider timeout after 120s
```

Use `--json` for structured output suitable for scripts:

```
docsfy status my-app --json
```

### Web Dashboard

Click any variant in the project tree. The detail panel shows status, page count, commit SHA, generation cost, repo type, and a link to the source repository.

## Downloading Documentation

Download the generated static site as a `.tar.gz` archive.

### CLI

Download the latest ready variant:

```
docsfy download my-app
```

Download a specific variant:

```
docsfy download my-app --branch main --provider cursor --model gpt-5.4-xhigh-fast
```

Extract directly to a directory instead of saving the archive:

```
docsfy download my-app --output ./docs-site
```

Use `--flatten` to strip the top-level directory wrapper from the archive:

```
docsfy download my-app --output ./docs-site --flatten
```

You can also download by Generation ID:

```
docsfy download a1b2c3d4-5678-9abc-def0-123456789abc --output ./docs-site
```

### Web Dashboard

On the variant detail panel for any **Ready** variant, click the **Download** button to save the `.tar.gz` archive through your browser.

> **Tip:** For recipes on hosting downloaded sites with common static-file servers, see [Common Workflow Recipes](recipes-common-workflows.html).

## Aborting a Generation

Stop an in-progress generation when you realize you submitted the wrong branch or want to free up resources.

### CLI

Abort by project name (works when only one variant is actively generating):

```
docsfy abort my-app
```

Abort a specific variant:

```
docsfy abort my-app --branch dev --provider gemini --model gemini-2.5-pro
```

Abort by Generation ID:

```
docsfy abort a1b2c3d4-5678-9abc-def0-123456789abc
```

The variant status changes to **aborted** and the error message will read "Generation aborted by user."

### Web Dashboard

While a variant is generating, the detail panel shows an **Abort Generation** button. Click it and confirm the prompt. The progress bar stops and the status switches to **Aborted**.

> **Note:** Aborted variants keep any partially generated pages in cache. Regenerating the same variant will attempt an incremental update from where it left off — use **Force full regeneration** to start clean.

## Deleting Projects and Variants

### Deleting a Single Variant

Remove one specific branch/provider/model combination and all its generated files.

**CLI:**

```
docsfy delete my-app --branch main --provider cursor --model gpt-5.4-xhigh-fast
```

Add `--yes` to skip the confirmation prompt (useful in scripts):

```
docsfy delete my-app --branch main --provider cursor --model gpt-5.4-xhigh-fast --yes
```

**Web dashboard:** Click the **Delete** button on the variant detail panel and confirm.

### Deleting All Variants

Remove every variant of a project in one operation.

**CLI:**

```
docsfy delete my-app --all
```

**Web dashboard:** Right-click (or use the menu on) a project in the tree and choose **Delete All Variants**.

> **Warning:** Deletion is permanent. All generated pages, cached content, and metadata for the affected variant(s) are removed from the server.

### Deleting by Generation ID

You can pass a Generation ID instead of a project name. When combined with `--all`, it resolves the UUID to a project name first, then deletes all variants:

```
docsfy delete a1b2c3d4-5678-9abc-def0-123456789abc --all
```

Without `--all`, the UUID resolves to a specific variant's branch, provider, and model:

```
docsfy delete a1b2c3d4-5678-9abc-def0-123456789abc
```

## Variant Statuses

Every variant has one of four statuses:

| Status | Meaning |
|---|---|
| **ready** | Documentation generated successfully and is viewable/downloadable |
| **generating** | Generation is in progress — pages are being planned and written |
| **error** | Generation failed (check the error message for details) |
| **aborted** | Generation was manually cancelled by a user |

## Advanced Usage

### Filtering and Scripting with JSON Output

All listing and status commands support `--json` for programmatic use:

```bash
# Get all ready projects as JSON
docsfy list --status ready --json

# Extract page counts with jq
docsfy list --json | jq '.[] | {name, branch, page_count}'

# Check if a specific variant is ready
docsfy status my-app --branch main --provider cursor --model gpt-5.4-xhigh-fast --json \
  | jq -r '.status'
```

### Admin Operations

Admins see **all** projects across all users. When multiple users own variants of the same project name, use `--owner` to disambiguate:

```
docsfy status my-app --owner alice
docsfy delete my-app --branch main --provider cursor --model gpt-5.4-xhigh-fast --owner alice
docsfy abort my-app --owner bob
```

> **Note:** Admin deletion requires `--owner` (or `?owner=` in the API). This prevents accidental deletion of the wrong user's project.

### Active Generation Conflicts

You cannot delete a variant while it is actively generating. Abort it first:

```
docsfy abort my-app --branch dev --provider gemini --model gemini-2.5-pro
docsfy delete my-app --branch dev --provider gemini --model gemini-2.5-pro --yes
```

Similarly, you cannot start a new generation for a variant that is already generating — the server returns a `409 Conflict`.

### Viewing Documentation Without Downloading

You can browse generated docs directly in your browser at:

```
https://<your-server>/docs/<project>/<branch>/<provider>/<model>/
```

Or let the server serve the latest ready variant automatically:

```
https://<your-server>/docs/<project>/
```

See [Browsing Generated Documentation](browsing-docs.html) for details on search, variant switching, and sharing URLs.

### Regenerating a Variant

From the web dashboard, every ready, errored, or aborted variant shows a **Regenerate** section where you can change the provider, model, or toggle **Force full regeneration** before starting a new run.

From the CLI, use the `generate` command again with the same repo URL and variant parameters. See [Generating Documentation](generating-docs.html) for full details.

## Troubleshooting

**"No active generation for '...'" when aborting**
The generation already finished (or failed) before your abort request arrived. Run `docsfy status <project>` to check the current state.

**"Cannot delete '...' while generation is in progress"**
You must abort the active generation before deleting. Run `docsfy abort <project>` first.

**"Multiple owners found for this variant, please specify owner"**
This happens when an admin queries a project name that exists under multiple owners. Add `--owner <username>` to resolve the ambiguity.

**"Variant not ready" when downloading**
Only variants with status **ready** can be downloaded. Check `docsfy status <project>` and wait for generation to complete, or regenerate if the variant errored.

## Related Pages

- [Generating Documentation](generating-docs.html)
- [Browsing Generated Documentation](browsing-docs.html)
- [Using the CLI](using-the-cli.html)
- [CLI Command Reference](cli-reference.html)
- [Common Workflow Recipes](recipes-common-workflows.html)