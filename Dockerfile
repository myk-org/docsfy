# --- Stage 1: build ---
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev

# --- Stage 2: runtime ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash git curl ca-certificates gnupg && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (for Gemini CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user (OpenShift compatible)
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /data /home/appuser/.npm-global && \
    chown -R appuser:0 /data /home/appuser && \
    chmod -R g=u /data /home/appuser

USER appuser
WORKDIR /app

ENV HOME=/home/appuser \
    PATH="/home/appuser/.local/bin:/home/appuser/.npm-global/bin:${PATH}"

# Install AI CLIs (unpinned for latest)
RUN /bin/bash -o pipefail -c "curl -fsSL https://claude.ai/install.sh | bash"
RUN /bin/bash -o pipefail -c "curl -fsSL https://cursor.com/install | bash"
RUN npm config set prefix '/home/appuser/.npm-global' && \
    npm install -g @google/gemini-cli

# Copy app from builder
COPY --from=builder --chown=appuser:0 /app /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uv", "run", "--no-sync", "uvicorn", "docsfy.main:app", "--host", "0.0.0.0", "--port", "8000"]
