# E2E UI Tests: Post-Generation Pipeline

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.
>
> **UI Framework Note:** The app UI is a React SPA using shadcn/ui components and Tailwind CSS. Real-time updates use WebSocket (`/api/ws`).

---

## Test 27: Post-Generation Pipeline

This test group verifies the features added by the post-generation pipeline: version detection in the footer, related-pages cross-links, the validation, completeness-check, and cross-linking stages that appear during generation, generation duration tracking and display, elapsed time indicator during active generation, and stage-specific status labels in the activity log header.

**Precondition:** Log in as `testuser-e2e`. Ensure the `for-testing-only` repo is accessible.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

---

### 27.1 Version shown in footer when pyproject.toml contains a version

**Precondition:** The `for-testing-only` repo on `main` contains a `pyproject.toml` with a `version` field. Generate docs and wait for completion.

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser clear "[data-testid='branch-input']"
agent-browser type "[data-testid='branch-input']" "main"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser click "[data-testid='force-checkbox']"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
```

Poll until ready (max 5 minutes):

```shell
for i in $(seq 1 30); do
  STATUS=$(curl -s -H "Cookie: $SESSION_COOKIE" http://localhost:8800/api/projects | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='main' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('status','') if matches else '')")
  echo "Poll $i: $STATUS"
  if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ]; then break; fi
  sleep 10
done
```

Navigate to a generated page and check the footer:

```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/
agent-browser javascript "document.querySelector('footer span[class*=\"version\"], footer .version, footer [data-version]')?.textContent"
agent-browser screenshot
```

**Expected result:**
- A version span is present in the footer
- The text matches the pattern `vX.Y.Z` (e.g., `v1.0.0`)
- The version matches the `version` field from the repo's `pyproject.toml`

---

### 27.2 No version span when repo has no version files

**Precondition:** Generate docs for the `dev` branch of `for-testing-only`, which does not contain `pyproject.toml`, `setup.cfg`, or `package.json` with a version field. If the `dev` branch also contains version files, mark this test as `blocked` and note the reason.

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
agent-browser click "[data-testid='force-checkbox']"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
```

Poll until ready (max 5 minutes):

```shell
for i in $(seq 1 30); do
  STATUS=$(curl -s -H "Cookie: $SESSION_COOKIE" http://localhost:8800/api/projects | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='dev' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('status','') if matches else '')")
  echo "Poll $i: $STATUS"
  if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ]; then break; fi
  sleep 10
done
```

Navigate to a generated page and verify the footer:

```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/dev/gemini/gemini-2.5-flash/
agent-browser javascript "document.querySelector('footer span[class*=\"version\"], footer .version, footer [data-version]')"
agent-browser javascript "document.querySelector('footer')?.textContent"
agent-browser screenshot
```

**Expected result:**
- No version span element is present in the footer (`null` from the first JavaScript query)
- The footer still contains the "Generated with docsfy" text
- No `vX.Y.Z` pattern appears anywhere in the footer text

