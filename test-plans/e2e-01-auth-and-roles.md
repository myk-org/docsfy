# E2E UI Tests: Authentication and Roles

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

> **UI Framework Note:** The app UI is a React SPA using shadcn/ui components and Tailwind CSS. All modals, toasts, and dialogs are React components. Real-time updates use WebSocket (`/api/ws`).

---

## Test 1: Login Page

### 1.1 Login page loads

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser screenshot
```

**Check:** The login page renders with the docsfy branding.

**Expected result:**
- The React SPA loads and renders the login form
- The heading shows "docsfy" with the "fy" portion in accent color
- The subtitle text reads "Enter your credentials to continue"
- A "Username" input field is visible with placeholder "Enter your username"
- A "Password" input field is visible with placeholder "Enter your password"
- A "Sign In" button is visible
- A hint at the bottom reads: `Admin login: username admin with the admin password.`

---

### 1.2 Dark theme by default

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser javascript "document.documentElement.classList.contains('dark')"
agent-browser screenshot
```

**Check:** The app defaults to dark theme.

**Expected result:**
- The return value is `true` (the `dark` class is on the `<html>` element --- Tailwind dark mode)
- The page visually appears with a dark background
- Text is light-colored on the dark background

---

### 1.3 Theme toggle works

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser click "[data-testid='theme-toggle']"
agent-browser javascript "document.documentElement.classList.contains('dark')"
agent-browser screenshot
```

**Check:** After clicking the theme toggle, the theme changes from dark to light.

**Expected result:**
- The return value is `false` (dark class removed --- now light mode)
- The page background changes to light colors

**Then toggle back:**
```
agent-browser click "[data-testid='theme-toggle']"
agent-browser javascript "document.documentElement.classList.contains('dark')"
```

**Expected result:**
- The return value is `true` again (dark mode restored)

---

### 1.4 Invalid login shows error

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "wronguser"
agent-browser type "[name='password']" "wrongpassword"
agent-browser click "button[type='submit']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** An error message appears on the login page.

**Expected result:**
- The page remains on `/login`
- A red error message or toast is visible with text "Invalid username or password"

---

### 1.5 Admin login succeeds

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** Login succeeds and redirects to the dashboard.

**Expected result:**
- The browser is redirected to `/` (the dashboard)
- The React SPA renders the dashboard view
- The header shows the username "admin"
- The "Admin Panel" link is visible (because the admin role is active)
- The "Generate Documentation" form section is visible
- A "Logout" option is available in the user menu

---

### 1.6 ADMIN_KEY user Change Password is denied

**Precondition:** Logged in as `admin` (ADMIN_KEY user, from Test 1.5).

**Commands:**
```
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
agent-browser click "[data-testid='change-password']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The change password dialog appears (React dialog component).

**Expected result:**
- A dialog/modal is visible
- The title reads "Change Password"

**Enter a new password and confirm:**
```
agent-browser type "[data-testid='password-input']" "somenewpassword12345"
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** An error message is shown indicating ADMIN_KEY users cannot change passwords.

**Expected result:**
- Error message appears: "ADMIN_KEY users cannot rotate keys. Change the ADMIN_KEY env var instead."
- The password is NOT changed
- The admin session remains valid

---

## Test 2: Admin Panel

### 2.1 Admin link visible for admin

**Precondition:** Logged in as `admin` (from Test 1.5).

**Commands:**
```
agent-browser javascript "document.querySelector('[data-testid=\"admin-link\"], a[href=\"/admin\"]') !== null"
agent-browser screenshot
```

**Check:** The Admin link exists in the navigation.

**Expected result:**
- Returns `true`
- The link navigates to `/admin`

---

### 2.2 Create user (user role)

**Commands:**
```shell
agent-browser navigate http://localhost:8800/admin
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The admin panel loads with user management features.

**Expected result:**
- URL is `http://localhost:8800/admin`
- The React SPA renders the admin panel
- A "Create User" form is visible with username input, role dropdown, and submit button

