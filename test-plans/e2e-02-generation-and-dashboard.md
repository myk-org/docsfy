# E2E UI Tests: Doc Generation and Dashboard Features

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 6: Doc Generation (via User)

**Precondition:** Log back in as `testuser-e2e`.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

### 6.0 Verify default provider and model

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.getElementById('gen-provider').value"
agent-browser javascript "document.getElementById('gen-model').value"
```

**Check:** Default provider and model are set correctly.

**Expected result:**
- Provider returns `"cursor"`
- Model returns `"gpt-5.4-xhigh-fast"`

---

### 6.1 Fill generate form with gemini/gemini-2.5-flash

**Note:** The default provider is `cursor` with model `gpt-5.4-xhigh-fast`, but this test explicitly selects `gemini/gemini-2.5-flash` for generation.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser clear "#gen-branch"
agent-browser type "#gen-branch" ""
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser screenshot
```

**Check:** The form fields are correctly populated.

**Expected result:**
- Repository URL field contains `https://github.com/myk-org/for-testing-only`
- Branch field is empty (defaults to main)
- Provider dropdown shows `gemini`
- Model field shows `gemini-2.5-flash`
- Force checkbox is unchecked

---

### 6.2 Generation starts (card appears)

**Commands:**
```shell
agent-browser click "#gen-submit"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** A generation task is started.

**Expected result:**
- A toast notification appears with a success message about generation starting
- The project list shows a card for `for-testing-only` with status `GENERATING`
- A progress bar is visible inside the card
- The text "Generating..." is visible

---

### 6.3 View progress link works

**Note:** The "View progress" link has `target="_blank"`, so `click + wait-for-navigation` will not follow it. Instead, capture the `href` and open it directly.

**Commands:**
```shell
agent-browser javascript "document.querySelector('.status-link') !== null"
agent-browser javascript "document.querySelector('.status-link').getAttribute('href')"
```

Capture the returned href (e.g., `/status/for-testing-only/main/gemini/gemini-2.5-flash`), then open it:
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser screenshot
```

**Check:** The status page loads for the project.

**Expected result:**
- The link href matches `/status/for-testing-only/main/gemini/gemini-2.5-flash`
- The status page shows the project name `for-testing-only`
- The provider/model shows `gemini/gemini-2.5-flash`

---

### 6.4 Status page shows real-time progress

**Commands:**
```shell
agent-browser wait 5000
agent-browser screenshot
```

**Check:** The status page updates automatically with progress.

**Expected result:**
- The status indicator shows `generating` with a blue dot
- The progress bar is visible and updates as pages are generated
- The "Activity Log" section shows log entries (stages like "cloning", "planning", "generating_pages")
- A spinner is shown in the log status area

---

### 6.5 Wait for completion

**Commands:**
```shell
agent-browser wait 120000
agent-browser screenshot
```

**Note:** Adjust the wait time based on generation speed. The test repo is small so generation should complete in under 2 minutes. Poll if needed:

```shell
agent-browser javascript "document.getElementById('status-text').textContent"
```

Repeat every 10 seconds until the status is `ready` or `error`.

**Check:** The generation completes successfully.

**Expected result:**
- The status indicator shows `ready` with a green dot
- The success message reads "Documentation generated successfully!"
- The "View Documentation" button appears
- The "Download" button appears
- The page count is greater than 0
- The log status shows "Complete"

---

### 6.6 View Docs link works

**Note:** The "View Docs" button has `target="_blank"`, so `click + wait-for-navigation` will not follow it. Instead, capture the `href` and open it directly.

**Commands:**
```shell
agent-browser javascript "document.getElementById('btn-view-docs').getAttribute('href')"
```

Capture the returned href, then open it:
```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/
agent-browser screenshot
```

**Check:** The generated documentation page loads.

**Expected result:**
- The URL matches `/docs/for-testing-only/main/gemini/gemini-2.5-flash/` or similar
- The page renders HTML documentation content
- A sidebar with navigation links is visible

---

