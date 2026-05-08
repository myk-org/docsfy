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
- Models are discovered from AI CLI tools and LiteLLM pricing data, not from completed generations

---

### 28.8 Cleanup

**No cleanup needed.** Test 28.7 only queries available models and does not create any variant.
