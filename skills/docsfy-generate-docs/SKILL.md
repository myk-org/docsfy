---
name: docsfy-generate-docs
description: Use when the user asks to generate documentation with docsfy, create docs for a repository using docsfy, or mentions docsfy documentation generation for any project
---

# Generate Documentation with docsfy

## Overview

Generate AI-powered documentation for a Git repository using the docsfy CLI.
The CLI connects to a docsfy server that clones the repo, plans documentation structure, and generates pages using AI.

## Bug Reporting Policy (MANDATORY)

**DO NOT work around issues. Report them so they get fixed.**

When you encounter ANY error, unexpected behavior, or reproducible bug during this workflow:

1. **Determine the source:**
   - **CLI issue** (docsfy command fails, returns wrong data, unexpected behavior) → report to `https://github.com/myk-org/docsfy`
   - **Skill issue** (wrong instructions, missing step, workflow logic error) → report to `https://github.com/myk-org/claude-code-config`

2. **Ask the user:** "I encountered [issue]. Should I create a GitHub issue for this in [repo]?"

3. **NEVER work around the issue silently.** Do not:
   - Retry with arbitrary parameter changes hoping it works (documented retry loops like polling are fine)
   - Skip the failing step and continue
   - Apply a manual fix that hides the root cause
   - Say "this is a known limitation" without filing an issue

4. **After filing** (or if user declines), then proceed with the best available path.

The goal is to fix bugs at the source, not accumulate workarounds.

## Prerequisites (MANDATORY - check before anything else)

### 1. docsfy CLI installed

Check if `docsfy` is installed:

```bash
docsfy --help
```

If not found: `uv tool install docsfy`

### 2. Server is alive

```bash
docsfy health
```

If health check fails, inform the user that the docsfy server is not reachable and stop. The user may need to:

- Start the server: `docsfy-server`
- Check their config: `docsfy config show`
- Set up a profile: `docsfy config init`

## Workflow

### Phase 1: Collect Parameters

**Always ask the user — NEVER assume or hardcode provider/model:**

| Parameter | Required | How to get |
|-----------|----------|------------|
| Repository URL | Yes | Ask user or infer from current repo's git remote |
| AI Provider | Yes | From `docsfy models --json` → `providers` array |
| AI Model | Yes | From `docsfy models --json` → `available_models.<provider>` array of `{id, name}` objects |
| Branch | No | Default: `main` |
| Output directory | No | Default: `docs/` |
| Force regeneration | No | Only offered when re-generating an existing project |

**MANDATORY: Use `AskUserQuestion` to collect ALL parameters. Never skip a question.**

#### Step 1: Fetch existing projects and available models

Run both commands (can be parallel):

```bash
docsfy list --json
docsfy models --json
```

**From `docsfy list --json`** — check if the current repository + branch has been generated before.
Match by comparing BOTH:

- The current repo's git remote URL against `repo_url`
- The current git branch against `branch`

If multiple entries match (same repo, same branch, different provider/model), prefer the one
with the most recent `last_generated` timestamp.

Only consider entries with `status` equal to `ready`. Ignore failed, aborted, or in-progress entries.

**URL normalization:** Remote URLs may differ in format (SSH `git@github.com:org/repo.git`
vs HTTPS `https://github.com/org/repo.git`). Normalize both to `owner/repo` form before
comparing (strip protocol, host, `.git` suffix).
Key fields per entry:

```json
{
  "name": "project-name",
  "branch": "main",
  "ai_provider": "cursor",
  "ai_model": "gpt-5.4-xhigh-fast",
  "repo_url": "https://github.com/org/repo.git",
  "status": "ready",
  "last_generated": "2026-04-01 20:53:36"
}
```

**From `docsfy models --json`** — get available providers and models (same as before):

```json
{
  "providers": ["claude", "gemini", "cursor"],
  "default_provider": "cursor",
  "default_model": "gpt-5.4-xhigh-fast",
  "available_models": {
    "claude": [{"id": "claude-opus-4-6", "name": "Claude Opus 4"}],
    "cursor": [{"id": "composer-2-fast", "name": "Composer 2 Fast"}]
  }
}
```

Extract `providers` for provider selection and `available_models` for model selection.
Each model entry has `id` (use for API calls) and `name` (use for display).
Note: not all providers may have entries in `available_models` (e.g., `gemini` above has no models listed).

**Fallback behavior:**

- If `docsfy models` fails or returns empty/malformed JSON → fall back to hardcoded
  providers (`claude`, `gemini`, `cursor`) and free-form model input.
- If a provider's `available_models` list is empty → allow free-form model input for that provider.
- If `docsfy list` fails → treat as no previous generation (lose smart defaults
  but still use `models` data for provider/model selection).
- If both fail → hardcoded providers + free-form model + no smart defaults.

#### Step 2: Ask for parameters