### 6.7 Download link works

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser javascript "document.getElementById('btn-download').getAttribute('href')"
```

**Check:** The download link points to the correct endpoint.

**Expected result:**
- The href is `/api/projects/for-testing-only/main/gemini/gemini-2.5-flash/download`
- Clicking the link triggers a `.tar.gz` file download with filename `for-testing-only-gemini-gemini-2.5-flash-docs.tar.gz`

---

## Test 7: Dashboard Features

**Precondition:** Log in as `admin` to have maximum visibility. Ensure the `for-testing-only` project from Test 6 exists; if Test 6 failed or was blocked, mark Tests 7.1-7.8 as `blocked` and continue to Test 7.9.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

### 7.1 Search filter works

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser type "#search-filter" "for-testing"
agent-browser wait 500
agent-browser screenshot
```

**Check:** Only matching projects are visible.

**Expected result:**
- The `for-testing-only` project group is visible
- Any other projects (if they exist) are hidden with the class `search-hidden`

**Clear the filter:**
```shell
agent-browser clear "#search-filter"
agent-browser wait 500
```

**Expected result:**
- All project groups are visible again

**Search for a non-existent project:**
```shell
agent-browser type "#search-filter" "zzz-does-not-exist"
agent-browser wait 500
agent-browser javascript "document.querySelectorAll('.project-group:not(.search-hidden)').length"
```

**Expected result:**
- Returns `0` -- no matching groups are visible

```shell
agent-browser clear "#search-filter"
```

---

### 7.2 Pagination works (if enough projects)

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser select "#per-page" "10"
agent-browser wait 500
agent-browser javascript "document.querySelectorAll('.project-group').length"
```

**Check:** Determine whether the dashboard spans multiple pages when `per-page` is set to `10`.

**If the project-count command above returned greater than `10`, verify pagination moves between pages:**
```shell
agent-browser javascript "document.getElementById('per-page') !== null && document.getElementById('prev-page') !== null && document.getElementById('next-page') !== null && document.getElementById('page-info') !== null"
agent-browser javascript "document.getElementById('prev-page').disabled"
agent-browser javascript "document.getElementById('next-page').disabled"
agent-browser javascript "document.getElementById('page-info').textContent.trim()"
agent-browser click "#next-page"
agent-browser wait 500
agent-browser javascript "document.getElementById('page-info').textContent.trim()"
agent-browser javascript "document.getElementById('prev-page').disabled"
agent-browser click "#prev-page"
agent-browser wait 500
agent-browser javascript "document.getElementById('page-info').textContent.trim()"
```

**Expected result:**
- The first command returns `true`
- `prev-page` is disabled on page 1
- `next-page` is enabled on page 1
- The first `page-info` value starts with `Page 1 of `
- After clicking Next, the `page-info` value changes to start with `Page 2 of `
- After moving to page 2, `prev-page` is enabled
- After clicking Previous, the `page-info` value returns to the original `Page 1 of ...` text

**If the project-count command above returned `10` or less, verify pagination controls exist but do not paginate:**
```shell
agent-browser javascript "document.getElementById('per-page') !== null"
agent-browser javascript "document.getElementById('prev-page') !== null"
agent-browser javascript "document.getElementById('next-page') !== null"
agent-browser javascript "document.getElementById('page-info') !== null"
agent-browser javascript "document.getElementById('prev-page').disabled"
agent-browser javascript "document.getElementById('next-page').disabled"
agent-browser javascript "document.getElementById('page-info').textContent.trim()"
```

**Expected result:**
- All pagination elements exist
- `prev-page` button is disabled (returns `true`)
- `next-page` button is disabled (returns `true`)
- Page info shows "Page 1 of 1"

**Still in the `10 or less` branch, change the per-page setting:**
```shell
agent-browser select "#per-page" "50"
agent-browser wait 500
agent-browser javascript "document.getElementById('page-info').textContent"
```

**Expected result:**
- The page info updates to "Page 1 of 1" (since total projects are `10` or less and therefore still less than `50`)

---

### 7.3 Regenerate without force (should skip if unchanged)

**Precondition:** The `for-testing-only` project was generated in Test 6.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

Find the regenerate controls for the `for-testing-only` project:
```shell
agent-browser javascript "document.querySelector('[data-regenerate-variant=\"for-testing-only\"]') !== null"
```

**Expected result:** Returns `true`.

**Click Regenerate (without Force checkbox):**
```shell
agent-browser click "[data-regenerate-variant='for-testing-only']"
agent-browser wait 5000
agent-browser screenshot
```

**Check:** The generation starts, but quickly resolves as "up to date" since the commit hasn't changed and Force is unchecked.

**Expected result:**
- A toast notification appears indicating generation started
- After a few seconds, the project status returns to `READY`

**Verify the "up to date" message on the status page:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser javascript "document.body.textContent.includes('up to date') || document.body.textContent.includes('no changes')"
```

