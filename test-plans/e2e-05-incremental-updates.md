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
agent-browser select "#gen-provider" "gemini"
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

**Capture baseline page count:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser javascript "document.getElementById('page-count').textContent"
```

Store as `BASELINE_PAGE_COUNT`.

**Capture baseline commit SHA:**
```shell
agent-browser javascript "document.getElementById('commit-sha')?.textContent || document.querySelector('[data-commit]')?.getAttribute('data-commit')"
```

Store as `BASELINE_COMMIT`.

---

### 14.2 Regenerate without force after code change (incremental)

**Precondition:** A newer remote commit must exist in `TEST_REPO` than `BASELINE_COMMIT`. If the remote repository has not changed, mark Tests 14.2-14.6 as `blocked`, continue to Test 15, and do not invent a synthetic remote change for these user-flow tests.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
```

Find the regenerate controls for the exact `for-testing-only` variant with `gemini/gemini-2.5-flash` and regenerate WITHOUT force. Scope to the specific variant card to avoid hitting the wrong variant when multiple provider/model combinations exist:
```shell
agent-browser javascript "document.querySelector('.variant-card[data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"][data-project=\"for-testing-only\"] [data-regen-force]').checked = false"
agent-browser javascript "document.querySelector('.variant-card[data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"][data-project=\"for-testing-only\"] [data-regenerate-variant]').click()"
agent-browser wait 3000
agent-browser screenshot
```

**Check:** The generation starts and uses the incremental planner (not the full planner).

**Expected result:**
- A toast notification appears indicating generation started
- The project status changes to `GENERATING`
- The status page activity log shows an incremental planning stage (e.g., "incremental_planning" or "diff_planning") rather than a full "planning" stage

---

### 14.3 Verify incremental planner runs (not full planner)

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser wait 10000
agent-browser javascript "Array.from(document.querySelectorAll('#log-body > *')).map(el => el.textContent)"
agent-browser screenshot
```

**Check:** The activity log entries indicate incremental planning was used.

**Expected result:**
- The log entries include a stage related to incremental or diff-based planning
- The log does NOT show a full "planning" stage (which would indicate a from-scratch plan)
- The log may show stages like "diff_analysis", "incremental_planning", or similar

---

### 14.4 Verify unchanged pages are cached (byte-for-byte identical)

**Precondition:** Incremental generation from Test 14.2 has completed. Wait for completion if needed (poll until ready).

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser wait 5000
agent-browser javascript "document.getElementById('status-text').textContent"
```

Verify status is `ready`. Then check the activity log for cache hits:

```shell
agent-browser javascript "Array.from(document.querySelectorAll('#log-body > *')).filter(el => el.textContent.toLowerCase().includes('cache') || el.textContent.toLowerCase().includes('unchanged') || el.textContent.toLowerCase().includes('skip')).length > 0"
```

**Check:** Some pages were served from cache (unchanged).

**Expected result:**
- Returns `true` -- at least some log entries reference cached/unchanged/skipped pages
- Pages that had no code changes in the diff were not regenerated

---

### 14.5 Verify changed pages contain new content

**Precondition:** Incremental generation completed from Test 14.2.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/
agent-browser screenshot
```

**Check:** The generated docs page loads and contains updated content reflecting the new commit.

**Expected result:**
- The docs page loads without error
- If the new commit introduced a visible change (e.g., new function, new file), that content is present in the documentation
- The documentation reflects the current state of the repository, not the baseline

---

### 14.6 Verify plan was reused (not regenerated from scratch)

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser javascript "document.getElementById('page-count').textContent"
agent-browser javascript "fetch('/api/projects/for-testing-only/gemini/gemini-2.5-flash/status', {credentials:'same-origin'}).then(r => r.json()).then(d => ({page_count: d.page_count, has_plan: d.plan_json !== undefined && d.plan_json !== null && d.plan_json !== ''}))"
```

**Check:** The plan was reused rather than regenerated from scratch.

**Expected result:**
- The `page_count` is greater than `0`
- The `has_plan` field returns `true`, confirming the `plan_json` field is non-empty (indicating plan reuse)
- A non-empty `plan_json` combined with a positive page count confirms the incremental planner reused the existing plan rather than creating one from scratch

---

### 14.7 Cleanup

