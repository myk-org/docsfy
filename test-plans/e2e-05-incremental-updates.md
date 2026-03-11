# E2E UI Tests: Incremental Documentation Updates, JSON Patch, and Progress Page

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 14: Incremental Documentation Updates

**Precondition:** Log in as `testuser-e2e` and ensure a completed generation exists for `for-testing-only` with `gemini/gemini-2.5-flash`. If not, generate one with the Force checkbox checked.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

### 14.1 Force-generate docs for baseline

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "#gen-repo-url"
agent-browser type "#gen-repo-url" "https://github.com/myk-org/for-testing-only"
agent-browser clear "#gen-branch"
agent-browser select "#gen-provider" "gemini"
agent-browser wait 500
agent-browser clear "#gen-model"
agent-browser type "#gen-model" "gemini-2.5-flash"
agent-browser click "#gen-force"
agent-browser click "#gen-submit"
agent-browser wait 3000
```

Wait for completion (poll status every 10s until ready, max 2 minutes).

**Check:** A baseline generation completes successfully.

**Expected result:**
- The project status is `ready`
- The status page shows "Documentation generated successfully!"
- A page count greater than 0 is displayed

**Capture baseline commit SHA:**
```shell
curl -s http://localhost:8800/api/status -H "Authorization: Bearer <TEST_USER_PASSWORD>" | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='main' and p['ai_model']=='gemini-2.5-flash']; print(matches[0]['last_commit_sha'] if matches else 'not found')"
```

Store as `BASELINE_COMMIT`.

**Capture baseline plan hash:**
```shell
curl -s "http://localhost:8800/api/projects/for-testing-only/main/gemini/gemini-2.5-flash" -H "Authorization: Bearer <TEST_USER_PASSWORD>" | python3 -c "import sys,json,hashlib; p=json.load(sys.stdin); print(hashlib.sha256(str(p.get('plan_json','')).encode()).hexdigest()[:16])"
```

Store as `BASELINE_PLAN_HASH`.

---

### 14.2 Push a verifiable code change to the test repo

**Commands:**

Clone the test repo, add a new Python function with a unique marker, and push:

```shell
git clone --depth 1 https://github.com/myk-org/for-testing-only /tmp/e2e-incremental-test
cd /tmp/e2e-incremental-test
git checkout -b e2e-incremental-test
cat >> src/request_handler/handler.py << 'PYEOF'


def e2e_incremental_test_function():
    """This function was added by the e2e incremental update test.

    It verifies that incremental documentation updates detect new code
    and include it in the generated documentation.
    """
    return "e2e-incremental-marker-12345"
