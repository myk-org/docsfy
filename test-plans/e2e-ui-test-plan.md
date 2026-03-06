# docsfy E2E UI Test Plan

## Prerequisites

- Server running at `http://localhost:8800`
- ADMIN_KEY configured in `.dev/.env` (default: `12345678901234567890`)
- `agent-browser` available and operational
- Test repo: `https://github.com/myk-org/for-testing-only`
- AI provider for generation tests: `gemini` with model `gemini-2.5-flash`

## Variables Used Throughout

| Variable | Value |
|---|---|
| `SERVER` | `http://localhost:8800` |
| `ADMIN_KEY` | Read from `.dev/.env` at runtime (default `12345678901234567890`) |
| `ADMIN_USER` | `admin` |
| `TEST_REPO` | `https://github.com/myk-org/for-testing-only` |
| `AI_PROVIDER` | `gemini` |
| `AI_MODEL` | `gemini-2.5-flash` |
| `TEST_USER` | `testuser-e2e` |
| `TEST_ADMIN` | `testadmin-e2e` |
| `TEST_VIEWER` | `testviewer-e2e` |

Passwords for created users will be captured at creation time and stored in variables:
- `TEST_USER_PASSWORD`
- `TEST_ADMIN_PASSWORD`
- `TEST_VIEWER_PASSWORD`

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
- Page title is "docsfy - Login"
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
agent-browser javascript "document.documentElement.getAttribute('data-theme')"
agent-browser screenshot
```

**Check:** The `data-theme` attribute on the `<html>` element is `"dark"`.

**Expected result:**
- The return value from `getAttribute('data-theme')` is `"dark"`
- The page visually appears with a dark background (`#0f1117` body, `#161822` card area)
- Text is light-colored on the dark background

---

### 1.3 Theme toggle works

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser click "#theme-toggle"
agent-browser javascript "document.documentElement.getAttribute('data-theme')"
agent-browser screenshot
```

**Check:** After clicking the theme toggle, the theme changes from dark to light.

**Expected result:**
- The return value from `getAttribute('data-theme')` is `"light"`
- The page background changes to light colors (white/`#ffffff`)
- The sun icon is now hidden and the moon icon is visible

**Then toggle back:**
```
agent-browser click "#theme-toggle"
agent-browser javascript "document.documentElement.getAttribute('data-theme')"
```

**Expected result:**
- The return value is `"dark"` again

---

### 1.4 Invalid login shows error

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser type "#username" "wronguser"
agent-browser type "#api_key" "wrongpassword"
agent-browser click ".btn-login"
agent-browser screenshot
```

**Check:** An error message appears on the login page.

**Expected result:**
- The page reloads and remains on `/login`
- A red error box is visible with the text "Invalid username or password"
- The error box has class `error-msg`

---

### 1.5 Admin login succeeds

**Commands:**
```
agent-browser navigate http://localhost:8800/login
agent-browser type "#username" "admin"
agent-browser type "#api_key" "12345678901234567890"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** Login succeeds and redirects to the dashboard.

**Expected result:**
- The browser is redirected to `/` (the dashboard)
- The page title is "docsfy - Dashboard"
- The header shows the username "admin"
- The "Admin" link is visible in the header (because the admin role is active)
- The "Generate Documentation" form section is visible
- The "Logout" link is visible in the header
- The "Change Password" button is visible in the header

---

### 1.6 ADMIN_KEY user Change Password is denied

**Precondition:** Logged in as `admin` (ADMIN_KEY user, from Test 1.5).

**Commands:**
```
agent-browser click ".btn-change-password"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The change password modal appears.

**Expected result:**
- The modal overlay is visible
- The modal title reads "Change Password"

**Enter a new password and confirm:**
```
agent-browser type "#modal-input" "somenewpassword12345"
agent-browser click "#modal-ok"
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
agent-browser javascript "document.querySelector('.top-bar-admin-link') !== null"
agent-browser javascript "document.querySelector('.top-bar-admin-link').textContent.trim()"
agent-browser screenshot
```

**Check:** The Admin link exists in the header.

**Expected result:**
- The first query returns `true`
- The second query returns `"Admin"`
- The link points to `/admin`

---

### 2.2 Create user (user role)

**Commands:**
```
agent-browser click ".top-bar-admin-link"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** The admin panel loads with the "User Management" heading.

**Expected result:**
- URL is `http://localhost:8800/admin`
- Page title is "docsfy - Admin Panel"
- The heading "User Management" is visible
- The "Create User" card is visible with username input, role dropdown, and "Create User" button

**Now create the user:**
```
agent-browser type "#new-username" "testuser-e2e"
agent-browser select "#new-role" "user"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user is created and the password is displayed.

**Expected result:**
- A success alert appears with text containing "User 'testuser-e2e' created successfully"
- The `#new-key-display` section becomes visible (the yellow/amber bordered box)
- The displayed username shows `testuser-e2e`
- The displayed role shows `user`
- A password value is shown (capture this as `TEST_USER_PASSWORD`)
- The user appears in the users table with a `user` role badge