**Cleanup:** Delete the dev branch variant generated for this test:

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/dev/gemini/gemini-2.5-flash?owner=testuser-e2e', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
agent-browser wait 2000
```

**Expected result:** Returns `200`.

---

### 27.3 Related Pages section links to other pages

**Precondition:** Docs for `for-testing-only/main/gemini/gemini-2.5-flash` are in `ready` state.

**Navigate to the index page:**

```shell
agent-browser navigate http://localhost:8800/docs/for-testing-only/main/gemini/gemini-2.5-flash/
agent-browser javascript "document.querySelector('.related-pages, [class*=\"related\"], section[aria-label*=\"related\" i]') !== null"
agent-browser screenshot
```

If the index page has no Related Pages section, check sub-pages:

```shell
agent-browser javascript "Array.from(document.querySelectorAll('nav a[href*=\"/docs/\"]')).map(a => a.href).slice(0, 3)"
# Navigate to each and check
agent-browser navigate <first-subpage-href>
agent-browser javascript "document.querySelector('.related-pages, [class*=\"related\"], section[aria-label*=\"related\" i]') !== null"
agent-browser screenshot
```

**On a page that contains a Related Pages section, verify its contents:**

```shell
agent-browser javascript "document.querySelector('.related-pages, [class*=\"related\"]')?.querySelectorAll('a').length"
agent-browser javascript "Array.from(document.querySelectorAll('.related-pages a, [class*=\"related\"] a')).map(a => ({text: a.textContent.trim(), href: a.getAttribute('href')}))"
```

**Expected result:**
- A "Related Pages" section (or equivalent heading) is present on at least one documentation page
- The section contains at least one anchor (`<a>`) link
- Each link `href` points to another page within the same documentation set (relative URL or path containing `/docs/for-testing-only/`)
- Link text is a human-readable page name (not a raw URL or empty string)

---

### 27.4 Validation and cross-linking stages appear in WebSocket progress

**Precondition:** Start a fresh generation with `force: true` and monitor the WebSocket for stage names.

**Set up WebSocket listener before starting generation:**

```shell
agent-browser javascript "await new Promise((resolve, reject) => { window.__pipelineStages = new Set(); const ws = new WebSocket('ws://localhost:8800/api/ws'); ws.onopen = () => { window.__pipelineWs = ws; resolve('connected'); }; ws.onerror = (e) => reject('ws error'); ws.onmessage = (e) => { const msg = JSON.parse(e.data); if (msg.current_stage) window.__pipelineStages.add(msg.current_stage); if (msg.progress && msg.progress.current_stage) window.__pipelineStages.add(msg.progress.current_stage); if (msg.status) window.__pipelineStages.add(msg.status); }; })"
```

**Start generation:**

```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', branch:'main', ai_provider:'gemini', ai_model:'gemini-2.5-flash', force:true})}).then(r => r.status)"
```

**Wait for generation to progress past the page-writing phase (at least 60 seconds):**

```shell
agent-browser wait 60000
```

**Check captured stages:**

```shell
agent-browser javascript "JSON.stringify(Array.from(window.__pipelineStages))"
```

**Expected result:**
- The returned array contains `"validating"` or a stage name containing `"validat"`
- The returned array contains `"cross_linking"` or a stage name containing `"cross_link"` or `"crosslink"`
- The returned array contains `"completeness_check"` or a stage name containing `"completeness"`
- Both stages appear after the page-writing stages (they are post-processing)

**Cleanup:**

```shell
agent-browser javascript "if (window.__pipelineWs) { window.__pipelineWs.close(); delete window.__pipelineWs; delete window.__pipelineStages; }"
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.5-flash/abort', {method:'POST', credentials:'same-origin'}).then(r => r.status)"
agent-browser wait 3000
```

**Expected result:** Abort returns `200` (aborted) or `404` (already completed). Both are acceptable.

---

### 27.5 Dashboard activity log shows validating and cross-linking stages

**Precondition:** Start a fresh force generation and watch the activity log in the dashboard UI without refreshing the page.

**Start generation:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser clear "[data-testid='repo-url']"
agent-browser type "[data-testid='repo-url']" "https://github.com/myk-org/for-testing-only"
agent-browser clear "[data-testid='branch-input']"
agent-browser type "[data-testid='branch-input']" "main"
agent-browser click "[data-testid='provider-select']"
agent-browser wait 500
agent-browser click "[data-value='gemini']"
agent-browser wait 500
agent-browser clear "[data-testid='model-input']"
agent-browser type "[data-testid='model-input']" "gemini-2.5-flash"
agent-browser click "[data-testid='force-checkbox']"
agent-browser click "[data-testid='generate-btn']"
agent-browser wait 3000
```

Navigate to the status page and stay there — do NOT refresh:

```shell
agent-browser navigate http://localhost:8800/status/for-testing-only/main/gemini/gemini-2.5-flash
agent-browser wait 5000
agent-browser screenshot
```

