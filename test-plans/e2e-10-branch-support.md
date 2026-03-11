# E2E UI Tests: Branch Support

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 22: Generate Docs for Specific Branch

**Precondition:** Log in as `testuser-e2e`. The `for-testing-only` repo has both `main` and `dev` branches.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

### 22.1 Generate docs for dev branch

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser clear "#gen-branch"
agent-browser type "#gen-branch" "dev"
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser screenshot
```

**Check:** The form fields are correctly populated including the branch field.

**Expected result:**
- Repository URL field contains `https://github.com/myk-org/for-testing-only`
- Branch field contains `dev`
- Provider dropdown shows `gemini`
- Model field shows `gemini-2.5-flash`

---

### 22.2 Generation starts for dev branch

**Commands:**
```shell
agent-browser click "#gen-submit"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** A generation task is started for the dev branch.

**Expected result:**
- A toast notification appears with a success message about generation starting
- The project list shows a card for `for-testing-only` under `@dev` branch section with status `GENERATING`

---

### 22.3 Wait for dev branch completion

**Commands:**
```shell
# Poll status every 10s until ready or error, max 3 minutes
for i in $(seq 1 18); do
  STATUS=$(curl -s http://localhost:8800/api/status -H "Authorization: Bearer <TEST_USER_PASSWORD>" | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='dev' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('status','') if matches else '')")
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

**Check:** The generation completes successfully.

**Expected result:**
- The status indicator shows `ready` with a green dot
- The page count is greater than 0

---

### 22.4 Dashboard shows branch grouping

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Check:** The dashboard groups the `for-testing-only` project with branch sub-sections.

**Expected result:**
- The `for-testing-only` project group contains a `@dev` branch section
- The `@dev` section shows the `gemini/gemini-2.5-flash` variant with status `READY`
- If a `@main` variant exists from earlier tests, it appears in a separate `@main` section

---

### 22.5 View docs for dev branch

**Commands:**
```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/dev/gemini/gemini-2.5-flash/
agent-browser screenshot
```

**Check:** The generated documentation loads for the dev branch.

**Expected result:**
- The documentation page renders HTML content
- A sidebar with navigation links is visible

---

### 22.6 Download docs for dev branch

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/dev/gemini/gemini-2.5-flash
agent-browser javascript "document.getElementById('btn-download').getAttribute('href')"
```

**Check:** The download link includes the branch segment.

**Expected result:**
- The href is `/api/projects/for-testing-only/dev/gemini/gemini-2.5-flash/download`

---

### 22.7 Generate docs for invalid branch (error handling)

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser clear "#gen-branch"
agent-browser type "#gen-branch" "nonexistent-branch-xyz"
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-submit"
agent-browser wait 10000
agent-browser screenshot
```

**Check:** The generation fails with a clear error about the invalid branch.

**Verify the error card content:**
```shell
agent-browser javascript "var cards = document.querySelectorAll('[data-project=\"for-testing-only\"]'); var errorCard = Array.from(cards).find(c => c.getAttribute('data-status') === 'error'); errorCard ? errorCard.textContent : 'no error card'"
```

**Expected result:**
- The project card shows status `ERROR`
- The error card text contains `nonexistent-branch-xyz` or `not found` or `Clone failed`

---

### 22.8 Delete dev branch variant

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click "[data-delete-variant='for-testing-only/dev/gemini/gemini-2.5-flash']"
agent-browser wait 1000
agent-browser click "#modal-ok"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** The dev branch variant is deleted.

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

Find the regenerate controls for the `for-testing-only` project:
```shell
agent-browser javascript "document.querySelector('.variant-card[data-project=\"for-testing-only\"][data-branch=\"main\"][data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"] [data-regen-branch]') !== null"
```

**Expected result:** Returns `true` --- branch input exists in regen controls.

Change the branch to `dev` and regenerate:
```shell
agent-browser javascript "var branchInput = document.querySelector('.variant-card[data-project=\"for-testing-only\"][data-branch=\"main\"][data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"] [data-regen-branch]'); branchInput.value = 'dev'; branchInput.dispatchEvent(new Event('input'));"
agent-browser javascript "document.querySelector('.variant-card[data-project=\"for-testing-only\"][data-branch=\"main\"][data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"] [data-regen-force]').checked = true"
agent-browser javascript "document.querySelector('.variant-card[data-project=\"for-testing-only\"][data-branch=\"main\"][data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"] [data-regenerate-variant]').click()"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** A new generation starts for the `dev` branch.

**Expected result:**
- A toast notification appears indicating generation started
- The dashboard shows a new `@dev` branch section for `for-testing-only`

---

### 22.11 Generate with omitted branch (defaults to main)

**Commands:**
```shell
curl -s -X POST http://localhost:8800/api/generate -H "Authorization: Bearer <TEST_USER_PASSWORD>" -H "Content-Type: application/json" -d '{"repo_url":"https://github.com/myk-org/for-testing-only","ai_provider":"gemini","ai_model":"gemini-2.5-flash"}'
```

**Check:** Generation uses default branch "main".

**Expected result:**
- Response includes `"branch": "main"`
- The variant is created with branch=main