Model is collected in Round 2 because it depends on the provider selected in Round 1.

**If a previous generation exists for this repo + branch:**

Show the user what was used before and present smart defaults:

**Round 1** — Present:

- Provider: show previous `ai_provider` as first option "(Previously used)", then other providers
- Repository URL: pre-fill from current repo
- Branch: pre-fill from current branch
- Output directory: default `docs/`
- Force regeneration: **always offer `--force`** since this is a re-generation of an existing project.
  Show when it was last generated: "Last generated: {last_generated}"

**Round 2** — After provider is selected, present models from `available_models.<selected_provider>`.
Use the `name` field for display and the `id` field for API calls.
If the user kept the same provider as before, show the previous `ai_model` as first option "(Previously used)".
Mark `default_model` as "(Recommended)" if it appears in the list and is different from the previous model.
If `available_models` does not contain the selected provider or the array is empty,
fall back to free-form model input.

**If NO previous generation exists:**

**Round 1** — Ask for provider (from `providers` array), repository URL, branch,
output directory. Do NOT offer `--force` (it does nothing for new generations).

**Round 2** — After provider is selected, present that provider's models from
`available_models.<selected_provider>` as `AskUserQuestion` options (use `name` for display, `id` for value).
If the provider matches `default_provider` and `default_model` appears in the list,
mark it as "(Recommended)" in the AskUserQuestion options.
If `available_models` does not contain the selected provider or the array is empty,
fall back to free-form model input.

### GitHub Pages Setup (GitHub repos only)

If the repository URL does not contain `github.com`, skip the GitHub Pages setup entirely and treat GitHub Pages as not configured.

If the repository is hosted on GitHub, check if GitHub Pages is configured to serve from `docs/` on the target branch:

```bash
gh api repos/<owner>/<repo>/pages --jq '.source' 2>/dev/null
```

- If **not configured** or returns error: ask the user if they want to enable GitHub Pages to serve the generated docs.
  - **Yes** → Configure GitHub Pages to serve from `docs/` on the target branch:

    ```bash
    gh api repos/<owner>/<repo>/pages -X POST -f "source[branch]=<branch>" -f "source[path]=/docs"
    ```

  - **No** → Skip and continue with generation.
- If **already configured** with `docs/` path: no action needed, continue.
- If **configured with a different path**: inform the user and ask how to proceed.

**Track whether GitHub Pages is confirmed to serve from `docs/` on the target branch**
(either pre-existing or newly set up) — this is needed for Phase 6.
If Pages is configured but serves from a different path and the user chose not to change it,
treat it as not configured for Phase 6 purposes.

### Phase 2: Generate Documentation

Run the generation command using **`Bash(run_in_background=true)`** since it is a long-running blocking operation:

```bash
docsfy generate <repo_url> --branch <branch> --provider <provider> --model <model> --watch [--force]
```

- Always use `--watch` for real-time WebSocket progress
- Add `--force` only if user requested force regeneration
- **Use `run_in_background=true`** on the Bash tool so the main conversation is not blocked.
  You will be notified when the command completes.

When the background command completes, check the output for status `ready`, `error`, or `aborted`.

If generation fails, show the error and ask the user how to proceed.

### Phase 3: Create Branch

After generation completes (status: `ready`), create a local branch to isolate docs changes.

**Note:** This phase assumes the current working directory is the target repository
(the same repo as `<repo_url>`). If the user provided a URL for a different
repository, inform them that the docs branch will be created in the current
local repository and confirm before proceeding.

**Extract `<project_name>`** from the repo URL: strip any trailing `/` and `.git` suffix, then take the last path segment (e.g., `docsfy` from `https://github.com/myk-org/docsfy.git`).

Before switching branches, check for uncommitted changes:

```bash
git status --porcelain
```

If the working tree is dirty, inform the user and ask whether to stash changes, abort, or continue.

Create the branch:

```bash
git fetch origin <branch>
git checkout -B docs/docsfy-<project_name> origin/<branch>
```

- `<branch>` is the branch parameter from Phase 1.
- Uses `-B` (capital B) to create or reset the branch if it already exists from a previous run.

This ensures docs changes are on a separate branch, not directly on the current working branch.

### Phase 4: Download Generated Docs

```bash
docsfy download <project_name> --branch <branch> --provider <provider> --model <model> --output <output_dir> --flatten
```

`<project_name>` is the same value extracted in Phase 3.

The `--flatten` flag extracts docs directly into `<output_dir>/` instead of creating a nested subdirectory. It also handles model names with special characters (e.g., brackets) safely.

If `--flatten` is not available (older CLI version), fall back to manual extraction:

