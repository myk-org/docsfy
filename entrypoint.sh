#!/bin/bash
set -euo pipefail

# Dev mode: start Vite dev server in background for frontend HMR
if [ "${DEV_MODE:-}" = "true" ] && [ -f /app/frontend/package.json ]; then
    echo "[DEV] Frontend source detected, starting Vite dev server..."
    cd /app/frontend || exit 1
    npm ci
    npm run dev -- --host 0.0.0.0 --port 5173 &
    cd /app
fi

# Start Pi SDK sidecar in background with lifecycle coupling
# Dev mode: rebuild TypeScript from source before starting
if [ "${DEV_MODE:-}" = "true" ] && [ -f /app/sidecar-helper/src/server.ts ]; then
    echo "[sidecar] Dev mode: compiling TypeScript..."
    cd /app/sidecar-helper || { echo "[sidecar] Failed to enter sidecar-helper"; exit 1; }
    npm install --ignore-scripts || { echo "[sidecar] npm install failed"; exit 1; }
    npx tsc || { echo "[sidecar] TypeScript build failed"; exit 1; }
    cd /app || { echo "[sidecar] Failed to return to /app"; exit 1; }
fi
if [ -f /app/sidecar-helper/dist/server.js ]; then
    export SIDECAR_PORT="${SIDECAR_PORT:-9100}"
    node /app/sidecar-helper/dist/server.js &
    SIDECAR_PID=$!
    echo "[sidecar] Started Pi SDK sidecar (PID $SIDECAR_PID) on port $SIDECAR_PORT"

    # Kill sidecar when main process exits
    trap 'kill $SIDECAR_PID 2>/dev/null; wait $SIDECAR_PID 2>/dev/null' EXIT

    # Monitor sidecar — if it dies, kill the main process too
    (trap 'exit 0' TERM
     while kill -0 $SIDECAR_PID 2>/dev/null; do sleep 5; done
     echo "[sidecar] Sidecar died, shutting down container"
     kill 1 2>/dev/null) &

    # Wait for health (up to 15s)
    echo "[sidecar] Waiting for health check..."
    for i in $(seq 1 30); do
        curl -sf "http://127.0.0.1:${SIDECAR_PORT}/health" > /dev/null 2>&1 && break
        sleep 0.5
    done

    if ! curl -sf "http://127.0.0.1:${SIDECAR_PORT}/health" > /dev/null 2>&1; then
        echo "[sidecar] ERROR: not healthy after 15s — aborting" >&2
        exit 1
    fi
    echo "[sidecar] Health check passed"
fi

# Resolve PORT with a default
export PORT="${PORT:-8000}"

if [ "${DEV_MODE:-}" = "true" ]; then
    echo "Starting FastAPI with hot reload on port $PORT..."
    uv run --no-sync uvicorn docsfy.main:app \
        --host 0.0.0.0 --port "$PORT" \
        --reload --reload-dir /app/src
elif [ -n "${SIDECAR_PID:-}" ]; then
    # Sidecar is running — don't exec so EXIT trap fires for cleanup
    uv run --no-sync uvicorn docsfy.main:app \
        --host 0.0.0.0 --port "$PORT"
else
    # No sidecar — exec for efficiency
    exec uv run --no-sync uvicorn docsfy.main:app \
        --host 0.0.0.0 --port "$PORT"
fi
