# Serving Documentation

Once docsfy generates documentation for a project, you can access it in two ways: browse it directly through the built-in static file server, or download it as a tar.gz archive and host it yourself.

## Built-in Static File Server

Every generated project is automatically served at a predictable URL under the `/docs/` prefix.

### Accessing Your Documentation

After generation completes, your documentation is available at:

```
http://localhost:8000/docs/{project-name}/
```

For example, if you generated docs for a project named `my-api`:

```
http://localhost:8000/docs/my-api/
```

This serves the fully rendered static HTML site — including navigation, search, syntax highlighting, and dark/light theme toggling — directly from the docsfy server with no additional setup.

### URL Structure

The server maps URLs to files under the project's `site/` directory on the filesystem:

| URL | Filesystem Path |
|-----|-----------------|
| `/docs/my-api/` | `/data/projects/my-api/site/index.html` |
| `/docs/my-api/getting-started.html` | `/data/projects/my-api/site/getting-started.html` |
| `/docs/my-api/assets/style.css` | `/data/projects/my-api/site/assets/style.css` |
| `/docs/my-api/search-index.json` | `/data/projects/my-api/site/search-index.json` |

All static assets — stylesheets, JavaScript files for search and theme toggling, and syntax highlighting — are bundled within each project's `site/assets/` directory and served alongside the HTML pages.

```
/data/projects/{project-name}/
  site/                     # served at /docs/{project-name}/
    index.html
    *.html
    assets/
      style.css
      search.js
      theme-toggle.js
      highlight.js
    search-index.json
```

### Checking Project Status Before Accessing

Documentation is only available for projects with a `ready` status. Use the status endpoint to verify:

```bash
curl http://localhost:8000/api/status
```

Or check a specific project:

```bash
curl http://localhost:8000/api/projects/my-api
```

> **Note:** Attempting to access `/docs/{project-name}/` for a project that is still in `generating` status or ended in `error` will not return valid documentation. Always confirm the project status is `ready` before browsing.

## Downloading as a tar.gz Archive

For self-hosting, you can download the complete generated site as a compressed archive.

### Download Endpoint

```
GET /api/projects/{name}/download
```

Download a project's documentation using `curl`:

```bash
curl -O http://localhost:8000/api/projects/my-api/download
```

Or specify an output filename:

```bash
curl -o my-api-docs.tar.gz http://localhost:8000/api/projects/my-api/download
```

The archive contains the entire contents of the project's `site/` directory — all HTML pages, CSS, JavaScript, and the search index — everything needed for a fully self-contained documentation site.

### Archive Contents

The downloaded `.tar.gz` archive extracts to a complete static site:

```
my-api/
  index.html
  getting-started.html
  api-reference.html
  ...
  assets/
    style.css
    search.js
    theme-toggle.js
    highlight.js
  search-index.json
```

Every file required for the documentation to function is included. There are no external dependencies or CDN references to worry about — search, theme toggling, and code highlighting all work offline.

## Self-Hosting the Downloaded Archive

The downloaded archive is a plain static site that can be served by any HTTP server. No server-side processing is required.

### Using Python's Built-in Server

For quick local previewing:

```bash
tar -xzf my-api-docs.tar.gz
cd my-api
python3 -m http.server 3000
```

Then browse to `http://localhost:3000`.

### Using Nginx

```nginx
server {
    listen 80;
    server_name docs.example.com;

    root /var/www/docs/my-api;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### Using Apache

```apache
<VirtualHost *:80>
    ServerName docs.example.com
    DocumentRoot /var/www/docs/my-api

    <Directory /var/www/docs/my-api>
        Options Indexes FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>
</VirtualHost>
```

### Using Caddy

```
docs.example.com {
    root * /var/www/docs/my-api
    file_server
}
```

### Hosting on GitHub Pages

Extract the archive and push to a GitHub Pages branch:

```bash
tar -xzf my-api-docs.tar.gz
cd my-api
git init
git add .
git commit -m "Deploy documentation"
git remote add origin git@github.com:yourorg/my-api-docs.git
git push -u origin main
```

Then enable GitHub Pages in the repository settings, serving from the `main` branch.

> **Tip:** Since the generated site uses client-side search and has no server-side dependencies, it works perfectly on any static hosting platform — GitHub Pages, GitLab Pages, Netlify, Cloudflare Pages, S3 + CloudFront, or a simple file server.

## Running docsfy with Docker

The recommended way to run docsfy in production is with Docker. The built-in server starts on port 8000.

### docker-compose.yaml

```yaml
services:
  docsfy:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/data
      - ~/.config/gcloud:/home/appuser/.config/gcloud:ro
      - ./cursor:/home/appuser/.config/cursor
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

The `/data` volume is where all project data lives — the SQLite database and all generated sites. Persist this volume to retain documentation across container restarts.

> **Warning:** If the `/data` volume is not mounted, generated documentation will be lost when the container stops. Always mount a persistent volume for production deployments.

### Starting the Server

```bash
docker compose up -d
```

The server starts with uvicorn on port 8000:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
```

## Putting a Reverse Proxy in Front of docsfy

For production deployments, place a reverse proxy in front of docsfy to handle TLS, caching, and access control.

### Nginx Reverse Proxy Example

```nginx
server {
    listen 443 ssl;
    server_name docsfy.example.com;

    ssl_certificate     /etc/ssl/certs/docsfy.crt;
    ssl_certificate_key /etc/ssl/private/docsfy.key;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Cache static documentation assets
    location /docs/ {
        proxy_pass http://localhost:8000;
        proxy_cache_valid 200 10m;
        add_header Cache-Control "public, max-age=600";
    }
}
```

> **Tip:** Since documentation changes only when you regenerate a project, you can safely apply aggressive caching to the `/docs/` path. Invalidate the cache after triggering a new generation.

## Quick Reference

| Task | Command |
|------|---------|
| Browse docs in browser | `http://localhost:8000/docs/{project}/` |
| Check project status | `curl http://localhost:8000/api/projects/{name}` |
| List all projects | `curl http://localhost:8000/api/status` |
| Download docs archive | `curl -o docs.tar.gz http://localhost:8000/api/projects/{name}/download` |
| Health check | `curl http://localhost:8000/health` |
