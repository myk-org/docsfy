# E2E UI Tests: Delete with Owner Scoping

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 15: Delete with Owner Scoping

**Precondition:** Log in as `admin`. Ensure at least two users have generated docs for the same repo. Use `testuser-e2e` and `userb-e2e` from Test 11.9 (both have `for-testing-only` with `gemini/gemini-2.5-flash`). If not present, regenerate them.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

### 15.1 Admin deletes a specific user's variant via Delete button

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

Identify the variant card for `userb-e2e`'s `for-testing-only` project:
```shell
agent-browser javascript "document.querySelector('.variant-card[data-owner=\"userb-e2e\"]') !== null"
```

**Expected result:** Returns `true` -- the variant card for `userb-e2e` exists.

**Click the Delete button on `userb-e2e`'s variant:**
```shell
agent-browser click ".variant-card[data-owner='userb-e2e'] [data-delete-variant]"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The confirmation dialog appears.

**Expected result:**
- The modal overlay is visible
- The modal title reads "Delete Variant"
- The modal body mentions the variant path and references the owner `userb-e2e`

---

### 15.2 Verify `?owner=` parameter is sent in the DELETE request

**Commands:**
```shell
agent-browser click "#modal-cancel"
agent-browser wait 500
agent-browser javascript "if (!window.__docsfyDeleteInterceptInstalled) { const originalFetch = window.fetch.bind(window); window.fetch = (...args) => { const [input, init] = args; const url = typeof input === 'string' ? input : input.url; const method = (init?.method || (typeof input !== 'string' && input.method) || 'GET').toUpperCase(); if (method === 'DELETE') { sessionStorage.setItem('docsfyLastDeleteRequest', JSON.stringify({ url, method })); } return originalFetch(...args); }; window.__docsfyDeleteInterceptInstalled = true; } sessionStorage.removeItem('docsfyLastDeleteRequest');"
agent-browser click ".variant-card[data-owner='userb-e2e'] [data-delete-variant]"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 3000
agent-browser javascript "sessionStorage.getItem('docsfyLastDeleteRequest')"
```

**Check:** The actual DELETE request sent by the UI includes owner scoping for `userb-e2e`.

**Expected result:**
- The captured JSON shows `"method":"DELETE"`
- The captured `url` contains `?owner=userb-e2e`
- The request targets the `for-testing-only/gemini/gemini-2.5-flash` variant owned by `userb-e2e`

---

### 15.3 Verify other users' variants are NOT affected

**Commands:**
```shell
agent-browser javascript "document.querySelector('.variant-card[data-owner=\"userb-e2e\"]') === null"
agent-browser javascript "document.querySelector('.variant-card[data-owner=\"testuser-e2e\"]') !== null"
agent-browser screenshot
```

**Check:** Only `userb-e2e`'s variant was deleted; `testuser-e2e`'s variant remains.

**Expected result:**
- First returns `true` (userb-e2e's variant is gone)
- Second returns `true` (testuser-e2e's variant still exists)

---

### 15.4 Verify legacy variants (empty owner) can be deleted

**Precondition:** If any legacy variants exist (variants created before owner-scoping was introduced, with an empty or null owner), this test applies. If no legacy variants exist, this test can be skipped.

**Commands:**
```shell
agent-browser javascript "document.querySelector('.variant-card[data-owner=\"\"]') !== null || document.querySelector('.variant-card:not([data-owner])') !== null"
```

If returns `true`, proceed to delete the legacy variant:
```shell
agent-browser click ".variant-card:not([data-owner]) [data-delete-variant], .variant-card[data-owner=''] [data-delete-variant]"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 3000
```

**Check:** The legacy variant is deleted without errors.

**Expected result:**
- The delete request succeeds (no 400 or 500 error)
- The legacy variant card is removed from the DOM
- The server handles empty/null owner gracefully

If returns `false` (no legacy variants), this test is **SKIPPED**.

---

### 15.5 Verify Delete All button removes all variants of an owner-scoped project group

**Precondition:** Re-create `userb-e2e`'s `for-testing-only` project group with two variants so Delete All removes multiple variants without touching `testuser-e2e`'s variant needed by later tests.

Log in as `userb-e2e` and generate `gemini/gemini-2.5-flash`:
```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "userb-e2e"
agent-browser type "#api_key" "<USERB_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-submit"
```

Wait for completion (poll until ready, max 2 minutes).

Generate the second variant `gemini/gemini-2.0-flash` for the same owner/project:
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.0-flash"
agent-browser click "#gen-submit"
```

