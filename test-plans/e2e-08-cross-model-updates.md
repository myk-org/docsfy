# E2E UI Tests: Cross-Model Incremental Updates

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 20: Cross-Model Incremental Updates

### Prerequisites
- Admin access to the local-path generation API is required for this section.

**Step 1: Prepare shell variables for this test section.**

Run these shell commands in the same terminal session and keep that session open for all of Test 20:

```shell
export SERVER="http://localhost:8800"
export CROSS_PROVIDER_ROOT="/tmp/ai-output/cross-provider-e2e"
mkdir -p "/tmp/ai-output"
rm -rf "$CROSS_PROVIDER_ROOT"
mkdir -p "$CROSS_PROVIDER_ROOT"

eval "$(
uv run python - <<'PY'
from pathlib import Path
wanted = {"ADMIN_KEY"}
for line in Path('.dev/.env').read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    if key in wanted:
        print(f'export {key}="{value}"')
PY
)"

export TEST_REPO_URL="https://github.com/myk-org/for-testing-only"
export BASELINE_PROVIDER="gemini"
export BASELINE_MODEL="gemini-2.5-flash"
export SWITCH_PROVIDER="gemini"
export SWITCH_MODEL="gemini-2.0-flash"
export SWITCH_MODEL_URL="gemini-2.0-flash"
export DOCSFY_CONTAINER=""  # optional: set to the running container name if the server uses Docker
```

**Step 2: If `.dev/.env` is missing, or if `ADMIN_KEY` could not be loaded, mark Test 20.1-20.5 as `blocked`, continue to Test 21, and do not invent substitute values.**

### 20.1 Generate Baseline Docs with First Model

**Step 1: Start a forced baseline generation for the test repo with `gemini/gemini-2.5-flash`.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -X POST "$SERVER/api/generate" \
  -d "{\"repo_url\":\"$TEST_REPO_URL\",\"ai_provider\":\"$BASELINE_PROVIDER\",\"ai_model\":\"$BASELINE_MODEL\",\"force\":true}"
```

**Expected result:**
- The response JSON contains `"project": "for-testing-only"`
- The response JSON contains `"status": "generating"`

**Step 2: Poll the Gemini variant until it reaches a terminal state. Use the Standard Polling Procedure with this exact status command.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/for-testing-only/main/$BASELINE_PROVIDER/$BASELINE_MODEL"
```

Store the value of `last_commit_sha` from the response as `BASELINE_COMMIT`.

**Expected result:**
- The final JSON has `"status": "ready"`
- `page_count` is greater than `0`

**Step 3: Download and extract the baseline docs so later steps can compare artifacts directly.**

```shell
curl -s -L -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/for-testing-only/main/$BASELINE_PROVIDER/$BASELINE_MODEL/download" \
  -o "$CROSS_PROVIDER_ROOT/baseline.tar.gz"
mkdir -p "$CROSS_PROVIDER_ROOT/baseline"
tar -xzf "$CROSS_PROVIDER_ROOT/baseline.tar.gz" --strip-components=1 -C "$CROSS_PROVIDER_ROOT/baseline"
ls "$CROSS_PROVIDER_ROOT/baseline"
```

**Expected result:**
- The download succeeds
- The extracted directory contains generated docs artifacts such as `index.html`, `llms.txt`, and page files

### 20.2 Regenerate with a Different Model on the Same Commit

**Step 1: Trigger a non-force generation for the same commit using `gemini/gemini-2.0-flash`.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -X POST "$SERVER/api/generate" \
  -d "{\"repo_url\":\"$TEST_REPO_URL\",\"ai_provider\":\"$SWITCH_PROVIDER\",\"ai_model\":\"$SWITCH_MODEL\"}"
```

**Expected result:**
- The response JSON contains `"project": "for-testing-only"`
- The response JSON contains `"status": "generating"`

**Step 2: Poll the `gemini/gemini-2.0-flash` variant until it is ready. Use the Standard Polling Procedure with this exact status command.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/for-testing-only/main/$SWITCH_PROVIDER/$SWITCH_MODEL_URL"
```

**Expected result:**
- The final JSON has `"status": "ready"`
- `last_commit_sha` still equals `BASELINE_COMMIT`

**Step 3: Verify the old `gemini-2.5-flash` variant was replaced.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -w "\nHTTP_STATUS:%{http_code}\n" \
  "$SERVER/api/projects/for-testing-only/main/$BASELINE_PROVIDER/$BASELINE_MODEL"
```

**Expected result:**
- The output ends with `HTTP_STATUS:404`
- The old `gemini-2.5-flash` variant no longer exists for owner `admin`

**Step 4: Download the `gemini-2.0-flash` docs and compare them against the baseline `gemini-2.5-flash` docs.**

```shell
curl -s -L -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/for-testing-only/main/$SWITCH_PROVIDER/$SWITCH_MODEL_URL/download" \
  -o "$CROSS_PROVIDER_ROOT/same-commit-switch.tar.gz"
