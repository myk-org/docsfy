# E2E UI Tests: Username Dropdown Menu, Theme, Sidebar, Dialog Theming, and Variant Card Visual Hierarchy

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

> **UI Framework Note:** The app UI is a React SPA using shadcn/ui components (DropdownMenu, Card, etc.) and Tailwind CSS.

---

## Test 18: Username Dropdown Menu

### 18.1 Dashboard dropdown shows correct items for admin

**Precondition:** Log in as `admin`.

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
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown menu appears with admin-specific items.

**Expected result:**
- The dropdown menu is visible
- It contains "Admin Panel" (visible only for admin users)
- It contains "Change Password"
- It contains "Logout"

---

### 18.2 Dashboard dropdown shows correct items for non-admin user

**Precondition:** Log in as `testuser-e2e`.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
agent-browser screenshot
```

**Expected result:**
- The dropdown menu is visible
- It does NOT contain "Admin Panel"
- It contains "Change Password"
- It contains "Logout"

---

### 18.3 Admin panel dropdown shows correct items

**Precondition:** Log in as `admin` and navigate to the admin panel.

```shell
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
```shell
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
agent-browser screenshot
```

**Expected result:**
- The dropdown menu is visible
- It contains "Dashboard" (link back to main page)
- It contains "Logout"

---

### 18.4 Click-outside closes dropdown

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
agent-browser screenshot
```

**Now click outside the dropdown:**
```shell
agent-browser click "body"
agent-browser wait 500
agent-browser screenshot
```

**Expected result:**
- The dropdown menu is no longer visible

---

### 18.5 Escape key closes dropdown

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
```

**Press Escape:**
```shell
agent-browser press "Escape"
agent-browser wait 500
agent-browser screenshot
```

**Expected result:**
- The dropdown menu is no longer visible

---

### 18.6 Escape key does not steal focus from modals

**Precondition:** Navigate to admin panel, open a dialog.

```shell
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-delete-user='testviewer-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Press Escape:**
```shell
agent-browser press "Escape"
agent-browser wait 500
```

**Expected result:**
- The dialog closes (not the dropdown behind it)
- Escape key targets the topmost overlay first

---

### 18.7 Theme toggle works independently

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

```shell
agent-browser javascript "document.querySelector('[data-testid=\"theme-toggle\"]') !== null"
```

**Expected result:**
- The theme toggle exists (returns `true`)
- The theme toggle is not inside the dropdown menu --- it operates independently

**Toggle theme:**
```shell
agent-browser click "[data-testid='theme-toggle']"
agent-browser javascript "document.documentElement.classList.contains('dark')"
```

**Expected result:**
- The theme changes (dark class toggled)

---

### 18.8 Theme persists across page refresh

**Precondition:** Logged in as `admin` (from Test 18.1).

**Commands (switch to light mode and verify persistence):**
```shell
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.documentElement.classList.contains('dark')"
```

If the return value is `true` (dark mode), toggle to light:
```shell
agent-browser click "[data-testid='theme-toggle']"
agent-browser wait 500
agent-browser javascript "document.documentElement.classList.contains('dark')"
```

**Check:** Theme is now light.

**Expected result:**
- Returns `false` (light mode active)

**Now refresh the page:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser javascript "document.documentElement.classList.contains('dark')"
agent-browser screenshot
```

**Check:** Theme persists as light after refresh.

**Expected result:**
- Returns `false` (light mode persisted --- not reset to dark)
- The page visually appears with a light background

**Toggle back to dark and verify persistence:**
```shell
agent-browser click "[data-testid='theme-toggle']"
agent-browser wait 500
agent-browser javascript "document.documentElement.classList.contains('dark')"
```

**Expected result:**
- Returns `true` (dark mode active)

