# docsfy

AI-powered documentation generator that creates Mintlify-quality static HTML docs from GitHub repositories using Claude, Gemini, or Cursor CLI.

[**Documentation**](https://myk-org.github.io/docsfy/) | [**GitHub**](https://github.com/myk-org/docsfy)

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
