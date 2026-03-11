# E2E UI Tests: Authentication and Roles

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

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
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** Login succeeds and redirects to the dashboard.

**Expected result:**
- The browser is redirected to `/` (the dashboard)
- The page title is "docsfy - Dashboard"
- The header shows the username "admin"
- The "Admin Panel" link is visible in the header (because the admin role is active)
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
agent-browser eval 'document.querySelector(".user-menu-item[href=\"/admin\"]") !== null'
agent-browser eval 'document.querySelector(".user-menu-item[href=\"/admin\"]").textContent.trim()'
agent-browser screenshot
```

**Check:** The Admin link exists in the header.

**Verify the href:**
```shell
agent-browser eval 'document.querySelector(".user-menu-item[href=\"/admin\"]").getAttribute("href")'
```

**Expected result:**
- The first query returns `true`
- The second query returns `"Admin Panel"`
- The link href is "/admin"

---

### 2.2 Create user (user role)

**Commands:**
```shell
agent-browser click ".user-menu-item[href='/admin']"
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
agent-browser wait 500
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
agent-browser wait 500
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
agent-browser wait 500
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
agent-browser wait 500
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
agent-browser wait 500
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
agent-browser wait 500
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
```shell
agent-browser navigate http://localhost:8800/admin
agent-browser clear "#new-username"
agent-browser type "#new-username" "Admin"
agent-browser select "#new-role" "user"
agent-browser wait 500
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
agent-browser wait 500
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
agent-browser javascript "fetch('/api/admin/users/admin', {method:'DELETE', credentials:'same-origin'}).then(r => r.json().then(body => ({status: r.status, body: body})))"
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

**Verify branch input is visible:**
```shell
agent-browser javascript "document.getElementById('gen-branch') !== null"
```

**Expected result:** `true` --- branch input is visible.

---

### 3.3 User does NOT see Admin link

**Commands:**
```shell
agent-browser eval 'document.querySelector(".user-menu-item[href=\"/admin\"]")'
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
agent-browser wait 500
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
agent-browser eval 'document.querySelector(".user-menu-item[href=\"/admin\"]")'
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
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only'})}).then(r => r.status)"
```

**Expected result:** Returns `403`.

**Abort endpoint (POST):**
```
agent-browser javascript "fetch('/api/projects/some-project/gemini/gemini-2.5-flash/abort', {method:'POST', credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `403` or `404`.

**Delete endpoint (DELETE):**
```
agent-browser javascript "fetch('/api/projects/some-project/gemini/gemini-2.5-flash', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
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
agent-browser eval 'document.querySelector(".user-menu-item[href=\"/admin\"]") !== null'
agent-browser eval 'document.querySelector(".user-menu-item[href=\"/admin\"]").textContent.trim()'
```

**Check:** The Admin link is visible for DB users with admin role.

**Expected result:**
- The first query returns `true`
- The second query returns `"Admin Panel"`

---

### 5.3 Admin user can access /admin

**Commands:**
```shell
agent-browser click ".user-menu-item[href='/admin']"
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
