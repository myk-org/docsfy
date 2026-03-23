# E2E UI Tests: Delete with Owner Scoping

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 15: Delete with Owner Scoping

**Precondition:** Log in as `admin`. Ensure at least two users have generated docs for the same repo. Use `testuser-e2e` and `userb-e2e` from Test 11.9 (both have `for-testing-only/main/gemini/gemini-2.5-flash`). If not present, regenerate them.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
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
agent-browser click "[data-testid='dialog-cancel']"
agent-browser wait 500
agent-browser javascript "if (!window.__docsfyDeleteInterceptInstalled) { const originalFetch = window.fetch.bind(window); window.fetch = (...args) => { const [input, init] = args; const url = typeof input === 'string' ? input : input.url; const method = (init?.method || (typeof input !== 'string' && input.method) || 'GET').toUpperCase(); if (method === 'DELETE') { sessionStorage.setItem('docsfyLastDeleteRequest', JSON.stringify({ url, method })); } return originalFetch(...args); }; window.__docsfyDeleteInterceptInstalled = true; } sessionStorage.removeItem('docsfyLastDeleteRequest');"
agent-browser click ".variant-card[data-owner='userb-e2e'] [data-delete-variant]"
agent-browser wait 1000
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
agent-browser javascript "sessionStorage.getItem('docsfyLastDeleteRequest')"
```

**Check:** The actual DELETE request sent by the UI includes owner scoping for `userb-e2e`.

**Expected result:**
- The captured JSON shows `"method":"DELETE"`
- The captured `url` contains `?owner=userb-e2e`
- The request targets the `for-testing-only/main/gemini/gemini-2.5-flash` variant owned by `userb-e2e`

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

### 15.4 Verify Delete All button removes all variants of an owner-scoped project group (main branch)

**Precondition:** Re-create `userb-e2e`'s `for-testing-only` project group with two variants so Delete All removes multiple variants without touching `testuser-e2e`'s variant needed by later tests.

Log in as `userb-e2e` and generate `gemini/gemini-2.5-flash`:
```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "userb-e2e"
agent-browser type "[name='password']" "<USERB_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser clear "[data-testid='branch-input']"
agent-browser type "[data-testid='branch-input']" "main"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser click "[data-testid='generate-btn']"
```

Wait for completion (poll until ready, max 2 minutes).

Generate the second variant `gemini/gemini-2.0-flash` for the same owner/project:
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser clear "[data-testid='branch-input']"
agent-browser type "[data-testid='branch-input']" "main"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.0-flash"
agent-browser click "[data-testid='generate-btn']"
```

Wait for completion (poll until ready, max 2 minutes).

Log back in as `admin`:
```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
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
agent-browser click "[data-testid='dialog-confirm']"
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

### 15.5 Confirmation dialog shows owner name when admin deletes another user's docs

**Precondition:** Stay logged in as `admin`. Reuse `testuser-e2e`'s existing `for-testing-only/main/gemini/gemini-2.5-flash` variant from Tests 14-15. Do NOT regenerate it here because Tests 16-17 rely on that existing variant history.

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelector('.variant-card[data-owner=\"testuser-e2e\"] [data-delete-variant=\"for-testing-only/main/gemini/gemini-2.5-flash\"]') !== null"
```

**Expected result:** Returns `true`.

If the previous command returned `false`, mark only Test 15.5 as `blocked`, note that the prerequisite variant is unexpectedly missing, and do not recreate it inside this subsection.

**If the previous command returned `true`, open the delete confirmation modal:**

```shell
agent-browser click ".variant-card[data-owner='testuser-e2e'] [data-delete-variant='for-testing-only/main/gemini/gemini-2.5-flash']"
agent-browser wait 1000
agent-browser javascript "document.getElementById('modal-body').textContent"
agent-browser screenshot
```

**Check:** The confirmation dialog explicitly mentions the owner name.

**Expected result:**
- The modal body contains "for-testing-only/main/gemini/gemini-2.5-flash" and "(owner: testuser-e2e)"

**Cancel:**

```shell
agent-browser click "[data-testid='dialog-cancel']"
```

---

### 15.7 Admin can delete a project without "owner is needed" error