**Capture the password:**
```
agent-browser javascript "document.getElementById('new-key-value').textContent"
```

Store this value as `TEST_USER_PASSWORD`.

**Click Done to dismiss:**
```
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 2000
```

---

### 2.3 Create user (admin role)

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "#new-username" "testadmin-e2e"
agent-browser select "#new-role" "admin"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The admin user is created.

**Expected result:**
- Success alert with "User 'testadmin-e2e' created successfully"
- The `#new-key-display` section shows the password
- The displayed role shows `admin`
- The user appears in the table with an `admin` role badge (green)

**Capture the password:**
```
agent-browser javascript "document.getElementById('new-key-value').textContent"
```

Store this value as `TEST_ADMIN_PASSWORD`.

**Click Done:**
```
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 2000
```

---

### 2.4 Create user (viewer role)

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "#new-username" "testviewer-e2e"
agent-browser select "#new-role" "viewer"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The viewer user is created.

**Expected result:**
- Success alert with "User 'testviewer-e2e' created successfully"
- The `#new-key-display` section shows the password
- The displayed role shows `viewer`
- The user appears in the table with a `viewer` role badge (gray)

**Capture the password:**
```
agent-browser javascript "document.getElementById('new-key-value').textContent"
```

Store this value as `TEST_VIEWER_PASSWORD`.

**Click Done:**
```
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 2000
```

---

### 2.5 Delete user works

**First, create a disposable user to delete:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "#new-username" "delete-me-e2e"
agent-browser select "#new-role" "user"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user `delete-me-e2e` appears in the users table.

**Expected result:**
- A row with username `delete-me-e2e` exists in the table
- The row has a "Delete" button

**Now delete the user:**
```
agent-browser click "[data-delete-user='delete-me-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A custom modal dialog appears (not a browser `confirm` dialog).

**Expected result:**
- The modal overlay (`.modal-overlay`) is visible
- The modal title reads "Delete User"
- The modal body reads "Delete user 'delete-me-e2e'? This cannot be undone."
- There is a red "Delete" button and a "Cancel" button

**Confirm the deletion:**
```
agent-browser click "#modal-ok"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user is removed from the table.

**Expected result:**
- A success alert appears with text "User 'delete-me-e2e' deleted"
- The row `#user-row-delete-me-e2e` no longer exists in the DOM

**Verify:**
```
agent-browser javascript "document.getElementById('user-row-delete-me-e2e') === null"
```

**Expected result:** Returns `true`.

---

### 2.6 Change password works

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-rotate-user='testuser-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A modal prompt appears for entering a new password.

**Expected result:**
- The modal overlay is visible
- The modal title reads "Change Password"
- The modal body contains "Enter new password for 'testuser-e2e'"
- There is a password input field
- There is a hint "Minimum 16 characters"

**Enter a new password and confirm:**
```
agent-browser type "#modal-input" "newpassword1234567890"
agent-browser click "#modal-ok"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The new password is displayed in the key result section.

**Expected result:**
- The `#new-key-display` section becomes visible
- The username shows `testuser-e2e`
- The role shows `rotated`
- The password value shows `newpassword1234567890`

**Capture the updated password:**
```
agent-browser javascript "document.getElementById('new-key-value').textContent"
```

Update `TEST_USER_PASSWORD` to this new value (`newpassword1234567890`).

**Click Done:**
```
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 2000
```

---

### 2.7 Deleted user session is invalidated

**Commands (create and login as a disposable user):**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "#new-username" "session-test-e2e"
agent-browser select "#new-role" "user"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user `session-test-e2e` is created and the password is displayed.

**Expected result:**
- A success alert appears with text containing "User 'session-test-e2e' created successfully"
- The `#new-key-display` section becomes visible
- The displayed username shows `session-test-e2e`

**Capture the password:**
```
agent-browser javascript "document.getElementById('new-key-value').textContent"
```

Save the password as `SESSION_TEST_PASSWORD`.

**Click Done:**
```
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 2000
```

**Open a new browser context and login as session-test-e2e:**
```
agent-browser new-context
agent-browser navigate http://localhost:8800/login
agent-browser type "#username" "session-test-e2e"
agent-browser type "#api_key" "<SESSION_TEST_PASSWORD>"
agent-browser click ".btn-login"
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
agent-browser click "#modal-ok"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** The user is deleted from the admin panel.

**Expected result:**
- A success alert appears with text "User 'session-test-e2e' deleted"
- The row for `session-test-e2e` no longer exists in the table

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

### 2.8 Cannot create user with reserved username "admin" (case-insensitive)

**Precondition:** Logged in as `admin` on the admin panel.

**Attempt with lowercase "admin":**
```
agent-browser navigate http://localhost:8800/admin
agent-browser type "#new-username" "admin"
agent-browser select "#new-role" "user"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser screenshot
```

**Check:** An error message appears and no new user is created.

**Expected result:**
- An error message appears indicating that the username "admin" is reserved
- No new user row for "admin" appears in the users table
- The `#new-key-display` section does NOT become visible