**Note:** Test 14 generates/regenerates the `for-testing-only` variant with `gemini/gemini-2.5-flash` owned by `testuser-e2e`. This variant is reused by subsequent tests (Test 15, Test 16, Test 17), so do NOT delete it here. Cleanup of this variant is handled in Test 21.

---

## Test 16: Incremental Page JSON Patch

### 16.1 Verify incremental prompt returns JSON patches

**Precondition:** An incremental generation from Test 14.2 exists. If Tests 14.2-14.6 were blocked or failed before incremental generation started, mark Tests 16.1-16.4 as `blocked` and continue. This test verifies backend behavior through the activity log and API responses.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser wait 10000
agent-browser javascript "Array.from(document.querySelectorAll('#log-body > *')).map(el => el.textContent)"
agent-browser screenshot
```

**Check:** The activity log shows evidence of JSON patch-based incremental updates.

**Expected result:**
- Log entries reference "patch", "incremental", "old_text/new_text", or similar terminology indicating JSON patch mode was used
- The incremental generation did not regenerate all pages from scratch

---

### 16.2 Verify patches are applied correctly to existing content

**Commands:**
```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/gemini/gemini-2.5-flash/
agent-browser screenshot
agent-browser javascript "document.querySelector('.content, .main-content, article')?.innerHTML.length > 0"
```

**Check:** The resulting documentation is coherent and the patches were applied correctly.

**Expected result:**
- Returns `true` -- the content area has non-empty HTML
- The documentation page renders without broken HTML or missing sections
- No visible artifacts from incorrectly applied patches (e.g., duplicated text, missing paragraphs)

---

### 16.3 Fallback to full page generation when patch fails (observational)

**Note:** This is an observational log-inspection check, not an executable E2E test. The patch-failure fallback path cannot be reliably triggered in an E2E environment because it requires a specific AI provider response that produces an un-applicable patch. This check verifies that the fallback behavior IS DOCUMENTED in the codebase and activity log infrastructure.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser javascript "Array.from(document.querySelectorAll('#log-body > *')).filter(el => el.textContent.toLowerCase().includes('fallback') || el.textContent.toLowerCase().includes('full generation') || el.textContent.toLowerCase().includes('patch failed')).map(el => el.textContent)"
```

**Check:** Inspect the activity log for any evidence of fallback behavior.

**Expected result:**
- This is an observational check only -- no pass/fail determination is made
- If fallback entries exist, note them as evidence that the fallback code path was exercised
- If no fallback entries exist, all patches succeeded, which is the expected happy path in E2E
- The purpose is to confirm the fallback mechanism is wired into the logging infrastructure, not to trigger it

---

### 16.4 Fallback when diff retrieval fails (observational)

**Note:** This is an observational log-inspection check, not an executable E2E test. The diff-retrieval failure path cannot be reliably triggered in an E2E environment because it requires the upstream repository to be unavailable or the git diff command to fail. This check verifies that the fallback behavior IS DOCUMENTED in the codebase and activity log infrastructure.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
agent-browser javascript "Array.from(document.querySelectorAll('#log-body > *')).filter(el => el.textContent.toLowerCase().includes('diff') && (el.textContent.toLowerCase().includes('fail') || el.textContent.toLowerCase().includes('error') || el.textContent.toLowerCase().includes('fallback'))).map(el => el.textContent)"
```

**Check:** Inspect the activity log for any evidence of diff-retrieval failure handling.

**Expected result:**
- This is an observational check only -- no pass/fail determination is made
- If diff error entries exist, note them as evidence that the fallback code path was exercised
- If no diff error entries exist, the diff was retrieved successfully, which is the expected happy path in E2E
- The purpose is to confirm the diff-failure fallback mechanism is wired into the logging infrastructure, not to trigger it

---

### 16.5 Cleanup

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
agent-browser javascript "document.querySelector('.variant-card[data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"][data-project=\"for-testing-only\"] [data-regen-force]').checked = true"
agent-browser javascript "document.querySelector('.variant-card[data-provider=\"gemini\"][data-model=\"gemini-2.5-flash\"][data-project=\"for-testing-only\"] [data-regenerate-variant]').click()"
agent-browser wait 2000
agent-browser navigate http://localhost:8800/status/for-testing-only/gemini/gemini-2.5-flash
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