**Now create the user:**
```
agent-browser type "[data-testid='new-username']" "testuser-e2e"
agent-browser click "[data-testid='role-select']"
agent-browser wait 500
agent-browser click "[data-value='user']"
agent-browser wait 500
agent-browser click "[data-testid='create-user-btn']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user is created and the password is displayed.

**Expected result:**
- A success message or toast appears with text containing "User 'testuser-e2e' created successfully"
- The generated password is displayed (capture this as `TEST_USER_PASSWORD`)
- The user appears in the users table with a `user` role badge

**Capture the password:**
```
agent-browser javascript "document.querySelector('[data-testid=\"generated-password\"]')?.textContent"
```

Store this value as `TEST_USER_PASSWORD`.

**Click Done to dismiss:**
```
agent-browser click "[data-testid='dismiss-password']"
agent-browser wait 2000
```

---

### 2.3 Create user (admin role)

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "[data-testid='new-username']" "testadmin-e2e"
agent-browser click "[data-testid='role-select']"
agent-browser wait 500
agent-browser click "[data-value='admin']"
agent-browser wait 500
agent-browser click "[data-testid='create-user-btn']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The admin user is created.

**Expected result:**
- Success message with "User 'testadmin-e2e' created successfully"
- The displayed role shows `admin`
- The user appears in the table with an `admin` role badge

**Capture the password:**
```
agent-browser javascript "document.querySelector('[data-testid=\"generated-password\"]')?.textContent"
```

Store this value as `TEST_ADMIN_PASSWORD`.

**Click Done:**
```
agent-browser click "[data-testid='dismiss-password']"
agent-browser wait 2000
```

---

### 2.4 Create user (viewer role)

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "[data-testid='new-username']" "testviewer-e2e"
agent-browser click "[data-testid='role-select']"
agent-browser wait 500
agent-browser click "[data-value='viewer']"
agent-browser wait 500
agent-browser click "[data-testid='create-user-btn']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The viewer user is created.

**Expected result:**
- Success message with "User 'testviewer-e2e' created successfully"
- The displayed role shows `viewer`
- The user appears in the table with a `viewer` role badge

**Capture the password:**
```
agent-browser javascript "document.querySelector('[data-testid=\"generated-password\"]')?.textContent"
```

Store this value as `TEST_VIEWER_PASSWORD`.

**Click Done:**
```
agent-browser click "[data-testid='dismiss-password']"
agent-browser wait 2000
```

---

### 2.5 Delete user works

**First, create a disposable user to delete:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "[data-testid='new-username']" "delete-me-e2e"
agent-browser click "[data-testid='role-select']"
agent-browser wait 500
agent-browser click "[data-value='user']"
agent-browser wait 500
agent-browser click "[data-testid='create-user-btn']"
agent-browser wait 2000
agent-browser click "[data-testid='dismiss-password']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user `delete-me-e2e` appears in the users table.

**Now delete the user:**
```
agent-browser click "[data-delete-user='delete-me-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A confirmation dialog appears (React AlertDialog, not a browser `confirm`).

**Expected result:**
- A dialog is visible
- The dialog title reads "Delete User"
- The dialog body reads "Delete user 'delete-me-e2e'? This cannot be undone."
- There is a destructive "Delete" button and a "Cancel" button

**Confirm the deletion:**
```
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user is removed from the table.

**Expected result:**
- A success toast appears with text "User 'delete-me-e2e' deleted"
- The row for `delete-me-e2e` no longer exists in the DOM

---

### 2.6 Users panel renders (not blank)

**Precondition:** Logged in as `admin` (from Test 2.2).

**Commands:**
```shell
agent-browser navigate http://localhost:8800/admin
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The Users panel renders content (not a blank/white page).

**Expected result:**
- The admin panel URL is `http://localhost:8800/admin`
- The users table or user management section is visible
- The page is NOT blank or showing only a white background
- At least the "Create User" form section is rendered
- If users exist, the users table shows their rows

**Verify users table is in the DOM:**
```shell
agent-browser javascript "document.querySelector('[data-testid=\"users-table\"], table, [data-testid=\"create-user-btn\"]') !== null"
```

**Expected result:**
- Returns `true` (the users panel has rendered its content)

---

### 2.7 Change password works

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-rotate-user='testuser-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A dialog appears for entering a new password.

**Expected result:**
- A dialog is visible
- The dialog title reads "Change Password"
- The dialog body contains "Enter new password for 'testuser-e2e'"
- There is a password input field
- There is a hint "Minimum 16 characters"

**Enter a new password and confirm:**
```
agent-browser type "[data-testid='password-input']" "newpassword1234567890"
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The new password is displayed.

**Expected result:**
- The password display shows `newpassword1234567890`

Update `TEST_USER_PASSWORD` to this new value (`newpassword1234567890`).

**Click Done:**
```
agent-browser click "[data-testid='dismiss-password']"
agent-browser wait 2000
```

---

### 2.8 Deleted user session is invalidated

**Commands (create and login as a disposable user):**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "[data-testid='new-username']" "session-test-e2e"
agent-browser click "[data-testid='role-select']"
agent-browser wait 500
agent-browser click "[data-value='user']"
agent-browser wait 500
agent-browser click "[data-testid='create-user-btn']"
agent-browser wait 2000
agent-browser screenshot
```

