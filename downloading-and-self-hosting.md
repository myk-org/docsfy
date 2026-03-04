# Downloading & Self-Hosting

docsfy supports two hosting models: serving documentation directly from the API, or downloading the generated static site as a `.tar.gz` archive to host on your own infrastructure. This page covers the download API, the structure of the archive, and how to deploy the static site to common hosting platforms.

## Prerequisites

Before downloading documentation, you need a docsfy instance running and at least one project with a `ready` status. Generate documentation for a repository first:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/your-org/your-repo"}'
```

Verify the project status is `ready` before attempting to download:

```bash
curl http://localhost:8000/api/status
```

The response includes the status of each project. Only projects with `"status": "ready"` have a complete static site available for download.

## Downloading the Archive

### Download Endpoint

```
GET /api/projects/{name}/download
```

This endpoint returns the generated documentation site as a `.tar.gz` archive. The `{name}` parameter is the project name assigned during generation.

### Using curl

```bash
curl -O http://localhost:8000/api/projects/your-project/download \
  --output your-project-docs.tar.gz
```

### Using wget

```bash
wget http://localhost:8000/api/projects/your-project/download \
  -O your-project-docs.tar.gz
```

### Using Python

```python
import httpx

response = httpx.get("http://localhost:8000/api/projects/your-project/download")
with open("your-project-docs.tar.gz", "wb") as f:
    f.write(response.content)
