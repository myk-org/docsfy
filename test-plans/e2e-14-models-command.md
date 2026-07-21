# E2E Tests: Models Command

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.
> **Note:** These tests exercise the `docsfy models` CLI command and the `GET /api/models` API endpoint. The server must be running at `http://localhost:8800`.

---

## Test 28: Models Command

### Prerequisites

Set up the CLI configuration:

```shell
export DOCSFY_SERVER="http://localhost:8800"
export DOCSFY_API_KEY="<ADMIN_KEY>"
```

### 28.1 Models returns providers list with defaults marked

**Commands:**

```shell
docsfy models
```

**Expected result:**
- The output lists all known providers (e.g., `claude`, `gemini`, `cursor`)
- The server's default provider is marked with `(default)` next to its name
- The server's default model is marked with `(default)` next to its name under the default provider
- Each provider section shows its discovered models or `(no models available)` if none exist

---

### 28.2 Models filters to single provider

**Commands:**

```shell
docsfy models --provider cursor
```

**Expected result:**
- Only the `cursor` provider is listed
- No other providers appear in the output
- If `cursor` has discovered models from provider APIs, they are shown
- If not, `(no models available)` is displayed

---

### 28.3 Models with invalid provider returns error

**Commands:**

```shell
docsfy models --provider invalid
echo "Exit code: $?"
```

**Expected result:**
- The output contains `Unknown provider: invalid`
- The exit code is non-zero (1)

---

### 28.4 Models JSON output returns valid JSON

**Commands:**

```shell
docsfy models --json
```

**Check:**

```shell
docsfy models --json | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'providers' in data; assert 'default_provider' in data; assert 'default_model' in data; assert 'available_models' in data; print('Valid JSON with all required keys')"
```

**Expected result:**
- The output is valid JSON
- The JSON contains the keys `providers`, `default_provider`, `default_model`, and `available_models`
- `providers` is a list containing the known provider names (e.g., `["claude", "gemini", "cursor"]`)
- `default_provider` is a string matching one of the providers
- `default_model` is a string
- `available_models` is an object keyed by provider name, where each value is an array of `{id, name}` objects

---

### 28.5 Models JSON output with provider filter

**Commands:**

```shell
docsfy models --json --provider gemini
```

**Check:**

```shell
docsfy models --json --provider gemini | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['providers'] == ['gemini'], f'Expected [\"gemini\"], got {data[\"providers\"]}'; assert list(data['available_models'].keys()) == ['gemini'], f'Expected only gemini key in available_models, got {list(data[\"available_models\"].keys())}'; print('Filtered JSON is correct')"
```

**Expected result:**
- The JSON output contains only `gemini` in the `providers` list
- The `available_models` object contains only the `gemini` key
- `default_provider` and `default_model` are still present (they reflect the server defaults, not the filter)

---

### 28.6 API endpoint is accessible without authentication

**Commands:**

```shell
curl -s -o /dev/null -w "%{http_code}" "$DOCSFY_SERVER/api/models"
```

**Expected result:**
- The HTTP status code is `200`
- No `Authorization` header is required

**Verify response body:**

```shell
curl -s "$DOCSFY_SERVER/api/models" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'providers' in data; assert 'default_provider' in data; assert 'default_model' in data; assert 'available_models' in data; print('API response is valid')"
```

**Expected result:**
- The response is valid JSON with the same schema as the CLI `--json` output
- Contains `providers`, `default_provider`, `default_model`, and `available_models`

---

### 28.7 Response includes available_models from provider discovery

**Precondition:** The server must be running and able to discover models from configured AI providers.

**Check for available models:**

```shell
AVAILABLE=$(curl -s "$DOCSFY_SERVER/api/models" | python3 -c "
import sys, json
data = json.load(sys.stdin)
available = data.get('available_models', {})
total = sum(len(v) for v in available.values())
print(total)
")
echo "Available models count: $AVAILABLE"
```

**Verify available_models contains data:**