**Attempt with mixed case "Admin":**
```
agent-browser navigate http://localhost:8800/admin
agent-browser clear "#new-username"
agent-browser type "#new-username" "Admin"
agent-browser select "#new-role" "user"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser screenshot
```

**Expected result:**
- An error message appears indicating that the username is reserved
- No new user row for "Admin" appears in the users table
- The `#new-key-display` section does NOT become visible

**Attempt with uppercase "ADMIN":**
```
agent-browser navigate http://localhost:8800/admin
agent-browser clear "#new-username"
agent-browser type "#new-username" "ADMIN"
agent-browser select "#new-role" "user"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser screenshot
```

**Expected result:**
- An error message appears indicating that the username is reserved
- No new user row for "ADMIN" appears in the users table
- The `#new-key-display` section does NOT become visible

---

### 2.9 Cannot delete own admin account

**Precondition:** Logged in as `admin` on the admin panel.

**Commands (attempt via API):**
```
agent-browser javascript "fetch('/api/admin/users/admin', {method:'DELETE', credentials:'same-origin'}).then(r => r.json())"
agent-browser wait 2000
```

**Check:** The API rejects the self-deletion attempt.

**Expected result:**
- The response status is `400`
- The response body contains "Cannot delete your own account"

**Verify admin still exists in the table:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser javascript "document.getElementById('user-row-admin') !== null"
agent-browser screenshot
```

**Expected result:**
- Returns `true`
- The admin row is still visible in the users table

---

## Test 3: User Role Permissions

### 3.1 User can login

**Commands:**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** The user is redirected to the dashboard.

**Expected result:**
- URL is `http://localhost:8800/`
- The header shows `testuser-e2e` as the username
- The page title is "docsfy - Dashboard"

---

### 3.2 User sees generate form

**Commands:**
```
agent-browser javascript "document.querySelector('.generate-section') !== null"
agent-browser javascript "document.querySelector('.generate-section h2').textContent.trim()"
agent-browser screenshot
```

**Check:** The "Generate Documentation" form is visible for users.

**Expected result:**
- The first query returns `true`
- The second query returns `"Generate Documentation"`
- The form contains: Repository URL input, Provider select, Model input, Force checkbox, and Generate button

---

### 3.3 User does NOT see Admin link

**Commands:**
```
agent-browser javascript "document.querySelector('.top-bar-admin-link')"
```

**Check:** The Admin link is absent from the header.

**Expected result:**
- Returns `null` (the element does not exist in the DOM)

---

### 3.4 User cannot access /admin (403)

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser screenshot
agent-browser javascript "document.body.innerText"
```

**Check:** The server returns a 403 Forbidden error.

**Expected result:**
- The page shows a JSON or text response containing "Admin access required"
- The HTTP status code is 403

---

### 3.5 User can generate docs

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-submit"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** The generation request is accepted and a card appears.

**Expected result:**
- A toast notification appears with text "Generation started" or similar success message
- A new project card appears in the project list with status "GENERATING"
- The card shows a progress bar and "Generating..." text
- A "View progress" link is visible on the card
- An "Abort" button is visible on the card

---

### 3.6 User sees own projects only

**Precondition:** The `testuser-e2e` user just triggered a generation in Test 3.5.

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser javascript "Array.from(document.querySelectorAll('.project-group')).map(g => g.getAttribute('data-repo'))"
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
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testviewer-e2e"
agent-browser type "#api_key" "<TEST_VIEWER_PASSWORD>"
agent-browser click ".btn-login"
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
agent-browser javascript "document.querySelector('.generate-section')"
```

**Check:** The generate form is not rendered for viewers.

**Expected result:**
- Returns `null` (the `.generate-section` element does not exist in the DOM)
- The template uses `{% if role != 'viewer' %}` to conditionally render the form

---

### 4.3 Viewer does NOT see Admin link

**Commands:**
```
agent-browser javascript "document.querySelector('.top-bar-admin-link')"
```

**Check:** The Admin link is absent from the header.

**Expected result:**
- Returns `null`

---

### 4.4 Viewer cannot access /admin (403)

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser screenshot
agent-browser javascript "document.body.innerText"
```

**Check:** The server returns a 403 Forbidden error.

**Expected result:**
- The response contains "Admin access required"

---

### 4.5 Viewer can change password

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelector('.top-bar-btn') !== null"
agent-browser javascript "document.querySelector('.top-bar-btn').textContent.trim()"
```

**Check:** The "Change Password" button is visible for viewers.

**Expected result:**
- The first query returns `true`
- The second query returns `"Change Password"`

**Click it:**
```
agent-browser click ".top-bar-btn"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The modal prompt appears.

**Expected result:**
- The modal overlay is visible
- The title reads "Change Password"
- A password input is shown

**Cancel the modal (do not actually change the password):**
```
agent-browser click "#modal-cancel"
```

---

### 4.6 Viewer sees only assigned projects

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('.project-group').length"
agent-browser screenshot
```

**Check:** The viewer sees no projects (none have been assigned yet).

**Expected result:**
- The project count is `0`
- The empty state is shown with text "No projects yet"

---

