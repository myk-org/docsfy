# Test 34: Image Support in Documentation

[Back to Test Plan Index](e2e-ui-test-plan.md)

## Prerequisites

- Server running at `http://localhost:8800`
- `ADMIN_KEY` read from `.dev/.env` at runtime (see [test plan index](e2e-ui-test-plan.md#variable-capture-rules))
- Test repo: `https://github.com/myk-org/for-testing-only`

---

### 34.1 Generation without docsfy-images/ folder

Generate docs for a repo that does NOT have a `docsfy-images/` folder.

```bash
curl -s -X POST -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/generate" \
  -d "{\"repo_url\": \"$TEST_REPO\", \"ai_provider\": \"$AI_PROVIDER\", \"ai_model\": \"$AI_MODEL\"}"
```

Poll until ready. Then check the generated site:

```bash
curl -s -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/docs/for-testing-only/main/$AI_PROVIDER/$AI_MODEL/images/" -o /dev/null -w "%{http_code}"
```

**Expected result:** 404 — no `images/` directory created in the site output when the repo has no `docsfy-images/` folder. Zero overhead.

---

### 34.2 Generation with docsfy-images/ folder and manifest

Create a branch in the test repo with a `docsfy-images/` folder containing images and an `images.yaml` manifest. Push to test repo via PR workflow.

**Expected result:** Generation completes. The `cataloging_images` stage appears in progress updates. Generated pages may include `![description](images/filename)` references. The site output has an `images/` directory containing the copied image files.

---

### 34.3 Generation with docsfy-images/ folder without manifest

Same as 34.2 but without `images.yaml`. The AI should describe images using vision.

**Expected result:** Generation completes. Images are described automatically. The site output has `images/` directory.

---

### 34.4 Vision provider/model via API

```bash
curl -s -X POST -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  "$SERVER/api/generate" \
  -d "{\"repo_url\": \"$TEST_REPO\", \"ai_provider\": \"$AI_PROVIDER\", \"ai_model\": \"$AI_MODEL\", \"vision_provider\": \"gemini\", \"vision_model\": \"gemini-2.5-flash\"}"
```

**Expected result:** HTTP 202. Vision provider/model are accepted by the API.

---

### 34.5 Vision provider/model via CLI

```bash
docsfy generate "$TEST_REPO" \
  --provider "$AI_PROVIDER" --model "$AI_MODEL" \
  --vision-provider gemini --vision-model gemini-2.5-flash
```

**Expected result:** Generation starts. CLI accepts `--vision-provider` and `--vision-model` flags.

---

### 34.6 Vision provider/model in UI

Navigate to the generate form. Check for Vision Provider and Vision Model fields.

**Expected result:** Vision Provider select shows "Same as generation provider" plus provider options. When a vision provider is selected, Vision Model combobox appears filtered by that provider.

---

### 34.7 Vision provider/model in admin settings

Navigate to Admin → Settings. Check for Vision AI Provider and Vision AI Model fields.

**Expected result:** Fields exist in the "Vision (Image Description)" group. Can be set independently of generation defaults. Setting them affects default vision behavior for all generations.

---

### 34.8 cataloging_images stage appears in progress

During a generation of a repo with `docsfy-images/`, monitor progress via WebSocket or polling.

**Expected result:** The `cataloging_images` stage appears between `analyzing` and `planning` stages.

---

### 34.9 Cleanup

Delete any test variants created during this test:
```bash
curl -s -X DELETE -H "Authorization: Bearer $ADMIN_KEY" \
  "$SERVER/api/projects/for-testing-only?owner=admin"
```