**Expected result:**
- Returns true --- the status page indicates documentation is already up to date

---

### 7.4 Abort generation

**Start a new generation first (with Force checked to ensure it actually runs):**
```shell
agent-browser navigate http://localhost:8800/
```

Find the Force checkbox for the for-testing-only variant:
```shell
agent-browser javascript "document.querySelector('[data-regen-force=\"for-testing-only\"]').checked = true"
agent-browser click "[data-regenerate-variant='for-testing-only']"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** The generation starts with status `GENERATING`.

**Now abort:**
```shell
agent-browser click ".variant-card[data-owner='testuser-e2e'] [data-abort-variant]"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A confirmation modal appears.

**Expected result:**
- The modal title reads "Abort Generation"
- The modal body contains "Abort generation for for-testing-only"
- There is a red "Delete" button (used as confirm for dangerous actions) and a "Cancel" button

**Confirm the abort:**
```shell
agent-browser click "#modal-ok"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- The page reloads
- The project status changes to `ABORTED`
- The error message reads "Generation aborted by user"

---

### 7.5 Delete project variant

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click ".variant-card[data-owner='testuser-e2e'] [data-delete-variant='for-testing-only/main/gemini/gemini-2.5-flash']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A custom confirmation modal appears for deletion.

**Expected result:**
- The modal title reads "Delete Variant"
- The modal body contains "Are you sure you want to delete" and the variant path
- The body mentions "This will remove the generated documentation for this variant and cannot be undone."
- There is a red "Delete" button and a "Cancel" button

**Cancel first to verify cancel works:**
```shell
agent-browser click "#modal-cancel"
agent-browser wait 500
agent-browser javascript "document.querySelector('.modal-overlay').style.display"
```

**Expected result:**
- The modal is dismissed
- The `display` style is `"none"`
- The project card is still present

**Now actually delete:**
```shell
agent-browser click ".variant-card[data-owner='testuser-e2e'] [data-delete-variant='for-testing-only/main/gemini/gemini-2.5-flash']"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- A toast notification appears with "Variant ... deleted"
- The variant card fades out and is removed from the DOM
- If it was the only variant, the entire project group is removed

---

### 7.6 Model combobox shows known models

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser click "#gen-model"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The model dropdown opens and shows only the two allowed Gemini models.

**Expected result:**
- The `#model-dropdown` element has the class `active`
- Exactly two visible `.model-option` elements are shown
- The visible options are `gemini-2.5-flash` and `gemini-2.0-flash`
- No visible option refers to a different provider or a third model

**Verify visible option count:**
```shell
agent-browser javascript "Array.from(document.querySelectorAll('#model-dropdown .model-option')).filter(o => o.style.display !== 'none').length"
```

**Expected result:** Returns `2`.

---

### 7.7 Provider switch updates model suggestions

