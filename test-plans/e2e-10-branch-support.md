# E2E UI Tests: Branch Support

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

> **UI Framework Note:** The app UI is a React SPA. Real-time updates use WebSocket (`/api/ws`).

---

## Test 22: Generate Docs for Specific Branch

**Precondition:** Log in as `testuser-e2e`. The `for-testing-only` repo has both `main` and `dev` branches.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

### 22.1 Generate docs for dev branch

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser clear "[data-testid='branch-input']"
agent-browser type "[data-testid='branch-input']" "dev"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser screenshot
```

**Expected result:**
- Repository URL field contains `https://github.com/myk-org/for-testing-only`
- Branch field contains `dev`
- Provider shows `gemini`
- Model field shows `gemini-2.5-flash`

---

### 22.2 Generation starts for dev branch

**Commands:**
```shell
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- A toast notification appears with a success message about generation starting
- The project list shows a card for `for-testing-only` under `@dev` branch section with status `GENERATING`

---

### 22.3 Wait for dev branch completion

**Commands:**
```shell
# Poll status every 10s until ready or error, max 3 minutes
for i in $(seq 1 18); do
  STATUS=$(curl -s http://localhost:8800/api/projects -H "Authorization: Bearer <TEST_USER_PASSWORD>" | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='dev' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('status','') if matches else '')")
  echo "Poll $i: $STATUS"
  if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ]; then break; fi
  sleep 10
done
if [ "$STATUS" != "ready" ]; then
    echo "FAIL: Generation did not reach ready status. Last status: $STATUS"
    exit 1
fi
agent-browser screenshot
```

**Expected result:**
- The status indicator shows `ready`
- The page count is greater than 0

---

### 22.4 Dashboard shows branch grouping

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Expected result:**
- The `for-testing-only` project group contains a `@dev` branch section
- The `@dev` section shows the `gemini/gemini-2.5-flash` variant with status `READY`

---

### 22.5 View docs for dev branch

**Commands:**
```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/dev/gemini/gemini-2.5-flash/
agent-browser screenshot
```

**Expected result:**
- The documentation page renders HTML content
- A sidebar with navigation links is visible

---

### 22.6 Download docs for dev branch

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/dev/gemini/gemini-2.5-flash
agent-browser javascript "document.querySelector('[data-testid=\"download-btn\"]')?.getAttribute('href')"
```

**Expected result:**
- The href is `/api/projects/for-testing-only/dev/gemini/gemini-2.5-flash/download`

---

### 22.7 Generate docs for invalid branch (error handling)

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser clear "[data-testid='branch-input']"
agent-browser type "[data-testid='branch-input']" "nonexistent-branch-xyz"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 10000
agent-browser screenshot
```

**Expected result:**
- The project card shows status `ERROR`
- The error text contains `nonexistent-branch-xyz` or `not found` or `Clone failed`

---

### 22.8 Delete dev branch variant

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-delete-variant='for-testing-only/dev/gemini/gemini-2.5-flash']"
agent-browser wait 1000
agent-browser click "[data-testid='dialog-confirm']"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- The `@dev` section is removed from the `for-testing-only` group
- A toast notification confirms deletion

---

### 22.9 Cleanup

Delete any remaining test artifacts:
```shell
agent-browser navigate http://localhost:8800/
```

If the invalid branch variant from 22.7 exists, delete it:
```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/nonexistent-branch-xyz/gemini/gemini-2.5-flash?owner=testuser-e2e', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
```

**Expected result:** Returns `200` (deleted) or `404` (already gone).

---

### 22.10 Regenerate with different branch

**Precondition:** A `for-testing-only` variant exists on `main` branch from earlier tests.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
```

Find the regenerate controls for the `for-testing-only` project and change the branch to `dev`:
```shell
agent-browser javascript "var branchInput = document.querySelector('[data-regen-branch]'); branchInput.value = 'dev'; branchInput.dispatchEvent(new Event('input'));"
agent-browser click "[data-regen-force]"
agent-browser click "[data-regenerate-variant]"
agent-browser wait 3000
agent-browser screenshot
```

**Expected result:**
- A toast notification appears indicating generation started
- The dashboard shows a new `@dev` branch section for `for-testing-only`

---

### 22.11 Generate with omitted branch (defaults to main)

**Commands:**
```shell
curl -s -X POST http://localhost:8800/api/generate -H "Authorization: Bearer <TEST_USER_PASSWORD>" -H "Content-Type: application/json" -d '{"repo_url":"https://github.com/myk-org/for-testing-only","ai_provider":"gemini","ai_model":"gemini-2.5-flash"}'
```

**Expected result:**
- Response includes `"branch": "main"`
- The variant is created with branch=main
