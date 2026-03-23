# E2E UI Tests: Cross-User Isolation, Logout, and Direct URL Authorization

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

> **UI Framework Note:** The app UI is a React SPA. Logout uses `POST /api/auth/logout`. Login uses `POST /api/auth/login` (JSON body). WebSocket notifications may alert users of access changes in real-time.

---

## Test 11: Cross-User Isolation

### 11.1 User A generates docs

**Precondition:** Ensure `testuser-e2e` has a completed project. If the project was deleted or aborted in earlier tests, regenerate it.

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
```

Check if the project exists and is ready via API:

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.5-flash', {credentials:'same-origin'}).then(r => r.status)"
```

If not `200`, regenerate via the generate form and wait for completion.

**Check:** `testuser-e2e` has at least one project in `ready` state.

---

### 11.2 User B cannot see User A's docs

**Step 1: Ensure `userb-e2e` exists.**

Log in as `admin`, navigate to admin panel, create `userb-e2e` if needed, capture password as `USERB_PASSWORD`.

**Step 2: Log in as `userb-e2e`.**

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "userb-e2e"
agent-browser type "[name='password']" "<USERB_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('[data-testid=\"project-group\"]').length"
agent-browser screenshot
```

**Check:** User B sees zero projects because they have no projects and no access grants yet.

**Expected result:**
- The project count is `0`
- An empty state is shown
- User B cannot see `testuser-e2e`'s `for-testing-only` project

---

### 11.3 Admin can see both users' docs

**Commands:**

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelectorAll('[data-testid=\"project-group\"]').length"
agent-browser screenshot
```

**Expected result:**
- The admin sees all projects including `for-testing-only` (owned by `testuser-e2e`)

---

### 11.4 Admin assigns User A's project to Viewer

**Commands (via API):**

```
agent-browser javascript "fetch('/api/admin/projects/for-testing-only/access', { method: 'POST', headers: {'Content-Type': 'application/json'}, credentials: 'same-origin', body: JSON.stringify({username: 'testviewer-e2e', owner: 'testuser-e2e'}) }).then(r => r.json()).then(d => JSON.stringify(d))"
agent-browser wait 2000
```

**Expected result:**
- The response JSON contains `{"granted": "for-testing-only", "username": "testviewer-e2e", "owner": "testuser-e2e"}`

---

### 11.5 Viewer can now see assigned project

**Commands:**

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testviewer-e2e"
agent-browser type "[name='password']" "<TEST_VIEWER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Expected result:**
- The project list includes `for-testing-only`
- The viewer can see the project card with `READY` status
- The viewer does NOT see "Delete" or "Regenerate" controls (because `role == 'viewer'`)

---

### 11.6 Admin lists access for a project

**Precondition:** Log back in as `admin` (11.5 left us logged in as viewer).

**Commands:**

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser javascript "fetch('/api/admin/projects/for-testing-only/access?owner=testuser-e2e', {credentials:'same-origin'}).then(r => r.json())"
```

**Expected result:**
- Returns a JSON object with a users list
- The list includes `testviewer-e2e`

---

### 11.7 Admin revokes access

**Commands:**

```
agent-browser javascript "fetch('/api/admin/projects/for-testing-only/access/testviewer-e2e?owner=testuser-e2e', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `200`.

---

### 11.8 Viewer can no longer see revoked project

**Commands:**

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testviewer-e2e"
agent-browser type "[name='password']" "<TEST_VIEWER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Expected result:**
- The `for-testing-only` project is NOT in the list
- The viewer sees the empty state

---

### 11.9 Two users generate same repo with same provider/model

**Precondition:** Test 11.8 is complete.

Generate as `testuser-e2e`, wait for completion, then generate as `userb-e2e`, wait for completion.

Verify each user sees only their copy, and admin sees both.

**Expected result:**
- `testuser-e2e` sees exactly 1 project group for `for-testing-only`
- `userb-e2e` sees exactly 1 project group for `for-testing-only`
- Admin sees 2 project groups (one per owner)

---

### 11.10 After revoke, viewer cannot access via direct URL

**Precondition:** Access has been revoked from `testviewer-e2e`.

Log in as `testviewer-e2e`, then try direct URL access:

```shell
agent-browser javascript "fetch('/docs/for-testing-only/main/gemini/gemini-2.5-flash/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.5-flash/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:**
- All direct URL accesses return `404`
- Revocation is enforced at the route level, not just UI level

---

## Test 12: Logout

### 12.1 Logout redirects to login

**Precondition:** Logged in as any user.

**Commands:**

```
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/
agent-browser wait-for-navigation
agent-browser screenshot
```

**Check:** After logout, navigating to dashboard redirects to login.

**Expected result:**
- The URL becomes `http://localhost:8800/login` (React Router redirect)
- The login form is visible

---

### 12.2 Logout is instant (no delay)

**Precondition:** Logged in as any user.

**Commands:**

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

**Now logout via the UI and verify redirect:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser click "[data-testid='user-menu-trigger']"
agent-browser wait 500
agent-browser click "[data-testid='logout']"
agent-browser wait 2000
agent-browser javascript "window.location.href"
agent-browser screenshot
```

**Check:** The login page appears immediately after clicking Logout.

**Expected result:**
- The URL is `http://localhost:8800/login`
- The login page is visible within 1 second (elapsed time < 1000ms)
- There is no visible loading spinner or delay between clicking Logout and seeing the login page

---

### 12.3 After logout, /dashboard redirects to login

**Commands:**

```
agent-browser navigate http://localhost:8800/
agent-browser wait-for-navigation
agent-browser javascript "window.location.href"
agent-browser screenshot
```

**Expected result:**
- The URL has been redirected to `http://localhost:8800/login`
- The login form is displayed
- No dashboard content is visible

---

## Test 13: Direct URL Authorization

Test that a non-owner user cannot access resources by URL. First re-authenticate as `testviewer-e2e` (Test 12 logged out the browser).

**Precondition:** Log in as `testviewer-e2e`.

```shell
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testviewer-e2e"
agent-browser type "[name='password']" "<TESTVIEWER_API_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

### 13.1 Non-owner cannot access docs

```shell
agent-browser javascript "fetch('/docs/for-testing-only/main/gemini/gemini-2.5-flash/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `404` (user is authenticated but not the owner and has no access grant).

---

### 13.2 Non-owner cannot access variant details

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.5-flash', {credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `404`.

---

### 13.3 Non-owner cannot download

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.5-flash/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `404`.

---

### 13.4 Non-owner cannot access via owner-agnostic download route

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/download', {credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `404`.

---

### 13.5 Non-owner cannot access via owner-agnostic docs route

```shell
agent-browser javascript "fetch('/docs/for-testing-only/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `404`.

---

### 13.6 Granted user CAN access

**Precondition:** Admin grants `testviewer-e2e` access, then viewer accesses docs.

```shell
# Switch to admin to grant access
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "admin"
agent-browser type "[name='password']" "<ADMIN_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation

# Grant access
agent-browser javascript "fetch('/api/admin/projects/for-testing-only/access', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body: JSON.stringify({username:'testviewer-e2e', owner:'admin'})}).then(r => r.status)"

# Switch back to viewer
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testviewer-e2e"
agent-browser type "[name='password']" "<TESTVIEWER_API_KEY>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation

# Now try accessing docs
agent-browser javascript "fetch('/docs/for-testing-only/main/gemini/gemini-2.5-flash/index.html', {credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:**
- Grant returns `200`
- Docs fetch returns `200` (granted user can access the documentation)

---

### 13.7 Cleanup note

Access grant from 13.6 is cleaned up in Test 21 (Cleanup and Teardown).