### 4.7 Viewer blocked by API (not just UI)

**Precondition:** Logged in as `testviewer-e2e`.

Verify that the backend enforces viewer restrictions, not just the UI. Run `fetch` calls in the browser console:

**Generate endpoint (POST):**
```
agent-browser eval "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only'})}).then(r => r.status)"
```

**Expected result:** Returns `403`.

**Abort endpoint (POST):**
```
agent-browser eval "fetch('/api/projects/some-project/claude/opus/abort', {method:'POST', credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `403` or `404`.

**Delete endpoint (DELETE):**
```
agent-browser eval "fetch('/api/projects/some-project/claude/opus', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `403` or `404`.

---

## Test 5: Admin Role (DB user) Permissions

### 5.1 Admin user can login

**Commands:**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testadmin-e2e"
agent-browser type "#api_key" "<TEST_ADMIN_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** The DB admin user is redirected to the dashboard.

**Expected result:**
- URL is `http://localhost:8800/`
- The header shows `testadmin-e2e` as the username

---

### 5.2 Admin user sees Admin link

**Commands:**
```
agent-browser javascript "document.querySelector('.top-bar-admin-link') !== null"
agent-browser javascript "document.querySelector('.top-bar-admin-link').textContent.trim()"
```

**Check:** The Admin link is visible for DB users with admin role.

**Expected result:**
- The first query returns `true`
- The second query returns `"Admin"`

---

### 5.3 Admin user can access /admin

**Commands:**
```
agent-browser click ".top-bar-admin-link"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** The admin panel loads without a 403 error.

**Expected result:**
- URL is `http://localhost:8800/admin`
- The "User Management" heading is visible
- The users table shows the created test users

---

### 5.4 Admin user sees ALL projects

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser javascript "Array.from(document.querySelectorAll('.project-group')).map(g => g.getAttribute('data-repo'))"
agent-browser screenshot
```

**Check:** The DB admin user can see all projects from all users.

**Expected result:**
- If `testuser-e2e` generated a project in Test 3.5, the `for-testing-only` project is visible here
- Admin users see all projects regardless of owner (the code calls `list_projects()` without owner filter for admins)

---

## Test 6: Doc Generation (via User)

**Precondition:** Log back in as `testuser-e2e`.

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

### 6.1 Fill generate form with gemini/gemini-2.5-flash

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser screenshot
```

**Check:** The form fields are correctly populated.

**Expected result:**
- Repository URL field contains `https://github.com/myk-org/for-testing-only`
- Provider dropdown shows `gemini`
- Model field shows `gemini-2.5-flash`
- Force checkbox is unchecked

---

### 6.2 Generation starts (card appears)

**Commands:**
```
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
```
agent-browser javascript "document.querySelector('.status-link') !== null"
agent-browser javascript "document.querySelector('.status-link').getAttribute('href')"
```

Capture the returned href (e.g., `/status/for-testing-only/gemini/gemini-2.5-flash`), then open it:
```
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser screenshot
```

**Check:** The status page loads for the project.

**Expected result:**
- The link href matches `/status/for-testing-only/gemini/gemini-2.5-flash`
- The status page shows the project name `for-testing-only`
- The provider/model shows `gemini/gemini-2.5-flash`

---

### 6.4 Status page shows real-time progress

**Commands:**
```
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
```
agent-browser wait 120000
agent-browser screenshot
```

**Note:** Adjust the wait time based on generation speed. The test repo is small so generation should complete in under 2 minutes. Poll if needed:

```
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
```
agent-browser javascript "document.getElementById('btn-view-docs').getAttribute('href')"
```

Capture the returned href, then open it:
```
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/
agent-browser screenshot
```

**Check:** The generated documentation page loads.

**Expected result:**
- The URL matches `/docs/for-testing-only/gemini/gemini-2.5-flash/` or similar
- The page renders HTML documentation content
- A sidebar with navigation links is visible

---

### 6.7 Download link works

**Commands:**
```
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser javascript "document.getElementById('btn-download').getAttribute('href')"
```

**Check:** The download link points to the correct endpoint.

**Expected result:**
- The href is `/api/projects/for-testing-only/gemini/gemini-2.5-flash/download`
- Clicking the link triggers a `.tar.gz` file download with filename `for-testing-only-gemini-gemini-2.5-flash-docs.tar.gz`

---

## Test 7: Dashboard Features

**Precondition:** Log in as `admin` to have maximum visibility.

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "12345678901234567890"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

### 7.1 Search filter works

**Commands:**
```
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
```
agent-browser clear "#search-filter"
agent-browser wait 500
```

**Expected result:**
- All project groups are visible again

**Search for a non-existent project:**
```
agent-browser type "#search-filter" "zzz-does-not-exist"
agent-browser wait 500
agent-browser javascript "document.querySelectorAll('.project-group:not(.search-hidden)').length"
```

**Expected result:**
- Returns `0` -- no matching groups are visible

```
agent-browser clear "#search-filter"
```

---

