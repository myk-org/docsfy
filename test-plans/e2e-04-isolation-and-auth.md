# E2E UI Tests: Cross-User Isolation, Logout, and Direct URL Authorization

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

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

**Step 1: Ensure `userb-e2e` exists and capture a working password.**

Log in as `admin`:
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/admin
```

Check whether `userb-e2e` already exists:
```
agent-browser javascript "document.getElementById('user-row-userb-e2e') !== null"
```

If the previous command returned `false`, create `userb-e2e` and capture the generated password:
```
agent-browser clear "#new-username"
agent-browser type "#new-username" "userb-e2e"
agent-browser select "#new-role" "user"
agent-browser click "#create-user-form button[type='submit']"
agent-browser wait 2000
agent-browser javascript "document.getElementById('new-key-value').textContent.trim()"
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 1000
```
Store the captured value as `USERB_PASSWORD`.

If the previous command returned `true`, rotate `userb-e2e`'s password to a deterministic value and store that value as `USERB_PASSWORD`:
```
agent-browser click "[data-rotate-user='userb-e2e']"
agent-browser wait 1000
agent-browser type "#modal-input" "userb-password-12345678"
agent-browser click "#modal-ok"
agent-browser wait 2000
agent-browser javascript "document.getElementById('new-key-value').textContent.trim()"
agent-browser click "#new-key-display .btn-primary"
agent-browser wait 1000
```
Store the returned value as `USERB_PASSWORD`.

**Step 2: Log in as `userb-e2e`.**
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

**Check:** User B sees zero projects because they have no projects and no access grants yet.

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
agent-browser type "#api_key" "<ADMIN_KEY>"
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
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Commands:**
```
agent-browser javascript "fetch('/api/admin/projects/for-testing-only/access?owner=testuser-e2e', {credentials:'same-origin'}).then(r => r.json())"
```

**Check:** The access list includes the previously granted viewer.

**Expected result:**
- Returns a JSON object with a users list
- The list includes `testviewer-e2e` (granted in Test 11.4)

---

### 11.7 Admin revokes access

**Commands:**
```
agent-browser javascript "fetch('/api/admin/projects/for-testing-only/access/testviewer-e2e?owner=testuser-e2e', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
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
agent-browser type "#api_key" "<ADMIN_KEY>"
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
agent-browser javascript "fetch('/docs/for-testing-only/gemini/gemini-2.5-flash/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

**Try accessing status page directly:**
```
agent-browser javascript "fetch('/status/for-testing-only/gemini/gemini-2.5-flash', {credentials:'same-origin'}).then(r => r.status)"
```

**Try accessing download API directly:**
```
agent-browser javascript "fetch('/api/projects/for-testing-only/gemini/gemini-2.5-flash/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** All direct URL accesses return 404, not just hidden from the dashboard.

**Expected result:**
- Docs endpoint returns `404`
- Status page endpoint returns `404`
- Download API endpoint returns `404`
- Revocation is enforced at the route level, not just UI level

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

## Test 13: Direct URL Authorization

Test that a user with no own `for-testing-only` variant and no access grant cannot access resources by URL even if they know the path. This section uses `testviewer-e2e` because `userb-e2e` owns their own `for-testing-only` variant after Test 11.9.

### 13.1 Non-owner cannot access status page

**Precondition:** Logged in as `testviewer-e2e` (access was revoked in Test 11.7 and they do not own a `for-testing-only` variant).

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testviewer-e2e"
agent-browser type "#api_key" "<TEST_VIEWER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Commands:**
```
agent-browser javascript "fetch('/status/for-testing-only/gemini/gemini-2.5-flash', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The server returns a 404 (not 403, to avoid leaking information about the resource).

**Expected result:** Returns `404`.

---

### 13.2 Non-owner cannot access docs

**Commands:**
```
agent-browser javascript "fetch('/docs/for-testing-only/gemini/gemini-2.5-flash/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The server returns a 404.

**Expected result:** Returns `404`.

---

### 13.3 Non-owner cannot access variant details

**Commands:**
```
agent-browser javascript "fetch('/api/projects/for-testing-only/gemini/gemini-2.5-flash', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The API returns 404.

**Expected result:** Returns `404`.

---

### 13.4 Non-owner cannot download

**Commands:**
```
agent-browser javascript "fetch('/api/projects/for-testing-only/gemini/gemini-2.5-flash/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The API returns 404.

**Expected result:** Returns `404`.

---

### 13.5 Non-owner cannot access via owner-agnostic download route

**Precondition:** Stay logged in as `testviewer-e2e` (still no access grant and no own `for-testing-only` variant).

**Commands:**
```
agent-browser javascript "fetch('/api/projects/for-testing-only/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The owner-agnostic download route returns 404 for non-owners.

**Expected result:** Returns `404`.

---

### 13.6 Non-owner cannot access via owner-agnostic docs route

**Commands:**
```
agent-browser javascript "fetch('/docs/for-testing-only/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

**Check:** The owner-agnostic docs route returns 404 for non-owners.

**Expected result:** Returns `404`.

---

### 13.7 Granted user CAN access

**Precondition:** Admin grants `testviewer-e2e` access to `testuser-e2e`'s project.

```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Grant access:**
```
agent-browser javascript "fetch('/api/admin/projects/for-testing-only/access', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({username:'testviewer-e2e', owner:'testuser-e2e'})}).then(r => r.status)"
```

**Expected result:** Returns `200`.

**Now log in as `testviewer-e2e` and access the docs:**
```
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testviewer-e2e"
agent-browser type "#api_key" "<TEST_VIEWER_PASSWORD>"
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
