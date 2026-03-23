---
name: docsfy-generate-docs
description: Use when the user asks to generate documentation with docsfy, create docs for a repository using docsfy, or mentions docsfy documentation generation for any project
---

# Generate Documentation with docsfy

## Overview

Generate AI-powered documentation for a Git repository using the docsfy CLI. The CLI connects to a docsfy server that clones the repo, plans documentation structure, and generates pages using AI.

## Prerequisites (MANDATORY - check before anything else)

### 1. docsfy CLI installed

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

### GitHub Pages Setup (GitHub repos only)

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

| Parameter | Required | How to get |
|-----------|----------|------------|
| Repository URL | Yes | Ask user or infer from current repo's git remote |
| AI Provider | Yes | Ask user (options: `claude`, `gemini`, `cursor`) |
| AI Model | Yes | Ask user — provider-specific model name |
| Branch | No | Default: `main` |
| Output directory | No | Default: `docs/` |
| Force regeneration | No | Default: no |

Use `AskUserQuestion` to collect provider, model, and any missing parameters.

### Phase 2: Generate Documentation

```bash
docsfy generate <repo_url> --branch <branch> --provider <provider> --model <model> --watch [--force]
```

- Always use `--watch` for real-time WebSocket progress
- Add `--force` only if user requested force regeneration

Monitor output until generation completes with status `ready`, `error`, or `aborted`.

If generation fails, show the error and ask the user how to proceed.

### Phase 3: Download Generated Docs

After generation completes (status: `ready`):

```bash
docsfy download <project_name> --branch <branch> --provider <provider> --model <model> --output <output_dir>
```

`<project_name>` is extracted from the repo URL (e.g., `docsfy` from `https://github.com/myk-org/docsfy`).

### Phase 4: Summary

Display:
- Project name and repository URL
- Branch, provider, model used
- Output directory where docs were extracted
- Suggest: open `<output_dir>/index.html` in a browser

## Quick Reference

| Command | Purpose |
|---------|---------|
| `docsfy generate <url> --watch` | Generate docs with live progress |
| `docsfy status <name>` | Check generation status |
| `docsfy download <name> -o <dir>` | Download docs to directory |
| `docsfy list` | List all projects |
| `docsfy abort <name>` | Abort active generation |
| `docsfy health` | Check server connectivity |
| `docsfy config show` | Show server profiles |
| `docsfy config init` | Set up a new server profile |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Hardcoding provider/model | Always ask the user |
| Skipping health check | Server must be reachable before generating |
| Using local files instead of repo URL | docsfy works with Git repository URLs |
| Forgetting `--watch` flag | Always use `--watch` for real-time progress |
| Downloading before ready | Check status is `ready` before downloading |
