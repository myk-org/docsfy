# Get Started with docsfy

You want a working docsfy server quickly so you can sign in, run one real generation, and confirm the full flow before you tune anything else. This guide takes you from a fresh checkout to a browsable docs site with the shortest supported path.

## Prerequisites

- Docker with Compose
- A Git repository URL you want to document
- An `ADMIN_KEY` you can store in `.env` with at least 16 characters
- At least one working `cursor`, `claude`, or `gemini` model in the environment where docsfy runs

## Quick Example

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
cp .env.example .env
```

```dotenv
ADMIN_KEY=change-this-to-a-16-plus-character-password
SECURE_COOKIES=false
```

```bash
docker compose up --build -d
curl http://localhost:800/health
```

Open `http://localhost:800/login`, sign in as `admin` with the same `ADMIN_KEY`, then start a generation for `https://github.com/myk-org/for-testing-only`.

| Field | Value |
| --- | --- |
| Username | `admin` |
| Password | your `ADMIN_KEY` |
| Repository URL | `https://github.com/myk-org/for-testing-only` |
| Branch | `main` |
| Repository Type | `Auto-detect` |
| Force full regeneration | off |

> **Note:** This quick example uses plain local HTTP, so `SECURE_COOKIES=false` is required for the browser session to stick on `http://localhost`.

## Step-by-step

1. Prepare your local config.

```bash
cp .env.example .env
```

Set these values first:

```dotenv
ADMIN_KEY=change-this-to-a-16-plus-character-password
SECURE_COOKIES=false
```

Leave the checked-in AI defaults alone for your first run unless you already know you need a different provider or model. Do not commit `.env`.

| Where you open docsfy | `SECURE_COOKIES` |
| --- | --- |
| `http://localhost:800` | `false` |
| HTTPS deployment | `true` |

> **Warning:** The server refuses to start if `ADMIN_KEY` is missing or shorter than 16 characters.

2. Start the server.

```bash
docker compose up --build -d
```

```bash
curl http://localhost:800/health
```

When the health check succeeds, docsfy is ready at `http://localhost:800`. The Compose setup also mounts `./data` into the container, so your database and generated docs survive restarts.

3. Sign in as the built-in admin.

Open `http://localhost:800/login` and enter the same values you just configured.

| Field | Value |
| --- | --- |
| Username | `admin` |
| Password | your `ADMIN_KEY` |

![docsfy login page with username and password fields](images/login-page.png)

After sign-in, you land on the dashboard and can start a generation right away.

![Dashboard showing the project sidebar with project count and total generation cost](images/dashboard.png)

4. Start your first generation.

Use a small public repository for the easiest first run. In **New Generation**, enter these values and click **Generate**.

```text
Repository URL: https://github.com/myk-org/for-testing-only
Branch: main
Repository Type: Auto-detect
Provider: cursor
Model: gpt-5.4-xhigh-fast
Force full regeneration: off
```

Leave **Repository Type** on **Auto-detect** and keep **Force full regeneration** off for this first pass. See [Generate Documentation](generate-documentation.html) for the full field-by-field guide.

![New generation form with repository URL, branch, provider, model, vision provider, and repository type fields](images/generate-form.png)

5. Wait for the run to finish.

docsfy opens the new variant view and updates it as the run progresses. When the status becomes `Ready`, use **View Documentation** to open the generated site.

See [Track Generation Progress](track-generation-progress.html) if you want the meaning of each stage or need to monitor a longer run.

![Variant detail panel showing generation status, page count, commit SHA, and documentation links](images/variant-detail.png)

Once the project appears in the sidebar, you can expand it to see the branch and model variant that was generated.

![Dashboard with project tree expanded showing variants, branches, and generation status](images/dashboard-expanded.png)

6. Open your docs site.

Click **View Documentation** to open the finished site in a new tab. You should see a homepage with sidebar navigation and links for the pages docsfy generated from your repository.

See [Browse and Download Docs](browse-and-download-docs.html) when you want direct doc URLs, downloadable artifacts, or the generated `llms.txt` files.

![Generated documentation site homepage with navigation sidebar and getting started links](images/docs-site-index.png)

Open any page from the sidebar to confirm that the generated content rendered cleanly.

