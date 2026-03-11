# E2E UI Tests: Generated Docs Quality, Status Page, and Custom Modals

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 8: Generated Docs Quality

**Precondition:** Generate docs first as `testuser-e2e` if not already done. Log in as `testuser-e2e` and ensure docs are in `ready` state.

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

If the project was deleted in Test 7.5, regenerate it:
```
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-submit"
```

Wait for generation to complete (poll status every 10s until ready).

### 8.1 Docs page loads with sidebar

**Commands:**
```
agent-browser navigate http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/
agent-browser screenshot
```

**Check:** The generated documentation site loads with a sidebar.

**Expected result:**
- The page loads without error
- A sidebar (`.sidebar` or similar navigation element) is visible on the left
- The sidebar contains navigation links to documentation sections
- The main content area contains the documentation text

---

### 8.2 Dark theme works on docs

**Commands:**
```
agent-browser javascript "document.documentElement.getAttribute('data-theme')"
```

**Check:** The docs page respects the theme.

**Expected result:**
- The docs page has theme support (either inherits from localStorage or defaults to dark)
- The docs content is readable with appropriate contrast

---

### 8.3 "On this page" TOC present

**Commands:**
```
agent-browser javascript "document.querySelectorAll('.toc a[href^=\"#\"], .on-this-page a[href^=\"#\"]').length > 0"
agent-browser screenshot
```

**Check:** A table of contents or "on this page" section exists with anchor links.

**Expected result:**
- Returns true --- TOC contains at least one anchor link

---

### 8.4 Code copy button works

**Commands:**
```
agent-browser javascript "document.querySelector('.copy-btn, [data-copy], button[class*=\"copy\"]') !== null"
```

**Check:** Code blocks have copy buttons.

**Expected result:**
- If code blocks exist in the generated docs, they include a copy button

**Click the copy button and verify feedback:**
```shell
agent-browser javascript "var btn = document.querySelector('.copy-btn, [data-copy], button[class*=\"copy\"]'); if (btn) { btn.click(); true; } else { false; }"
agent-browser wait 1000
agent-browser javascript "document.querySelector('.copy-btn.copied, [data-copy].copied, .copy-success') !== null || document.body.textContent.includes('Copied')"
```

**Expected result:**
- Returns true --- clicking copy button shows feedback (copied state or success message)

---

### 8.5 "Generated with docsfy" in footer

**Commands:**
```
agent-browser javascript "document.querySelector('footer') !== null"
agent-browser javascript "document.querySelector('footer').textContent.toLowerCase().includes('docsfy')"
```

**Check:** The footer credits docsfy.

**Expected result:**
- A `<footer>` element exists
- The footer text contains "docsfy"

---

### 8.6 llms.txt accessible

**Commands:**
```
agent-browser navigate http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/llms.txt
agent-browser javascript "document.body.innerText.length > 0"
agent-browser screenshot
```

**Check:** The `llms.txt` file is accessible and contains content.

**Expected result:**
- The page loads without a 404 error
- The content is non-empty text (LLM-friendly summary of the documentation)

---

### 8.7 llms-full.txt accessible

**Commands:**
```
agent-browser navigate http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/llms-full.txt
agent-browser javascript "document.body.innerText.length > 0"
agent-browser screenshot
```

**Check:** The `llms-full.txt` file is accessible and contains content.

**Expected result:**
- The page loads without a 404 error
- The content is non-empty text (full documentation in LLM-friendly format)
- This file should be larger than `llms.txt`

---

## Test 9: Status Page

**Precondition:** Start a new generation to observe the status page in action. Log in as `testuser-e2e`.

```
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-force"
agent-browser click "#gen-submit"
agent-browser wait 3000
```

### 9.1 Activity log shows progress

**Commands:**
```
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser wait 5000
agent-browser screenshot
```

**Check:** The activity log section shows real-time updates.

**Expected result:**
- The "Activity Log" section is visible with a title and status area
- Log entries appear showing stages (e.g., "cloning", "planning", "generating_pages")
- Each log entry has an icon indicating its state (check for complete, spinner for in-progress, circle for pending)
- The log status area shows a spinner while generating

**Verify log entries exist:**
```
agent-browser javascript "document.querySelectorAll('#log-body > *').length > 0"
```

**Expected result:** Returns `true`.

---

### 9.2 Abort button works

**Precondition:** A generation is running. If Test 9.1 shows the variant already reached `ready`, `error`, or `aborted`, start a fresh forced generation before continuing.

