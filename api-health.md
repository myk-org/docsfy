# GET /health

Health check endpoint for monitoring and container orchestration. Returns the operational status of the docsfy service, enabling Docker, Kubernetes, and external monitoring tools to verify the application is running and responsive.

## Endpoint

```
GET /health
```

No authentication or parameters required.

## Response

**Status Code:** `200 OK`

```json
{
  "status": "healthy"
}
```

A successful response indicates the FastAPI server is running and able to handle requests on port `8000`.

## Usage

### curl

```bash
curl -f http://localhost:8000/health
```

The `-f` flag causes curl to return a non-zero exit code on HTTP errors, which is critical for use in health check scripts and container orchestration.

### Python (requests)

```python
import requests

response = requests.get("http://localhost:8000/health")
response.raise_for_status()
print(response.json())  # {"status": "healthy"}
```

## Docker Health Check

The `docker-compose.yaml` configures automatic health monitoring using this endpoint:

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
| `test` | `curl -f http://localhost:8000/health` | Command to run inside the container |
| `interval` | `30s` | Time between health checks |
| `timeout` | `10s` | Maximum time to wait for a response |
| `retries` | `3` | Consecutive failures before marking unhealthy |

> **Note:** The container image includes `curl` as a system dependency (installed in the Dockerfile alongside bash, git, nodejs, npm, and ca-certificates), so it is always available for health checks.

### Container Health States

Docker tracks three health states based on the check results:

| State | Meaning |
|-------|---------|
| `starting` | Container started, initial health check not yet run |
| `healthy` | Last health check succeeded (HTTP 200 from `/health`) |
| `unhealthy` | 3 consecutive health checks failed (no response or non-200 status) |

Check the current health status of the container:

```bash
docker inspect --format='{{.State.Health.Status}}' docsfy-docsfy-1
```

Or view it in the container listing:

```bash
docker ps
```

The `STATUS` column will show `(healthy)` or `(unhealthy)` next to the uptime.

## Kubernetes Probes

When deploying to Kubernetes, use the `/health` endpoint for liveness and readiness probes:

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

> **Tip:** Set `initialDelaySeconds` on the liveness probe high enough for uvicorn to finish startup. The default entrypoint (`uv run --no-sync uvicorn docsfy.main:app --host 0.0.0.0 --port 8000`) typically starts within a few seconds.

| Probe | Purpose | Behavior on Failure |
|-------|---------|---------------------|
| **Liveness** | Is the process alive? | Kubernetes restarts the container |
| **Readiness** | Can it serve traffic? | Kubernetes removes the pod from Service endpoints |

## Architecture Context

The `/health` endpoint sits alongside the core docsfy API:

```
FastAPI Server (:8000)
├── POST   /api/generate                  # Start doc generation
├── GET    /api/status                    # List all projects
├── GET    /api/projects/{name}           # Project details
├── DELETE /api/projects/{name}           # Remove a project
├── GET    /api/projects/{name}/download  # Download site as .tar.gz
├── GET    /docs/{project}/{path}         # Serve generated HTML
└── GET    /health                        # Health check  ← this endpoint
```

The health endpoint is intentionally lightweight — it confirms the FastAPI/uvicorn process is responding to HTTP requests without performing expensive operations like database queries or filesystem checks.

## Monitoring Integration

### Uptime Monitoring

Point any HTTP uptime monitor at the health endpoint:

```
https://your-domain.com/health
```

Configure your monitor to:
- Expect HTTP status `200`
- Check at 30-second intervals (matching the Docker health check)
- Alert after 3 consecutive failures

### Docker Compose Restart Policy

Pair the health check with a restart policy so Docker automatically recovers from failures:

```yaml
services:
  docsfy:
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

> **Warning:** Without a restart policy, Docker will mark the container as `unhealthy` but will **not** automatically restart it. Add `restart: unless-stopped` or `restart: always` to enable automatic recovery.

## Troubleshooting

### Health Check Failing

1. **Verify the server is running:**

   ```bash
   docker logs docsfy-docsfy-1
   ```

   Look for the uvicorn startup message:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

2. **Test from inside the container:**

   ```bash
   docker exec docsfy-docsfy-1 curl -f http://localhost:8000/health
   ```

3. **Check port binding:**

   ```bash
   docker port docsfy-docsfy-1
   ```

   Expected output: `8000/tcp -> 0.0.0.0:8000`

4. **Review health check history:**

   ```bash
   docker inspect --format='{{json .State.Health}}' docsfy-docsfy-1 | python3 -m json.tool
   ```

   This shows the last 5 health check results, including timestamps and any error output.

### Common Causes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Connection refused | uvicorn hasn't started yet | Increase `start_period` in health check config |
| Timeout | Server overloaded (long-running generation) | The health endpoint should still respond; check for event loop blocking |
| curl not found | Custom image missing dependencies | Ensure `curl` is installed in the Dockerfile |
