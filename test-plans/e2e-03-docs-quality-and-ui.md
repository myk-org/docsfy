# E2E UI Tests: Generated Docs Quality, Status Page, and Custom Modals

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

> **UI Framework Note:** The app UI is a React SPA using shadcn/ui components and Tailwind CSS. Modals and dialogs are React AlertDialog/Dialog components. Real-time updates use WebSocket (`/api/ws`).

---

## Test 8: Generated Docs Quality

**Precondition:** Generate docs first as `testuser-e2e` if not already done. Log in as `testuser-e2e` and ensure docs are in `ready` state.

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

If the project was deleted in Test 7.5, regenerate it via the generate form.

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
- A sidebar navigation element is visible on the left
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
agent-browser javascript "const btn = document.querySelector('.copy-btn, [data-copy], button[class*=\"copy\"]'); btn !== null"
agent-browser javascript "const btn = document.querySelector('.copy-btn, [data-copy], button[class*=\"copy\"]'); if (btn) { btn.click(); true } else { 'no copy button found' }"
agent-browser wait 500
agent-browser screenshot
```

**Check:** Code blocks have copy buttons and clicking them triggers the copy action.

**Expected result:**
- If code blocks exist in the generated docs, they include a copy button
- After clicking the copy button, a visual confirmation appears (e.g., button text/icon changes to "Copied" or a checkmark)

---

### 8.5 "Generated with docsfy" in footer

**Commands:**

```
agent-browser javascript "document.querySelector('footer') !== null"
agent-browser javascript "document.querySelector('footer').textContent.toLowerCase().includes('docsfy')"
```

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

**Expected result:**
- The page loads without a 404 error
- The content is non-empty text

---

### 8.7 llms-full.txt accessible

**Commands:**

```
agent-browser navigate http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/llms-full.txt
agent-browser javascript "document.body.innerText.length > 0"
agent-browser screenshot
```

**Expected result:**
- The page loads without a 404 error
- The content is non-empty text
- This file should be larger than `llms.txt`

---

## Test 9: Status Page

**Precondition:** Start a new generation to observe the status page in action. Log in as `testuser-e2e`.

```
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
agent-browser click "[data-testid='force-checkbox']"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
```

### 9.1 Activity log shows progress

**Commands:**

```
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser wait 5000
agent-browser screenshot
```

**Check:** The activity log section shows real-time updates via WebSocket.

**Expected result:**
- The "Activity Log" section is visible
- Log entries appear showing stages (e.g., "cloning", "planning", "generating_pages")
- Each log entry has an icon indicating its state
- Updates arrive in real-time via WebSocket

---

### 9.2 Abort button works

**Precondition:** A generation is running.

**Commands:**

```
agent-browser javascript "document.querySelector('button[title=\"Stop the documentation generation\"]') !== null"
agent-browser click "button[title='Stop the documentation generation']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The abort confirmation dialog appears (React component).

**Expected result:**
- The dialog title reads "Abort Generation"
- There is a destructive confirm button and a "Cancel" button

**Confirm abort:**

```
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- The status changes to `aborted`
- The error message shows "Generation aborted by user"

---

### 9.3 Regenerate controls on error/aborted

**Precondition:** The project is in `aborted` state from Test 9.2.

**Commands:**

```
agent-browser javascript "document.querySelector('button[title=\"Re-generate documentation with these settings\"]') !== null"
agent-browser javascript "document.querySelector('select') !== null || document.querySelector('[data-testid=\"provider-select\"]') !== null"
agent-browser javascript "document.querySelector('input[type=\"checkbox\"]') !== null"
agent-browser screenshot
```

**Check:** Regenerate controls appear when the project is in error or aborted state.

**Expected result:**
- Regenerate button exists with title "Re-generate documentation with these settings"
- Provider select control is present
- Force checkbox is present
- All controls are visible in the screenshot

---

## Test 10: Custom Modals

### 10.1 Delete confirmation uses React dialog (not browser dialog)

**Precondition:** Log in as `admin` and navigate to admin panel.

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/admin
```

**Commands:**

```
agent-browser click "[data-delete-user='testviewer-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A React AlertDialog appears (not a browser `window.confirm`).

**Expected result:**
- A dialog overlay is visible
- The dialog has themed styling (dark background with light text in dark mode)
- The title reads "Delete User"
- The confirm button is styled as destructive (red)

**Cancel to close:**

```
agent-browser click "[data-testid='dialog-cancel']"
agent-browser wait 500
```

---

### 10.2 Password change uses React dialog

**Commands:**

```
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-rotate-user='testuser-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The password change dialog uses a React component.

**Expected result:**
- A dialog is visible
- Title is `"Change Password"`
- Input type is `"password"` (masked input)

**Cancel:**

```
agent-browser click "[data-testid='dialog-cancel']"
```

---

### 10.3 Abort uses React dialog

**Precondition:** Start a generation to enable the abort button.

```
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser click "[data-testid='force-checkbox']"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
```

**Commands:**

```
agent-browser click "button[title='Stop the documentation generation']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The abort confirmation uses a React dialog.

**Expected result:**
- A dialog is visible
- Title is `"Abort Generation"`
- The confirm button is styled as destructive

**Cancel and then abort to clean up:**

```
agent-browser click "[data-testid='dialog-cancel']"
agent-browser click "button[title='Stop the documentation generation']"
agent-browser wait 1000
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
```

---

### 10.4 Escape closes dialog

**Commands:**

```
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-delete-user='testviewer-e2e']"
agent-browser wait 1000
```

**Check:** Dialog is open.

**Press Escape:**

```
agent-browser press "Escape"
agent-browser wait 500
agent-browser screenshot
```

**Check:** Dialog closes on Escape key.

**Expected result:** The dialog is no longer visible.
