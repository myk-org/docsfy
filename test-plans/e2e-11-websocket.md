# E2E UI Tests: WebSocket Connection and Real-Time Updates

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 23: WebSocket

### 23.1 WebSocket connection establishes with valid session

**Precondition:** Log in as `testuser-e2e`.

```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

**Commands:**
```shell
agent-browser javascript "new Promise(resolve => { const ws = new WebSocket('ws://localhost:8800/api/ws'); ws.onopen = () => { resolve('connected'); ws.close(); }; ws.onerror = () => resolve('error'); setTimeout(() => resolve('timeout'), 5000); })"
```

**Expected result:**
- Returns `"connected"`
- The WebSocket connection opens successfully with the session cookie

---

### 23.2 WebSocket rejects unauthenticated connection

**Commands:**
```shell
agent-browser javascript "fetch('/api/auth/logout', {method:'POST', credentials:'same-origin'})"
agent-browser wait 1000
agent-browser javascript "new Promise(resolve => { const ws = new WebSocket('ws://localhost:8800/api/ws'); ws.onopen = () => { resolve('connected'); ws.close(); }; ws.onclose = (e) => resolve('closed:' + e.code); ws.onerror = () => resolve('error'); setTimeout(() => resolve('timeout'), 5000); })"
```

**Expected result:**
- Returns `"closed:1008"` or `"error"` (WebSocket rejects without valid auth)
- The connection does NOT open for unauthenticated clients

---

### 23.3 WebSocket receives sync messages

**Precondition:** Log in as `testuser-e2e`.

```shell
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

**Commands:**
```shell
agent-browser javascript "new Promise(resolve => { const ws = new WebSocket('ws://localhost:8800/api/ws'); const msgs = []; ws.onmessage = (e) => { msgs.push(JSON.parse(e.data)); if (msgs.length >= 1) { resolve(JSON.stringify(msgs[0])); ws.close(); } }; ws.onerror = () => resolve('error'); setTimeout(() => { resolve(msgs.length > 0 ? JSON.stringify(msgs[0]) : 'no messages'); ws.close(); }, 10000); })"
```

**Expected result:**
- A message is received (the server sends an initial sync or ping)
- The message has a `type` field (e.g., `"sync"` or `"ping"`)

---

### 23.4 WebSocket receives progress updates during generation

**Precondition:** Start a generation while the WebSocket is connected.

**Commands:**
```shell
agent-browser javascript "window.__wsMessages = []; const ws = new WebSocket('ws://localhost:8800/api/ws'); ws.onmessage = (e) => { window.__wsMessages.push(JSON.parse(e.data)); }; ws.onopen = () => { window.__wsConnected = true; }; ws.onerror = () => { window.__wsConnected = false; };"
agent-browser wait 2000
```

Now start a generation:
```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', ai_provider:'gemini', ai_model:'gemini-2.5-flash', force:true})}).then(r => r.status)"
agent-browser wait 10000
```

Check received messages:
```shell
agent-browser javascript "JSON.stringify(window.__wsMessages.filter(m => m.type === 'status_change' || m.type === 'progress').slice(0, 3))"
```

**Expected result:**
- At least one `status_change` or `progress` message is received
- The messages contain project name, status, and/or progress information

---

### 23.5 WebSocket delivers status change notifications

**Commands:**
```shell
agent-browser javascript "window.__wsMessages.filter(m => m.type === 'status_change').length"
```

**Expected result:**
- Returns at least `1` (status changed from idle to generating, or generating to ready/error)

---

### 23.6 WebSocket reconnects after disconnect

**Commands:**
```shell
agent-browser javascript "window.__wsMessages = []; new Promise(resolve => { const ws = new WebSocket('ws://localhost:8800/api/ws'); ws.onopen = () => { ws.close(); setTimeout(() => { const ws2 = new WebSocket('ws://localhost:8800/api/ws'); ws2.onopen = () => { resolve('reconnected'); ws2.close(); }; ws2.onerror = () => resolve('reconnect_error'); }, 1000); }; ws.onerror = () => resolve('error'); setTimeout(() => resolve('timeout'), 10000); })"
```

**Expected result:**
- Returns `"reconnected"`
- A new WebSocket connection can be established after the previous one closes

---

### 23.7 SPA falls back to polling when WebSocket unavailable

**Note:** This test verifies the fallback behavior. If the WebSocket server is down, the React SPA should fall back to polling the API for status updates.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser wait 2000
agent-browser screenshot
```

**Expected result:**
- The dashboard loads and shows project data even if WebSocket connection fails initially
- The SPA gracefully degrades to API polling

---

### 23.8 Activity log updates continuously during long generation

**Precondition:** Log in as `testuser-e2e` and navigate to the dashboard.

```shell
agent-browser navigate http://localhost:8800/login
agent-browser type "[name='username']" "testuser-e2e"
agent-browser type "[name='password']" "<TEST_USER_PASSWORD>"
agent-browser click "button[type='submit']"
agent-browser wait-for-navigation
```

Start a generation and stay on the page without refreshing:

```shell
agent-browser javascript "fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body:JSON.stringify({repo_url:'https://github.com/myk-org/for-testing-only', ai_provider:'gemini', ai_model:'gemini-2.5-flash', force:true})}).then(r => r.status)"
```

Wait for generation to progress through multiple pages (do NOT refresh):

```shell
agent-browser wait 30000
agent-browser screenshot
```

Check that the activity log in the UI has updated beyond the initial cloning/planning events:

```shell
agent-browser javascript "document.querySelectorAll('[class*=\"activity\"] li, [class*=\"log\"] li, [class*=\"progress\"] li').length"
```

**Expected result:**
- The activity log shows progress entries beyond initial cloning and planning
- Page-level progress entries (e.g., "Page 1 of N: ...") are visible WITHOUT requiring a page refresh
- The screenshot shows current generation progress, not stale initial state

**Bug reference:** [#33](https://github.com/myk-org/docsfy/issues/33) — WebSocket progress activity log stops updating when page stays open

---

### 23.9 Cleanup

**Note:** Test 23 does not create persistent data (the generation started in 23.4 uses existing test infrastructure). Clean up the WebSocket state:

```shell
agent-browser javascript "delete window.__wsMessages; delete window.__wsConnected;"
```

Wait for any active generation to complete or abort:
```shell
agent-browser javascript "fetch('/api/projects/for-testing-only/main/gemini/gemini-2.5-flash/abort', {method:'POST', credentials:'same-origin'}).then(r => r.status)"
agent-browser wait 3000
```

**Expected result:** Returns `200` (aborted) or `404` (no active generation). Both are acceptable.
