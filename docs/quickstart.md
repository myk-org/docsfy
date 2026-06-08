# Getting Started with docsfy

Generate a polished, browsable documentation site from any Git repository in minutes. This guide walks you through installing docsfy, configuring it, and producing your first set of docs.

## Prerequisites

- **Docker** and **Docker Compose** (for running the server)
- A **Git repository** (public HTTPS URL) you want to document
- (Optional) [uv](https://docs.astral.sh/uv/) for installing the CLI tool

## Quick Start

```bash
git clone https://github.com/myk-org/docsfy.git && cd docsfy
cp .env.example .env   # then set ADMIN_KEY (min 16 chars)
docker compose up       # open http://localhost:8000
```

That's it — the web dashboard is now running at `http://localhost:8000`. Log in with username `admin` and the `ADMIN_KEY` you set, paste a repo URL, and click **Generate**.

## Step-by-Step Setup

### 1. Clone the repository

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and set the required `ADMIN_KEY` value. This is the master password for the admin account and must be at least 16 characters:

```bash
ADMIN_KEY=your-secure-password-here
```

> **Warning:** Never commit your `.env` file to version control. It contains secrets.

For local HTTP development (not behind HTTPS), also add:

```bash
SECURE_COOKIES=false
```

### 3. Start the server

```bash
docker compose up
```

Docker builds the application image, starts the AI sidecar service, and launches the web server on port **8000**. Wait for the health check to pass, then open your browser to `http://localhost:8000`.

### 4. Log in

On the login screen, enter:

| Field    | Value                        |
|----------|------------------------------|
| Username | `admin`                      |
| Password | The `ADMIN_KEY` from `.env`  |

### 5. Generate your first docs

1. In the dashboard, paste a Git repository URL (e.g., `https://github.com/myk-org/for-testing-only`).
2. Leave **Branch** as `main` (or pick another branch).
3. Click **Generate**.
4. Watch the progress in real time — docsfy clones the repo, plans the documentation structure, generates pages with AI, and renders a static HTML site.

When the status shows **Ready**, click the project name to browse your generated docs.

> **Tip:** docsfy auto-detects the repository type (app, library, framework, or tests) and tailors the documentation structure accordingly. You can override this in the generate form if needed.

## Using the CLI

The CLI lets you do everything from the terminal — generate, check status, download, and manage projects.

### Install the CLI

```bash
uv tool install docsfy
```

### Configure a server profile

```bash
docsfy config init
```

You'll be prompted for:

| Prompt       | Example value              |
|--------------|----------------------------|
| Profile name | `dev`                      |
| Server URL   | `http://localhost:8000`     |
| Username     | `admin`                    |
| Password     | Your `ADMIN_KEY`           |

This saves a profile to `~/.config/docsfy/config.toml`. You can add multiple server profiles (dev, staging, prod) and switch between them with `--server`:

```bash
docsfy --server prod list
```

### Generate docs from the terminal

```bash
docsfy generate https://github.com/org/repo
```

Target a specific branch:

```bash
docsfy generate https://github.com/org/repo --branch dev
```

Watch generation progress in real time:

```bash
docsfy generate https://github.com/org/repo --watch
```

### Check project status

```bash
docsfy list
docsfy status my-repo
```

### Download generated docs

```bash
docsfy download my-repo --output ./my-docs --flatten
```

This extracts the generated HTML site into `./my-docs`, ready to deploy anywhere.

> **Tip:** See [Using the CLI](using-the-cli.html) for the full setup guide and [CLI Command Reference](cli-reference.html) for all available commands and flags.

## Understanding Variants

Every documentation build is a **variant** — a unique combination of project name, branch, AI provider, and AI model. This means you can generate docs for the same repo on different branches or with different AI models and compare the results side by side.

The URL pattern for browsing a specific variant is:

```
http://localhost:8000/docs/{project}/{branch}/{provider}/{model}/
```

For example: `http://localhost:8000/docs/my-repo/main/cursor/gpt-5.4-xhigh-fast/`

If you browse `/docs/{project}/` without specifying a variant, docsfy serves the most recently generated one.

See [Browsing Generated Documentation](browsing-docs.html) for more on navigating and sharing doc URLs.

## Advanced Usage

### Choosing an AI provider and model

docsfy supports three AI providers: **claude**, **gemini**, and **cursor**. The server defaults (set via `AI_PROVIDER` and `AI_MODEL` in `.env`) are used for new generations unless you override them.

From the CLI:

```bash
docsfy generate https://github.com/org/repo --provider claude --model claude-sonnet-4-20250514
```

To see available providers and models:

```bash
docsfy models
```

See [Configuring AI Providers](configuring-ai-providers.html) for details on provider setup and the sidecar service.

### Force a full regeneration

By default, docsfy performs **incremental updates** — it detects code changes since the last generation and only regenerates affected pages. To force a complete rebuild:

```bash
docsfy generate https://github.com/org/repo --force
```

Or check the **Force** checkbox in the web dashboard.

See [Working with Incremental Updates](incremental-updates.html) for how change detection works.

### Specifying the repository type

docsfy auto-detects whether your repo is an app, library, framework, or test suite. You can override this to get better-tailored documentation:

```bash
docsfy generate https://github.com/org/repo --repo-type library
```

Valid types: `app`, `library`, `framework`, `tests`.

### Managing users

Create additional user accounts with the CLI:

```bash
docsfy admin users create alice --role user
```

Roles control access levels:

| Role     | Permissions                              |
|----------|------------------------------------------|
| `admin`  | Full access — manage users, all projects |
| `user`   | Generate, view, and manage own projects  |
| `viewer` | Read-only access to shared projects      |

See [Managing Users and Access Control](managing-users.html) for the full user management guide.

### Running in production

For production deployments with persistent storage, TLS, and custom configuration, see [Deploying with Docker](deployment.html).

## Troubleshooting

**"ADMIN_KEY environment variable is required"**
Set `ADMIN_KEY` in your `.env` file. It must be at least 16 characters.

**Login works but the session drops immediately**
If you're running over plain HTTP (not HTTPS), set `SECURE_COOKIES=false` in `.env`. Secure cookies are rejected by browsers on non-HTTPS connections.

**"Variant is already being generated" (409 error)**
A generation is already running for the same project/branch/provider/model combination. Wait for it to finish, or abort it:

```bash
docsfy abort my-repo --branch main --provider cursor --model gpt-5.4-xhigh-fast
```

**Generation fails with sidecar errors**
The AI sidecar service must be running and healthy. In Docker, the entrypoint handles this automatically. Check the container logs for `[sidecar] Sidecar is ready`. If the sidecar isn't starting, verify your AI provider credentials are configured correctly — see [Configuring AI Providers](configuring-ai-providers.html).

**Branch names with slashes are rejected**
Branch names cannot contain `/` because they appear as URL path segments. Use hyphens instead (e.g., `release-1.x` instead of `release/1.x`).

## Next Steps

- [Generating Documentation](generating-docs.html) — detailed guide on all generation options
- [Managing Projects and Variants](managing-projects.html) — list, inspect, and delete projects
- [Configuration Reference](configuration-reference.html) — all environment variables and settings
- [Common Workflow Recipes](recipes-common-workflows.html) — CI/CD automation, multi-branch docs, and more

## Related Pages

- [Generating Documentation](generating-docs.html)
- [Deploying with Docker](deployment.html)
- [Using the CLI](using-the-cli.html)
- [Configuration Reference](configuration-reference.html)
- [Managing Projects and Variants](managing-projects.html)