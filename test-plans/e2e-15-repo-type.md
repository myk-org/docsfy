# E2E Tests: Repository Type Support

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 30: Repo Type API Validation

**Precondition:** Logged in as `testuser-e2e`.

### 30.1 Generate with explicit repo_type

**Commands:**

```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body: JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', branch:'main', repo_type:'tests'})}).then(r=>r.json())"
```

**Expected result:**
- Response status 202
- Response includes `"repo_type": "tests"`

---

### 30.2 Generate with invalid repo_type

**Commands:**

```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body: JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', branch:'main', repo_type:'invalid'})}).then(r=>({status:r.status, body:r.json()}))"
```

**Expected result:**
- Response status 422 (Pydantic validation error)
- Error detail mentions invalid repo_type value

---

### 30.3 Generate with auto-detect (no repo_type)

**Commands:**

```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body: JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', branch:'main'})}).then(r=>r.json())"
```

**Expected result:**
- Response status 202
- Response includes `"repo_type": null`

---

## Test 31: Repo Type UI Elements

**Precondition:** Logged in as `testuser-e2e`.

### 31.1 Verify repo type dropdown exists on generate form

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Expected result:**
- Generate form shows "Repository Type" label with a dropdown selector
- Default value shows "Auto-detect"

---

### 31.2 Verify repo type dropdown options

**Commands:**

```shell
agent-browser click "[data-testid='repo-type-select']"
agent-browser screenshot
```

**Expected result:**
- Dropdown contains 5 options: Auto-detect, App, Tests, Library, Framework

---

### 31.3 Select a repo type and verify session persistence

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-testid='repo-type-select']"
agent-browser click "[data-testid='repo-type-select'] [data-value='tests']"
agent-browser javascript "sessionStorage.getItem('docsfy-repo-type')"
```

**Expected result:**
- sessionStorage returns `"tests"`

---

### 31.4 Verify repo type display in variant detail

**Precondition:** A generation has completed (from Test 6 or other).

**Commands:**

```shell
# Click on a completed variant in the sidebar
agent-browser screenshot
```

**Expected result:**
- Variant detail shows "Repo Type" field with the detected/specified type (e.g., "App")
- Value is capitalized (CSS `capitalize`)

---

## Test 32: Repo Type CLI

### 32.1 CLI generate with --repo-type flag

**Commands:**

```shell
docsfy generate https://github.com/myk-org/for-testing-only --repo-type tests --branch main
```

**Expected result:**
- Output includes `Repo Type: tests`
- Generation starts successfully

---

### 32.2 CLI generate with invalid --repo-type

**Commands:**

```shell
docsfy generate https://github.com/myk-org/for-testing-only --repo-type invalid --branch main
```

**Expected result:**
- Error message: `Invalid repo type: 'invalid'. Must be one of: app, tests, library, framework`
- Exit code 1

---

### 32.3 CLI generate without --repo-type

**Commands:**

```shell
docsfy generate https://github.com/myk-org/for-testing-only --branch main
```

**Expected result:**
- No "Repo Type" line in output (auto-detect mode)
- Generation starts successfully