**Capture the password:**
```
agent-browser javascript "document.querySelector('[data-testid=\"generated-password\"]')?.textContent"
```

Save the password as `SESSION_TEST_PASSWORD`.

**Click Done:**
```
agent-browser click "[data-testid='dismiss-password']"
agent-browser wait 2000
```

**Open a new browser context and login as session-test-e2e:**
```
agent-browser new-context
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "session-test-e2e"
agent-browser type "[name='password']" "<SESSION_TEST_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** The dashboard loads for session-test-e2e.

**Expected result:**
- The browser is redirected to `/` (the dashboard)
- The header shows the username "session-test-e2e"

**Switch back to admin context and delete the user:**
```
agent-browser switch-context 0
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-delete-user='session-test-e2e']"
agent-browser wait 1000
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user is deleted from the admin panel.

**Switch back to session-test-e2e's context and refresh:**
```
agent-browser switch-context 1
agent-browser navigate http://localhost:8800/
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** The deleted user's session is invalidated.

**Expected result:**
- The browser is redirected to `/login`
- The session is no longer valid; the dashboard does not load

**Clean up (close extra context):**
```
agent-browser close-context
```

---

### 2.9 Cannot create user with reserved username "admin" (case-insensitive)

**Precondition:** Logged in as `admin` on the admin panel.

**Attempt with lowercase "admin":**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "[data-testid='new-username']" "admin"
agent-browser click "[data-testid='role-select']"
agent-browser wait 500
agent-browser click "[data-value='user']"
agent-browser wait 500
agent-browser click "[data-testid='create-user-btn']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** An error message appears and no new user is created.

**Expected result:**
- An error message/toast appears indicating that the username "admin" is reserved
- No new user row for "admin" appears in the users table

**Repeat with "Admin" and "ADMIN" --- same expected result for each.**

---

### 2.10 Cannot delete own admin account

**Precondition:** Logged in as `admin` on the admin panel.

**Commands (attempt via API):**
```
agent-browser javascript "fetch('/api/admin/users/admin', {method:'DELETE', credentials:'same-origin'}).then(r => r.json().then(body => ({status: r.status, body: body})))"
agent-browser wait 2000
```

**Check:** The API rejects the self-deletion attempt.

**Expected result:**
- The response status is `400`
- The response body contains "Cannot delete your own account"

---

### 2.11 Change password dialog shows correct fields and displays new key

**Precondition:** Logged in as `admin` on the admin panel. At least one non-admin user exists (e.g., `testuser-e2e`).

**Commands (open change password for testuser-e2e):**
```shell
agent-browser navigate http://localhost:8800/admin
agent-browser wait 2000
agent-browser click "[data-rotate-user='testuser-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The change password dialog shows correct fields.

**Expected result:**
- A dialog/modal is visible with title "Change Password"
- There is a single password input field (NOT a "current password" field --- admin does not need the old password)
- There is a hint about minimum password length

**Enter a new password and confirm:**
```shell
agent-browser type "[data-testid='password-input']" "test-change-pw-e2e-1234"
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The new password/key is displayed after confirmation.

**Expected result:**
- The new password `test-change-pw-e2e-1234` is displayed in the success alert or password display area
- The user is NOT left with a blank screen or missing password
- The password display is clearly visible and copyable

**Dismiss and verify redirect:**
```shell
agent-browser click "[data-testid='dismiss-password']"
agent-browser wait 2000
agent-browser screenshot
```

**Expected result:**
- The admin panel reloads or the dialog closes cleanly
- The admin session remains valid (admin is still on the admin panel)

**Restore the original password for testuser-e2e:**
```shell
agent-browser click "[data-rotate-user='testuser-e2e']"
agent-browser wait 1000
agent-browser type "[data-testid='password-input']" "<TEST_USER_PASSWORD>"
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 2000
agent-browser click "[data-testid='dismiss-password']"
agent-browser wait 2000
```

---

## Test 3: User Role Permissions

### 3.1 User can login

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** The user is redirected to the dashboard.

**Expected result:**
- URL is `http://localhost:8800/`
- The header shows `testuser-e2e` as the username

---

### 3.2 User sees generate form

**Commands:**
```
agent-browser javascript "document.querySelector('[data-testid=\"generate-form\"]') !== null"
agent-browser screenshot
```

**Check:** The "Generate Documentation" form is visible for users.

