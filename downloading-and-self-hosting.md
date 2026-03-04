# Downloading & Self-Hosting

docsfy can serve your generated documentation directly from its built-in API, but you can also download the entire static site as a `.tar.gz` archive and deploy it to any hosting provider. This page covers how to download your documentation and deploy it yourself.

## How the Static Site Works

When docsfy generates documentation for a repository, the final output is a fully self-contained static HTML site stored at `/data/projects/{project-name}/site/`. This site requires no server-side processing — it's plain HTML, CSS, and JavaScript that can be served by any web server or static hosting provider.

The generated site includes:

```
site/
  index.html            # Main entry point
  *.html                # Individual documentation pages
  assets/
    style.css           # Bundled stylesheet
    search.js           # Client-side search functionality
    theme-toggle.js     # Dark/light theme toggle
    highlight.js        # Code syntax highlighting
  search-index.json     # Pre-built search index
```

All assets are bundled — there are no external CDN dependencies. The site works offline and can be hosted anywhere.

## Downloading the Archive

### Via the API

Use the download endpoint to retrieve the generated site as a `.tar.gz` archive:

```
GET /api/projects/{name}/download
```

For example, using `curl`:

```bash
curl -O http://localhost:8000/api/projects/my-project/download
```

This downloads a `my-project.tar.gz` file containing the complete static site.

> **Note:** The project must have a status of `ready` before you can download it. Check the project status first if the download fails.

### Checking Project Status Before Download

Before downloading, verify that documentation generation has completed:

```bash
# List all projects and their statuses
curl http://localhost:8000/api/status

# Check a specific project
curl http://localhost:8000/api/projects/my-project
```

A project can be in one of three states:

| Status | Description |
|--------|-------------|
| `generating` | Documentation is still being generated — download not yet available |
| `ready` | Generation complete — archive is available for download |
| `error` | Generation failed — check logs for details |

> **Warning:** Attempting to download a project that is still in the `generating` state will fail. Wait until the status changes to `ready`.

## Extracting the Archive

Once downloaded, extract the archive:

```bash
tar -xzf my-project.tar.gz
```

This produces a directory containing the full static site with `index.html` at the root.

You can preview it locally before deploying:

```bash
cd my-project/site
python3 -m http.server 3000
```

Then open `http://localhost:3000` in your browser.

## Deploying to Hosting Providers

Since the downloaded archive is a standard static site, it works with any hosting provider that serves HTML files.

### Nginx

Create an Nginx configuration to serve the extracted site:

```nginx
server {
    listen 80;
    server_name docs.example.com;

    root /var/www/my-project/site;
    index index.html;

    location / {
        try_files $uri $uri/ $uri.html =404;
    }

    # Cache static assets
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

Then copy the site files and reload Nginx:

```bash
tar -xzf my-project.tar.gz -C /var/www/my-project
sudo nginx -s reload
```

### Apache

Use an `.htaccess` file or virtual host configuration:

```apache
<VirtualHost *:80>
    ServerName docs.example.com
    DocumentRoot /var/www/my-project/site

    <Directory /var/www/my-project/site>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>

    # Cache static assets
    <LocationMatch "/assets/">
        ExpiresActive On
        ExpiresDefault "access plus 1 year"
    </LocationMatch>
</VirtualHost>
```

### GitHub Pages

Push the extracted site contents to a GitHub Pages branch:

```bash
# Extract the archive
tar -xzf my-project.tar.gz

# Initialize a repo or use an existing one
cd my-project/site
git init
git checkout -b gh-pages
git add .
git commit -m "Deploy documentation"
git remote add origin git@github.com:yourorg/yourproject-docs.git
git push -u origin gh-pages
```

Then enable GitHub Pages in your repository settings, selecting the `gh-pages` branch as the source.

> **Tip:** Automate this with a CI/CD pipeline that periodically fetches the latest archive from docsfy and deploys it to GitHub Pages.

### Netlify

Deploy using the Netlify CLI:

```bash
tar -xzf my-project.tar.gz

# Install the Netlify CLI if needed
npm install -g netlify-cli

# Deploy the site directory
netlify deploy --prod --dir=my-project/site
```

Or use drag-and-drop: extract the archive locally and drag the `site/` folder into the Netlify dashboard.

### Cloudflare Pages

Deploy using the Wrangler CLI:

```bash
tar -xzf my-project.tar.gz

npm install -g wrangler
wrangler pages deploy my-project/site --project-name=my-docs
```

### Amazon S3 + CloudFront

Upload the static site to an S3 bucket configured for static hosting:

```bash
tar -xzf my-project.tar.gz

aws s3 sync my-project/site/ s3://my-docs-bucket/ --delete
```

Configure the S3 bucket for static website hosting and optionally place a CloudFront distribution in front of it for HTTPS and caching.

## Automating Downloads

You can script periodic downloads to keep your self-hosted docs in sync with the latest generated output. The following example uses `curl` to download and extract the archive whenever the project has been regenerated:

```bash
#!/usr/bin/env bash
set -euo pipefail

DOCSFY_URL="http://localhost:8000"
PROJECT="my-project"
DEPLOY_DIR="/var/www/${PROJECT}/site"

# Check if project is ready
status=$(curl -s "${DOCSFY_URL}/api/projects/${PROJECT}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")

if [ "$status" != "ready" ]; then
  echo "Project not ready (status: ${status}), skipping."
  exit 0
fi

# Download and extract
curl -s "${DOCSFY_URL}/api/projects/${PROJECT}/download" -o /tmp/${PROJECT}.tar.gz
tar -xzf /tmp/${PROJECT}.tar.gz -C /tmp/${PROJECT}-new

# Swap into place
rm -rf "${DEPLOY_DIR}"
mv /tmp/${PROJECT}-new/site "${DEPLOY_DIR}"
rm -rf /tmp/${PROJECT}.tar.gz /tmp/${PROJECT}-new

echo "Documentation deployed successfully."
```

> **Tip:** Run this script on a cron schedule or trigger it via a webhook after calling `POST /api/generate` to regenerate documentation when your repository changes.

## Serving Directly from docsfy

If you prefer not to self-host, docsfy serves the generated documentation directly:

```
GET /docs/{project}/{path}
```

For example, once a project named `my-project` has been generated, its documentation is available at:

```
http://localhost:8000/docs/my-project/
http://localhost:8000/docs/my-project/getting-started.html
```

This is useful for development or internal use. For production, you can expose the docsfy service behind a reverse proxy:

```nginx
server {
    listen 80;
    server_name docs.example.com;

    location / {
        proxy_pass http://localhost:8000/docs/my-project/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

> **Note:** When serving directly from docsfy, the service must remain running. For zero-downtime documentation hosting, downloading and self-hosting the static site is recommended.

## Comparison: Direct Serving vs. Self-Hosting

| | Direct Serving | Self-Hosting |
|---|---|---|
| **Setup** | No extra setup needed | Requires a web server or hosting provider |
| **Availability** | Requires docsfy to be running | Independent of docsfy |
| **Performance** | Served through FastAPI | Optimized static file serving |
| **CDN support** | Requires separate configuration | Native support on most platforms |
| **Custom domain** | Via reverse proxy | Native support |
| **Offline access** | No | Yes (after download) |
| **Best for** | Development, internal use | Production, public-facing docs |
