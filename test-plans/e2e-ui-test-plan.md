# docsfy E2E UI Test Plan

## Mandatory AI Execution Workflow

These rules apply to every `###` test subsection in this plan.

1. Execute all required tests in order before reporting bugs or changing code.
2. For each test, satisfy the listed preconditions first, then execute every command block exactly in the order shown.
3. When a step says to capture a value, store it in the named variable and reuse it exactly. Never invent placeholder values.
4. If a test fails, record the failure, keep the evidence, and continue to the next required test. Do not start fixing yet.
5. If a test cannot run because an external prerequisite is missing, record it as `blocked` and continue unless that prerequisite blocks the rest of the plan.
6. Only after executing all required tests, report the collected failed tests and discovered bugs, and only then start fixing the bugs.
7. After fixing all bugs, re-run ONLY the previously failed tests with the fixed code. Repeat this fix-and-rerun cycle until all tests pass. The test plan is complete only when every test has passed.
8. **NEVER stop to ask the user if they want to continue.** Execute ALL tests from start to finish without pausing for confirmation. Do not ask "should I continue?", "this will take a long time, are you sure?", or any similar question. The user already told you to run all tests — run them.
9. **NEVER skip tests.** Every test section must be executed in order. Do not summarize, batch, or skip tests to "save time". Execute each test step exactly as written.
10. **NEVER suggest running a subset of tests.** When asked to run the e2e tests, that means ALL of them, every single one, in order.
11. **Log every test result to `UI-TESTS-RESULTS.md`.** As each `###` test subsection completes, append a row to `UI-TESTS-RESULTS.md` in the project root. Use this format:

    ```markdown
    # E2E UI Test Results

    **Run date:** YYYY-MM-DD HH:MM UTC
    **Branch:** <current git branch>
    **Commit:** <current HEAD short SHA>

    | Test | Name | Result | Details |
    |------|------|--------|---------|
    | 1.1 | Login page loads | PASS | |
    | 1.2 | Dark theme by default | PASS | |
    | 2.3 | Create viewer user | FAIL | Expected role "viewer" in table, got "user". Fixed in commit abc1234: corrected default role in admin.py |
    ```

    - Create the file with the header at the start of the test run
    - Append each result immediately after the test completes
    - For **PASS**: leave Details empty
    - For **FAIL**: describe what failed, what was expected vs actual, and if fixed: the commit SHA and what was changed
    - For **BLOCKED**: explain the blocker
    - At the end of the run, add a summary line: `**Total: X passed, Y failed, Z blocked out of N tests**`

12. **NEVER include private data in test plans, commits, PRs, or any git-tracked file.** API keys, passwords, tokens, and credentials must ONLY appear as runtime-captured variables (e.g., `<ADMIN_KEY>`, `<TEST_USER_PASSWORD>`). If you accidentally include a secret in a commit, immediately notify the user.

## Default Procedure For Every `###` Test

1. Execute the command block immediately below the subsection heading.
2. If the subsection contains additional command blocks later, execute them in the order they appear.
3. Treat every `**Check:**` block as a required assertion step.
4. Treat every `**Expected result:**` block as the pass/fail criteria for that subsection.
5. Treat every explicit branch such as `If 0, ...`, `If true, ...`, or `If the previous command returned ...` as a required decision point. Run the probe command first, take only the branch the plan specifies, and record which branch was taken.
6. When a shell block exports variables, execute later shell blocks from the same terminal session so those variables remain available.
7. When an expected result says `or similar`, accept only the literal examples listed or an exact equivalent with the same key text/function. If that is still ambiguous, record a failure instead of guessing that the test passed.
8. After every `agent-browser select` command, wait 500 milliseconds (`agent-browser wait 500`) before the next interaction to ensure DOM change events fire. The `agent-browser wait` command takes milliseconds as the argument.

## Standard Polling Procedure

Whenever this plan says `Wait for completion`, `poll until ready`, `wait if needed`, or `repeat every 5 seconds / 10 seconds`, use this exact polling procedure unless the subsection gives a different command:

