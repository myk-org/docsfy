# E2E UI Tests: Doc Generation and Dashboard Features

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

> **UI Framework Note:** The app UI is a React SPA using shadcn/ui components and Tailwind CSS. Real-time progress updates use WebSocket (`/api/ws`) instead of HTTP polling.

---

## Test 6: Doc Generation (via User)

**Precondition:** Log back in as `testuser-e2e`.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

### 6.0 Verify default provider and model

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelector('[data-testid=\"provider-select\"]')?.textContent || document.querySelector('[data-testid=\"provider-select\"] [data-value]')?.getAttribute('data-value')"
agent-browser javascript "document.querySelector('[data-testid=\"model-input\"]')?.value"
```

**Check:** Default provider and model are set correctly.

**Expected result:**
- Provider returns `"cursor"` (or contains "cursor")
- Model returns `"gpt-5.4-xhigh-fast"`

---

### 6.1 Fill generate form with gemini/gemini-2.5-flash

**Note:** The default provider is `cursor` with model `gpt-5.4-xhigh-fast`, but this test explicitly selects `gemini/gemini-2.5-flash` for generation.

**Commands:**

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
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser screenshot
```

**Check:** The form fields are correctly populated.

**Expected result:**
- Repository URL field contains `https://github.com/myk-org/for-testing-only`
- Branch field shows `main`
- Provider shows `gemini`
- Model field shows `gemini-2.5-flash`
- Force checkbox is unchecked

---

### 6.2 Generation starts (card appears)

**Commands:**

```shell
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** A generation task is started.

**Expected result:**
- A toast notification appears with a success message about generation starting
- The project list shows a card for `for-testing-only` with status `GENERATING`
- A progress indicator is visible inside the card (updated via WebSocket)

---

### 6.3 View progress link works

**Commands:**

```shell
agent-browser javascript "document.querySelector('[data-testid=\"view-progress\"]') !== null"
agent-browser javascript "document.querySelector('[data-testid=\"view-progress\"]')?.click()"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A view progress link/button exists and clicking it navigates to the status/detail view.

**Expected result:**
- The link/button exists and is clickable
- After clicking, the view transitions to show the project status detail for `for-testing-only` with provider/model `gemini/gemini-2.5-flash`
- The status view shows the project name `for-testing-only` and the provider/model `gemini/gemini-2.5-flash`

---

### 6.4 Status page shows real-time progress

**Commands:**

```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser wait 5000
agent-browser screenshot
```

**Check:** The status view updates automatically via WebSocket.

**Expected result:**
- The status indicator shows `generating` with appropriate styling
- The progress indicator is visible and updates in real-time (via WebSocket)
- The "Activity Log" section shows log entries (stages like "cloning", "planning", "generating_pages")

---

### 6.5 Wait for completion

**Commands:**

```shell
agent-browser wait 120000
agent-browser screenshot
```

**Note:** Adjust the wait time based on generation speed. The test repo is small so generation should complete in under 2 minutes. Poll if needed:

```shell
agent-browser javascript "document.querySelector('[data-testid=\"status-text\"]')?.textContent"
```

Repeat every 10 seconds until the status is `ready` or `error`.

**Check:** The generation completes successfully.

**Expected result:**
- The status indicator shows `ready` with success styling
- The "View Documentation" button appears
- The "Download" button appears
- The page count is greater than 0

---

### 6.6 View Docs link works

**Commands:**

```shell
agent-browser javascript "document.querySelector('[data-testid=\"view-docs\"]')?.getAttribute('href')"
```

Capture the returned href (includes `?owner=...`), then navigate to it:

```shell
# Use the captured href from the previous command
agent-browser navigate <captured-docs-href>
agent-browser screenshot
```

**Check:** The generated documentation page loads.

**Expected result:**
- The page renders HTML documentation content
- A sidebar with navigation links is visible
- The URL may include an `?owner=` query parameter

---

### 6.7 Download link works

**Commands:**

```shell
agent-browser javascript "document.querySelector('[data-testid=\"download-btn\"]')?.getAttribute('href')"
```

**Check:** The download link points to the correct endpoint.

