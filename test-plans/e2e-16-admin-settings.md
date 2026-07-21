# Test 33: Admin Settings Page

[Back to Test Plan Index](e2e-ui-test-plan.md)

## Prerequisites

- Server running at `http://localhost:8800`
- `ADMIN_KEY` captured per [Variable Capture Rules](e2e-ui-test-plan.md#variable-capture-rules)
- At least one non-admin user created (from previous tests)

---

### 33.1 Settings page loads for admin

```bash
curl -s -X POST "$SERVER/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"admin\", \"api_key\": \"$ADMIN_KEY\"}"
```

Navigate to the dashboard. In the admin sidebar section, click "Settings".

**Expected result:** Settings page loads with 3 groups:
- "Generation Defaults" — Default AI Provider (select), Default AI Model (combobox)
- "Vision (Image Description)" — Vision AI Provider (select), Vision AI Model (combobox)
- "Performance" — AI CLI Timeout (number input), Max Concurrent Pages (number input)

---

### 33.2 GET /api/admin/settings returns current values

```bash
curl -s -H "Authorization: Bearer $ADMIN_KEY" "$SERVER/api/admin/settings" | jq .
```

**Expected result:** JSON response with structure:
```json
{
  "settings": {
    "default_ai_provider": "...",
    "default_ai_model": "...",
    "ai_cli_timeout": "...",
    "max_concurrent_pages": "...",
    "vision_provider": "...",
    "vision_model": "..."
  },
  "env_overrides": {}
}
```

The `env_overrides` object contains entries only for settings controlled by env vars.

---

### 33.3 PUT /api/admin/settings updates values

```bash
curl -s -X PUT -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/admin/settings" \
  -d '{"settings": {"default_ai_provider": "gemini", "default_ai_model": "gemini-2.5-flash"}}'
```

**Expected result:** `{"status": "ok"}`

Verify the change:
```bash
curl -s -H "Authorization: Bearer $ADMIN_KEY" "$SERVER/api/admin/settings" | jq '.settings.default_ai_provider'
```

**Expected result:** `"gemini"`

---

### 33.4 PUT /api/admin/settings validates provider

```bash
curl -s -X PUT -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/admin/settings" \
  -d '{"settings": {"default_ai_provider": "invalid-provider"}}'
```

**Expected result:** HTTP 400 with error about invalid provider.

---

### 33.5 PUT /api/admin/settings validates numeric fields

```bash
curl -s -X PUT -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/admin/settings" \
  -d '{"settings": {"ai_cli_timeout": "-5"}}'
```

**Expected result:** HTTP 400 with error about positive integer.

---

### 33.6 PUT /api/admin/settings rejects unknown keys

```bash
curl -s -X PUT -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/admin/settings" \
  -d '{"settings": {"unknown_key": "value"}}'
```

**Expected result:** HTTP 400 with error about unknown setting key.

---

### 33.7 Non-admin cannot access settings

```bash
curl -s -X POST "$SERVER/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$TEST_USER\", \"api_key\": \"$TEST_USER_PASSWORD\"}" \
  -c /tmp/user-cookies.txt

curl -s -b /tmp/user-cookies.txt "$SERVER/api/admin/settings"
```

**Expected result:** HTTP 403 Forbidden.

---

### 33.8 Settings sidebar item not visible for non-admin

Log in as `$TEST_USER` via the UI. Check the sidebar.

**Expected result:** No "Settings" item in the sidebar. Only admin users see the Admin section.

---

### 33.9 Env var override warning displays

If any env vars are set (e.g., `AI_PROVIDER`), the Settings page should show a warning below that field:

**Expected result:** Warning text: "⚠ Controlled by environment variable `AI_PROVIDER`. Changes will be lost on server restart — remove the env var to make this setting persistent."

---

### 33.10 Settings affect generate form defaults

After setting defaults via Settings page (or API), navigate to the generate form.

**Expected result:** The Provider and Model fields pre-populate with the admin-configured defaults. If no default is set, the fields are empty.

---

### 33.11 Settings affect /api/models response

```bash
curl -s "$SERVER/api/models" | jq '{default_provider, default_model}'
```

**Expected result:** Returns the values set in admin settings.

---

### 33.12 Settings page shows placeholder when no default is selected

Clear defaults via API:
```bash
curl -s -X PUT -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/admin/settings" \
  -d '{"settings": {"default_ai_provider": "", "default_ai_model": "", "vision_provider": "", "vision_model": ""}}'
```

Navigate to the Settings page.

**Expected result:**
- Default AI Provider select shows placeholder text "No default" (not `__clear__` or empty)
- Vision AI Provider select shows placeholder text "Same as generation provider" (not `__clear__` or empty)

Navigate to the Generate form.

**Expected result:**
- Vision Provider select shows placeholder text "Same as generation provider" (not `__clear__` or empty)

---

### 33.12b Provider without model cannot be saved

**Steps:**

1. Open Admin → Settings.
2. Change Default AI Provider to another value (model field clears).
3. Click Save without selecting a model.

**Expected result:**
- UI shows an error toast requiring a default model
- Settings are not persisted
- API `PUT /api/admin/settings` with `default_ai_provider` set and empty `default_ai_model` returns HTTP 400

---

### 33.13 Refresh models button visible for admin

Navigate to the Generate form as admin.

**Expected result:**
- A small refresh icon (⟳) appears next to the "Provider" label
- Clicking it triggers model re-discovery from AI providers
- A success toast "Models refreshed" appears
- The provider/model dropdowns are updated with fresh data

---

### 33.14 Refresh models button not visible for non-admin

Log in as `$TEST_USER` via the UI. Navigate to the Generate form.

**Expected result:**
- No refresh icon appears next to the "Provider" label
- Non-admin users cannot trigger model refresh

---

### 33.15 Generate fails without provider when no default configured

Clear the default provider:
```bash
curl -s -X PUT -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/admin/settings" \
  -d '{"settings": {"default_ai_provider": "", "default_ai_model": ""}}'
```

Try to generate without specifying provider/model:
```bash
curl -s -X POST -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/generate" \
  -d '{"repo_url": "https://github.com/myk-org/for-testing-only"}'
```

**Expected result:** HTTP 400 with message about no default provider configured.

---

### 33.16 Cleanup

Restore defaults:
```bash
curl -s -X PUT -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/admin/settings" \
  -d '{"settings": {"default_ai_provider": "gemini", "default_ai_model": "gemini-2.5-flash"}}'
```