**Refresh and verify:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser javascript "document.documentElement.classList.contains('dark')"
```

**Expected result:**
- Returns `true` (dark mode persisted across refresh)

---

### 18.9 First click on theme toggle changes theme immediately

**Precondition:** Fresh page load (no prior toggle interaction in this session).

**Commands:**
```shell
agent-browser javascript "sessionStorage.clear(); localStorage.removeItem('theme')"
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser javascript "document.documentElement.classList.contains('dark')"
```

**Check:** Capture the initial theme state.

**Expected result:**
- Returns `true` (default dark mode)

**Click the theme toggle exactly once:**
```shell
agent-browser click "[data-testid='theme-toggle']"
agent-browser wait 500
agent-browser javascript "document.documentElement.classList.contains('dark')"
agent-browser screenshot
```

**Check:** The theme changes on the very first click (no second click needed).

**Expected result:**
- Returns `false` (theme changed to light on the first click)
- The page visually changes to light mode immediately

**Restore dark mode:**
```shell
agent-browser click "[data-testid='theme-toggle']"
agent-browser wait 500
```

---

### 18.10 Cleanup

**Note:** Test 18 does not create any data. No cleanup needed.

---

## Test 25: Sidebar Collapse Toggle Position

### 25.1 Collapse toggle is at the bottom of the sidebar

**Precondition:** Logged in as `admin`.

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

**Check:** The sidebar collapse toggle button is positioned at the bottom of the sidebar.

**Expected result:**
- The collapse toggle button is visible at the bottom of the sidebar
- It is not positioned at the top or middle of the sidebar

---

### 25.2 Collapse toggle stays at bottom after collapsing

**Commands:**
```shell
agent-browser click "[data-testid='sidebar-collapse']"
agent-browser wait 500
agent-browser screenshot
```

**Check:** After collapsing, the toggle button remains at the bottom of the collapsed sidebar.

**Expected result:**
- The sidebar is collapsed (narrow width)
- The collapse toggle button is still at the bottom of the collapsed sidebar
- The toggle button is still visible and clickable

---

### 25.3 Collapse toggle stays at bottom after expanding

**Commands:**
```shell
agent-browser click "[data-testid='sidebar-collapse']"
agent-browser wait 500
agent-browser screenshot
```

**Check:** After expanding the sidebar, the toggle button remains at the bottom.

**Expected result:**
- The sidebar is expanded (full width)
- The collapse toggle button is at the bottom of the expanded sidebar

---

### 25.4 Cleanup

**Note:** Test 25 does not create any data. No cleanup needed.

---

## Test 26: Dialog Theme Consistency

### 26.1 Confirmation dialog matches dark theme

**Precondition:** Logged in as `admin` in dark mode.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

**Ensure dark mode is active:**
```shell
agent-browser javascript "document.documentElement.classList.contains('dark')"
```

If returns `false`, toggle to dark:
```shell
agent-browser click "[data-testid='theme-toggle']"
agent-browser wait 500
```

**Open a confirmation dialog (e.g., delete user):**
```shell
agent-browser navigate http://localhost:8800/admin
agent-browser wait 2000
agent-browser click "[data-delete-user='testviewer-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The dialog background and styling match the dark theme.

**Expected result:**
- The dialog/modal background is dark (not white)
- Dialog text is light-colored on the dark background
- The dialog visually matches the app's dark theme
- There is no jarring white box against the dark UI

**Cancel the dialog:**
```shell
agent-browser click "[data-testid='dialog-cancel']"
agent-browser wait 500
```

---

### 26.2 Cleanup

**Note:** Test 26 does not create any data. No cleanup needed.

---

## Test 19: Variant Card Visual Hierarchy

### 19.1 Variant cards are indented under project headers

**Precondition:** Log in as `admin` to see multiple projects and variants.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
```

**Commands:**
```shell
agent-browser screenshot
```

**Check:** Variant cards are visually indented relative to the project header.

**Expected result:**
- Variant cards appear nested under their project group headers
- The visual hierarchy is clear

---

### 19.2 Variant cards have distinct styling from project header

**Commands:**
```shell
agent-browser screenshot
```

**Expected result:**
- Project headers and variant cards have visually distinct styles
- The hierarchy is clear: project header sits above/contains the variant cards

---

### 19.3 Project groups are collapsible

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Click the project header to collapse:**
```shell
agent-browser click "[data-testid='project-header']"
agent-browser wait 500
agent-browser screenshot
```

**Expected result:**
- The variant cards within the project group are hidden
- The project header remains visible
- A collapse indicator changes direction

**Click again to expand:**
```shell
agent-browser click "[data-testid='project-header']"
agent-browser wait 500
agent-browser screenshot
```

**Expected result:**
- The variant cards are visible again

---

### 19.4 Project header shows ready/error variant counts

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Expected result:**
- The project header displays counts of ready and error variants
- Ready count reflects the number of variants with `ready` status
- Error count reflects the number of variants with `error` or `aborted` status

---

### 19.5 Cleanup

**Note:** Test 19 does not create any data. No cleanup needed.
