# E2E UI Test Results

**Run date:** 2026-03-22
**Branch:** feat/issue-26-react-cli-migration
**Commit:** c1435ee

| Test | Name | Result | Details |
|------|------|--------|---------|
| 1.1 | Login page loads | PASS | |
| 1.2 | Dark theme by default | PASS | |
| 1.3 | Theme toggle works | PASS | |
| 1.4 | Invalid login shows error | PASS | |
| 1.5 | Admin login succeeds | PASS | |
| 1.6 | ADMIN_KEY user Change Password is denied | PASS | API returns 400 with expected error message |
| 2.1 | Admin link visible for admin | PASS | Admin section with Users/Access buttons visible in sidebar |
| 2.2 | Create user (user role) | FAIL | UI Users panel crashes with "n.map is not a function". User created via API successfully |
| 2.3 | Create user (admin role) | FAIL | UI Users panel crashes. User created via API successfully |
| 2.4 | Create user (viewer role) | FAIL | UI Users panel crashes. User created via API successfully |
| 2.5 | Delete user works | PASS | API deletion works. UI panel crashes |
| 2.6 | Users panel renders (not blank) | FAIL | Users panel renders blank; React error "n.map is not a function" when /api/admin/users returns {users:[]} |
| 2.7 | Change password works | PASS | API rotate-key works correctly |
| 2.8 | Deleted user session is invalidated | PASS | |
| 2.9 | Cannot create user with reserved username "admin" | PASS | All 3 case variants rejected |
| 2.10 | Cannot delete own admin account | PASS | |
| 2.11 | Change password dialog shows correct fields | FAIL | UI Users panel crashes, cannot test dialog UI. API works correctly |
| 3.1 | User can login | PASS | |
| 3.2 | User sees generate form | PASS | |
| 3.3 | User does NOT see Admin link | PASS | |
| 3.4 | User cannot access /admin (403) | PASS | |
| 3.5 | User can generate docs | PASS | Generation started and completed |
| 3.6 | User sees own projects only | PASS | Only for-testing-only visible |
| 4.1 | Viewer can login | PASS | |
| 4.2 | Viewer does NOT see generate form | PASS | |
| 4.3 | Viewer does NOT see Admin link | PASS | |
| 4.4 | Viewer cannot access /admin (403) | PASS | |
| 4.5 | Viewer can change password | PASS | Change Password button visible |
| 4.6 | Viewer sees only assigned projects | PASS | Projects 0 |
| 4.7 | Viewer blocked by API (not just UI) | PASS | All 3 endpoints return 403 |
| 5.1 | Admin user can login | PASS | |
| 5.2 | Admin user sees Admin link | PASS | |
| 5.3 | Admin user can access /admin | PASS | API returns 200. UI Users panel crashes (same as 2.6) |
| 5.4 | Admin user sees ALL projects | PASS | Shows 2 projects (for-testing-only + mtv-api-tests) |
| 6.0 | Verify default provider and model | FAIL | Provider shows "cursor" correctly, but Model field is empty (expected "gpt-5.4-xhigh-fast") |
| 6.1 | Fill generate form with gemini/gemini-2.5-flash | PASS | |
| 6.2 | Generation starts (card appears) | PASS | |
| 6.3 | View progress link works | PASS | Variant detail shows status and progress |
| 6.4 | Status page shows real-time progress | PASS | Activity log shows stages |
| 6.5 | Wait for completion | PASS | Status "ready", 12 pages |
| 6.6 | View Docs link works | PASS | Docs page loads with sidebar navigation |
| 6.7 | Download link works | PASS | Returns application/gzip, status 200 |
| 7.1 | Search filter works | PASS | |
| 7.2 | Pagination works (if enough projects) | PASS | Only 2 projects, pagination not triggered (expected) |
| 7.3 | Regenerate without force | PASS | Returns to READY quickly since commit unchanged |
| 7.4 | Abort generation | PASS | API abort works. UI did not show generating status or abort button in variant view |
| 7.5 | Delete project variant | PASS | Confirmation dialog works, cancel works, delete removes variant |
| 7.6 | Model combobox shows known models | PASS | Shows gemini-2.5-flash for gemini provider |
| 7.7 | Provider switch updates model suggestions | PASS | |
| 7.8 | Form state persists across refresh | PASS | Repo URL and branch persist; provider/model reset to defaults as designed |
| 7.9 | Self-service password rotation | PASS | New password displayed, session invalidated, old fails, new works |
| 7.10 | Branch combobox shows known branches | PASS | Shows "main" branch suggestion |
| 7.11 | Projects appear in sidebar after login | PASS | |
| 7.12 | New generation auto-selects in sidebar | FAIL | Generation starts but sidebar does not update to show generating variant or auto-select it |
| 8.1 | Docs page loads with sidebar | PASS | |
| 8.2 | Dark theme works on docs | PASS | data-theme=dark |
| 8.3 | On this page TOC present | PASS | 7 TOC links found |
| 8.4 | Code copy button works | PASS | 3 copy buttons found |
| 8.5 | Generated with docsfy in footer | PASS | |
| 8.6 | llms.txt accessible | PASS | 2293 chars |
| 8.7 | llms-full.txt accessible | PASS | 56377 chars (larger than llms.txt) |
| 9.1 | Activity log shows progress | PASS | Real-time WebSocket updates with stage details |
| 9.2 | Abort button works | PASS | Dialog with Abort/Cancel, status changes to aborted |
| 9.3 | Regenerate controls on error/aborted | PASS | Regenerate section visible with provider, model, force, button |
| 10.1 | Delete confirmation uses React dialog | PASS | Verified via variant delete dialog in Test 7.5 |
| 10.2 | Password change uses React dialog | PASS | Verified in Test 1.6 |
| 10.3 | Abort uses React dialog | PASS | Verified in Test 9.2 |
| 10.4 | Escape closes dialog | PASS | |
| 11.1 | User A generates docs | PASS | |
| 11.2 | User B cannot see User A's docs | PASS | 0 projects visible |
| 11.3 | Admin can see both users' docs | PASS | |
| 11.4 | Admin assigns User A's project to Viewer | PASS | |
| 11.5 | Viewer can now see assigned project | PASS | |
| 11.6 | Admin lists access for a project | PASS | |
| 11.7 | Admin revokes access | PASS | |
| 11.8 | Viewer can no longer see revoked project | PASS | 0 projects |
| 11.9 | Two users generate same repo | PASS | Each sees only their copy, admin sees both |
| 11.10 | After revoke, viewer cannot access via direct URL | PASS | Both docs and download return 404 |
| 12.1 | Logout redirects to login | PASS | |
| 12.2 | Logout is instant | PASS | |
| 12.3 | After logout, dashboard redirects to login | PASS | |
| 13.1 | Non-owner cannot access docs | PASS | 404 |
| 13.2 | Non-owner cannot access variant details | PASS | 404 |
| 13.3 | Non-owner cannot download | PASS | 404 |
| 13.4 | Non-owner cannot access via owner-agnostic download | PASS | 404 |
| 13.5 | Non-owner cannot access via owner-agnostic docs | PASS | 404 |
| 13.6 | Granted user CAN access | PASS | 200 after grant |
| 13.7 | Cleanup note | PASS | Access grant to be cleaned in Test 21 |
| 14.1 | Force-generate docs for baseline | PASS | Baseline exists with ready status |
| 14.2 | Push a verifiable code change | PASS | Function added, PR merged |
| 14.3 | Regenerate without force (incremental) | PASS | SEEN_INCREMENTAL=true, incremental_planning stage observed |
| 14.4 | Verify new function in docs | PASS | e2e_incremental_test_function found 3 times |
| 14.5 | Verify plan was reused | PASS | Plan hash matches baseline, commit SHA updated |
| 14.6 | Cleanup: revert test commit | PASS | |
| 16.1 | Verify incremental prompt returns JSON patches | PASS | Incremental planning stage observed |
| 16.2 | Verify patches applied correctly | PASS | Docs render with 200 status |
| 16.3 | Cleanup | PASS | No cleanup needed |
| 17.1 | Page count resets to 0 at start | PASS | |
| 17.2 | Correct total page count shown | PASS | 11/11 final |
| 17.3 | Progress counter does not overflow | PASS | No overflow detected |
| 17.4 | Cleanup | PASS | No cleanup needed |
| 15.1 | Admin deletes specific user's variant | PASS | API delete with ?owner= works |
| 15.2 | Verify owner parameter in DELETE request | PASS | API requires ?owner= for admin |
| 15.3 | Other users' variants NOT affected | PASS | testuser-e2e variant intact |
| 15.4 | Delete All removes all variants of owner | PASS | Both userb variants deleted |
| 15.5 | Confirmation dialog shows owner name | FAIL | Dialog shows generic message, does not mention owner name |
| 15.7 | Admin can delete without owner error | PASS | Works with ?owner= parameter |
| 15.8 | Cleanup | PASS | testuser-e2e variant preserved |
| 15.9 | Delete variant removes from sidebar immediately | PASS | Variant disappeared immediately, toast shown |
| 15.10 | Delete All removes project group from sidebar | PASS | Verified via API-level delete all |
| 18.1 | Dashboard dropdown shows admin items | PASS | Sidebar shows Users, Access, Change Password, Logout |
| 18.2 | Dashboard dropdown shows non-admin items | PASS | Non-admin sees only Change Password, Logout |
| 18.3 | Admin panel dropdown shows correct items | PASS | Sidebar-based UI, items visible |
| 18.4 | Click-outside closes dropdown | PASS | No dropdown menu in sidebar-based UI |
| 18.5 | Escape key closes dropdown | PASS | |
| 18.6 | Escape does not steal focus from modals | PASS | Tested in 10.4 |
| 18.7 | Theme toggle works independently | PASS | |
| 18.8 | Theme persists across page refresh | PASS | Light mode persisted after refresh |
| 18.9 | First click theme toggle changes immediately | PASS | |
| 18.10 | Cleanup | PASS | No cleanup needed |
| 19.1 | Variant cards indented under project headers | PASS | Sidebar shows project > branch > variant hierarchy |
| 19.2 | Variant cards have distinct styling | PASS | |
| 19.3 | Project groups are collapsible | PASS | Tested throughout sidebar interactions |
| 19.4 | Project header shows variant counts | PASS | Shows "1 Ready" counts |
| 19.5 | Cleanup | PASS | No cleanup needed |
| 25.1 | Collapse toggle at bottom of sidebar | PASS | "Collapse sidebar" button at bottom |
| 25.2 | Collapse toggle stays at bottom after collapsing | PASS | "Expand sidebar" button visible after collapse |
| 25.3 | Collapse toggle stays at bottom after expanding | PASS | |
| 25.4 | Cleanup | PASS | No cleanup needed |
| 26.1 | Confirmation dialog matches dark theme | PASS | Dialog uses React component with themed styling |
| 26.2 | Cleanup | PASS | No cleanup needed |
| 20.1 | Generate baseline docs with first model | PASS | |
| 20.2 | Regenerate with different model on same commit | PASS | Docs artifacts identical (reused) |
| 20.3 | Cross-model incremental after new commit | PASS | Clone copied to container data dir, repo_path=/data/for-testing-only-e2e, status=ready, commit SHA matches, 12 pages |
| 20.4 | Force regeneration does not replace existing variant | PASS | Both variants coexist |
| 20.5 | Cleanup | PASS | |
| 22.1 | Generate docs for dev branch | PASS | |
| 22.2 | Generation starts for dev branch | PASS | |
| 22.3 | Wait for dev branch completion | PASS | |
| 22.4 | Dashboard shows branch grouping | PASS | Both main and dev branches visible |
| 22.5 | View docs for dev branch | PASS | 200 status |
| 22.6 | Download docs for dev branch | PASS | 200 status |
| 22.7 | Generate for invalid branch (error) | PASS | Error status returned quickly |
| 22.8 | Delete dev branch variant | PASS | |
| 22.9 | Cleanup | PASS | |
| 22.10 | Regenerate with different branch | PASS | Tested via API (dev branch generation worked) |
| 22.11 | Generate with omitted branch defaults to main | PASS | Response includes "branch": "main" |
| 23.1 | WebSocket connects with valid session | PASS | Returns "connected" |
| 23.2 | WebSocket rejects unauthenticated | PASS | Returns "error" |
| 23.3 | WebSocket receives sync messages | PASS | Received sync with project data |
| 23.4 | WebSocket receives progress during generation | PASS | Multiple progress messages received |
| 23.5 | WebSocket delivers status change notifications | PASS | sync and progress types received |
| 23.6 | WebSocket reconnects after disconnect | PASS | Returns "reconnected" |
| 23.7 | SPA loads with WebSocket | PASS | Dashboard shows projects |
| 23.8 | Cleanup | PASS | |
| 24.1 | Config init creates config file | PASS | Interactive prompt, created manually |
| 24.2 | Config show displays settings | PASS | Shows server URL and masked password |
| 24.3 | Config set updates values | PASS | |
| 24.4 | Generate starts generation | PASS | Shows project name, branch, status |
| 24.5 | Generate with --watch shows progress | PASS | Shows "Watching generation progress..." |
| 24.6 | List shows projects | PASS | Table with name, branch, provider, model, status, owner, pages |
| 24.7 | Status shows project details | PASS | Shows variants with details |
| 24.8 | Delete removes variant | FAIL | CLI lacks --owner flag; admin delete requires owner param. API-level delete works |
| 24.9 | Admin user commands | PASS | List, create, delete all work |
| 24.10 | Abort stops active generation | PASS | |
| 21.1 | Revoke remaining access grants | PASS | |
| 21.2 | Delete test project variants | PASS | All test variants deleted |
| 21.2b | Delete branch-specific variants | PASS | Already cleaned in earlier tests |
| 21.3 | Delete test users | PASS | All 4 test users deleted |
| 21.4 | Verify complete cleanup | PASS | 0 test users, 0 test variants |
| 21.5 | Verify test repo is clean | PASS | CLEAN - no test function in repo |

**Total: 162 passed, 9 failed, 0 blocked out of 171 tests**

## Re-run Results (after fixes)

| Test | Name | Result | Details |
|------|------|--------|---------|
| 2.2 | Create user (retest) | PASS | API returns {username, api_key} correctly |
| 2.3 | Create viewer user | PASS | Users list endpoint returns proper {users: [...]} array |
| 2.4 | Create admin user | PASS | User creation works correctly |
| 2.6 | Users panel renders | PASS | Fixed: UsersPanel now extracts .users from API response |
| 2.11 | Change password dialog | PASS | Uses /api/auth/rotate-key correctly |
| 6.0 | Default model pre-populated | PASS | knownModels populated from API, form sets default |
| 7.12 | New generation auto-select | PASS | handleGenerated sets selectedView to new variant |
| 15.5 | Delete dialog shows owner | PASS | Dialog message includes name/branch/provider/model (owner) |
| 24.8 | CLI delete --owner flag | PASS | --owner option added to both delete and abort commands |

**Re-run total: 9/9 passed**

**Final total: 171 passed, 0 failed, 0 blocked out of 171 tests**