Wait for generation to complete fully (poll until `ready` or `error`, max 5 minutes). Do NOT refresh the page between polls — use JavaScript to read UI text:

```shell
for i in $(seq 1 30); do
  STAGE_TEXT=$(agent-browser javascript "Array.from(document.querySelectorAll('[class*=\"activity\"] li, [class*=\"log\"] li, [class*=\"progress\"] li')).map(li => li.textContent.trim()).join(' | ')")
  echo "Poll $i activity: $STAGE_TEXT"
  STATUS_TEXT=$(agent-browser javascript "document.querySelector('[data-testid=\"status-text\"]')?.textContent")
  echo "Poll $i status: $STATUS_TEXT"
  if echo "$STATUS_TEXT" | grep -qi "ready\|error"; then break; fi
  sleep 10
done
agent-browser screenshot
```

**Check the activity log contains post-processing stage entries:**

```shell
agent-browser javascript "Array.from(document.querySelectorAll('[class*=\"activity\"] li, [class*=\"log\"] li, [class*=\"progress\"] li')).map(li => li.textContent.trim())"
```

**Expected result:**
- The activity log list contains at least one entry with text matching `validat` (case-insensitive), such as "Validating pages", "Validation complete", or similar
- The activity log list contains at least one entry with text matching `completeness` (case-insensitive), such as "Checking documentation completeness...", "Verified documentation completeness", or similar
- The activity log list contains at least one entry with text matching `cross.link` (case-insensitive), such as "Cross-linking pages", "Cross-linking complete", or similar
- All three entries appear after page-writing entries in the log order
- These entries arrive via WebSocket without requiring a page refresh
- The activity log status header shows stage-specific text (e.g., "Checking completeness...") instead of generic "Generating..." during the completeness_check stage
- If the completeness check generated additional pages beyond the original plan, the activity log contains entries matching `gap page` (e.g., "Generated gap page 7 (coverage gap)"). These appear after the original page entries and before cross-linking

---

### 27.6 Performance baseline: wall-clock generation time comparison

**Note:** This test measures the overhead introduced by the post-generation pipeline (validation, cross-linking, version detection). Run the test on the current build (with the pipeline enabled). Compare the result against the documented baseline from before the pipeline was added.

**Documented pre-pipeline baseline:** Record the generation time for `for-testing-only/main` before this feature was merged (obtained from the previous test run history or git log). If no baseline is available, mark the baseline as `N/A` and document only the current time.

**Measure current generation time:**

```shell
START_TIME=$(date +%s)
```

```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', branch:'main', ai_provider:'gemini', ai_model:'gemini-2.5-flash', force:true})}).then(r => r.status)"
```

Poll until ready or error (max 5 minutes):

```shell
for i in $(seq 1 30); do
  STATUS=$(curl -s -H "Cookie: $SESSION_COOKIE" http://localhost:8800/api/projects | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='main' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('status','') if matches else '')")
  echo "Poll $i: $STATUS"
  if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ]; then break; fi
  sleep 10
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo "Generation wall-clock time: ${ELAPSED}s"
```

**Record the result in `UI-TESTS-RESULTS.md`** using this format:

```markdown
| 27.6 | Performance baseline (post-pipeline) | PASS | Wall-clock: Xs. Pre-pipeline baseline: Ys. Overhead: Zs (P%). |
```

**Expected result:**
- Generation completes successfully (`ready` status)
- The wall-clock time is recorded for comparison
- The overhead added by validation, cross-linking, and version detection is documented
- Acceptable overhead: the post-generation pipeline should add no more than 30 seconds to generation of the `for-testing-only` test repo (which is small). If overhead exceeds 30 seconds, record as a performance concern in the Details column but do not mark the test as FAIL unless the total time exceeds 10 minutes

---

### 27.7 Generation duration displayed for ready variants