mkdir -p "$CROSS_PROVIDER_ROOT/same-commit-switch"
tar -xzf "$CROSS_PROVIDER_ROOT/same-commit-switch.tar.gz" --strip-components=1 -C "$CROSS_PROVIDER_ROOT/same-commit-switch"
diff -rq "$CROSS_PROVIDER_ROOT/baseline" "$CROSS_PROVIDER_ROOT/same-commit-switch"
```

**Expected result:**
- `diff -rq` prints no differences and exits successfully
- The same-commit model switch reused the existing docs artifacts exactly

### 20.3 Cross-Model Incremental Update After a New Commit

> **Docker note:** If the server runs inside a Docker container, `repo_path` must
> resolve inside the container. The default `docker-compose.dev.yml` bind-mounts
> `.dev/data` → `/data`, so clone into `$HOST_DATA_DIR` and reference
> `/data/<dir-name>` in the API call. Set `HOST_DATA_DIR` in the shell variables
> at the top of this file (defaults to `.dev/data` relative to the project root).

**Step 0 (Docker only): Set the host-side data directory that is bind-mounted into the container.**

```shell
# Resolve the host-side data dir (adjust if your mount differs)
HOST_DATA_DIR="${HOST_DATA_DIR:-$(git -C "$(dirname "$0")/../" rev-parse --show-toplevel 2>/dev/null)/.dev/data}"
# Fallback for manual runs:
HOST_DATA_DIR="${HOST_DATA_DIR:-/home/$USER/git/docsfy/.dev/data}"
```

**Step 1: Create a local clone and add a deterministic commit so the server sees a newer SHA than the baseline.**

```shell
LOCAL_CLONE="$CROSS_PROVIDER_ROOT/for-testing-only"
git clone --depth 1 --branch main "$TEST_REPO_URL" "$LOCAL_CLONE"
printf '\n\n## E2E Cross-Provider Marker\n\nThis line was added by the docsfy cross-provider E2E test.\n' >> "$LOCAL_CLONE/README.md"
git -C "$LOCAL_CLONE" add README.md
git -C "$LOCAL_CLONE" -c user.name="docsfy-e2e" -c user.email="docsfy-e2e@example.com" commit -m "test: update README for cross-provider e2e"
git -C "$LOCAL_CLONE" rev-parse HEAD
```

Store the final SHA as `LOCAL_UPDATED_COMMIT`.

**Step 2: Copy the clone to the container-accessible data directory and trigger a non-force generation using the container-side path.**

```shell
# Copy clone to container-accessible location
CONTAINER_CLONE_NAME="for-testing-only-e2e"
cp -r "$LOCAL_CLONE" "$HOST_DATA_DIR/$CONTAINER_CLONE_NAME"

curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -X POST "$SERVER/api/generate" \
  -d "{\"repo_path\":\"/data/$CONTAINER_CLONE_NAME\",\"ai_provider\":\"$BASELINE_PROVIDER\",\"ai_model\":\"$BASELINE_MODEL\"}"
```

**Expected result:**
- The response JSON contains `"project": "for-testing-only-e2e"`
- The response JSON contains `"status": "generating"`

**Step 3: Poll the Gemini variant until it is ready. Use the Standard Polling Procedure with this exact status command.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/$CONTAINER_CLONE_NAME/main/$BASELINE_PROVIDER/$BASELINE_MODEL"
```

**Expected result:**
- The final JSON has `"status": "ready"`
- `last_commit_sha` equals `LOCAL_UPDATED_COMMIT`

**Step 4: Verify the `gemini-2.0-flash` variant was replaced.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -w "\nHTTP_STATUS:%{http_code}\n" \
  "$SERVER/api/projects/$CONTAINER_CLONE_NAME/main/$SWITCH_PROVIDER/$SWITCH_MODEL_URL"
```

**Expected result:**
- The output ends with `HTTP_STATUS:404`
- The old `gemini-2.0-flash` variant no longer exists for owner `admin`

**Step 5: If the server is running in Docker and `DOCSFY_CONTAINER` is set, check the application logs for explicit cross-provider reuse evidence. Otherwise mark only this log assertion as `blocked` and continue.**

```shell
docker logs "$DOCSFY_CONTAINER" --since 10m 2>&1 | rg -i "cross-provider update"
```

**Expected result:**
- The output contains a line showing `Cross-provider update:` for `for-testing-only`
- If `DOCSFY_CONTAINER` is empty or Docker is unavailable, mark only this log assertion as `blocked` and continue with the remaining artifact checks

**Step 6: Download the updated `gemini-2.5-flash` docs and compare them against the same-commit `gemini-2.0-flash` docs.**

```shell
curl -s -L -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/$CONTAINER_CLONE_NAME/main/$BASELINE_PROVIDER/$BASELINE_MODEL/download" \
  -o "$CROSS_PROVIDER_ROOT/updated-gemini.tar.gz"