```bash
NESTED_DIR="<output_dir>/<project>-<branch>-<provider>-<model>"
OUTPUT_DIR="<output_dir>"

if [ ! -d "$NESTED_DIR" ]; then
    echo "Error: Expected directory $NESTED_DIR not found"
    exit 1
fi

# Clear old content in output dir (preserve the nested dir itself)
find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 ! -path "$NESTED_DIR" -exec rm -rf {} +

# Move new content (POSIX-compatible; avoids glob issues with brackets in model names)
find "$NESTED_DIR" -mindepth 1 -maxdepth 1 -exec mv {} "$OUTPUT_DIR/" \;
rm -rf "$NESTED_DIR"
```

If the nested subdirectory does not exist after download, the project name or parameters may not match what was used during generation — surface the error to the user.

**IMPORTANT: Never edit generated documentation files.** The files in `<output_dir>/` are generated artifacts. If they contain errors, leaked secrets, or incorrect content, report the issue to docsfy (the generation pipeline) — do not manually edit the output files. Manual edits will be overwritten on the next regeneration.

### Phase 5: Security Scan

After downloading and flattening, scan ALL generated docs for leaked sensitive content before proceeding.

**This phase is MANDATORY — never skip it.**

Run Grep searches across all files in `<output_dir>/` for these patterns:

| Category | Grep Patterns | Notes |
|----------|--------------|-------|
| Private IPs | `192\.168\.`, `10\.\d+\.\d+\.\d+`, `172\.(1[6-9]\|2[0-9]\|3[01])\.` | Internal network addresses |
| Localhost | `localhost`, `127\.0\.0\.1`, `0\.0\.0\.0` | Local-only URLs |
| Home paths | `/home/\w+`, `/Users/\w+` | User-specific filesystem paths |
| Email addresses | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(com\|org\|io\|net\|dev)` | Real email addresses (ignore `user@example.com` patterns) |
| API key prefixes | `sk-`, `ghp_`, `gho_`, `github_pat_`, `xoxb-`, `xoxp-` | Known secret prefixes |
| Crypto keys | `BEGIN.*PRIVATE`, `ssh-rsa`, `ssh-ed25519` | Leaked private/public keys |
| Sensitive keywords | `password\s*[:=]`, `secret\s*[:=]`, `token\s*[:=]`, `api[_-]key\s*[:=]` | Hardcoded credentials (skip if in code examples showing placeholder values) |
| Env file refs | `\.env`, `credentials\.json`, `\.pem` | References to sensitive files |

**How to handle findings:**

- **No findings** → Report clean scan to user, proceed to Phase 6.
- **Findings detected** → Present ALL findings to the user with file, line number, and matched content. Ask the user how to proceed:
  - **Fix** → Edit the docs to redact/remove sensitive content, then re-scan.
  - **Ignore** → User confirms false positives, proceed to Phase 6.
  - **Abort** → Stop the workflow.

**After choosing Fix or Abort**, ask the user if they want to open a GitHub issue on `https://github.com/myk-org/docsfy` to report the leak. docsfy generated this content — if it's leaking sensitive data, that's a bug in the generation pipeline that needs to be fixed at the source. Include the leaked patterns, file names, and matched content in the issue body.

#### Secret Scanner Conflicts

Generated docs may contain placeholder tokens (e.g., `ghp_xxxxxxxxxxxx`, `sk-xxx`) that trigger secret scanning tools (pre-commit hooks, CI checks, GitHub Actions, etc.). These are not real secrets — they are example values in the documentation.

If committing or pushing fails due to secret scanner errors, exclude `<output_dir>/` from the scanner's configuration. The exact method depends on the tool:
- `.pre-commit-config.yaml` → add `exclude` pattern
- `.gitleaks.toml` → add path to `[allowlist]`
- `.detect-secrets` baseline → regenerate with `--exclude-files`
- CI pipeline config → add path exclusion

Ask the user before modifying any scanner configuration.

### Phase 6: GitHub Pages Post-Setup (conditional)

**This phase runs ONLY if GitHub Pages is confirmed to serve from `docs/` on the target branch** (determined in Phase 1).

#### 6a. Display Docs Site Link

Show the user the live documentation URL.

Extract `<owner>` and `<repo>` from the repository URL, then construct the URL:

- If the repo name equals `<owner>.github.io` (org/user pages site):
  `https://<owner>.github.io/`
- Otherwise: `https://<owner>.github.io/<repo>/`

Display the URL to the user.

#### 6b. Offer README Simplification

**Before asking, check if the README is already simplified.**

Read `README.md` in the repository root. Consider it "already simplified" if ALL of these are true:

- It contains a link to the docs site URL (from Phase 6a)
- It is shorter than 80 lines
- It does NOT contain detailed API documentation, configuration guides, or multi-section reference content
  - Specifically: it does NOT have sections like `## API Reference`, `## Configuration`,
    or `## Detailed Usage` with more than 3 subsections each

If unsure whether the README is already simplified, ask the user rather than deciding autonomously.