PYEOF
git add src/request_handler/handler.py
git commit -m "test: add e2e_incremental_test_function for incremental docs test"
git push origin e2e-incremental-test
PR_URL=$(gh pr create --repo myk-org/for-testing-only --title "test: e2e incremental test function" --body "Adding test function for e2e incremental docs test" --base main --head e2e-incremental-test)
PR_NUM=$(echo "$PR_URL" | grep -o '[0-9]*$')
gh pr merge --repo myk-org/for-testing-only "$PR_NUM" --squash --delete-branch
MERGED_SHA=$(gh api "repos/myk-org/for-testing-only/pulls/$PR_NUM" --jq '.merge_commit_sha')
echo "MERGED_SHA=$MERGED_SHA"
rm -rf /tmp/e2e-incremental-test
```

Store as `MERGED_SHA`.

> **Note:** The `MERGED_SHA` is captured from the PR's `merge_commit_sha` field, which is stable regardless of concurrent pushes to `main`.

**Check:** The push succeeds.

**Expected result:**
- The commit is pushed to `main`
- The new commit SHA differs from `BASELINE_COMMIT`

---

### 14.3 Regenerate without force (incremental update)

**Commands:**

Find the regenerate controls for the `for-testing-only` variant with `gemini/gemini-2.5-flash` and regenerate WITHOUT force:

```shell
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelector('.variant-card[data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"][data-project=\"for-testing-only\"][data-branch=\"main\"] [data-regen-force]').checked = false"
agent-browser javascript "document.querySelector('.variant-card[data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"][data-project=\"for-testing-only\"][data-branch=\"main\"] [data-regenerate-variant]').click()"
agent-browser wait 3000
```

Poll the API every 2 seconds, capturing `current_stage` and `status` values until the generation completes:

```shell
# Poll API every 2s, capture current_stage values
SEEN_INCREMENTAL="false"
for i in $(seq 1 120); do
  STAGE=$(curl -s http://localhost:8800/api/status -H "Authorization: Bearer <TEST_USER_PASSWORD>" | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='main' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('current_stage','') if matches else '')")
  STATUS=$(curl -s http://localhost:8800/api/status -H "Authorization: Bearer <TEST_USER_PASSWORD>" | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='main' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('status','') if matches else '')")
  echo "Poll $i: status=$STATUS stage=$STAGE"
  if echo "$STAGE" | grep -q "incremental"; then SEEN_INCREMENTAL="true"; fi
  if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ]; then break; fi
  sleep 2
done
echo "SEEN_INCREMENTAL=$SEEN_INCREMENTAL"
```

**Check:** The generation uses the incremental planner.

**Expected result:**
- `SEEN_INCREMENTAL=true`. Final status is ready.
- The `last_commit_sha` is updated to the new commit (different from `BASELINE_COMMIT`)

---

### 14.4 Verify the new function appears in the documentation

**Commands:**

Search the generated docs for the specific function name added in 14.2:

```shell
curl -s http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/llms-full.txt -H "Authorization: Bearer <TEST_USER_PASSWORD>"
```

Search the response for `e2e_incremental_test_function`.

**Check:** The incrementally updated docs contain the new function.

**Expected result:**
- The content contains `e2e_incremental_test_function`
- This confirms the incremental update detected the code change and updated the relevant documentation page

---

### 14.5 Verify plan was reused (not regenerated from scratch)

**Commands:**
```shell
curl -s "http://localhost:8800/api/projects/for-testing-only/main/gemini/gemini-2.5-flash" -H "Authorization: Bearer <TEST_USER_PASSWORD>"
```

**Capture post-incremental plan hash:**
```shell
curl -s "http://localhost:8800/api/projects/for-testing-only/main/gemini/gemini-2.5-flash" -H "Authorization: Bearer <TEST_USER_PASSWORD>" | python3 -c "import sys,json,hashlib; p=json.load(sys.stdin); print(hashlib.sha256(str(p.get('plan_json','')).encode()).hexdigest()[:16])"
```

**Check:** The plan was reused (hash matches `BASELINE_PLAN_HASH`).

**Expected result:**
- `page_count` is greater than 0
- `plan_json` is non-empty (plan reuse)
- The plan hash matches `BASELINE_PLAN_HASH` (plan structure unchanged)
- `last_commit_sha` matches `MERGED_SHA`

---

### 14.6 Cleanup: revert the test commit

**Commands:**

Remove the test function from the repo:

```shell
git clone --depth 5 https://github.com/myk-org/for-testing-only /tmp/e2e-incremental-cleanup
cd /tmp/e2e-incremental-cleanup
git checkout -b revert-e2e-incremental-test
if [ -n "$MERGED_SHA" ]; then
    git revert --no-edit "$MERGED_SHA"
fi
git push origin revert-e2e-incremental-test
gh pr create --repo myk-org/for-testing-only --title "Revert: e2e incremental test function" --body "Cleanup after e2e incremental test" --base main --head revert-e2e-incremental-test
gh pr merge --repo myk-org/for-testing-only --squash --delete-branch
rm -rf /tmp/e2e-incremental-cleanup
```

**Check:** The revert is pushed.

**Expected result:**
- The test function is removed from the repo
- The repo is back to its original state

---

## Test 16: Incremental Page JSON Patch

### 16.1 Verify incremental prompt returns JSON patches

**Precondition:** An incremental generation from Test 14.3 exists.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser wait 2000
agent-browser javascript "Array.from(document.querySelectorAll('#log-body > *')).map(el => el.textContent)"
```

**Check:** The activity log shows evidence of JSON patch-based incremental updates.

**Expected result:**
- Log entries reference "patch", "incremental", "old_text/new_text", or similar terminology indicating JSON patch mode was used
- The incremental generation did not regenerate all pages from scratch

---

### 16.2 Verify patches are applied correctly to existing content

**Commands:**
```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/
agent-browser javascript "document.querySelector('.content, .main-content, article')?.innerHTML.length > 0"
```

**Check:** The resulting documentation is coherent.

**Expected result:**
- Returns `true` -- the content area has non-empty HTML
- The documentation page renders without broken HTML or missing sections

---

### 16.3 Cleanup

**Note:** Test 16 does not create new data -- it inspects the status page and activity log of the existing `for-testing-only` variant generated in earlier tests. No cleanup needed.

---

## Test 17: Progress Page During Regeneration

**Precondition:** Log in as `testuser-e2e` and trigger a forced regeneration to observe the progress page behavior.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

### 17.1 Page count resets to 0 at start of regeneration

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser javascript "document.querySelector('.variant-card[data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"][data-project=\"for-testing-only\"][data-branch=\"main\"] [data-regen-force]').checked = true"
agent-browser javascript "document.querySelector('.variant-card[data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"][data-project=\"for-testing-only\"][data-branch=\"main\"] [data-regenerate-variant]').click()"
agent-browser wait 2000
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser screenshot
```

**Check:** The page count resets when a new generation starts.

**Expected result:**
- The progress counter shows `0` or is reset at the start of the new generation
- The previous generation's page count is not carried over
- The status shows `generating`

---

### 17.2 Correct total page count shown once plan is ready

**Commands:**
```shell
agent-browser wait 15000
agent-browser screenshot
agent-browser javascript "document.querySelector('.progress-bar, [data-progress]')?.textContent || document.getElementById('page-count')?.textContent"
```

**Check:** Once the planner finishes, the total page count is displayed correctly.

**Expected result:**
- The progress display shows a format like "X / Y" where Y is the total planned pages
- The total (Y) matches the number of pages in the plan
- The current count (X) increments as pages are generated

---

### 17.3 Progress counter does not overflow

**Commands:**

Poll the progress counter during generation:
```shell
agent-browser javascript "const progress = document.querySelector('.progress-text, [data-progress-text]')?.textContent; const match = progress?.match(/(\\d+)\\s*\\/\\s*(\\d+)/); match ? {current: parseInt(match[1]), total: parseInt(match[2]), overflow: parseInt(match[1]) > parseInt(match[2])} : 'no progress display found'"
```

Repeat every 5 seconds during generation until status is `ready`:
```shell
agent-browser wait 5000
agent-browser javascript "const progress = document.querySelector('.progress-text, [data-progress-text]')?.textContent; const match = progress?.match(/(\\d+)\\s*\\/\\s*(\\d+)/); match ? {current: parseInt(match[1]), total: parseInt(match[2]), overflow: parseInt(match[1]) > parseInt(match[2])} : 'no progress display found'"
```

**Check:** The current page count never exceeds the total page count.

**Expected result:**
- The `overflow` field is always `false`
- No "15/12" or similar overflow scenarios occur
- When generation is complete, current equals total (e.g., "12/12")

Wait for generation to complete before continuing.

---

### 17.4 Cleanup

**Note:** Test 17 triggers a forced regeneration of the existing `for-testing-only` variant owned by `testuser-e2e`. This overwrites the variant in-place (no new variant is created). No cleanup needed.