**Expected result:**
- Returns `true`
- The form contains: Repository URL input, Provider select, Model input, Force checkbox, and Generate button
- Branch input is visible

---

### 3.3 User does NOT see Admin link

**Commands:**
```shell
agent-browser javascript "document.querySelector('[data-testid=\"admin-link\"], a[href=\"/admin\"]') === null"
```

**Check:** The Admin link is absent from the navigation.

**Expected result:**
- Returns `true` (the element does not exist in the DOM)

---

### 3.4 User cannot access /admin (403)

**Commands:**
```
agent-browser javascript "fetch('/api/admin/users', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The API returns 403 Forbidden for non-admin users.

**Expected result:**
- Returns `403`

---

### 3.5 User can generate docs

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** The generation request is accepted and a card appears.

**Expected result:**
- A toast notification appears with text "Generation started" or similar success message
- A new project card appears in the project list with status "GENERATING"
- The card shows a progress indicator

---

### 3.6 User sees own projects only

**Precondition:** The `testuser-e2e` user just triggered a generation in Test 3.5.

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('[data-testid=\"project-group\"]').length"
agent-browser screenshot
```

**Check:** The user only sees projects they own.

**Expected result:**
- The list contains only `for-testing-only` (or is empty if the project has not been created yet)
- No projects owned by other users are visible

---

## Test 4: Viewer Role Permissions

### 4.1 Viewer can login

**Commands:**
```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testviewer-e2e"
agent-browser type "[name='password']" "<TEST_VIEWER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** The viewer is redirected to the dashboard.

**Expected result:**
- URL is `http://localhost:8800/`
- The header shows `testviewer-e2e` as the username

---

### 4.2 Viewer does NOT see generate form

**Commands:**
```
agent-browser javascript "document.querySelector('[data-testid=\"generate-form\"]') === null"
```

**Check:** The generate form is not rendered for viewers.

**Expected result:**
- Returns `true` (the generate form does not exist in the DOM for viewer role)

---

### 4.3 Viewer does NOT see Admin link

**Commands:**
```
agent-browser javascript "document.querySelector('[data-testid=\"admin-link\"], a[href=\"/admin\"]') === null"
```

**Expected result:**
- Returns `true`

---

### 4.4 Viewer cannot access /admin (403)

**Commands:**
```
agent-browser javascript "fetch('/api/admin/users', {credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:**
- Returns `403`

---

### 4.5 Viewer can change password

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
agent-browser javascript "document.querySelector('[data-testid=\"change-password\"]') !== null"
```

**Expected result:**
- Returns `true` --- the change password option is available

**Cancel to avoid actually changing:**
```
agent-browser press "Escape"
```

---

### 4.6 Viewer sees only assigned projects

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('[data-testid=\"project-group\"]').length"
agent-browser screenshot
```

**Expected result:**
- The project count is `0`
- An empty state message is shown

---

### 4.7 Viewer blocked by API (not just UI)

**Precondition:** Logged in as `testviewer-e2e`.

**Generate endpoint (POST):**
```
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only'})}).then(r => r.status)"
```

**Expected result:** Returns `403`.

**Abort endpoint (POST):**
```
agent-browser javascript "fetch('/api/projects/some-project/main/gemini/gemini-2.5-flash/abort', {method:'POST', credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `403` or `404`.

**Delete endpoint (DELETE):**
```
agent-browser javascript "fetch('/api/projects/some-project/main/gemini/gemini-2.5-flash', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `403` or `404`.

---

## Test 5: Admin Role (DB user) Permissions

### 5.1 Admin user can login

**Commands:**
```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testadmin-e2e"
agent-browser type "[name='password']" "<TEST_ADMIN_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Expected result:**
- URL is `http://localhost:8800/`
- The header shows `testadmin-e2e` as the username

---

### 5.2 Admin user sees Admin link

**Commands:**
```
agent-browser javascript "document.querySelector('[data-testid=\"admin-link\"], a[href=\"/admin\"]') !== null"
```

**Expected result:**
- Returns `true`

---

### 5.3 Admin user can access /admin

**Commands:**
```shell
agent-browser navigate http://localhost:8800/admin
agent-browser wait 2000
agent-browser screenshot
```

**Expected result:**
- URL is `http://localhost:8800/admin`
- The user management interface is visible
- The users table shows the created test users

---

### 5.4 Admin user sees ALL projects

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('[data-testid=\"project-group\"]').length"
agent-browser screenshot
```

**Expected result:**
- If `testuser-e2e` generated a project in Test 3.5, the `for-testing-only` project is visible here
- Admin users see all projects regardless of owner
