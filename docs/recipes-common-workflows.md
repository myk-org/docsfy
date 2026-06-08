# Common Workflow Recipes

Practical, copy-paste patterns for working with docsfy in real-world scenarios.

## Generate Docs for Multiple Branches

Generate documentation for `main` and a release branch from the same repository.

```bash
# Generate docs for the main branch (default)
docsfy generate https://github.com/your-org/your-repo

# Generate docs for a release branch
docsfy generate https://github.com/your-org/your-repo --branch release-2.x
```

Each branch produces its own independent documentation variant. Browse them at `/docs/your-repo/main/cursor/gpt-5.4-xhigh-fast/` and `/docs/your-repo/release-2.x/cursor/gpt-5.4-xhigh-fast/` respectively.

> **Note:** Branch names cannot contain slashes. Use hyphens instead — `release-2.x` not `release/2.x`.

## Force-Regenerate Stale Documentation

Discard all cached pages and rebuild documentation from scratch.

```bash
docsfy generate https://github.com/your-org/your-repo --force
```

The `--force` flag clears the page cache for the variant and runs a full regeneration instead of an incremental update. Use this when you suspect the docs have drifted from the code or after major refactors.

- Combine with `--branch` to force-regenerate a specific branch: `--force --branch dev`
- See [Working with Incremental Updates](incremental-updates.html) for how docsfy decides what to regenerate without `--force`

## Watch Generation Progress in Real Time

Start a generation and stream progress updates to your terminal.

```bash
docsfy generate https://github.com/your-org/your-repo --watch
```

The `--watch` flag opens a WebSocket connection and prints each stage (`cloning`, `analyzing`, `planning`, `generating_pages`, `validating`, `cross_linking`, `rendering`) as it completes. The command exits automatically when generation finishes or fails.

- Without `--watch`, the `generate` command returns immediately with a `generation_id` and the generation continues in the background
- Check status later with: `docsfy status your-repo`

## Download and Host a Static Documentation Site

Download the generated site and serve it locally with any static file server.

```bash
# Download as tar.gz archive
docsfy download your-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast

# Or extract directly into a directory
docsfy download your-repo -b main -p cursor -m gpt-5.4-xhigh-fast \
  --output ./docs-site --flatten

# Serve with Python's built-in HTTP server
cd docs-site && python -m http.server 3000
```

The `--flatten` flag removes the nested archive directory structure so `index.html` sits directly in the output directory. Without `--flatten`, files are extracted under a `your-repo-main-cursor-gpt-5.4-xhigh-fast/` subdirectory.

- The site is fully self-contained — no backend needed to serve it
- See [Managing Projects and Variants](managing-projects.html) for more download options

## Download Docs via the REST API (curl)

Download documentation without the CLI using a direct API call.

```bash
# Download the latest variant of a project
curl -H "Authorization: Bearer $DOCSFY_API_KEY" \
  https://docsfy.example.com/api/projects/your-repo/download \
  -o your-repo-docs.tar.gz

# Download a specific variant
curl -H "Authorization: Bearer $DOCSFY_API_KEY" \
  https://docsfy.example.com/api/projects/your-repo/main/cursor/gpt-5.4-xhigh-fast/download \
  -o your-repo-docs.tar.gz

# Extract
tar xzf your-repo-docs.tar.gz
```

This is useful in CI/CD pipelines or environments where installing the CLI is not practical.

## Automate Doc Generation in CI/CD (GitHub Actions)

Trigger documentation generation on every push to `main`.

```yaml
# .github/workflows/docs.yml
name: Generate Documentation
on:
  push:
    branches: [main]

jobs:
  generate-docs:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger doc generation
        run: |
          RESPONSE=$(curl -s -X POST \
            -H "Authorization: Bearer ${{ secrets.DOCSFY_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{
              "repo_url": "https://github.com/${{ github.repository }}",
              "branch": "main"
            }' \
            ${{ vars.DOCSFY_SERVER }}/api/generate)

          echo "$RESPONSE"
          GEN_ID=$(echo "$RESPONSE" | jq -r '.generation_id')
          echo "generation_id=$GEN_ID" >> "$GITHUB_OUTPUT"

      - name: Wait for generation
        run: |
          for i in $(seq 1 60); do
            STATUS=$(curl -s \
              -H "Authorization: Bearer ${{ secrets.DOCSFY_API_KEY }}" \
              ${{ vars.DOCSFY_SERVER }}/api/projects/by-id/$GEN_ID \
              | jq -r '.status')

            echo "Attempt $i: status=$STATUS"

            if [ "$STATUS" = "ready" ]; then
              echo "Documentation generated successfully!"
              exit 0
            elif [ "$STATUS" = "error" ] || [ "$STATUS" = "aborted" ]; then
              echo "Generation failed with status: $STATUS"
              exit 1
            fi

            sleep 10
          done
          echo "Timed out waiting for generation"
          exit 1
        env:
          GEN_ID: ${{ steps.*.outputs.generation_id }}
```

