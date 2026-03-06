# docsfy

AI-powered documentation generator that creates polished static HTML docs from GitHub repositories using Claude, Gemini, or Cursor CLI.

[**Documentation**](https://myk-org.github.io/docsfy-docs/) | [**GitHub**](https://github.com/myk-org/docsfy)

## Documentation

Full documentation is available at [https://myk-org.github.io/docsfy-docs/](https://myk-org.github.io/docsfy-docs/)

## Quick Start

```bash
# Clone and configure
git clone https://github.com/myk-org/docsfy.git
cd docsfy
cp .env.example .env
# Edit .env with your AI provider credentials

# Run
docker compose up

# Generate docs for any repo
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/org/repo"}'

# Browse docs
open http://localhost:8000/docs/repo/
```

## License

Apache-2.0
