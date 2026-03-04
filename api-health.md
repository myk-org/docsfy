# GET /health

Health check endpoint used for container orchestration, monitoring, and load balancer readiness probes.

## Overview

The `/health` endpoint provides a lightweight mechanism to verify that the docsfy service is running and able to accept requests. It requires no authentication and returns immediately, making it suitable for automated health monitoring by container runtimes, orchestrators, and load balancers.

## Request

```
GET /health
```

**Parameters:** None

**Authentication:** Not required

**Headers:** No special headers required

## Response

### 200 OK

The service is healthy and ready to accept requests.

```json
{"status": "healthy"}
```

### 503 Service Unavailable

The service is running but not ready to handle requests (e.g., during startup or shutdown).

## Usage Examples

### cURL

```bash
curl -f http://localhost:8000/health
```

The `-f` flag causes curl to return a non-zero exit code on HTTP errors, which is the same approach used in the Docker health check configuration.

### Python (requests)

```python
import requests

response = requests.get("http://localhost:8000/health")
if response.status_code == 200:
    print("Service is healthy")
else:
    print("Service is unhealthy")
```

### Python (httpx, async)

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get("http://localhost:8000/health")
    assert response.status_code == 200
```

## Docker Health Check

The `/health` endpoint is configured as the Docker health check in `docker-compose.yaml`:

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

| Parameter | Value | Description |
|-----------|-------|-------------|
| `test` | `curl -f http://localhost:8000/health` | Probes the health endpoint; fails on non-2xx responses |
| `interval` | `30s` | Time between consecutive health checks |
| `timeout` | `10s` | Maximum time to wait for a response before marking as failed |
| `retries` | `3` | Consecutive failures required before the container is marked `unhealthy` |

> **Note:** The `curl` binary is included in the container image (`python:3.12-slim` base with `curl` added as a system dependency) specifically to support this health check.

### Container Health States

Docker tracks three health states based on the results of the health check:

| State | Meaning |
|-------|---------|
| `starting` | The container has started but the first health check has not yet run |
| `healthy` | The most recent health check returned a 2xx status code |
| `unhealthy` | Three consecutive health checks failed (non-2xx or timeout) |

You can inspect the current health state with:

```bash
docker inspect --format='{{.State.Health.Status}}' docsfy
```

Or view health check logs:

```bash
docker inspect --format='{{json .State.Health}}' docsfy | jq
```

## Kubernetes Integration

When deploying docsfy to Kubernetes, configure liveness and readiness probes to use the `/health` endpoint:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docsfy
spec:
  template:
    spec:
      containers:
        - name: docsfy
          image: docsfy:latest
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 3
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 2
```

> **Tip:** Use a shorter `periodSeconds` for the readiness probe than for the liveness probe. The readiness probe controls traffic routing and should detect issues quickly, while the liveness probe triggers a container restart and should be more conservative to avoid unnecessary restarts.

## Load Balancer Configuration

### NGINX

```nginx
upstream docsfy {
    server 127.0.0.1:8000;
}

server {
    location /health {
        proxy_pass http://docsfy/health;
    }
}
```

### AWS Application Load Balancer

Configure the target group health check:

| Setting | Value |
|---------|-------|
| Protocol | HTTP |
| Path | `/health` |
| Port | 8000 |
| Healthy threshold | 2 |
| Unhealthy threshold | 3 |
| Timeout | 10 seconds |
| Interval | 30 seconds |
| Success codes | 200 |

## Architecture Context

The `/health` endpoint sits at the FastAPI application level alongside the other API routes:

```
                    FastAPI Server
+--------------------------------------------------+
|                                                  |
|  POST /api/generate  <-- repo URL                |
|  GET  /api/status    <-- project list            |
|  GET  /docs/{project}/  <-- serves HTML          |
|  GET  /health           <-- health check         |
|                                                  |
|  Storage:                                        |
|  /data/docsfy.db  (SQLite: metadata)             |
|  /data/projects/  (filesystem: docs)             |
+--------------------------------------------------+
```

The endpoint is served by **uvicorn** on port `8000` (all interfaces) as defined in the container entrypoint:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

> **Warning:** The health endpoint only confirms the FastAPI process is responding. It does not verify that external dependencies (AI CLI tools, storage volumes) are available. A healthy response means the HTTP server is accepting connections, not that documentation generation will succeed.

## Monitoring Best Practices

- **Alerting threshold**: Alert when the endpoint is unreachable for more than 90 seconds (3 intervals at 30s each), matching the Docker retry configuration.
- **Dashboard integration**: Track response times from `/health` to detect performance degradation before full failures occur.
- **Dependency checks**: Complement the health endpoint with application-level monitoring of storage availability (`/data/docsfy.db`) and AI CLI tool readiness for full observability.
- **Log level**: Health check requests are logged at `INFO` level by default. Set `LOG_LEVEL=WARNING` in your `.env` file to suppress health check noise in production logs if your monitoring generates high request volume.