1. Run the listed status command immediately.
2. If the status is already terminal (`ready`, `error`, or `aborted`), stop polling and record the result.
3. If the status is not terminal, wait the stated interval and run the same status command again.
4. Keep polling until the status becomes terminal or the subsection's stated timeout is reached.
5. If the terminal status is `error` or `aborted`, record a failed test and continue to the next required test.
6. If the timeout is reached with no terminal status, record the test as failed due to timeout and continue unless later tests depend on the missing result.

## Variable Capture Rules

1. Read `ADMIN_KEY` from `.dev/.env` at runtime and store it as `ADMIN_KEY`. Never hardcode the example value.
2. Replace every placeholder such as `<ADMIN_KEY>`, `<TEST_USER_PASSWORD>`, or `<USERB_PASSWORD>` with the exact captured value before running the next dependent step.
3. Trim surrounding whitespace from captured values before storing them.
4. If a required variable was never captured successfully, mark the dependent test as `blocked` and continue.

## Cleanup Expectations

> **Important:** Each test section is responsible for cleaning up ONLY the data it creates.
> Do NOT delete pre-existing projects, users, or variants that were not created by the test.
> Tests that only read data or verify UI behavior (no data creation) do not need cleanup steps.
> The final **Test 21: Cleanup and Teardown** provides a comprehensive inventory of all test-created artifacts and a full teardown procedure.

## Execution Environment

These rules apply to ALL tests in this plan. The AI runner MUST follow them without exception.

### Server
- **URL:** `http://localhost:8800` --- all tests run against this server
- **The AI NEVER starts or restarts the server.** If the server is down or unreachable, the AI MUST ask the user to bring the server up and wait for confirmation before continuing.

### Authentication
- **Admin API key:** Read from `.dev/.env` file, variable `ADMIN_KEY`
- The AI reads this value once at the start and uses it for all admin operations
- Never hardcode the admin key in test steps

### Test Repository
- **URL:** `https://github.com/myk-org/for-testing-only`
- **Branches:** `main` (default), `dev`
- This is the ONLY repository used for testing doc generation, incremental updates, model-switch / variant-reuse, and branch support scenarios
- **The AI MAY commit to this repository** when tests require a newer commit (e.g., incremental update tests). Use a trivial change (update a timestamp in README or add a test file) and push it. This is expected and necessary for testing incremental documentation updates.
- **When pushing changes to the test repo**, always use a branch + PR + merge workflow. NEVER push directly to main. Create a branch, commit, push, create PR with `gh pr create`, merge with `gh pr merge --merge --delete-branch`.

### AI Providers/Models
- **Only two models are used for generation tests:**
  - `gemini/gemini-2.5-flash`
  - `gemini/gemini-2.0-flash`
- The default provider/model check (Test 6.0) verifies the configured defaults, which may differ from the generation test models
- All doc generation steps must explicitly select the test model — never rely on defaults
- Cross-model coverage in this plan uses these two Gemini models (different models, same provider) to exercise the variant replacement/update behavior

## Prerequisites

- Server running at `http://localhost:8800` --- if not reachable, ask the user to start it
- ADMIN_KEY configured in `.dev/.env` (read from `.dev/.env` at runtime; do not hardcode)
- `agent-browser` available and operational
- Test repo: `https://github.com/myk-org/for-testing-only`
- AI providers/models for generation tests: `gemini/gemini-2.5-flash` and `gemini/gemini-2.0-flash`

## Variables Used Throughout

| Variable | Value |
|---|---|
| `SERVER` | `http://localhost:8800` |
| `ADMIN_KEY` | Read from `.dev/.env` at runtime and store as `ADMIN_KEY`; never hardcode |
| `ADMIN_USER` | `admin` |
| `TEST_REPO` | `https://github.com/myk-org/for-testing-only` |
| `AI_PROVIDER` | `gemini` |
| `AI_MODEL` | `gemini-2.5-flash` |
| `AI_MODEL_ALT` | `gemini-2.0-flash` |
| `TEST_USER` | `testuser-e2e` |
| `TEST_ADMIN` | `testadmin-e2e` |
| `TEST_VIEWER` | `testviewer-e2e` |
| `USERB` | `userb-e2e` |
| `TEST_BRANCH` | `main` |
| `TEST_BRANCH_ALT` | `dev` |