**Expected result:**
- The href matches `/api/projects/for-testing-only/main/gemini/gemini-2.5-flash/download?owner=<USERNAME>`

---

## Test 7: Dashboard Features

**Precondition:** Log in as `admin` to have maximum visibility. Ensure the `for-testing-only` project from Test 6 exists; if Test 6 failed or was blocked, mark Tests 7.1-7.8 as `blocked` and continue to Test 7.9.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

### 7.1 Search filter works

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser type "[data-testid='search-filter']" "for-testing"
agent-browser wait 500
agent-browser screenshot
```

**Check:** Only matching projects are visible.

**Expected result:**
- The `for-testing-only` project group is visible
- Any other projects (if they exist) are filtered out

**Clear the filter:**

```shell
agent-browser clear "[data-testid='search-filter']"
agent-browser wait 500
```

**Expected result:**
- All project groups are visible again

---

### 7.2 Pagination works (if enough projects)

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('[data-testid=\"project-group\"]').length"
```

**Check:** Pagination controls exist and function when there are enough projects.

**Expected result:**
- Pagination controls (next/prev buttons, page info) are present
- If total projects exceed per-page limit, pagination navigates between pages

---

### 7.3 Regenerate without force (should skip if unchanged)

**Precondition:** The `for-testing-only` project was generated in Test 6.

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

Find the regenerate button for the `for-testing-only` project and click it (without Force):

```shell
agent-browser click "[data-regenerate-variant='for-testing-only']"
agent-browser wait 5000
agent-browser screenshot
```

**Check:** The generation starts, but quickly resolves as "up to date" since the commit hasn't changed and Force is unchecked.

**Expected result:**
- After a few seconds, the project status returns to `READY`
- The status indicates documentation is already up to date

---

### 7.4 Abort generation

**Start a new generation first (with Force checked to ensure it actually runs):**

```shell
agent-browser navigate http://localhost:8800/
```

Enable force and regenerate:

```shell
agent-browser click "[data-regen-force='for-testing-only']"
agent-browser click "[data-regenerate-variant='for-testing-only']"
agent-browser wait 3000
agent-browser screenshot
```

**Now abort:**

```shell
agent-browser click "[data-abort-variant='for-testing-only']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A confirmation dialog appears (React component).

**Expected result:**
- The dialog title reads "Abort Generation"
- There is a destructive confirm button and a "Cancel" button

**Confirm the abort:**

```shell
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- The project status changes to `ABORTED`
- The error message reads "Generation aborted by user"

---

### 7.5 Delete project variant

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-delete-variant='for-testing-only/main/gemini/gemini-2.5-flash']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A confirmation dialog appears for deletion.

**Expected result:**
- The dialog title reads "Delete Variant"
- There is a destructive "Delete" button and a "Cancel" button

**Cancel first to verify cancel works:**

```shell
agent-browser click "[data-testid='dialog-cancel']"
agent-browser wait 500
```

**Expected result:**
- The dialog is dismissed
- The project card is still present

**Now actually delete:**

```shell
agent-browser click "[data-delete-variant='for-testing-only/main/gemini/gemini-2.5-flash']"
agent-browser wait 1000
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- A toast notification appears with "Variant ... deleted"
- The variant card is removed from the DOM

---

### 7.6 Model combobox shows known models

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser click "[data-testid='model-input']"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The model dropdown opens and shows known Gemini models.

**Expected result:**
- Model suggestions are shown
- The visible options include `gemini-2.5-flash` and `gemini-2.0-flash`

---

### 7.7 Provider switch updates model suggestions

**Commands:**

```shell
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='cursor']"
agent-browser wait 500
agent-browser click "[data-testid='model-input']"
agent-browser wait 500
agent-browser screenshot
```

**Check:** After switching from `gemini` to `cursor`, the dropdown shows only Cursor models.

**Expected result:**
- Only model options for the `cursor` provider are visible
- The model suggestions differ from those shown for `gemini` in step 7.6

---

### 7.8 Form state persists across refresh

**Commands:**

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
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser click "[data-testid='force-checkbox']"
```