Check current status:
```
agent-browser javascript "document.getElementById('status-text')?.textContent?.trim().toLowerCase()"
```

If the previous command returned `ready`, `error`, or `aborted`, restart generation and return to the status page:
```
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-force"
agent-browser click "#gen-submit"
agent-browser wait 2000
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser wait 2000
```

**Commands:**
```
agent-browser javascript "document.getElementById('btn-abort') !== null"
agent-browser click "#btn-abort"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The abort modal appears.

**Expected result:**
- The modal title reads "Abort Generation"
- The modal body reads "Abort generation for for-testing-only?"
- There is a red "Delete" (confirm) button and a "Cancel" button

**Confirm abort:**
```
agent-browser click "#modal-ok"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- The status changes to `aborted`
- The error message shows "Generation aborted by user"
- The log status shows "Aborted"
- The "Abort" button is replaced by regenerate controls (provider select, model input, force checkbox, and "Regenerate" button)

---

### 9.3 Regenerate controls on error/aborted

**Precondition:** The project is in `aborted` state from Test 9.2.

**Commands:**
```
agent-browser javascript "document.getElementById('retry-provider') !== null"
agent-browser javascript "document.getElementById('retry-model') !== null"
agent-browser javascript "document.getElementById('retry-force') !== null"
agent-browser javascript "document.getElementById('btn-retry') !== null"
agent-browser screenshot
```

**Check:** Regenerate controls appear when the project is in error or aborted state.

**Expected result:**
- All four elements exist: provider select, model input, force checkbox, and "Regenerate" button
- The provider select shows the current provider (`gemini`)
- The model input shows the current model (`gemini-2.5-flash`)

---

## Test 10: Custom Modals

### 10.1 Delete confirmation uses themed modal (not browser dialog)

**Precondition:** Log in as `admin` and navigate to admin panel.

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/admin
```

**Commands:**
```
agent-browser click "[data-delete-user='testviewer-e2e']"
agent-browser wait 1000
agent-browser screenshot
agent-browser javascript "document.getElementById('custom-modal').style.display"
```

**Check:** A custom-themed modal appears (not a browser `window.confirm`).

**Expected result:**
- The return value is `"flex"` (the modal overlay is displayed as flex)
- The modal has the class `modal-overlay`
- The modal box uses the app's theme colors (dark background with light text in dark mode)
- The title reads "Delete User"
- The confirm button is styled as a danger button (red)

**Cancel to close:**
```
agent-browser click "#modal-cancel"
agent-browser wait 500
```

---

### 10.2 Password change uses themed modal

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-rotate-user='testuser-e2e']"
agent-browser wait 1000
agent-browser javascript "document.getElementById('custom-modal').style.display"
agent-browser javascript "document.getElementById('modal-title').textContent"
agent-browser javascript "document.getElementById('modal-input').type"
agent-browser screenshot
```

**Check:** The password change modal uses the themed modal component.

**Expected result:**
- Modal display is `"flex"`
- Title is `"Change Password"`
- Input type is `"password"` (masked input)
- The input hint shows "Minimum 16 characters"

**Cancel:**
```
agent-browser click "#modal-cancel"
```

---

### 10.3 Abort uses themed modal

**Precondition:** Start a generation to enable the abort button. Navigate to the dashboard.

```
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-force"
agent-browser click "#gen-submit"
agent-browser wait 3000
```

**Commands:**
```
agent-browser click ".variant-card[data-owner='admin'] [data-abort-variant]"
agent-browser wait 1000
agent-browser javascript "document.getElementById('custom-modal').style.display"
agent-browser javascript "document.getElementById('modal-title').textContent"
agent-browser screenshot
```

**Check:** The abort confirmation uses the themed modal.

**Expected result:**
- Modal display is `"flex"`
- Title is `"Abort Generation"`
- The confirm button is styled as a danger button

**Cancel:**
```
agent-browser click "#modal-cancel"
```

Then abort the generation to clean up:
```
agent-browser click ".variant-card[data-owner='admin'] [data-abort-variant]"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 3000
```

---

### 10.4 Escape closes modal

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-delete-user='testviewer-e2e']"
agent-browser wait 1000
agent-browser javascript "document.getElementById('custom-modal').style.display"
```

**Check:** Modal is open.

**Expected result:** Returns `"flex"`.

**Press Escape:**
```
agent-browser press "Escape"
agent-browser wait 500
agent-browser javascript "document.getElementById('custom-modal').style.display"
```

**Check:** Modal closes on Escape key.

**Expected result:** Returns `"none"`.