### 7.2 Pagination works (if enough projects)

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('.project-group').length"
```

**Check:** If there are more than 10 projects, pagination is active.

**If fewer than 10 projects, verify pagination controls exist but do not paginate:**
```
agent-browser javascript "document.getElementById('per-page') !== null"
agent-browser javascript "document.getElementById('prev-page') !== null"
agent-browser javascript "document.getElementById('next-page') !== null"
agent-browser javascript "document.getElementById('page-info') !== null"
```

**Expected result:**
- All pagination elements exist
- `prev-page` button is disabled (first page)
- `next-page` button is disabled (only one page of results)
- Page info shows "Page 1 of 1"

**Change per-page setting:**
```
agent-browser select "#per-page" "50"
agent-browser javascript "document.getElementById('page-info').textContent"
```

**Expected result:**
- The page info updates to "Page 1 of 1" (since total projects < 50)

---

### 7.3 Regenerate without force (should skip if unchanged)

**Precondition:** The `for-testing-only` project was generated in Test 6.

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

Find the regenerate controls for the `for-testing-only` project:
```
agent-browser javascript "document.querySelector('[data-regenerate-variant=\"for-testing-only\"]') !== null"
```

**Expected result:** Returns `true`.

**Click Regenerate (without Force checkbox):**
```
agent-browser click "[data-regenerate-variant='for-testing-only']"
agent-browser wait 5000
agent-browser screenshot
```

**Check:** The generation starts, but quickly resolves as "up to date" since the commit hasn't changed and Force is unchecked.

**Expected result:**
- A toast notification appears indicating generation started
- After a few seconds, the project status returns to `READY`
- The status page (if visited) shows "Documentation is already up to date -- no changes since last generation."

---

### 7.4 Abort generation

**Start a new generation first (with Force checked to ensure it actually runs):**
```
agent-browser navigate http://localhost:8800/
```

Find the Force checkbox for the for-testing-only variant:
```
agent-browser javascript "document.querySelector('[data-regen-force=\"for-testing-only\"]').checked = true"
agent-browser click "[data-regenerate-variant='for-testing-only']"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** The generation starts with status `GENERATING`.

**Now abort:**
```
agent-browser click "[data-abort-variant]"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** A confirmation modal appears.

**Expected result:**
- The modal title reads "Abort Generation"
- The modal body contains "Abort generation for for-testing-only"
- There is a red "Delete" button (used as confirm for dangerous actions) and a "Cancel" button

**Confirm the abort:**
```
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
```
agent-browser navigate http://localhost:8800/
agent-browser click "[data-delete-variant]"
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
```
agent-browser click "#modal-cancel"
agent-browser wait 500
agent-browser javascript "document.querySelector('.modal-overlay').style.display"
```

**Expected result:**
- The modal is dismissed
- The `display` style is `"none"`
- The project card is still present

**Now actually delete:**
```
agent-browser click "[data-delete-variant]"
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
```
agent-browser navigate http://localhost:8800/
agent-browser click "#gen-model"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The model dropdown opens and shows model options.

**Expected result:**
- The `.model-dropdown` element has the class `active`
- Model options are visible as `.model-option` elements
- Each option shows a model name and provider tag

**Verify options exist:**
```
agent-browser javascript "document.querySelectorAll('#model-dropdown .model-option').length > 0"
```

**Expected result:** Returns `true`.

---

### 7.7 Provider switch updates model suggestions

**Commands:**
```
agent-browser select "#gen-provider" "gemini"
agent-browser click "#gen-model"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown filters to show only Gemini models.

**Expected result:**
- Only model options with `data-provider="gemini"` are visible
- Options for other providers are hidden (`display: none`)

**Verify:**
```
agent-browser javascript "Array.from(document.querySelectorAll('#model-dropdown .model-option')).filter(o => o.style.display !== 'none').every(o => o.getAttribute('data-provider') === 'gemini')"
```

**Expected result:** Returns `true`.

**Switch to claude:**
```
agent-browser select "#gen-provider" "claude"
agent-browser click "#gen-model"
agent-browser wait 500
agent-browser javascript "Array.from(document.querySelectorAll('#model-dropdown .model-option')).filter(o => o.style.display !== 'none').every(o => o.getAttribute('data-provider') === 'claude')"
```

**Expected result:** Returns `true`.

---

### 7.8 Form state persists across refresh

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-force"
```

**Now reload the page:**
```
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser javascript "document.getElementById('gen-repo-url').value"
agent-browser javascript "document.getElementById('gen-provider').value"
agent-browser javascript "document.getElementById('gen-model').value"
agent-browser javascript "document.getElementById('gen-force').checked"
```

**Check:** The form state is restored from sessionStorage.

**Expected result:**
- Repository URL returns `"https://github.com/myk-org/for-testing-only"`
- Provider returns `"gemini"`
- Model returns `"gemini-2.5-flash"`
- Force checkbox returns `true`

---

### 7.9 Self-service password rotation full flow

**Precondition:** Logged in as `testuser-e2e`.

**Commands:**
```
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
```
agent-browser click "#modal-ok"
agent-browser wait 2000
```
The page should redirect to /login after the modal is dismissed.
```
agent-browser wait --url "**/login"
```