![Generated documentation page showing formatted content with code blocks and navigation](images/docs-site-page.png)

## Advanced Usage

- Keep the defaults for your first run, then switch providers or models only if your environment is already set up for them. See [Configure AI Providers and Models](configure-ai-providers-and-models.html) for model refresh, provider setup, and vision options.
- For your first run, leave **Repository Type** on **Auto-detect**. If docsfy guesses wrong or you want to force a different documentation style, see [Generate Documentation](generate-documentation.html).
- Keep **Force full regeneration** off unless you need a clean rebuild. See [Regenerate After Code Changes](regenerate-after-code-changes.html) for when to use it.
- If you switch providers, the model picker updates to show the models docsfy knows about for that provider.

![Generate form with Gemini provider selected showing the available AI models dropdown](images/generate-form-models.png)

- If you want a terminal-first workflow after this browser setup, see [Set Up the CLI](set-up-the-cli.html). For copy-paste command patterns, see [Run Common CLI Workflows](common-workflow-recipes.html).
- If you want to run docsfy outside Docker or prepare a longer-lived environment, see [Deploy docsfy](deploy-docsfy.html).

## Troubleshooting

- If the container exits immediately, re-check `.env`. `ADMIN_KEY` is required and must be at least 16 characters long.
- If you can load the login page but keep getting sent back to `/login` on `http://localhost`, set `SECURE_COOKIES=false`, restart the stack, and sign in again.
- If `curl http://localhost:800/health` never succeeds, run `docker compose logs -f docsfy` and fix the startup error before trying to sign in.
- If the server is healthy but generation fails quickly, the selected provider or model is not ready in the environment running docsfy. See [Configure AI Providers and Models](configure-ai-providers-and-models.html).
- If the repository URL is rejected, use a full hosted Git URL such as `https://github.com/myk-org/for-testing-only.git` or `git@github.com:myk-org/for-testing-only.git`.# Get Started with docsfy

You want a working docsfy server quickly so you can sign in, run one real generation, and confirm the full flow before you tune anything else. This guide takes you from a fresh checkout to a browsable docs site with the shortest supported path.

## Prerequisites

- Docker with Compose
- A Git repository URL you want to document
- An `ADMIN_KEY` you can store in `.env` with at least 16 characters
- At least one working `cursor`, `claude`, or `gemini` model in the environment where docsfy runs

## Quick Example

```bash
git clone https://github.com/myk-org/docsfy.git
cd docsfy
cp .env.example .env
```

```dotenv
ADMIN_KEY=change-this-to-a-16-plus-character-password
SECURE_COOKIES=false
```

```bash
docker compose up --build -d
curl http://localhost:8000/health
```

Open `http://localhost:8000/login`, sign in as `admin` with the same `ADMIN_KEY`, then start a generation for `https://github.com/myk-org/for-testing-only`.

| Field | Value |
| --- | --- |
| Username | `admin` |
| Password | your `ADMIN_KEY` |
| Repository URL | `https://github.com/myk-org/for-testing-only` |
| Branch | `main` |
| Repository Type | `Auto-detect` |
| Force full regeneration | off |

> **Note:** This quick example uses plain local HTTP, so `SECURE_COOKIES=false` is required for the browser session to stick on `http://localhost`.

## Step-by-step

1. Prepare your local config.

```bash
cp .env.example .env
```

Set these values first:

```dotenv
ADMIN_KEY=change-this-to-a-16-plus-character-password
SECURE_COOKIES=false
```

Leave the checked-in AI defaults alone for your first run unless you already know you need a different provider or model. Do not commit `.env`.

| Where you open docsfy | `SECURE_COOKIES` |
| --- | --- |
| `http://localhost:8000` | `false` |
| HTTPS deployment | `true` |

> **Warning:** The server refuses to start if `ADMIN_KEY` is missing or shorter than 16 characters.

2. Start the server.

```bash
docker compose up --build -d
```

```bash
curl http://localhost:8000/health
```

When the health check succeeds, docsfy is ready at `http://localhost:8000`. The Compose setup also mounts `./data` into the container, so your database and generated docs survive restarts.

3. Sign in as the built-in admin.

Open `http://localhost:8000/login` and enter the same values you just configured.