The `/api/generate` endpoint returns a `generation_id` (UUID) that you can poll via `/api/projects/by-id/{generation_id}` to check status. The generation runs asynchronously on the server.

> **Warning:** Store your API key in GitHub Secrets (`DOCSFY_API_KEY`), never in the workflow file. Set your server URL as a repository variable (`DOCSFY_SERVER`).

## Automate Doc Generation in CI/CD (GitLab CI)

Trigger doc generation from a GitLab pipeline.

```yaml
# .gitlab-ci.yml
generate-docs:
  stage: deploy
  image: curlimages/curl:latest
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  script:
    - |
      RESPONSE=$(curl -s -X POST \
        -H "Authorization: Bearer ${DOCSFY_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "{\"repo_url\": \"${CI_PROJECT_URL}.git\", \"branch\": \"main\"}" \
        ${DOCSFY_SERVER}/api/generate)

      echo "$RESPONSE"
      GEN_ID=$(echo "$RESPONSE" | jq -r '.generation_id')

      for i in $(seq 1 60); do
        STATUS=$(curl -s \
          -H "Authorization: Bearer ${DOCSFY_API_KEY}" \
          ${DOCSFY_SERVER}/api/projects/by-id/${GEN_ID} \
          | jq -r '.status')

        if [ "$STATUS" = "ready" ]; then exit 0; fi
        if [ "$STATUS" = "error" ] || [ "$STATUS" = "aborted" ]; then exit 1; fi
        sleep 10
      done
      exit 1
```

Set `DOCSFY_API_KEY` and `DOCSFY_SERVER` as CI/CD variables in GitLab project settings.

## Generate Docs with a Specific AI Provider

Override the server's default provider and model for a single generation.

```bash
# Use Claude
docsfy generate https://github.com/your-org/your-repo \
  --provider claude --model claude-sonnet-4-20250514

# Use Gemini
docsfy generate https://github.com/your-org/your-repo \
  --provider gemini --model gemini-2.5-pro
```

When you omit `--provider` and `--model`, the server defaults are used (configured via `AI_PROVIDER` and `AI_MODEL` environment variables). Each provider/model combination creates a separate variant.

- See [Configuring AI Providers](configuring-ai-providers.html) for supported providers and model selection
- View available models with `docsfy models`

## Specify the Repository Type

Hint the documentation style by specifying the repository type.

```bash
docsfy generate https://github.com/your-org/your-lib \
  --repo-type library

docsfy generate https://github.com/your-org/your-app \
  --repo-type app
```

Valid types are `app`, `library`, `framework`, and `tests`. When omitted, docsfy auto-detects the type from the repository structure. Setting it explicitly produces documentation tailored to that project type — for example, `library` documentation emphasizes API reference pages while `app` documentation focuses on setup and usage guides.

## Set Up CLI Server Profiles

Configure named server profiles to switch between environments.

```bash
# Interactive setup — creates a profile and sets it as default
docsfy config init

# Add a production profile manually
docsfy config set servers.prod.url https://docsfy.example.com
docsfy config set servers.prod.username admin
docsfy config set servers.prod.password your-api-key-here

# Switch the default profile
docsfy config set default.server prod

# Use a non-default profile for a single command
docsfy --server dev list
```

Configuration is stored in `~/.config/docsfy/config.toml` with file permissions restricted to the owner. See [Using the CLI](using-the-cli.html) for full CLI configuration details.

## Check Status of All Projects

List all projects with optional filtering.

```bash
# List all projects
docsfy list

# Filter by status
docsfy list --status ready
docsfy list --status generating

# Filter by provider
docsfy list --provider cursor

# JSON output for scripting
docsfy list --json | jq '.[] | select(.status == "error") | .name'
```