If already simplified: display "README already points to docs site — no changes needed." and skip.

If NOT simplified (or no README exists), ask the user:

> GitHub Pages is serving your docs. Would you like to simplify the project README to point to the docs site?

- **Yes, simplify README** → Create a simplified version that keeps ONLY:
  - Project title + one-line description
  - Link to the docs site prominently (use the URL from Phase 6a)
  - Quick start (e.g., docker run or install command, 5 lines max)
  - CLI install + 3-line usage example
  - "See the [full documentation](<docs_site_url>) for everything else"
  - License section

  Remove all other detailed content (API docs, configuration guides, detailed usage, etc.).
- **No, but add a docs link** → Keep the existing README content unchanged, but add a prominent link to the docs site near the top (after the title/description). Use a format like:
  ```markdown
  📖 **[Full Documentation](<docs_site_url>)**
  ```
- **No** → Skip entirely, make no changes to README.

### Phase 7: Commit, Push, and PR (optional)

Ask the user via `AskUserQuestion` if they want to commit, push, and create a PR for the docs changes:

Options:

- **Yes (Recommended)** — Commit all docs changes, push the branch, and create a PR
- **Commit only** — Commit locally but do not push
- **No** — Leave changes uncommitted

If **Yes**:

1. Stage all files in `<output_dir>/` and `README.md` (if simplified)
1b. **Offer to add docs guardrail** (if not already present):
       Check if `AGENTS.md` (or `CLAUDE.md`) contains a rule about not editing generated docs.
       If not, ask the user via `AskUserQuestion`:
       > "Would you like to add a rule to AGENTS.md that `<output_dir>/` should never be edited manually?"
       - **Yes** → Append to AGENTS.md:
         ```
         ## Generated Documentation

         The `<output_dir>/` directory contains AI-generated documentation from docsfy.
         **NEVER edit these files manually.** To update documentation, regenerate using docsfy.
         ```
         Stage `AGENTS.md` alongside the docs files.
       - **No** → Skip.
2. Commit with message: `docs: generate documentation with docsfy (<provider>/<model>)`
3. Push the branch: `git push -u origin docs/docsfy-<project_name>`
4. Create PR against the repository's default branch:
   `gh pr create --title "docs: add generated documentation" --body "Generated with docsfy using <provider>/<model>" --base $(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')`
5. Display the PR URL
6. Ask the user if they want to merge the PR now:
   - **Yes** → Merge with: `gh pr merge <PR_URL> --squash --delete-branch`
   - **No** → Skip, display: "PR is ready for review at <PR_URL>"

If **Commit only**:

1. Stage and commit (same as above, steps 1-2)
2. Display: "Changes committed locally. Push when ready with: `git push -u origin docs/docsfy-<project_name>`"

If **No**:

- Display: "Changes are on branch `docs/docsfy-<project_name>`. Commit when ready."

### Phase 8: Summary

Display:

- Project name and repository URL
- Branch, provider, model used
- Output directory where docs were extracted
- Docs site URL (if GitHub Pages is configured)
- Whether README was simplified (if applicable)
- Commit/push/PR status (if applicable)

## Quick Reference

| Command | Purpose |
|---------|---------|
| `docsfy generate <url> --watch` | Generate docs with live progress |
| `docsfy status <name>` | Check generation status |
| `docsfy download <name> -o <dir>` | Download docs to directory |
| `docsfy list` | List all projects |
| `docsfy abort <name>` | Abort active generation |
| `docsfy health` | Check server connectivity |
| `docsfy list --json` | List all previously generated projects |
| `docsfy models --json` | List all providers and their available models |
| `docsfy config show` | Show server profiles |
| `docsfy config init` | Set up a new server profile |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Hardcoding provider/model | Use `docsfy models --json` to get providers and models; free-form only on failure |
| Skipping health check | Server must be reachable before generating |
| Using local files instead of repo URL | docsfy works with Git repository URLs |
| Forgetting `--watch` flag | Always use `--watch` for real-time progress |
| Downloading before ready | Check status is `ready` before downloading |
| Leaving nested download folder | Flatten after download — move files to output root |
| Downloading before creating branch | Always create a docs branch before downloading |
| Showing docs link without Pages serving docs/ | Only show docs URL if GitHub Pages serves from `docs/` on target branch |
| Skipping security scan | Always scan docs for leaked private data before committing |
| Not excluding docs/ from secret scanners | Generated docs contain placeholder tokens that trigger secret scanners — exclude the output dir from the scanner's configuration |
| Editing generated docs manually | Generated docs must NEVER be edited — fix issues at the source (docsfy server/prompts), not in the output |
| Skipping --force when re-running existing project | When a prior generation exists for this repo+branch, always offer --force |
| Offering --force for new projects | Only offer --force when a matching `docsfy list` entry exists for this repo+branch |