```shell
curl -s "$DOCSFY_SERVER/api/models" | python3 -c "
import sys, json
data = json.load(sys.stdin)
available = data.get('available_models', {})
assert isinstance(available, dict), 'available_models should be a dict'
total = sum(len(v) for v in available.values())
assert total > 0, 'available_models should contain at least one model'
# Verify models have the correct shape: [{id, name}, ...]
for provider, models in available.items():
    for m in models:
        assert 'id' in m and 'name' in m, f'Model entry missing id/name: {m}'
# Verify at least one provider has discovered models
providers_with_models = [p for p, m in available.items() if len(m) > 0]
assert len(providers_with_models) > 0, f'Expected at least one provider with models, got {available}'
print(f'available_models contains {total} model(s) across {len(available)} provider(s)')
print(f'Providers with models: {providers_with_models}')
"
```

**Expected result:**
- `available_models` is a dictionary keyed by provider name
- Each value is an array of objects with `id` and `name` fields (e.g., `[{"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"}, ...]`)
- At least one provider has discovered models
- Models are discovered via pi-sidecar-client from the Pi SDK sidecar service, not from completed generations
- When both ACPX and CLI agents are configured (`ACPX_AGENTS` / `CLI_AGENTS`), model entries may include a `source` field (`acpx`, `cli`, or `api`)

---

### 28.7b Model source badges in UI

**Precondition:** Server running with at least one provider that has discovered models. Optional: `CLI_AGENTS` and/or `ACPX_AGENTS` set so both sources appear.

**Steps:**

1. Log in as admin and open the dashboard generate form (or Admin → Settings).
2. Select a provider that has models (e.g. `cursor`).
3. Open the model Combobox dropdown.

**Expected result:**
- Each model row shows the model id/name
- When a model has a `source` from the API, an uppercase badge (`ACPX`, `CLI`, or `API`) appears on that row
- Friendly provider list remains only `claude` / `gemini` / `cursor` (no `*-cli` providers)
- Selecting a CLI-tagged model and generating docs routes through `cli-*` on the sidecar; ACPX-tagged models use `acpx-*`
- Opening the Combobox with a selected model id shows the **full** list (not an empty or single-row list filtered by the full id)

---

### 28.7c Cursor auth banner when catalog empty

**Precondition:** Server running; Cursor discovery returns **zero** models (e.g. Cursor not logged in / no `CURSOR_API_KEY`), or temporarily empty catalog.

**Steps:**

1. Log in as admin; open generate form (or Admin → Settings).
2. Select provider `cursor`.
3. Inspect `GET /api/models` → `provider_status.cursor`.

**Expected result:**
- `provider_status.cursor.ok` is `false` with a `reason` / `hint`
- Admin response may include `has_api_key`; non-admin sees redacted `reason: unavailable` and a contact-admin hint
- UI shows `data-testid="cursor-auth-banner"` under the provider control
- When Cursor has models (`ok: true`), banner is **not** shown

---

### 28.8 Models refresh triggers re-discovery

**Commands:**

```shell
docsfy models --refresh
```

**Expected result:**
- The output begins with `Models refreshed from AI providers.`
- Followed by the normal provider/model listing
- Models are re-discovered from the sidecar (not served from cache)

---

### 28.9 Models refresh with JSON output

**Commands:**

```shell
docsfy models --refresh --json
```

**Expected result:**
- The output is valid JSON (no "Models refreshed" text since JSON mode)
- Contains `providers`, `default_provider`, `default_model`, and `available_models`
- Models are freshly discovered (same structure as 28.4)

---

### 28.10 API refresh endpoint requires admin auth

**Commands:**

```shell
# Without auth
curl -s -o /dev/null -w "%{http_code}" -X POST "$DOCSFY_SERVER/api/models/refresh"
```

**Expected result:**
- HTTP status code is `401` (unauthorized)

**With non-admin auth:**

```shell
curl -s -o /dev/null -w "%{http_code}" -X POST "$DOCSFY_SERVER/api/models/refresh" \
  -H "Authorization: Bearer $TEST_USER_PASSWORD"
```

**Expected result:**
- HTTP status code is `403` (forbidden, admin required)

**With admin auth:**

```shell
curl -s -X POST "$DOCSFY_SERVER/api/models/refresh" \
  -H "Authorization: Bearer $ADMIN_KEY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert 'providers' in data
assert 'available_models' in data
print('Refresh endpoint returned valid models response')
"
```

**Expected result:**
- HTTP status code is `200`
- Response has same structure as `GET /api/models`

---

### 28.11 Cleanup

**No cleanup needed.** Test 28.7 only queries available models and does not create any variant.