```

> **Tip:** Use the `GET /api/projects/{name}` endpoint to retrieve project details — including the last generated timestamp and commit SHA — before downloading. This helps you determine whether you need a fresh copy.

## Archive Contents

The `.tar.gz` archive contains the complete static site from `/data/projects/{project-name}/site/`. Once extracted, the directory structure looks like this:

```
site/
├── index.html
├── *.html
├── assets/
│   ├── style.css
│   ├── search.js
│   ├── theme-toggle.js
│   └── highlight.js
└── search-index.json
```

| File / Directory | Description |
|-----------------|-------------|
| `index.html` | Landing page for the documentation site |
| `*.html` | Individual documentation pages generated from the AI content pipeline |
| `assets/style.css` | Theme styles supporting dark and light modes |
| `assets/search.js` | Client-side search powered by lunr.js |
| `assets/theme-toggle.js` | Dark/light theme toggle functionality |
| `assets/highlight.js` | Code syntax highlighting |
| `search-index.json` | Pre-built search index for client-side search |

The site is entirely self-contained — all CSS, JavaScript, and search index data are bundled in the archive. No external CDN dependencies are required at runtime.

## Extracting the Archive

```bash
mkdir -p ./docs-site
tar -xzf your-project-docs.tar.gz -C ./docs-site
```

Verify the extraction:

```bash
ls ./docs-site/site/
```

You should see `index.html`, the `assets/` directory, and the other HTML pages.

## Hosting on Your Own Infrastructure

Since the downloaded archive is a fully static site, it can be served by any HTTP server or static hosting platform.

### Nginx

Create an Nginx configuration to serve the extracted site:

```nginx
server {
    listen 80;
    server_name docs.example.com;

    root /var/www/docs-site/site;
    index index.html;

    location / {
        try_files $uri $uri/ $uri.html =404;
    }

    # Cache static assets
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

Copy the extracted files and reload Nginx:

```bash
cp -r ./docs-site/site/ /var/www/docs-site/site/
sudo nginx -s reload
```

### Apache

```apache
<VirtualHost *:80>
    ServerName docs.example.com
    DocumentRoot /var/www/docs-site/site

    <Directory /var/www/docs-site/site>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>

    # Cache static assets
    <Directory /var/www/docs-site/site/assets>
        Header set Cache-Control "public, max-age=2592000, immutable"
    </Directory>
</VirtualHost>
```

### Python (Quick Preview)

For local preview or development, use Python's built-in HTTP server:

```bash
cd ./docs-site/site
python3 -m http.server 3000
```

Then open `http://localhost:3000` in your browser.

## Deploying to Cloud & CDN Providers

### AWS S3 + CloudFront

```bash
# Extract the archive
tar -xzf your-project-docs.tar.gz -C ./docs-site

# Sync to S3
aws s3 sync ./docs-site/site/ s3://your-docs-bucket/ \
  --delete

# Set cache headers for assets
aws s3 cp s3://your-docs-bucket/assets/ s3://your-docs-bucket/assets/ \
  --recursive \
  --cache-control "public, max-age=2592000, immutable" \
  --metadata-directive REPLACE
```

Configure the S3 bucket for static website hosting and point a CloudFront distribution at it for HTTPS and edge caching.

### GitHub Pages

```bash
# Extract into a repository configured for GitHub Pages
tar -xzf your-project-docs.tar.gz -C ./docs-site

# Copy site content to the repo root (or /docs depending on your config)
cp -r ./docs-site/site/* ./your-pages-repo/

cd ./your-pages-repo
git add .
git commit -m "Update documentation"
git push origin main
```

> **Note:** GitHub Pages serves from the repository root or a `/docs` folder. Adjust the copy destination to match your repository's Pages configuration.

### Netlify

```bash
# Extract the archive
tar -xzf your-project-docs.tar.gz -C ./docs-site

# Deploy with the Netlify CLI
netlify deploy --dir=./docs-site/site --prod
```

### Cloudflare Pages

```bash
# Extract the archive
tar -xzf your-project-docs.tar.gz -C ./docs-site

# Deploy with Wrangler
npx wrangler pages deploy ./docs-site/site --project-name=your-docs
```

## Automating Downloads with CI/CD

You can automate the download-and-deploy workflow in your CI/CD pipeline. Here is an example using GitHub Actions:

```yaml
name: Update Documentation

on:
  push:
    branches: [main]

jobs:
  update-docs:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger documentation generation
        run: |
          curl -X POST ${{ secrets.DOCSFY_URL }}/api/generate \
            -H "Content-Type: application/json" \
            -d '{"url": "https://github.com/${{ github.repository }}"}'

      - name: Wait for generation to complete
        run: |
          PROJECT_NAME="${{ github.event.repository.name }}"
          for i in $(seq 1 60); do
            STATUS=$(curl -s "${{ secrets.DOCSFY_URL }}/api/projects/${PROJECT_NAME}" | jq -r '.status')
            if [ "$STATUS" = "ready" ]; then
              echo "Documentation is ready"
              break
            elif [ "$STATUS" = "error" ]; then
              echo "Generation failed"
              exit 1
            fi
            echo "Status: $STATUS - waiting..."
            sleep 30
          done

      - name: Download documentation archive
        run: |
          PROJECT_NAME="${{ github.event.repository.name }}"
          curl -o docs.tar.gz \
            "${{ secrets.DOCSFY_URL }}/api/projects/${PROJECT_NAME}/download"
          tar -xzf docs.tar.gz -C ./docs-output

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs-output/site
```

> **Warning:** AI-powered documentation generation can take several minutes depending on repository size and complexity. The `AI_CLI_TIMEOUT` defaults to 60 minutes. Make sure your CI/CD job timeout accommodates the generation time.

## Incremental Updates

docsfy tracks the last commit SHA for each project. When you call `POST /api/generate` for a project that already exists, it:

1. Fetches the latest code and compares the current commit SHA against the stored SHA
2. Re-runs the AI Planner to detect structural changes to the documentation
3. Regenerates only pages whose content may be affected by the changes
4. Rebuilds the static site with updated pages

This means subsequent downloads after incremental updates will be faster to generate. You can check whether documentation needs regeneration by comparing the commit SHA:

```bash
# Get the current project state
curl -s http://localhost:8000/api/projects/your-project | jq '.last_commit_sha'

# Compare against your repo's latest commit
git ls-remote https://github.com/your-org/your-repo HEAD
```

> **Tip:** For repositories that change frequently, set up a webhook or scheduled CI job to trigger `POST /api/generate` and re-download the archive only when the commit SHA has changed.

## Verifying the Downloaded Site

After extracting the archive, verify that all expected files are present and the site works correctly:

```bash
# Check the file structure
find ./docs-site/site -type f | head -20

# Verify key files exist
test -f ./docs-site/site/index.html && echo "index.html: OK"
test -f ./docs-site/site/assets/style.css && echo "style.css: OK"
test -f ./docs-site/site/search-index.json && echo "search-index.json: OK"

# Quick local preview
cd ./docs-site/site && python3 -m http.server 3000
```

Open `http://localhost:3000` to verify:
- Pages render correctly with sidebar navigation
- Dark/light theme toggle works
- Client-side search returns results
- Code blocks have syntax highlighting

## Troubleshooting

### Download returns 404

The project either doesn't exist or hasn't finished generating. Check the project status:

```bash
curl http://localhost:8000/api/projects/your-project
```

If the status is `generating`, wait for it to complete. If the status is `error`, check the generation logs and retry with `POST /api/generate`.

### Archive is empty or incomplete

Ensure the generation completed successfully (status is `ready`). A project in `error` state may have partial output. Delete and regenerate:

```bash
curl -X DELETE http://localhost:8000/api/projects/your-project
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/your-org/your-repo"}'
```

### Search not working on self-hosted site

Client-side search requires the `search-index.json` file to be served with the correct MIME type (`application/json`). Most web servers handle this correctly by default. If search isn't working, verify the file is accessible:

```bash
curl -I http://docs.example.com/search-index.json
```

The `Content-Type` header should be `application/json`.

### CORS issues when hosting on a CDN

If you're serving the documentation from a different domain than your application, you may need to configure CORS headers on your hosting provider. The search functionality loads `search-index.json` via fetch, which requires CORS when cross-origin.