Use `docsfy status <project-name>` to see detailed information about a specific project and all its variants.

## Look Up a Project by Generation ID

Check the status of a specific generation run using its UUID.

```bash
# Check status by generation ID
docsfy status a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Download by generation ID
docsfy download a1b2c3d4-e5f6-7890-abcd-ef1234567890 --output ./docs

# Abort by generation ID
docsfy abort a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

The `generate` command prints the generation ID when it starts. All project commands (`status`, `download`, `delete`, `abort`) accept a generation ID in place of a project name, automatically resolving the correct variant.

## Delete a Specific Variant

Remove a single branch/provider/model variant without affecting others.

```bash
# Delete a specific variant
docsfy delete your-repo \
  --branch main --provider cursor --model gpt-5.4-xhigh-fast --yes

# Delete ALL variants of a project
docsfy delete your-repo --all --yes
```

Deleting a variant removes it from the database and cleans up its generated files from disk. Active generations must be aborted first — use `docsfy abort your-repo` before deleting.

- See [Managing Projects and Variants](managing-projects.html) for the full lifecycle

## Abort a Stuck Generation

Cancel an in-progress generation that is taking too long.

```bash
# Abort by project name (finds the active variant automatically)
docsfy abort your-repo

# Abort a specific variant
docsfy abort your-repo --branch dev --provider claude --model claude-sonnet-4-20250514
```

The aborted variant is marked with status `aborted`. You can then re-trigger generation with `docsfy generate`.

## Create a User and Grant Project Access

Set up a new user and share an existing project with them.

```bash
# Create a user (save the API key — it's shown only once)
docsfy admin users create alice --role user

# Grant access to a project
docsfy admin access grant your-repo --username alice --owner admin

# Verify access
docsfy admin access list your-repo --owner admin
```

Valid roles are `admin`, `user`, and `viewer`. Viewers have read-only access and cannot trigger generation or delete projects. See [Managing Users and Access Control](managing-users.html) for the full access model.

## Deploy to GitHub Pages After Generation

Download generated docs and publish them to GitHub Pages in CI.

```yaml
# .github/workflows/docs-pages.yml
name: Publish Docs to GitHub Pages
on:
  workflow_dispatch:

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
    steps:
      - name: Download docs
        run: |
          curl -H "Authorization: Bearer ${{ secrets.DOCSFY_API_KEY }}" \
            ${{ vars.DOCSFY_SERVER }}/api/projects/your-repo/download \
            -o docs.tar.gz
          mkdir -p docs-site
          tar xzf docs.tar.gz -C docs-site --strip-components=1

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: docs-site

      - name: Deploy to GitHub Pages
        uses: actions/deploy-pages@v4
```

The `--strip-components=1` removes the top-level archive directory so pages are deployed at the root. The generated site is fully static and works out of the box with GitHub Pages.

## Generate Docs via the REST API (Without CLI)

Trigger generation using `curl` when the CLI is not available.

```bash
# Start generation
curl -X POST \
  -H "Authorization: Bearer $DOCSFY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/your-org/your-repo",
    "branch": "main",
    "force": true
  }' \
  https://docsfy.example.com/api/generate

# Response:
# {"project":"your-repo","status":"generating","branch":"main","generation_id":"..."}
```

The `force` field is optional (defaults to `false`). You can also pass `ai_provider`, `ai_model`, and `repo_type` in the request body. See [REST API Reference](api-reference.html) for the full endpoint documentation.

> **Tip:** Pipe `curl` output through `jq` for readable JSON: `curl ... | jq .`

## Verify Server Health

Quickly check that the docsfy server and its AI sidecar are running.

```bash
# Via CLI
docsfy health

# Via curl (no auth required)
curl https://docsfy.example.com/health
# {"status":"ok"}
```

The `/health` endpoint is unauthenticated and returns `{"status": "ok"}` when the server is ready. The Docker healthcheck also validates the Pi SDK sidecar on its port.

## Related Pages

- [Using the CLI](using-the-cli.html)
- [Generating Documentation](generating-docs.html)
- [Managing Projects and Variants](managing-projects.html)
- [REST API Reference](api-reference.html)
- [Configuring AI Providers](configuring-ai-providers.html)