**Precondition:** Logged in as `admin`. Generate a throwaway project variant to test deletion using a unique model name (`gemini-2.0-flash-15-7`) so it does not conflict with variants created or deleted by other tests.

**Commands (generate a throwaway variant as admin):**

```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser clear "[data-testid='branch-input']"
agent-browser type "[data-testid='branch-input']" "dev"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.0-flash"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
```

Wait for completion (poll until ready, max 2 minutes):
```shell
agent-browser javascript "document.querySelector('[data-testid=\"status-text\"]')?.textContent"
```

Repeat every 10 seconds until the status is `ready` or `error`.

**Verify the variant exists before attempting deletion:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser javascript "document.querySelector('.variant-card[data-owner=\"admin\"][data-delete-variant*=\"dev/gemini/gemini-2.0-flash\"]') !== null"
```

If returns `false`, the generation did not complete — mark test as `blocked` and skip to 15.8.

**Now delete the admin's own throwaway variant:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser click ".variant-card[data-owner='admin'] [data-delete-variant='for-testing-only/dev/gemini/gemini-2.0-flash']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A confirmation dialog appears (no error about missing owner).

**Expected result:**
- The dialog title reads "Delete Variant"
- There is NO error message about "project owner is needed"
- The dialog shows the variant details

**Confirm the deletion:**

```shell
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** The deletion succeeds.

**Expected result:**
- A success toast appears confirming the deletion
- The variant card is removed from the sidebar
- No error message about missing owner parameter

**Also test Delete All Variants for admin's own project group:**

```shell
agent-browser navigate http://localhost:8800/
```

If admin has a project group with variants, click Delete All:
```shell
agent-browser javascript "document.querySelector('.project-group[data-owner=\"admin\"] [data-delete-all]') !== null"
```

If returns `true`:
```shell
agent-browser click ".project-group[data-owner='admin'] [data-delete-all]"
agent-browser wait 1000
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- Delete All succeeds without "project owner is needed" error
- All variants in the admin's project group are removed

---

### 15.9 Delete variant removes it from sidebar immediately

**Preconditions:** Logged in as admin, at least one ready project visible in the sidebar.

**Setup — generate a throwaway variant if needed:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

If no ready variant exists, generate one:
```shell
agent-browser click "button:has-text('New Generation')"
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser clear "[data-testid='branch-input']"
agent-browser type "[data-testid='branch-input']" "main"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.0-flash"
agent-browser click "[data-testid='generate-btn']"
```

Wait for completion (poll until ready, max 2 minutes).

**Steps:**

1. Note a project variant in the sidebar:
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

2. Expand the project group and branch, then click on the variant to select it:
```shell
agent-browser screenshot
```

3. Click "Delete" in the variant detail panel:
```shell
agent-browser click "button:has-text('Delete')"
agent-browser wait 1000
agent-browser screenshot
```

4. Confirm the deletion dialog:
```shell
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 2000
agent-browser screenshot
```

**Expected result:**
- The variant disappears from the sidebar immediately (no page refresh needed)
- The main panel shows the empty state ("Welcome" message or generate form)
- If all variants of a project were deleted, the project group disappears from the sidebar
- A success toast confirms the deletion

---

### 15.10 Delete All removes project group from sidebar immediately

**Preconditions:** Logged in as admin, a project group with at least one variant visible in the sidebar.

**Setup — generate two throwaway variants under the same project if needed** (see 15.9 setup).

**Steps:**

1. Note the project group in the sidebar.
2. Hover over the project group row and click the trash icon (Delete All):
```shell
agent-browser screenshot
```

3. Confirm the deletion dialog:
```shell
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- All variants under that project group disappear from the sidebar immediately (no refresh)
- The project group row itself disappears from the sidebar
- The main panel shows the empty state
- A success toast confirms the deletion

---

### 15.8 Cleanup

Test 15 deletes only `userb-e2e`'s variants. The Delete All coverage in 15.4 should remove the re-created `userb-e2e` project group entirely, so no additional cleanup is required for that owner here.

**Ensure `testuser-e2e`'s variant remains for subsequent tests:**

The existing `testuser-e2e` variant from Test 14 is still needed by Tests 16 and 17. Do NOT delete or regenerate it in this section.