**Commands:**
```shell
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser click "#gen-model"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown filters to show only Gemini models.

**Expected result:**
- Only model options with `data-provider="gemini"` are visible
- If non-Gemini options exist in the DOM, they are hidden (`display: none`)

**Verify:**
```shell
agent-browser javascript "Array.from(document.querySelectorAll('#model-dropdown .model-option')).filter(o => o.style.display !== 'none').every(o => o.getAttribute('data-provider') === 'gemini')"
```

**Expected result:** Returns `true`.

**Switch to a different model (stay on gemini provider):**
```shell
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.0-flash"
agent-browser click "#gen-model"
agent-browser wait 500
agent-browser javascript "Array.from(document.querySelectorAll('#model-dropdown .model-option')).filter(o => o.style.display !== 'none').every(o => o.getAttribute('data-provider') === 'gemini')"
```

**Expected result:** Returns `true` (all visible options are still gemini models).

---

### 7.8 Form state persists across refresh

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser clear "#gen-branch"
agent-browser type "#gen-branch" "dev"
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-force"
```

**Now reload the page:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser javascript "document.getElementById('gen-repo-url').value"
agent-browser javascript "document.getElementById('gen-branch').value"
agent-browser javascript "document.getElementById('gen-provider').value"
agent-browser javascript "document.getElementById('gen-model').value"
agent-browser javascript "document.getElementById('gen-force').checked"
```

**Check:** The form state is restored from sessionStorage.

**Expected result:**
- Repository URL returns `"https://github.com/myk-org/for-testing-only"`
- Branch returns `"dev"`
- Provider returns `"gemini"`
- Model returns `"gemini-2.5-flash"`
- Force checkbox returns `true`

**Cleanup:** Reset sessionStorage to avoid leaking state into later tests:
```shell
agent-browser javascript "sessionStorage.removeItem('docsfy-repo'); sessionStorage.removeItem('docsfy-branch'); sessionStorage.removeItem('docsfy-force'); sessionStorage.removeItem('docsfy-provider'); sessionStorage.removeItem('docsfy-model')"
```

---

### 7.9 Self-service password rotation full flow

**Precondition:** Logged in as `testuser-e2e`. Since Test 7 runs as `admin`, re-login as `testuser-e2e` first.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser wait 2000
agent-browser navigate http://localhost:8800/
agent-browser click ".btn-change-password"
agent-browser wait 1000
agent-browser type "#modal-input" "my-new-secure-password-123"
agent-browser click "#modal-ok"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The success modal shows the new password and the session is invalidated.

**Expected result:**
- Success modal displays the new password `my-new-secure-password-123`
- After dismissing the modal, the user is redirected to the login page (session invalidated)

**Dismiss the modal:**
```shell
agent-browser click "#modal-ok"
agent-browser wait 2000
```
The page should redirect to /login after the modal is dismissed.
```shell
agent-browser wait --url "**/login"
```

**Try logging in with the OLD password:**
```shell
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait 2000
agent-browser screenshot
```

**Expected result:**
- Login fails with "Invalid username or password" error
- The user remains on the login page

**Login with the NEW password:**
```shell
agent-browser clear "#username"
agent-browser type "#username" "testuser-e2e"
agent-browser clear "#api_key"
agent-browser type "#api_key" "my-new-secure-password-123"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** Login succeeds with the new password.

**Expected result:**
- Login succeeds and redirects to the dashboard
- The page title is "docsfy - Dashboard"
- The header shows the username "testuser-e2e"

**Update stored password variable:**
Set `TEST_USER_PASSWORD` = `my-new-secure-password-123` for subsequent tests.

---

### 7.10 Branch combobox shows known branches

**Precondition:** At least one project has been generated (from Test 6).

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser click "#gen-branch"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The branch dropdown shows known branches for the repo.

**Expected result:**
- The `#branch-dropdown` element has the class `active`
- At least one `.branch-option` is visible
- The visible options show branches previously generated for `for-testing-only`

**Verify dropdown hides when repo URL is empty:**
```shell
agent-browser clear "#gen-repo-url"
agent-browser click "#gen-branch"
agent-browser wait 500
agent-browser javascript "document.getElementById('branch-dropdown').classList.contains('active')"
```

**Expected result:** Returns `false` --- dropdown does not open without a repo URL.