mkdir -p "$CROSS_PROVIDER_ROOT/updated-gemini"
tar -xzf "$CROSS_PROVIDER_ROOT/updated-gemini.tar.gz" --strip-components=1 -C "$CROSS_PROVIDER_ROOT/updated-gemini"
uv run python - <<'PY'
from pathlib import Path
import hashlib
import json

before = Path('/tmp/ai-output/cross-provider-e2e/same-commit-switch')
after = Path('/tmp/ai-output/cross-provider-e2e/updated-gemini')

def hashes(root: Path) -> dict[str, str]:
    result = {}
    for path in root.rglob('*'):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

before_hashes = hashes(before)
after_hashes = hashes(after)
shared = sorted(set(before_hashes) & set(after_hashes))
same = [rel for rel in shared if before_hashes[rel] == after_hashes[rel]]
changed = [rel for rel in shared if before_hashes[rel] != after_hashes[rel]]
print(json.dumps({
    'same_count': len(same),
    'changed_count': len(changed),
    'same_samples': same[:5],
    'changed_samples': changed[:5],
}, indent=2))
PY
```

**Expected result:**
- `changed_count` is greater than or equal to `1`
- `same_count` is greater than or equal to `1`
- This proves at least one artifact changed for the new commit and at least one artifact was preserved unchanged

**Step 7: Verify the new README marker appears in the updated docs artifacts.**

```shell
rg -n "E2E Cross-Provider Marker|docsfy cross-provider E2E test" "$CROSS_PROVIDER_ROOT/updated-gemini"
```

**Expected result:**
- At least one match is returned from the updated docs artifacts
- The updated docs reflect the new local commit content

### 20.4 Force Regeneration Does Not Replace the Existing Variant

**Step 1: Trigger a forced `gemini/gemini-2.0-flash` generation using the remote repo URL.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -X POST "$SERVER/api/generate" \
  -d "{\"repo_url\":\"$TEST_REPO_URL\",\"ai_provider\":\"$SWITCH_PROVIDER\",\"ai_model\":\"$SWITCH_MODEL\",\"force\":true}"
```

**Expected result:**
- The response JSON contains `"status": "generating"`

**Step 2: Poll the `gemini/gemini-2.0-flash` variant until it is ready. Use the Standard Polling Procedure with this exact status command.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/for-testing-only/main/$SWITCH_PROVIDER/$SWITCH_MODEL_URL"
```

**Expected result:**
- The final JSON has `"status": "ready"`

**Step 3: Verify that both admin-owned variants now exist at the same time.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -w "\nHTTP_STATUS:%{http_code}\n" \
  "$SERVER/api/projects/for-testing-only/main/$BASELINE_PROVIDER/$BASELINE_MODEL"

curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -w "\nHTTP_STATUS:%{http_code}\n" \
  "$SERVER/api/projects/for-testing-only/main/$SWITCH_PROVIDER/$SWITCH_MODEL_URL"
```

**Expected result:**
- The `gemini-2.5-flash` request ends with `HTTP_STATUS:200`
- The `gemini-2.0-flash` request ends with `HTTP_STATUS:200`
- Force regeneration kept the existing `gemini-2.5-flash` variant instead of replacing it

### 20.5 Cleanup

**Step 1: Delete the admin-owned variants created in Test 20 and remove the temporary directory.**

```shell
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -X DELETE "$SERVER/api/projects/for-testing-only/main/$BASELINE_PROVIDER/$BASELINE_MODEL?owner=admin"

curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -X DELETE "$SERVER/api/projects/for-testing-only/main/$SWITCH_PROVIDER/$SWITCH_MODEL_URL?owner=admin"

# Clean up the container-accessible clone from Test 20.3
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  -X DELETE "$SERVER/api/projects/$CONTAINER_CLONE_NAME/main/$BASELINE_PROVIDER/$BASELINE_MODEL?owner=admin"
rm -rf "$HOST_DATA_DIR/$CONTAINER_CLONE_NAME"

rm -rf "$CROSS_PROVIDER_ROOT"
```

**Expected result:**
- The delete requests return success JSON or `404` if a prior step already removed the variant
- The temporary directory `$CROSS_PROVIDER_ROOT` no longer exists
- The container-accessible clone `$HOST_DATA_DIR/$CONTAINER_CLONE_NAME` no longer exists
