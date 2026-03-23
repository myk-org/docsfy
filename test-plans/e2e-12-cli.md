# E2E Tests: CLI Commands

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

> **Note:** These tests exercise the `docsfy` CLI tool. The server must be running at `http://localhost:8800`.

---

## Test 24: CLI Commands

### Prerequisites

Set up the CLI configuration:
```shell
export DOCSFY_SERVER="http://localhost:8800"
export DOCSFY_API_KEY="<ADMIN_KEY>"
```

### 24.1 Config init creates config file

**Commands:**
```shell
rm -f ~/.config/docsfy/config.toml
docsfy config init
cat ~/.config/docsfy/config.toml
```

**Expected result:**
- The config file is created at `~/.config/docsfy/config.toml`
- The file contains default configuration values (server URL, empty API key)

---

### 24.2 Config show displays current settings

**Commands:**
```shell
docsfy config show
```

**Expected result:**
- The output shows the current configuration
- Server URL, API key (masked), and default provider/model are displayed

---

### 24.3 Config set updates values

**Commands:**
```shell
docsfy config set server "$DOCSFY_SERVER"
docsfy config set api-key "$DOCSFY_API_KEY"
docsfy config show
```

**Expected result:**
- The server URL is updated to `http://localhost:8800`
- The API key is updated (shown masked in output)

---

### 24.4 Generate starts documentation generation

**Commands:**
```shell
docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force
```

**Expected result:**
- The CLI outputs "Generation started for for-testing-only" or similar
- The generation is triggered on the server
- The CLI shows initial status

---

### 24.5 Generate with --watch shows real-time progress

**Precondition:** Wait for test 24.4's generation to reach a terminal state before starting, to avoid a 409 conflict. Use the `dev` branch so this test does not conflict with 24.4's `main` branch generation.

**Wait for 24.4 to finish:**
```shell
for i in $(seq 1 60); do
  STATUS=$(curl -s "$DOCSFY_SERVER/api/projects" -H "Authorization: Bearer $DOCSFY_API_KEY" | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='main' and p['ai_model']=='gemini-2.5-flash']; print(matches[0].get('status','') if matches else 'not_found')")
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ] || [ "$STATUS" = "aborted" ] || [ "$STATUS" = "not_found" ]; then break; fi
  sleep 2
done
```

**Commands:**
```shell
timeout 30 docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --force --watch 2>&1 | head -20
```

**Expected result:**
- The CLI shows real-time progress updates (via WebSocket or polling)
- Status changes are displayed as they occur (e.g., "cloning...", "planning...", "generating pages...")
- The output includes a progress indicator

---

### 24.6 List shows projects

**Commands:**
```shell
docsfy list
```

**Expected result:**
- The output shows a table or list of projects
- The `for-testing-only` project is visible
- Each entry shows name, branch, provider, model, status, and owner

---

### 24.7 Status shows project details

**Commands:**
```shell
docsfy status for-testing-only
```

**Expected result:**
- The output shows detailed status for the project
- Information includes: status, provider, model, branch, page count, last commit SHA
- If the project has multiple variants, all are listed

---

### 24.8 Delete removes a project variant

**First generate a disposable variant (using `dev` branch to avoid conflicts with other tests):**
```shell
docsfy generate https://github.com/myk-org/for-testing-only --branch dev --provider gemini --model gemini-2.0-flash --force
```

**Wait for generation to complete before deleting (max 2 minutes):**
```shell
for i in $(seq 1 60); do
  STATUS=$(curl -s "$DOCSFY_SERVER/api/projects" -H "Authorization: Bearer $DOCSFY_API_KEY" | python3 -c "import sys,json; data=json.load(sys.stdin); matches=[p for p in data['projects'] if p['name']=='for-testing-only' and p['branch']=='dev' and p['ai_model']=='gemini-2.0-flash']; print(matches[0].get('status','') if matches else 'not_found')")
  echo "Poll $i: status=$STATUS"
  if [ "$STATUS" = "ready" ] || [ "$STATUS" = "error" ]; then break; fi
  sleep 2
done
```

**Verify the variant exists, then delete:**
```shell
docsfy list | grep -q "gemini-2.0-flash" && echo "Variant exists" || echo "Variant missing"
docsfy delete for-testing-only --branch dev --provider gemini --model gemini-2.0-flash --yes
```

**Expected result:**
- The CLI confirms deletion
- The variant no longer appears in `docsfy list`

---

### 24.9 Admin user commands

**Commands:**
```shell
docsfy admin users list
```

**Expected result:**
- The output shows a table of users
- Each entry shows username and role

**Create a test user:**
```shell
docsfy admin users create cli-test-user --role user
```

**Expected result:**
- The user is created
- The generated password is displayed

**Delete the test user:**
```shell
docsfy admin users delete cli-test-user --yes
```

**Expected result:**
- The user is deleted
- Confirmation message is shown

---

### 24.10 Abort stops active generation

**Start a generation:**
```shell
docsfy generate https://github.com/myk-org/for-testing-only --provider gemini --model gemini-2.5-flash --force &
sleep 5
```

**Abort it:**
```shell
docsfy abort for-testing-only --branch main --provider gemini --model gemini-2.5-flash
```

**Expected result:**
- The CLI confirms the abort
- The generation status changes to `aborted`

**Verify:**
```shell
docsfy status for-testing-only
```

**Expected result:**
- The status shows `aborted` or `error`

---

### 24.11 Cleanup

**Delete any remaining CLI-created variants (both main and dev branches):**
```shell
docsfy delete for-testing-only --branch main --provider gemini --model gemini-2.5-flash --yes 2>/dev/null || true
docsfy delete for-testing-only --branch main --provider gemini --model gemini-2.0-flash --yes 2>/dev/null || true
docsfy delete for-testing-only --branch dev --provider gemini --model gemini-2.5-flash --yes 2>/dev/null || true
docsfy delete for-testing-only --branch dev --provider gemini --model gemini-2.0-flash --yes 2>/dev/null || true
```

**Expected result:** Variants are deleted or already gone.