**Try logging in with the OLD password:**
```
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
```
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
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-submit"
```

Wait for generation to complete (poll status every 10s until ready).

### 8.1 Docs page loads with sidebar

**Commands:**
```
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/
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
agent-browser javascript "document.querySelector('.toc, .on-this-page, [class*=\"toc\"]') !== null"
agent-browser screenshot
```

**Check:** A table of contents or "on this page" section exists.

**Expected result:**
- Some form of table of contents is rendered (implementation may vary based on the generated docs template)
- If present, it contains anchor links to sections on the current page

---

### 8.4 Code copy button works

**Commands:**
```
agent-browser javascript "document.querySelector('.copy-btn, [data-copy], button[class*=\"copy\"]') !== null"
```

**Check:** Code blocks have copy buttons.

**Expected result:**
- If code blocks exist in the generated docs, they include a copy button
- The copy functionality is wired up via JavaScript

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
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/llms.txt
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
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/llms-full.txt
agent-browser javascript "document.body.innerText.length > 0"
agent-browser screenshot
```

**Check:** The `llms-full.txt` file is accessible and contains content.

**Expected result:**
- The page loads without a 404 error
- The content is non-empty text (full documentation in LLM-friendly format)
- This file should be larger than `llms.txt`

---

### 8.8 .md files accessible

**Commands:**
```
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/index.md
agent-browser javascript "document.body.innerText.length > 0"
```

**Check:** Markdown source files are accessible.

**Expected result:**
- If `.md` files are generated alongside the HTML, they should be accessible
- If not generated, a 404 is acceptable (note this as a known limitation)

---

## Test 9: Status Page

**Precondition:** Start a new generation to observe the status page in action. Log in as `testuser-e2e`.

```
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-force"
agent-browser click "#gen-submit"
agent-browser wait 3000
```

### 9.1 Activity log shows progress

**Commands:**
```
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
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

**Precondition:** Generation is still running from the setup above.

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
agent-browser type "#api_key" "12345678901234567890"
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
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-force"
agent-browser click "#gen-submit"
agent-browser wait 3000
```

**Commands:**
```
agent-browser click "[data-abort-variant]"
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
agent-browser click "[data-abort-variant]"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 3000
```

---

### 10.4 Escape closes modal

**Commands:**
```
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-delete-user='testuser-e2e']"
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

---

## Test 11: Cross-User Isolation

### 11.1 User A generates docs

**Precondition:** Ensure `testuser-e2e` has a completed project. If the project was deleted or aborted in earlier tests, regenerate it.

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
```

Check if the project exists and is ready:
```
agent-browser javascript "document.querySelectorAll('.variant-card[data-status=\"ready\"]').length"
```

If 0, regenerate:
```
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser select "#gen-provider" "gemini"
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-submit"
```

Wait for completion (poll until ready, max 2 minutes).

**Check:** `testuser-e2e` has at least one project in `ready` state.

---

### 11.2 User B cannot see User A's docs

**Commands:**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testadmin-e2e"
agent-browser type "#api_key" "<TEST_ADMIN_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

Wait -- `testadmin-e2e` has admin role, so they see all projects. Use a non-admin user instead. Create a temporary user for this test:

```
agent-browser navigate http://localhost:8800/admin
agent-browser type "#new-username" "userb-e2e"
agent-browser select "#new-role" "user"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser javascript "document.getElementById('new-key-value').textContent"
```

Capture as `USERB_PASSWORD`.

```
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 1000
```

Log in as `userb-e2e`:
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "userb-e2e"
agent-browser type "#api_key" "<USERB_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('.project-group').length"
agent-browser screenshot
```

**Check:** User B sees zero projects (they have no projects and no access grants).

**Expected result:**
- The project count is `0`
- The empty state is shown ("No projects yet")
- User B cannot see `testuser-e2e`'s `for-testing-only` project

---

### 11.3 Admin can see both users' docs

**Commands:**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "12345678901234567890"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "Array.from(document.querySelectorAll('.project-group')).map(g => g.getAttribute('data-repo'))"
agent-browser screenshot
```

**Check:** The admin sees all projects.

**Expected result:**
- The list includes `for-testing-only` (owned by `testuser-e2e`)
- The admin has full visibility across all users

---

### 11.4 Admin assigns User A's project to Viewer

**Commands (via API since admin panel access controls are API-based):**
```
agent-browser javascript "fetch('/api/admin/projects/for-testing-only/access', { method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin', body: JSON.stringify({username: 'testviewer-e2e', owner: 'testuser-e2e'}) }).then(r => r.json()).then(d => JSON.stringify(d))"
agent-browser wait 2000
```

**Check:** The access grant succeeds.

**Expected result:**
- The response JSON contains `{"granted": "for-testing-only", "username": "testviewer-e2e", "owner": "testuser-e2e"}`

---

### 11.5 Viewer can now see assigned project

