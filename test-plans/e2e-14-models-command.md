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
- Each provider section shows its known models or `(no models used yet)` if none exist

---

### 28.2 Models filters to single provider

**Commands:**
```shell
docsfy models --provider cursor
```

**Expected result:**
- Only the `cursor` provider is listed
- No other providers appear in the output
- If `cursor` has known models from completed generations, they are shown
- If not, `(no models used yet)` is displayed

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
docsfy models --json | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'providers' in data; assert 'default_provider' in data; assert 'default_model' in data; assert 'known_models' in data; print('Valid JSON with all required keys')"
```

**Expected result:**
- The output is valid JSON
- The JSON contains the keys `providers`, `default_provider`, `default_model`, and `known_models`
- `providers` is a list containing the known provider names (e.g., `["claude", "gemini", "cursor"]`)
- `default_provider` is a string matching one of the providers
- `default_model` is a string
- `known_models` is an object keyed by provider name

---

### 28.5 Models JSON output with provider filter

**Commands:**
```shell
docsfy models --json --provider gemini
```

**Check:**
```shell
docsfy models --json --provider gemini | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['providers'] == ['gemini'], f'Expected [\"gemini\"], got {data[\"providers\"]}'; assert list(data['known_models'].keys()) == ['gemini'], f'Expected only gemini key in known_models, got {list(data[\"known_models\"].keys())}'; print('Filtered JSON is correct')"
```

**Expected result:**
- The JSON output contains only `gemini` in the `providers` list
- The `known_models` object contains only the `gemini` key
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
curl -s "$DOCSFY_SERVER/api/models" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'providers' in data; assert 'default_provider' in data; assert 'default_model' in data; assert 'known_models' in data; print('API response is valid')"
```

**Expected result:**
- The response is valid JSON with the same schema as the CLI `--json` output
- Contains `providers`, `default_provider`, `default_model`, and `known_models`

---

### 28.7 Response includes known_models from completed generations

**Precondition:** At least one generation must have completed successfully. If no prior test has generated docs, trigger one first.

**Check for existing completed generation:**
```shell
COMPLETED=$(curl -s "$DOCSFY_SERVER/api/models" | python3 -c "
import sys, json
data = json.load(sys.stdin)
known = data.get('known_models', {})
total = sum(len(v) for v in known.values())
print(total)
")
echo "Known models count: $COMPLETED"
```

If 0, generate docs to populate known_models:
```shell
if [ "$COMPLETED" = "0" ]; then
  docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
  for i in $(seq 1 60); do
    STATUS=$(curl -s "$DOCSFY_SERVER/api/projects" -H "Authorization: Bearer $DOCSFY_API_KEY" | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='main' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('status','') if matches else 'not_found')")
    echo "Poll $i: status=$STATUS"
    if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ] || [ "$STATUS" = "aborted" ]; then break; fi
    sleep 2
  done
fi
```

**Verify known_models contains data:**
```shell
curl -s "$DOCSFY_SERVER/api/models" | python3 -c "
import sys, json
data = json.load(sys.stdin)
known = data.get('known_models', {})
assert isinstance(known, dict), 'known_models should be a dict'
total = sum(len(v) for v in known.values())
assert total > 0, 'known_models should contain at least one model after generation'
# Verify the model we generated with is present
gemini_models = known.get('gemini', [])
assert 'gemini-2.5-flash' in gemini_models, f'Expected gemini-2.5-flash in known gemini models, got {gemini_models}'
print(f'known_models contains {total} model(s) across {len(known)} provider(s)')
print(f'gemini models: {gemini_models}')
"
```

**Expected result:**
- `known_models` is a dictionary keyed by provider name
- The `gemini` key contains `gemini-2.5-flash` (from the completed generation)
- Models from completed generations are accurately reflected in the response

---

### 28.8 Cleanup

**Delete any generation created by test 28.7:**
```shell
docsfy delete for-testing-only --branch main --provider gemini --model gemini-2.5-flash --yes 2>/dev/null || true
```

**Expected result:** Variant is deleted or already gone.