Wait for completion (poll until ready, max 2 minutes).

Log back in as `admin`:
```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

Locate the "Delete All" button for `userb-e2e`'s `for-testing-only` project group:
```shell
agent-browser javascript "document.querySelector('.project-group[data-repo=\"for-testing-only\"][data-owner=\"userb-e2e\"] [data-delete-all]') !== null"
```

**Expected result:** Returns `true`.

**Click Delete All:**
```shell
agent-browser click ".project-group[data-repo='for-testing-only'][data-owner='userb-e2e'] [data-delete-all]"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The confirmation dialog appears.

**Expected result:**
- The modal title reads "Delete All Variants" or similar
- The modal body warns that all variants in `userb-e2e`'s project group will be removed

**Confirm deletion:**
```shell
agent-browser click "#modal-ok"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- All variant cards under `userb-e2e`'s `for-testing-only` project group are removed
- The `userb-e2e` project group is removed from the DOM
- The `testuser-e2e` project group for the same repo still exists
- A toast notification confirms the deletion

**Verify:**
```shell
agent-browser javascript "document.querySelector('.project-group[data-repo=\"for-testing-only\"][data-owner=\"userb-e2e\"]') === null"
agent-browser javascript "document.querySelector('.project-group[data-repo=\"for-testing-only\"][data-owner=\"testuser-e2e\"]') !== null"
```

**Expected result:**
- First returns `true`
- Second returns `true`

---

### 15.6 Confirmation dialog shows owner name when admin deletes another user's docs

**Precondition:** Stay logged in as `admin`. Reuse `testuser-e2e`'s existing `for-testing-only/gemini/gemini-2.5-flash` variant from Tests 14-15. Do NOT regenerate it here because Tests 16-17 rely on that existing variant history.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelector('.variant-card[data-owner=\"testuser-e2e\"] [data-delete-variant=\"for-testing-only/gemini/gemini-2.5-flash\"]') !== null"
```

**Expected result:** Returns `true`.

If the previous command returned `false`, mark only Test 15.6 as `blocked`, note that the prerequisite variant is unexpectedly missing, and do not recreate it inside this subsection.

**If the previous command returned `true`, open the delete confirmation modal:**
```shell
agent-browser click ".variant-card[data-owner='testuser-e2e'] [data-delete-variant='for-testing-only/gemini/gemini-2.5-flash']"
agent-browser wait 1000
agent-browser javascript "document.getElementById('modal-body').textContent"
agent-browser screenshot
```

**Check:** The confirmation dialog explicitly mentions the owner name.

**Expected result:**
- The modal body text includes the owner name `testuser-e2e`
- This makes it clear to the admin that they are deleting another user's documentation
- The text might read something like "Delete variant for-testing-only/gemini/gemini-2.5-flash owned by testuser-e2e?"

**Cancel:**
```shell
agent-browser click "#modal-cancel"
```

---

### 15.7 Cleanup

Test 15 deletes only `userb-e2e`'s variants. The Delete All coverage in 15.5 should remove the re-created `userb-e2e` project group entirely, so no additional cleanup is required for that owner here.

**Ensure `testuser-e2e`'s variant remains for subsequent tests:**

The existing `testuser-e2e` variant from Test 14 is still needed by Tests 16 and 17. Do NOT delete or regenerate it in this section.