**Commands:**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testviewer-e2e"
agent-browser type "#api_key" "<TEST_VIEWER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "Array.from(document.querySelectorAll('.project-group')).map(g => g.getAttribute('data-repo'))"
agent-browser screenshot
```

**Check:** The viewer now sees the assigned project.

**Expected result:**
- The project list includes `for-testing-only`
- The viewer can see the project card with `READY` status
- The viewer can see the "View Docs" and "Download" buttons
- The viewer does NOT see "Delete" or "Regenerate" controls (because `role == 'viewer'`)

**Verify no write controls for viewer:**
```
agent-browser javascript "document.querySelector('[data-delete-variant]')"
agent-browser javascript "document.querySelector('[data-regenerate-variant]')"
agent-browser javascript "document.querySelector('[data-abort-variant]')"
```

**Expected result:** All three return `null`.

---

### 11.6 Admin lists access for a project

**Precondition:** Logged in as `admin`.

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "12345678901234567890"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Commands:**
```
agent-browser eval "fetch('/api/admin/projects/for-testing-only/access?owner=testuser-e2e', {credentials:'same-origin'}).then(r => r.json())"
```

**Check:** The access list includes the previously granted viewer.

**Expected result:**
- Returns a JSON object with a users list
- The list includes `testviewer-e2e` (granted in Test 11.4)

---

### 11.7 Admin revokes access

**Commands:**
```
agent-browser eval "fetch('/api/admin/projects/for-testing-only/access/testviewer-e2e?owner=testuser-e2e', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The revocation succeeds.

**Expected result:** Returns `200`.

---

### 11.8 Viewer can no longer see revoked project

**Commands:**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testviewer-e2e"
agent-browser type "#api_key" "<TEST_VIEWER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "Array.from(document.querySelectorAll('.project-group')).map(g => g.getAttribute('data-repo'))"
agent-browser screenshot
```

**Check:** The revoked project no longer appears on the viewer's dashboard.

**Expected result:**
- The `for-testing-only` project is NOT in the list
- The viewer sees the empty state ("No projects yet") or only other assigned projects

---

### 11.9 Two users generate same repo with same provider/model

**Precondition:** Test 11.8 is complete. `testviewer-e2e` has been revoked access.

**Commands (User A generates):**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
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

**Commands (User B generates the same config):**
```
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

**Commands (Verify User A sees only their copy):**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "Array.from(document.querySelectorAll('.project-group')).length"
agent-browser screenshot
```

**Commands (Verify User B sees only their copy):**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "userb-e2e"
agent-browser type "#api_key" "<USERB_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "Array.from(document.querySelectorAll('.project-group')).length"
agent-browser screenshot
```

**Commands (Verify Admin sees both):**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "12345678901234567890"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "Array.from(document.querySelectorAll('.project-group[data-owner=\"testuser-e2e\"]')).length"
agent-browser javascript "Array.from(document.querySelectorAll('.project-group[data-owner=\"userb-e2e\"]')).length"
agent-browser screenshot
```

**Check:** Both users have independent copies of the same repo/provider/model combination.

**Expected result:**
- `testuser-e2e` sees exactly 1 project group for `for-testing-only`
- `userb-e2e` sees exactly 1 project group for `for-testing-only`
- Admin sees 2 project groups (one owned by `testuser-e2e`, one owned by `userb-e2e`)
- The variants are isolated by owner

---

### 11.10 After revoke, viewer cannot access via direct URL

**Precondition:** Test 11.7 is complete. Access has been revoked from `testviewer-e2e`.

**Commands (Login as testviewer-e2e):**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testviewer-e2e"
agent-browser type "#api_key" "<TEST_VIEWER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Try accessing docs directly:**
```
agent-browser eval "fetch('/docs/for-testing-only/gemini/gemini-2.5-flash/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

**Try accessing status page directly:**
```
agent-browser eval "fetch('/status/for-testing-only/gemini/gemini-2.5-flash', {credentials:'same-origin'}).then(r => r.status)"
```

**Try accessing download API directly:**
```
agent-browser eval "fetch('/api/projects/for-testing-only/gemini/gemini-2.5-flash/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** All direct URL accesses return 404, not just hidden from the dashboard.

**Expected result:**
- Docs endpoint returns `404`
- Status page endpoint returns `404`
- Download API endpoint returns `404`
- Revocation is enforced at the route level, not just UI level

---

## Test 13: Direct URL Authorization

Test that non-owners cannot access resources by URL even if they know the path.

### 13.1 Non-owner cannot access status page

**Precondition:** Logged in as `userb-e2e` (created in Test 11.2, has no access grants).

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "userb-e2e"
agent-browser type "#api_key" "<USERB_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Commands:**
```
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser screenshot
agent-browser javascript "document.body.innerText"
```

**Check:** The server returns a 404 (not 403, to avoid leaking information about the resource).

**Expected result:**
- The page shows a 404 Not Found response
- No project details are revealed

---

### 13.2 Non-owner cannot access docs

**Commands:**
```
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/index.html
agent-browser screenshot
agent-browser javascript "document.body.innerText"
```

**Check:** The server returns a 404.

**Expected result:**
- The page shows a 404 Not Found response
- No documentation content is revealed

---

### 13.3 Non-owner cannot access variant details

**Commands:**
```
agent-browser eval "fetch('/api/projects/for-testing-only/gemini/gemini-2.5-flash', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The API returns 404.