Passwords for created users will be captured at creation time and stored in variables:
- `TEST_USER_PASSWORD`
- `TEST_ADMIN_PASSWORD`
- `TEST_VIEWER_PASSWORD`
- `USERB_PASSWORD`

---

## Test Files

This index keeps the shared execution rules, environment constraints, variables, and overall test map.
Each linked sub-file contains only the detailed test bodies for its assigned sections and should link back here for the shared context above.

| File | Tests | Description |
|---|---|---|
| [e2e-01-auth-and-roles.md](e2e-01-auth-and-roles.md) | 1-5 | Login, Admin Panel, User/Viewer/Admin role permissions |
| [e2e-02-generation-and-dashboard.md](e2e-02-generation-and-dashboard.md) | 6-7 | Doc Generation (default provider/model verification, branch combobox), Dashboard Features |
| [e2e-03-docs-quality-and-ui.md](e2e-03-docs-quality-and-ui.md) | 8-10 | Generated Docs Quality, Status Page, Custom Modals |
| [e2e-04-isolation-and-auth.md](e2e-04-isolation-and-auth.md) | 11-13 | Cross-User Isolation, Logout, Direct URL Authorization |
| [e2e-05-incremental-updates.md](e2e-05-incremental-updates.md) | 14, 16-17 | Incremental Documentation Updates, JSON Patch, Progress Page |
| [e2e-06-delete-and-owner.md](e2e-06-delete-and-owner.md) | 15 | Delete with Owner Scoping |
| [e2e-07-ui-components.md](e2e-07-ui-components.md) | 18-19 | Username Dropdown Menu, Variant Card Visual Hierarchy |
| [e2e-08-cross-model-updates.md](e2e-08-cross-model-updates.md) | 20 | Cross-Model Incremental Updates |
| [e2e-10-branch-support.md](e2e-10-branch-support.md) | 22 | Branch Support (including regenerate with different branch) |
| [e2e-09-cleanup.md](e2e-09-cleanup.md) | 21 | Cleanup and Teardown |

**`e2e-09-cleanup.md` must always be executed last, after all other test files.**

---

## Summary

| Test | Area | Sub-tests |
|---|---|---|
| 1 | Login Page | 1.1-1.6 |
| 2 | Admin Panel | 2.1-2.9 |
| 3 | User Role Permissions | 3.1-3.6 |
| 4 | Viewer Role Permissions | 4.1-4.7 |
| 5 | Admin Role (DB user) Permissions | 5.1-5.4 |
| 6 | Doc Generation (via User) | 6.0-6.7 |
| 7 | Dashboard Features | 7.1-7.10 |
| 8 | Generated Docs Quality | 8.1-8.7 |
| 9 | Status Page | 9.1-9.3 |
| 10 | Custom Modals | 10.1-10.4 |
| 11 | Cross-User Isolation | 11.1-11.10 |
| 12 | Logout | 12.1-12.2 |
| 13 | Direct URL Authorization | 13.1-13.7 |
| 14 | Incremental Documentation Updates | 14.1-14.6 |
| 15 | Delete with Owner Scoping | 15.1-15.7 |
| 16 | Incremental Page JSON Patch | 16.1-16.3 |
| 17 | Progress Page During Regeneration | 17.1-17.4 |
| 18 | Username Dropdown Menu | 18.1-18.8 |
| 19 | Variant Card Visual Hierarchy | 19.1-19.5 |
| 20 | Cross-Model Incremental Updates | 20.1-20.5 |
| 22 | Branch Support | 22.1-22.11 |
| 21 | Cleanup and Teardown | 21.1-21.5 |
