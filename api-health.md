# GET /health

Health check endpoint for verifying that the docsfy service is running and responsive. Used by container orchestration platforms and monitoring systems to determine service availability.

## Endpoint

```
GET /health
```

**Authentication:** None required

## Response

### `200 OK`

The service is running and ready to accept requests.

```json
{"status": "ok"}
```

## Usage

### Manual Check

```bash
curl -f http://localhost:8000/health
```

The `-f` flag causes curl to return a non-zero exit code on HTTP errors, making it suitable for scripting and health check commands.

### Docker Compose

The `docker-compose.yaml` configures automatic health checking against this endpoint:

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
| `test` | `curl -f http://localhost:8000/health` | Command executed inside the container to check health |
| `interval` | `30s` | Time between consecutive health checks |
| `timeout` | `10s` | Maximum time to wait for a response before marking the check as failed |
| `retries` | `3` | Number of consecutive failures before the container is marked `unhealthy` |

> **Note:** The container image includes `curl` as a system dependency, so no additional installation is needed for the health check command to work.

### Kubernetes

To use this endpoint as a Kubernetes liveness and readiness probe:

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
```

> **Tip:** Use a shorter `periodSeconds` for the readiness probe so that the service is added to load balancer rotation quickly after startup.

## Container Health States

Docker reports three states based on health check results:

| State | Meaning |
|-------|---------|
| `starting` | Container started but the first health check has not completed yet |
| `healthy` | The most recent health check returned `200 OK` |
| `unhealthy` | Three consecutive health checks failed (timed out or returned a non-200 status) |

Check the current health state with:

```bash
docker inspect --format='{{.State.Health.Status}}' <container_id>
```

Or view it in the container listing:

```bash
docker compose ps
```

```
NAME      IMAGE          COMMAND                  SERVICE   STATUS
docsfy    docsfy:latest  "uv run --no-sync uv…"   docsfy   Up 2 minutes (healthy)
```

## Monitoring Integration

The health endpoint can be polled by external monitoring tools to track uptime:

```bash
# Simple uptime check with response time
curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" http://localhost:8000/health
```

> **Warning:** This endpoint only confirms the FastAPI process is running and serving HTTP requests. It does not verify downstream dependencies such as SQLite database connectivity or filesystem access at `/data/projects/`. A `200 OK` response means the web server is responsive, not that a full documentation generation pipeline will succeed.

## Server Configuration

The health endpoint is served by uvicorn on the address configured at container startup:

```
uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000
```

| Setting | Value |
|---------|-------|
| Host | `0.0.0.0` (all interfaces) |
| Port | `8000` |
| User | `appuser` (non-root, OpenShift compatible) |