**Expected result:** Returns `404`.

---

### 13.4 Non-owner cannot download

**Commands:**
```
agent-browser eval "fetch('/api/projects/for-testing-only/gemini/gemini-2.5-flash/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The API returns 404.

**Expected result:** Returns `404`.

---

### 13.5 Non-owner cannot access via owner-agnostic download route

**Precondition:** Logged in as `userb-e2e` (who has NOT been granted access yet).

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "userb-e2e"
agent-browser type "#api_key" "<USERB_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Commands:**
```
agent-browser eval "fetch('/api/projects/for-testing-only/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The owner-agnostic download route returns 404 for non-owners.

**Expected result:** Returns `404`.

---

### 13.6 Non-owner cannot access via owner-agnostic docs route

**Commands:**
```
agent-browser eval "fetch('/docs/for-testing-only/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The owner-agnostic docs route returns 404 for non-owners.

**Expected result:** Returns `404`.

---

### 13.7 Granted user CAN access

**Precondition:** Admin grants `userb-e2e` access to `testuser-e2e`'s project.

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "12345678901234567890"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Grant access:**
```
agent-browser eval "fetch('/api/admin/projects/for-testing-only/access', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({username:'userb-e2e', owner:'testuser-e2e'})}).then(r => r.status)"
```

**Expected result:** Returns `200`.

**Now log in as `userb-e2e` and access the docs:**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "userb-e2e"
agent-browser type "#api_key" "<USERB_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/
agent-browser screenshot
```

**Check:** The docs page loads successfully for the granted user.

**Expected result:**
- The page returns 200
- Documentation content is visible
- A sidebar with navigation is present

---

## Test 12: Logout

### 12.1 Logout redirects to login

**Precondition:** Logged in as any user.

**Commands:**
```
agent-browser click ".top-bar-logout"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** Logout redirects to the login page.

**Expected result:**
- The URL is `http://localhost:8800/login`
- The login form is visible
- The "Enter your credentials to continue" subtitle is shown

---

### 12.2 After logout, /dashboard redirects to login

**Commands:**
```
agent-browser navigate http://localhost:8800/
agent-browser wait-for-navigation
agent-browser javascript "window.location.href"
agent-browser screenshot
```

**Check:** Accessing the dashboard without authentication redirects to login.

**Expected result:**
- The URL has been redirected to `http://localhost:8800/login`
- The login form is displayed
- No dashboard content is visible

---

## Cleanup

Delete all test users created during this test suite. Log in as admin first.

```
agent-browser navigate http://localhost:8800/login
agent-browser type "#username" "admin"
agent-browser type "#api_key" "12345678901234567890"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/admin
```

**Delete testuser-e2e:**
```
agent-browser click "[data-delete-user='testuser-e2e']"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 2000
```

**Delete testadmin-e2e:**
```
agent-browser click "[data-delete-user='testadmin-e2e']"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 2000
```

**Delete testviewer-e2e:**
```
agent-browser click "[data-delete-user='testviewer-e2e']"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 2000
```

**Delete userb-e2e (if created in Test 11.2):**
```
agent-browser click "[data-delete-user='userb-e2e']"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 2000
```

**Verify all test users are deleted:**
```
agent-browser javascript "['testuser-e2e', 'testadmin-e2e', 'testviewer-e2e', 'userb-e2e'].filter(u => document.getElementById('user-row-' + u) !== null)"
agent-browser screenshot
```

**Expected result:**
- Returns an empty array `[]`
- No test user rows remain in the users table

**Close browser:**
```
agent-browser close
```

---

## Summary

| Test Section | Count | Description |
|---|---|---|
| Test 1: Login Page | 6 | Login page load, theme, invalid/valid login, ADMIN_KEY password denial |
| Test 2: Admin Panel | 9 | Admin link, CRUD users, change password, session invalidation, reserved username, self-delete guard |
| Test 3: User Role | 6 | User login, form visibility, permissions, generation |
| Test 4: Viewer Role | 7 | Viewer login, restricted UI, password change, API enforcement |
| Test 5: Admin DB User | 4 | DB admin login, access, project visibility |
| Test 6: Doc Generation | 7 | Full generation lifecycle |
| Test 7: Dashboard Features | 9 | Search, pagination, regen, abort, delete, combobox, form state, password rotation |
| Test 8: Generated Docs | 8 | Docs quality, theme, TOC, copy, footer, llms.txt |
| Test 9: Status Page | 3 | Activity log, abort, regenerate controls |
| Test 10: Custom Modals | 4 | Themed modals for delete, password, abort, escape key |
| Test 11: Cross-User Isolation | 10 | User isolation, admin visibility, access grants, revoke, collision test, direct URL after revoke |
| Test 12: Logout | 2 | Logout redirect, session invalidation |
| Test 13: Direct URL Authorization | 7 | Non-owner URL access blocked, granted user access, owner-agnostic routes |
| **Total** | **83** | |
