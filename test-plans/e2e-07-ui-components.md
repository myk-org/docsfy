# E2E UI Tests: Username Dropdown Menu and Variant Card Visual Hierarchy

> Back to the [main E2E index](e2e-ui-test-plan.md#test-files). Shared execution rules, prerequisites, variables, and environment constraints live there.

---

## Test 18: Username Dropdown Menu

### 18.1 Dashboard dropdown shows correct items for admin

**Precondition:** Log in as `admin`.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click ".username-dropdown, .user-menu-toggle, [data-dropdown-toggle]"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown menu appears with admin-specific items.

**Verify exact item order:**
```shell
agent-browser javascript "var items = Array.from(document.querySelectorAll('.user-menu-dropdown .user-menu-item')).filter(el => el.offsetParent !== null).map(el => el.textContent.trim()); JSON.stringify(items)"
```

**Expected result:**
- The dropdown menu is visible
- It contains "Admin Panel" (visible only for admin users)
- It contains "Change Password"
- It contains "Logout"
- The items appear in exact order: `["Admin Panel", "Change Password", "Logout"]`

---

### 18.2 Dashboard dropdown shows correct items for non-admin user

**Precondition:** Log in as `testuser-e2e`.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "testuser-e2e"
agent-browser type "#api_key" "<TEST_USER_PASSWORD>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
```

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click ".username-dropdown, .user-menu-toggle, [data-dropdown-toggle]"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown menu appears without admin-specific items.

**Verify exact item order:**
```shell
agent-browser javascript "var items = Array.from(document.querySelectorAll('.user-menu-dropdown .user-menu-item')).filter(el => el.offsetParent !== null).map(el => el.textContent.trim()); JSON.stringify(items)"
```

**Expected result:**
- The dropdown menu is visible
- It does NOT contain "Admin Panel"
- It contains "Change Password"
- It contains "Logout"
- The items appear in exact order: `["Change Password", "Logout"]`

---

### 18.3 Admin panel dropdown shows correct items

**Precondition:** Log in as `admin` and navigate to the admin panel.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/admin
```

**Commands:**
```shell
agent-browser click ".username-dropdown, .user-menu-toggle, [data-dropdown-toggle]"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown on the admin panel shows different items from the dashboard.

**Expected result:**
- The dropdown menu is visible
- It contains "Dashboard" (link back to main page)
- It contains "Logout"
- It does NOT show "Admin Panel" (already on admin page)

---

### 18.4 Click-outside closes dropdown

**Precondition:** The dropdown is open from the previous test step. If not, open it first.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click ".username-dropdown, .user-menu-toggle, [data-dropdown-toggle]"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown is open.

**Now click outside the dropdown:**
```shell
agent-browser click "body"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown closes when clicking outside.

**Expected result:**
- The dropdown menu is no longer visible
- The dropdown has lost its `active` or `open` class

---

### 18.5 Escape key closes dropdown

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser click ".username-dropdown, .user-menu-toggle, [data-dropdown-toggle]"
agent-browser wait 500
```

**Check:** The dropdown is open.

**Press Escape:**
```shell
agent-browser press "Escape"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The dropdown closes on Escape key.

**Expected result:**
- The dropdown menu is no longer visible
- The Escape key only closes the dropdown; it does not interfere with other page elements
- If a modal is also open, the Escape key should close the modal first (not steal focus from modals)

---

### 18.6 Escape key does not steal focus from modals

**Precondition:** Navigate to admin panel, open a modal, then verify Escape closes the modal (not the dropdown behind it).

```shell
agent-browser navigate http://localhost:8800/admin
agent-browser click "[data-delete-user='testviewer-e2e']"
agent-browser wait 1000
agent-browser screenshot
```

**Check:** The modal is open.

**Press Escape:**
```shell
agent-browser press "Escape"
agent-browser wait 500
agent-browser javascript "document.getElementById('custom-modal').style.display"
```

**Check:** The modal closes.

**Expected result:**
- The modal display is `"none"` (modal closed)
- The dropdown (if it was open behind the modal) remains unaffected
- Escape key targets the topmost overlay (modal) first

---

### 18.7 Theme toggle works independently (borderless text style)

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Check:** The theme toggle button exists and is styled independently from the dropdown.

```shell
agent-browser javascript "document.querySelector('#theme-toggle') !== null"
agent-browser javascript "window.getComputedStyle(document.querySelector('#theme-toggle')).borderWidth"
```

**Expected result:**
- The theme toggle exists (returns `true`)
- The theme toggle has a borderless text style (border-width is `0px` or the element has no visible border)
- The theme toggle is not inside the dropdown menu -- it operates independently

**Toggle theme:**
```shell
agent-browser click "#theme-toggle"
agent-browser javascript "document.documentElement.getAttribute('data-theme')"
```

**Expected result:**
- The theme changes (e.g., from `"dark"` to `"light"` or vice versa)
- The theme toggle works without opening or interacting with the dropdown menu

---

### 18.8 Cleanup

**Note:** Test 18 does not create any data. It only verifies dropdown UI behavior and theme toggling. No cleanup needed.

---

## Test 19: Variant Card Visual Hierarchy

### 19.1 Variant cards are indented under project headers

**Precondition:** Log in as `admin` to see multiple projects and variants.

```shell
agent-browser navigate http://localhost:8800/logout
agent-browser wait-for-navigation
agent-browser type "#username" "admin"
agent-browser type "#api_key" "<ADMIN_KEY>"
agent-browser click ".btn-login"
agent-browser wait-for-navigation
agent-browser navigate http://localhost:8800/
```

**Commands:**
```shell
agent-browser screenshot
agent-browser javascript "var header = document.querySelector('.group-header'); var card = document.querySelector('.variant-card'); header && card ? card.getBoundingClientRect().left > header.getBoundingClientRect().left : false"
```

**Check:** Variant cards are visually indented relative to the project header.

**Expected result:**
- Returns true --- variant card is indented relative to group header

**Verify via bounding rect comparison:**
```shell
agent-browser javascript "var h=document.querySelector('.group-header'); var c=document.querySelector('.variant-card'); h && c ? c.getBoundingClientRect().left >= h.getBoundingClientRect().left : false"
```

**Expected result:** returns `true`.

---

### 19.2 Variant cards have slightly different background from project header

**Commands:**
```shell
agent-browser javascript "const header = document.querySelector('.group-header'); const card = document.querySelector('.variant-card'); if (header && card) { ({headerBg: window.getComputedStyle(header).backgroundColor, cardBg: window.getComputedStyle(card).backgroundColor, different: window.getComputedStyle(header).backgroundColor !== window.getComputedStyle(card).backgroundColor}); } else { 'elements not found'; }"
```

**Check:** Variant cards have a distinct background color from the project header.

**Expected result:**
- The `different` field is `true` -- the background colors of the project header and variant card are not identical
- This visual distinction helps users differentiate between the project-level header and individual variant cards
- The difference should be subtle (e.g., a slightly lighter or darker shade) to maintain visual cohesion

**Screenshot for visual verification:**
```shell
agent-browser screenshot
```

**Expected result:**
- The project header has one background color
- The variant cards underneath have a slightly different background color
- The visual hierarchy is clear: project header sits above/contains the variant cards

---

### 19.3 Project groups are collapsible

**Precondition:** Logged in as `admin` on the dashboard with at least one project group visible.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Check:** Project groups have clickable headers that toggle visibility of their variant cards.

**Verify the project header is clickable:**
```shell
agent-browser javascript "const header = document.querySelector('.group-header'); header ? header.style.cursor || window.getComputedStyle(header).cursor : 'no header found'"
```

**Expected result:**
- The cursor style is `pointer` (indicating the header is clickable)

**Click the project header to collapse:**
```shell
agent-browser click ".group-header"
agent-browser wait 500
agent-browser screenshot
```

**Check:** The variant cards under the clicked project group are hidden.

**Expected result:**
- The variant cards within the project group are no longer visible (hidden via CSS class toggle, `display: none`, or `max-height: 0`)
- The project header remains visible
- A collapse indicator (chevron, arrow, or similar) changes direction to indicate collapsed state

**Verify cards are hidden:**
```shell
agent-browser javascript "const group = document.querySelector('.project-group'); const cards = group?.querySelectorAll('.variant-card'); cards ? Array.from(cards).every(c => c.offsetHeight === 0 || window.getComputedStyle(c).display === 'none' || c.closest('.collapsed, [data-collapsed]') !== null) : 'no cards found'"
```

**Expected result:** Returns `true` -- all variant cards in the group are hidden.

**Click again to expand:**
```shell
agent-browser click ".group-header"
agent-browser wait 500
agent-browser screenshot
```

**Expected result:**
- The variant cards are visible again
- The collapse indicator returns to the expanded state
- The cards render with their full content (status, buttons, etc.)

---

### 19.4 Project header shows ready/error variant counts

**Precondition:** Logged in as `admin` on the dashboard. At least one project group exists with variants.

**Commands:**
```shell
agent-browser navigate http://localhost:8800/
agent-browser screenshot
```

**Check:** The project header displays counts of ready and error variants.

```shell
agent-browser javascript "const header = document.querySelector('.group-header'); header ? header.textContent : 'no header found'"
```

**Expected result:**
- The header text includes count indicators for variant statuses (e.g., "2 ready", "1 error", or similar badge/count display)
- Ready count reflects the number of variants with `ready` status
- Error count reflects the number of variants with `error` or `aborted` status

**Verify counts match actual variant statuses:**
```shell
agent-browser javascript "const group = document.querySelector('.project-group'); if (group) { const readyCards = group.querySelectorAll('.variant-card[data-status=\"ready\"]').length; const errorCards = group.querySelectorAll('.variant-card[data-status=\"error\"], .variant-card[data-status=\"aborted\"]').length; ({readyCards, errorCards}); } else { 'no project group found'; }"
```

**Expected result:**
- The `readyCards` count matches the ready count displayed in the header
- The `errorCards` count matches the error count displayed in the header
- If all variants are ready and none are in error, the error count may be hidden (0 errors is not displayed)

---

### 19.5 Cleanup

**Note:** Test 19 does not create any data. It only verifies visual hierarchy, collapsible groups, and variant count display. No cleanup needed.