**Precondition:** A `ready` variant exists for `for-testing-only/main` (from test 27.1 or 27.6).

**Commands:**

```shell
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
```

Click on the ready variant to open its detail view:

```shell
agent-browser click "[data-testid='variant-for-testing-only-main-gemini-gemini-2.5-flash']"
agent-browser wait 1000
agent-browser screenshot
```

**Check the info grid contains a "Generation Time" field:**

```shell
agent-browser javascript "Array.from(document.querySelectorAll('[class*=\"grid\"] > div')).map(div => div.textContent.trim()).join(' | ')"
```

**Expected result:**
- The info grid contains a field labeled "Generation Time"
- The value is a human-readable duration format (e.g., "2m 34s", "45s", "1h 5m")
- The value is non-empty and non-zero

---

### 27.8 Generation duration tracked via API

**Precondition:** A `ready` variant exists for `for-testing-only/main`.

**Commands:**

```shell
curl -s -H "Cookie: $SESSION_COOKIE" http://localhost:8800/api/projects | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='main' and p['ai_model']=='gemini-2.5-flash']; print('generation_duration:', matches[0].get('generation_duration')) if matches else print('NOT FOUND')"
```

**Expected result:**
- The `generation_duration` field is present in the API response
- The value is a positive integer representing seconds
- The value is reasonable for the test repo (typically between 30 and 600 seconds)

---

### 27.9 Elapsed timer shown during active generation

**Precondition:** Start a fresh force generation and immediately check the status page for elapsed time.

**Commands:**

```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', branch:'main', ai_provider:'gemini', ai_model:'gemini-2.5-flash', force:true})}).then(r => r.status)"
agent-browser wait 5000
agent-browser screenshot
```

**Check the generating view shows elapsed time:**

```shell
agent-browser javascript "document.body.innerText.includes('Elapsed')"
```

**Expected result:**
- The page shows an "Elapsed: Xs" or "Elapsed: Xm Ys" indicator
- The elapsed time updates every second (take two screenshots 3 seconds apart and compare the time values)
- The elapsed time disappears once generation completes

**Cleanup:**

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.5-flash/abort', {method:'POST', credentials:'same-origin'}).then(r => r.status)"
agent-browser wait 3000
```

---

### 27.10 Activity log status header shows stage-specific text

**Precondition:** Start a fresh generation and observe the activity log header text.

**Commands:**

```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', branch:'main', ai_provider:'gemini', ai_model:'gemini-2.5-flash', force:true})}).then(r => r.status)"
agent-browser wait 10000
agent-browser screenshot
```

**Check the status header text is stage-specific:**

```shell
agent-browser javascript "document.querySelector('[class*=\"activity\"] [class*=\"header\"], [class*=\"log\"] [class*=\"header\"]')?.textContent"
```

**Expected result:**
- During generation, the status header shows a stage-specific label such as:
  - "Cloning...", "Analyzing...", "Planning...", "Generating pages...", "Validating...", "Checking completeness...", "Cross-linking...", "Rendering..."
- The header does NOT show a generic "Generating..." when a specific stage is known
- The label updates as the stage changes (observe multiple screenshots across different stages)

**Cleanup:**

```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.5-flash/abort', {method:'POST', credentials:'same-origin'}).then(r => r.status)"
agent-browser wait 3000
```

---

### 27.11 Cleanup

Delete variants created during Test 27 that are not needed by later tests:

```shell
# Delete dev-branch variant from 27.2 (if not already deleted in that step)
agent-browser javascript "fetch('/api/projects/for-testing-only/dev/gemini/gemini-2.5-flash?owner=testuser-e2e', {method:'DELETE', credentials:'same-origin'}).then(r => r.status)"
agent-browser wait 2000
```

**Expected result:** Returns `200` (deleted) or `404` (already gone). Both are acceptable.

The `main`-branch variant generated in 27.1 / 27.6 may be kept for subsequent test sections that depend on an existing `ready` variant.
