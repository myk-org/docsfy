# Working with Incremental Updates

Keep your documentation in sync with your codebase without regenerating every page from scratch. When you re-run generation on a repository that already has docs, docsfy automatically detects what changed and updates only the affected pages — saving time and AI costs.

## Prerequisites

- A completed documentation generation for your repository (status: **ready**)
- New commits pushed to the branch you originally generated docs from

## Quick Example

Simply regenerate the same repository without the **Force** checkbox:

```bash
docsfy generate https://github.com/your-org/your-repo --branch main
```

docsfy compares the current commit against the last-generated commit, identifies which files changed, and regenerates only the documentation pages affected by those changes.

## How Incremental Updates Work

When you trigger a generation for a repository that already has documentation, docsfy follows this process:

1. **Clone and compare** — Clones the repository and checks the current commit SHA against the one stored from the last generation
2. **Skip if unchanged** — If the commit SHA matches, docsfy reports "Documentation is already up to date" and finishes immediately
3. **Compute the diff** — If commits differ, docsfy runs a `git diff` between the old and new commits to find changed files
4. **Incremental planning** — The AI reviews the list of changed files against the existing documentation plan and decides which pages need updates
5. **Selective regeneration** — Only the affected pages are regenerated, using the diff content to make targeted edits
6. **Post-processing** — Validation, cross-linking, and rendering run as usual on the final page set

> **Note:** If the diff cannot be computed (e.g., the old commit is unreachable), docsfy falls back to a full regeneration automatically. You never need to intervene.

## Triggering an Incremental Update

### From the Dashboard

1. Open the dashboard and select the variant you want to update in the sidebar
2. In the detail panel, find the **Regenerate** section
3. Leave the **Force full regeneration** checkbox **unchecked**
4. Click **Regenerate**

The activity log will show an `incremental_planning` stage instead of the full `planning` stage, confirming the incremental path is active.

### From the CLI

```bash
docsfy generate https://github.com/your-org/your-repo --branch main --watch
```

The `--watch` flag streams progress to your terminal so you can see each stage as it happens. You'll see output like:

```
[generating] incremental_planning
[generating] generating_pages (3 pages)
[generating] validating
[generating] cross_linking
[generating] rendering
Generation complete! (12 pages)
```

> **Tip:** Use `--watch` to confirm docsfy is using the incremental path. If you see `planning` instead of `incremental_planning`, the full planner ran — check the troubleshooting section below.

## How Pages Are Updated

When the incremental planner identifies pages that need changes, docsfy doesn't simply regenerate those pages from scratch. Instead, it uses a targeted patch approach:

1. The AI reads the existing page content and the relevant portions of the diff
2. It produces a set of **find-and-replace edits** — each specifying an exact block of existing text (`old_text`) and its replacement (`new_text`)
3. docsfy applies these edits to the existing page, preserving all untouched sections

This means your documentation maintains consistent style and structure across updates, with only the affected sections modified.

> **Note:** If the patch-based approach fails for a specific page (e.g., the AI can't locate the text to replace), docsfy automatically falls back to regenerating that page fully. Other pages in the same run are unaffected.

## Generation Stages

During an incremental update, you'll see these stages in the dashboard or CLI:

| Stage | Description |
|---|---|
| `cloning` | Cloning the repository and fetching the old commit for diffing |
| `analyzing` | Building a code knowledge graph for AI context |
| `incremental_planning` | AI determines which pages need updates based on changed files |
| `generating_pages` | Regenerating only the affected pages |
| `validating` | Checking for stale references in updated pages |
| `completeness_check` | Verifying no major new features are undocumented |
| `cross_linking` | Updating cross-references between pages |
| `rendering` | Building the final HTML documentation site |

Compare this to a full generation, which shows `planning` instead of `incremental_planning` and regenerates all pages.

## Forcing a Full Regeneration

Sometimes you want to regenerate everything from scratch — for example, after upgrading your AI provider or when you want a fresh documentation structure.

### From the Dashboard

Check the **Force full regeneration** checkbox before clicking Regenerate.

### From the CLI

```bash
docsfy generate https://github.com/your-org/your-repo --branch main --force
```

The `--force` flag:

- Clears all cached pages for the variant
- Runs the full AI planner to create a new documentation plan
- Regenerates every page from scratch
- Resets the page count to 0 during generation

> **Warning:** Force regeneration is significantly more expensive than an incremental update since it regenerates all pages. Use it only when you need a complete refresh.

## Advanced Usage

### Cross-Provider Updates

When you switch AI providers or models (e.g., from `claude` to `gemini`), docsfy reuses existing documentation content from the previous provider as a starting point:

1. The system finds the most recent ready variant for the same project and branch
2. It copies the cached page content from the existing variant to the new one
3. If the commit SHA is the same, the documentation is marked as up to date immediately
4. If commits differ, it runs the normal incremental update flow using the copied content

This means switching providers doesn't require a full regeneration — you get the benefit of incremental updates even across provider changes.

### Multi-Branch Incremental Updates

Each branch maintains its own commit tracking independently. Generating docs for the `dev` branch doesn't affect the `main` branch's incremental state:

```bash
# These track changes independently
docsfy generate https://github.com/your-org/your-repo --branch main
docsfy generate https://github.com/your-org/your-repo --branch dev
```

See [Generating Documentation](generating-docs.html) for more on branch-based generation.

### Diff Size Limits

Large diffs (over 30,000 characters) are automatically truncated before being sent to the AI. When this happens:

- The AI only considers the visible portion of the diff
- Pages affected by truncated changes may not be updated
- A force regeneration will capture all changes

If you've accumulated many commits since the last generation, consider using `--force` to ensure nothing is missed.

## Troubleshooting

**docsfy runs a full regeneration instead of incremental**

This happens when:
- No previous generation exists for this variant (first run)
- The previous generation didn't complete successfully (no stored commit SHA)
- The old commit can't be fetched for diffing (e.g., force-pushed history)
- The existing documentation plan can't be parsed

In all cases, docsfy falls back gracefully to a full generation. No action needed.

**Incremental update missed some changes**

If a page wasn't updated when it should have been:
- The incremental planner may not have associated the changed files with that page
- The diff may have been truncated (see Diff Size Limits above)
- Run `--force` to regenerate everything

**"Documentation is already up to date" but content seems stale**

This means the commit SHA matches the last generation. The repository hasn't been updated since docs were last generated. Push new commits and try again, or use `--force` to regenerate from the same commit.

See [Managing Projects and Variants](managing-projects.html) for how to inspect variant details including the last commit SHA.

## Related Pages

- [Generating Documentation](generating-docs.html)
- [Configuring AI Providers](configuring-ai-providers.html)
- [Managing Projects and Variants](managing-projects.html)
- [Common Workflow Recipes](recipes-common-workflows.html)
- [Configuration Reference](configuration-reference.html)