**Now reload the page:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser javascript "document.querySelector('[data-testid=\"repo-url\"]')?.value"
agent-browser javascript "document.querySelector('[data-testid=\"branch-input\"]')?.value"
agent-browser javascript "document.querySelector('[data-testid=\"model-input\"]')?.value"
```

**Check:** The form state is restored from sessionStorage.

**Expected result:**
- Repository URL returns `"https://github.com/myk-org/for-testing-only"`
- Branch returns `"dev"`
- Model returns `"gemini-2.5-flash"`

**Cleanup:** Reset sessionStorage:

```shell
agent-browser javascript "sessionStorage.clear()"
```

---

### 7.9 Self-service password rotation full flow

**Precondition:** Log in as `testuser-e2e`.

**Commands:**

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser wait 2000
agent-browser navigate http://localhost:8800/
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
agent-browser click "[data-testid='change-password']"
agent-browser wait 1000
agent-browser type "[data-testid='password-input']" "my-new-secure-password-123"
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The password rotation succeeds and the session is invalidated (redirect to login).

**Expected result:**
- A success message confirms the password was changed (do NOT screenshot the new password value)
- After dismissing, the user is redirected to the login page (session invalidated)

**Verify new credentials work:**

```shell
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "my-new-secure-password-123"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser javascript "window.location.pathname !== '/login'"
```

**Expected result:**
- Login with the new password succeeds (user is redirected away from `/login`)
- Old password should no longer work

Update `TEST_USER_PASSWORD` = `my-new-secure-password-123` for subsequent tests.

---

### 7.10 Branch combobox shows known branches

**Precondition:** At least one project has been generated (from Test 6).

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser click "[data-testid='branch-input']"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The branch dropdown shows known branches for the repo.

**Expected result:**
- Branch suggestions are shown
- At least one branch option is visible (previously generated branches)

**Verify dropdown hides when repo URL is empty:**

```shell
agent-browser clear "[data-testid='repo-url']"
agent-browser click "[data-testid='branch-input']"
agent-browser wait 500
```

**Expected result:** No branch suggestions are shown without a repo URL.

---

### 7.11 Projects appear in sidebar immediately after login

**Precondition:** At least one project exists for `testuser-e2e` (from Test 6). Log out first.

**Commands:**

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser wait 2000
agent-browser screenshot
```

**Check:** Projects appear in the sidebar immediately after login without needing a manual page refresh.

**Expected result:**
- The dashboard loads at `/`
- Project groups are visible in the sidebar immediately (without a manual refresh)
- The `for-testing-only` project is listed
- No empty state is shown when the user has existing projects

**Verify project count:**

```shell
agent-browser javascript "document.querySelectorAll('[data-testid=\"project-group\"]').length"
```

**Expected result:**
- Returns at least `1` (projects loaded automatically on login)

---

### 7.12 New generation auto-selects in sidebar and shows progress

**Precondition:** Logged in as `testuser-e2e` (from Test 7.11 or re-login).

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-testid='new-generation']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The new generation form is visible.

**Fill the form and submit:**

```shell
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
agent-browser click "[data-testid='force-checkbox']"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** After submitting, the UI switches to show the generating variant.

**Expected result:**
- The main panel switches to the variant detail view (NOT stuck on the generation form)
- The generating variant appears in the sidebar with a blue pulsing status dot (indicating `generating`)
- A progress bar or activity log is visible without needing a manual page refresh
- The variant card shows `GENERATING` status

**Verify the sidebar shows the generating variant (scoped to sidebar element):**

```shell
agent-browser javascript "const sidebar = document.querySelector('[data-testid=\"project-tree\"]') || document.querySelector('nav'); sidebar ? (sidebar.querySelector('[role=\"img\"][aria-label=\"Generating\"]') !== null || sidebar.querySelector('.animate-pulse-status') !== null) : false"
```

**Expected result:**
- Returns `true` (a generating indicator is present specifically in the sidebar, not just anywhere on the page)

**Wait for completion or abort to clean up:**

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.0-flash/abort', {method:'POST', credentials:'same-origin'}).then(r => r.status)"
agent-browser wait 2000
```
