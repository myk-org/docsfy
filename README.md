# docsfy

AI-powered documentation generator that creates polished static HTML docs from GitHub repositories.

**[Full Documentation](https://myk-org.github.io/docsfy/)**

## Quick Start

```bash
git clone https://github.com/myk-org/docsfy.git && cd docsfy
cp .env.example .env   # then set ADMIN_KEY (min 16 chars)
docker compose up       # open http://localhost:8000
```

## CLI

```bash
uv tool install docsfy
docsfy config init
docsfy generate https://github.com/org/repo
```

See the [full documentation](https://myk-org.github.io/docsfy/) for everything else.

## License

Apache-2.0