| Field | Value |
| --- | --- |
| Username | `admin` |
| Password | your `ADMIN_KEY` |

![docsfy login page with username and password fields](images/login-page.png)

After sign-in, you land on the dashboard and can start a generation right away.

![Dashboard showing the project sidebar with project count and total generation cost](images/dashboard.png)

4. Start your first generation.

Use a small public repository for the easiest first run. In **New Generation**, enter these values and click **Generate**.

```text
Repository URL: https://github.com/myk-org/for-testing-only
Branch: main
Repository Type: Auto-detect
Provider: cursor
Model: gpt-5.4-xhigh-fast
Force full regeneration: off
```

Leave **Repository Type** on **Auto-detect** and keep **Force full regeneration** off for this first pass. See [Generate Documentation](generate-documentation.html) for the full field-by-field guide.

![New generation form with repository URL, branch, provider, model, vision provider, and repository type fields](images/generate-form.png)

5. Wait for the run to finish.

docsfy opens the new variant view and updates it as the run progresses. When the status becomes `Ready`, use **View Documentation** to open the generated site.

See [Track Generation Progress](track-generation-progress.html) if you want the meaning of each stage or need to monitor a longer run.

![Variant detail panel showing generation status, page count, commit SHA, and documentation links](images/variant-detail.png)

Once the project appears in the sidebar, you can expand it to see the branch and model variant that was generated.

![Dashboard with project tree expanded showing variants, branches, and generation status](images/dashboard-expanded.png)

6. Open your docs site.

Click **View Documentation** to open the finished site in a new tab. You should see a homepage with sidebar navigation and links for the pages docsfy generated from your repository.

See [Browse and Download Docs](browse-and-download-docs.html) when you want direct doc URLs, downloadable artifacts, or the generated `llms.txt` files.

![Generated documentation site homepage with navigation sidebar and getting started links](images/docs-site-index.png)

Open any page from the sidebar to confirm that the generated content rendered cleanly.

![Generated documentation page showing formatted content with code blocks and navigation](images/docs-site-page.png)

## Advanced Usage

- Keep the defaults for your first run, then switch providers or models only if your environment is already set up for them. See [Configure AI Providers and Models](configure-ai-providers-and-models.html) for model refresh, provider setup, and vision options.
- For your first run, leave **Repository Type** on **Auto-detect**. If docsfy guesses wrong or you want to force a different documentation style, see [Generate Documentation](generate-documentation.html).
- Keep **Force full regeneration** off unless you need a clean rebuild. See [Regenerate After Code Changes](regenerate-after-code-changes.html) for when to use it.
- If you switch providers, the model picker updates to show the models docsfy knows about for that provider.

![Generate form with Gemini provider selected showing the available AI models dropdown](images/generate-form-models.png)

- If you want a terminal-first workflow after this browser setup, see [Set Up the CLI](set-up-the-cli.html). For copy-paste command patterns, see [Run Common CLI Workflows](common-workflow-recipes.html).
- If you want to run docsfy outside Docker or prepare a longer-lived environment, see [Deploy docsfy](deploy-docsfy.html).

## Troubleshooting

- If the container exits immediately, re-check `.env`. `ADMIN_KEY` is required and must be at least 16 characters long.
- If you can load the login page but keep getting sent back to `/login` on `http://localhost`, set `SECURE_COOKIES=false`, restart the stack, and sign in again.
- If `curl http://localhost:8000/health` never succeeds, run `docker compose logs -f docsfy` and fix the startup error before trying to sign in.
- If the server is healthy but generation fails quickly, the selected provider or model is not ready in the environment running docsfy. See [Configure AI Providers and Models](configure-ai-providers-and-models.html).
- If the repository URL is rejected, use a full hosted Git URL such as `https://github.com/myk-org/for-testing-only.git` or `git@github.com:myk-org/for-testing-only.git`.

## Related Pages

- [Set Up the CLI](set-up-the-cli.html)
- [Generate Documentation](generate-documentation.html)
- [Configure AI Providers and Models](configure-ai-providers-and-models.html)
- [Track Generation Progress](track-generation-progress.html)
- [Browse and Download Docs](browse-and-download-docs.html)