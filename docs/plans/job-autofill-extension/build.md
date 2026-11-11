# Job application autofill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `job-autofill/`: an MV3 Chrome extension plus a stdlib Python helper on 127.0.0.1 that fill ATS application forms from Roosevelt's profile, draft open answers with Claude/OpenAI (always yellow), and continue/submit only on opted-in runs that pass every safety check.

**Architecture:** The helper owns profile import, Keychain keys, AI calls, answer cache and run log under `JOB_AUTOFILL_HOME`. The extension (no build step, plain scripts) syncs profile + resume bytes from the helper, and its content script walks frames/Shadow DOM, fills via per-host adapters then a generic label matcher, reads every value back, highlights, and drives the wizard/submit state machine. Run state lives in `chrome.storage.session` so the service worker can sleep.

**Tech Stack:** Python 3.9+ stdlib (`http.server`, `urllib`, `subprocess security`), Chrome MV3 JS, `node --test`, Playwright (`@playwright/test`, Chromium) as the only dev dependency.

**Spec:** `docs/plans/job-autofill-extension/rd.md`, acceptance `eval.md` (approved 2026-11-11), design bar `mockup.html`.

## Global Constraints

- Every test backing an eval case is named `<ID>: …` (JS) or `test_<ID>_…` (Python).
- Helper binds `127.0.0.1` only; default port `8766`; requests need header `X-Job-Autofill-Token` and `Origin: chrome-extension://…`, else 403 empty body.
- `JOB_AUTOFILL_HOME` default `~/.config/job-autofill/`, dir 0700, files 0600. Nothing personal inside the repo.
- Keychain services `job-autofill-anthropic`, `job-autofill-openai`; `JOB_AUTOFILL_KEYCHAIN=fake:<file>` swaps in a JSON-file keychain for tests.
- Provider base URLs overridable by `JOB_AUTOFILL_ANTHROPIC_URL` / `JOB_AUTOFILL_OPENAI_URL` (tests point both at `tests/fake_provider.py`). No model id literals in source (U13 grep).
- Colors: green `#16a34a` (`rgb(22, 163, 74)`), amber `#ca8a04`; tooltips prefixed `AutoFill: `.
- Manifest permissions ⊆ `storage, unlimitedStorage, scripting, activeTab, debugger, tabs`; `host_permissions` = `["http://127.0.0.1/*"]`; content scripts `<all_urls>`, `all_frames: true`.
- Playwright browsers at `job-autofill/.cache/ms-playwright`; `TMPDIR` on the USB volume. Gitignore `node_modules .cache test-results playwright-report` under `job-autofill/`.
- Daily AI cap default 30; helper AI timeout 20 s; confirmation wait 15 s; wizard settle 850 ms; max 10 steps; idle end 5 min.
- No reference to `interviews/`, `job-applications`, `workspace/agents`, `dashboard-app`, `.opencode/agents`, `job-application-submission-loop` (R3).
- Fixture person "Jordan Avery"; no real contact data anywhere (R5).

## Review Focus

- Site re-renders a field after fill (React controlled input reset on next tick) → read-back runs after a 150 ms settle, not synchronously. Test in Task 6 (`U19`/`F5` fixtures reset on a timer).
- Same question asked on two steps of one wizard → answer cache hit, one AI call. Covered by Task 4 cache key + Task 8 U25.
- Popup closed mid-run → run continues from content script; popup reopening reads `chrome.storage.session`. Task 8 asserts popup reopen shows running state.
- `resume/master.md` edited between syncs → next sync replaces imported fields; manual fields untouched. Task 2 test `test_U2_resync_keeps_manual`.
- Two tabs running at once → run state keyed by tabId; submit-once guard per tab+URL. Task 7 test `F6: second tab independent`.

---

## File map

```text
job-autofill/
  README.md  package.json  playwright.config.mjs  .gitignore
  helper/ server.py store.py profile_import.py ai.py keychain.py launchd/com.cloudtransition.job-autofill.plist
  extension/ manifest.json background.js
    content/ util.js scorer.js matcher.js adapters.js fill.js safety.js wizard.js hud.js main.js
    popup/ popup.html popup.css popup.js
  tests/ unit/*.test.mjs  helper/test_*.py  e2e/*.spec.mjs  e2e/harness.mjs
         fixtures/ats/*  fixtures/master.fixture.md  fixtures/resume.fixture.pdf
         fake_provider.py  check_no_personal_data.py
```

Content scripts are classic scripts sharing one `globalThis.AF` namespace (MV3 content scripts can't be ES modules); each file also exports via `if (typeof module !== 'undefined') module.exports = …` so `node --test` can load `scorer.js`, `matcher.js`, `safety.js`, and the draft post-processor.

### Task 1: Scaffold, harness, fixtures

**Files:** create `package.json`, `playwright.config.mjs`, `.gitignore`, `tests/e2e/harness.mjs`, `tests/fixtures/master.fixture.md`, `tests/fixtures/resume.fixture.pdf` (tiny valid PDF), `tests/check_no_personal_data.py`, `extension/manifest.json`; append `/job-autofill/node_modules/` etc. to root `.gitignore` only if nested ignore doesn't satisfy `git check-ignore`.

**Interfaces — Produces:**
- npm scripts: `test:unit` = `node --test tests/unit/`; `test:helper` = `python3 -m unittest discover -s tests/helper`; `test:e2e` = `playwright test`; `test` = all three; `check` = `node scripts/check.mjs` (node --check every extension js, manifest assertions, `python3 -m py_compile helper/*.py`).
- `harness.mjs`: `launch({fallback=true, helper=true}) -> {context, extId, page, helper:{port, token, home, stop()}, provider:{port, requests(), setMode(m)}, fixtureUrl(name, port='A'|'B')}`; `runAutofill(page, {submit=false}) -> summary` (opens popup URL `chrome-extension://<id>/popup/popup.html?tab=<tabId>` and clicks).
- Static server serving `tests/fixtures/ats/` on two ports.

- [ ] Write `R2` check script and `R5` checker (reads the real `resume/master.md` header line, extracts phone/email/LinkedIn/GitHub handles, greps `job-autofill/` and `eval-evidence/`; exits 1 on hit).
- [ ] `npm i -D @playwright/test && PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright npx playwright install chromium`.
- [ ] Smoke spec `harness: extension loads` passes; `npm run check` passes; commit `feat(job-autofill): scaffold and harness`.

### Task 2: Helper store, profile import, pairing, server

**Files:** `helper/store.py`, `helper/profile_import.py`, `helper/keychain.py`, `helper/server.py`; tests `tests/helper/test_store.py`, `test_profile.py`, `test_server.py`.

**Interfaces — Produces:**
- `profile_import.parse(md_text) -> (fields: dict[str,str], grounding: str, missing: list[str])`, keys `fullName firstName lastName city state phone email website github linkedin`.
- `store.Store(home)`: `config() / save_config(d)`, `profile() -> {imported, manual, missing, synced_at}`, `save_manual(d)`, `token()` (creates once), `append_run(rec)`, `answers` get/put, `ai_calls_today(now) / count_ai_call(now)`.
- `keychain.get(provider) / set(provider, key)` using `security find/add-generic-password -w`, or fake file.
- HTTP: `GET /health -> {ok, version}`, `GET/PUT /profile`, `GET /resume.pdf`, `GET /models?provider=`, `GET/PUT /config`, `POST /draft`, `POST /runs`. CLI: `server.py [serve] | pair | set-key <provider>`.
- Workspace root = `Path(__file__).resolve().parents[2]`.

- [ ] Tests `test_U2_*` (exact fields, master-only excluded, others empty, `test_U2_resync_keeps_manual`), `test_F18_*` (5 malformed fixtures), `test_F7_*` (4 refusals + allowed), `test_F8_*` (host override ignored + warning text), perms 0700/0600.
- [ ] Run → FAIL; implement; run → PASS; commit.

### Task 3: Scorer and field matcher (pure JS)

**Files:** `extension/content/scorer.js`, `matcher.js`; `tests/unit/scorer.test.mjs`, `matcher.test.mjs`.

**Interfaces — Produces:** `AF.scoreOption(label, value, target) -> 0..100`; `AF.aliases(v)`; `AF.matchField(ctx:{label,name,id,placeholder,autocomplete,automationId}) -> {key|null, questionStyle:bool}`; `questionStyle` = label has `?` or > 6 words.

- [ ] Port the Google plan's alias dictionary, scorer and `FIELD_MATCHERS` with fixes so `F14:` cases pass exactly (Male≠Female, CA→California not Africa/Canada, "Country (United States only)" not state, "Email address"→email, "No"→"No").
- [ ] Commit.

### Task 4: AI drafts in helper + post-processor

**Files:** `helper/ai.py`, `tests/fake_provider.py`, `tests/helper/test_ai.py`; `extension/content/drafts.js` (post-processor, also in unit tests) `tests/unit/drafts.test.mjs`.

**Interfaces:**
- `ai.list_models(provider) -> list[str]` (Anthropic `GET /v1/models`, OpenAI `GET /v1/models`).
- `ai.draft(req:{question, field_type, max_length, options?, page_title, company, job_heading}, store) -> {status:'review', text}|{error}`. Fixed `SYSTEM_RULES` constant; page fields only in the user message as JSON. Cache key `sha256(question|company|field_type|max_length|grounding_hash)`. Cap checked before call. Errors map to exactly: `AI error: key rejected` (401/403), `AI error: rate limited` (429), `AI error: provider error <code>` (5xx), `AI error: timed out`, `AI error: unreadable reply`; cap → `Daily AI limit reached (<n>)`. Errors are never cached.
- `AF.postProcess(text, {fieldType, maxLength, options}) -> string|null`: strip fences; number → first digits or null; select → exact option or null; trim to max at word boundary else hard cut; empty → null.
- fake provider modes: `ok`, `401`, `429`, `500`, `slow` (25 s), `malformed`, `echo`; records requests.

- [ ] Tests `test_F9_*`, `test_F10_*` (injected clock), `test_F20_*`, `U12:`, `F11:`, `F3:` (draft status always `review`; no code reads a confidence field). Implement; pass; commit.

### Task 5: Background worker + popup

**Files:** `extension/background.js`, `extension/popup/*`.

**Interfaces:**
- Messages: popup→bg `RUN {tabId, submit}`, `SYNC`, `PAIR {token}`; content→bg `DRAFT {req}`, `REPORT {tabId, summary}`, `DEBUGGER_FILL {frameId, selector, kind, value}`, `LOG_RUN {rec}`; bg→content `START {runId, profile, resumeRef, submit, fallback}`.
- Storage: `local`: `token, profile, resume:{name,type,b64}, syncedAt, prefs:{fallback}`; `session`: `runs[tabId] = {runId, submit, step, fingerprints[], counts, status, reason, submittedUrls[]}`.
- Popup copy exactly as mockup (states: Not paired, Helper connected, Helper offline …, Can't fill this page, No form fields found on this page). Submit switch has no persisted value (U17).

- [ ] E2E `U1:`, `U3:`, `U13:` (+ grep), `U17:`, `U20:` (popup part). Implement to mockup; pass; commit.

### Task 6: Fill engine, adapters, read-back, debugger fallback, highlights

**Files:** `content/util.js` (shadow walker, visibility, labels, native setter, click), `adapters.js`, `fill.js`, `hud.js`, `main.js`; fixtures `greenhouse*.html, lever.html, ashby.html, workday/, icims-host.html, icims-form.html, indeed/, generic*.html, workday-signin.html, indeed-signin.html`.

**Interfaces:**
- `AF.adapterFor(host) -> {name, fields(root)->[{el,key}], isSignIn(root), confirm:{paths:[RegExp], text:[RegExp]}, nextButton(root), submitButton(root)}`; hosts per rd "Builder-check calls".
- `AF.fillPage(root, profile, resume, opts) -> {items:[{el, key, level:'green'|'yellow', reason}], aiQueue}`; skips prefilled; file slot rules; question-style → yellow; read-back after 150 ms; on mismatch and `opts.fallback` → `DEBUGGER_FILL` then re-read; still mismatched → yellow `Couldn't set this field`.
- `AF.highlight(el, level, reason)` / `AF.clearHighlights()` restoring border/box-shadow/title.
- `AF.hud.render(summary)` Shadow DOM, top frame only, `aria-live="polite"`, collapses to pill below 900 px.

- [ ] E2E `U4: U5: U6: U7: U8: U9: U10: U11: U18: U19: U20: F12: F13: F19: F21: F22: U21:`. Implement; pass; commit per adapter group.

### Task 7: Safety checks, submit, confirmation, wizard

**Files:** `content/safety.js`, `content/wizard.js`; `tests/unit/safety.test.mjs`.

**Interfaces:** `AF.safetyCheck(state) -> {ok, reason, code}` with reasons exactly: `<CAPTCHA> detected — finish and submit yourself` (`captcha`), `<n> field(s) to review` (`review`), `<n> required field(s) empty` (`required`), `readback`, `page didn't advance`, `10-step limit`, `Already submitted from this tab`. Wizard: MutationObserver, 850 ms settle, FNV fingerprint, state persisted to session each step; submit once, 15 s confirmation wait → `submitted_confirmed|submitted_unconfirmed`.

- [ ] Tests `F1: F2: F3: F4: F5: F6: F15: F16: U15: U16: U25:` plus `F6: second tab independent`. Implement; pass; commit.

### Task 8: README, LaunchAgent, router, full verification

**Files:** `job-autofill/README.md` (install, load unpacked, start, pair, set-key, Run at login, troubleshooting), `helper/launchd/com.cloudtransition.job-autofill.plist`, `CODE.md` Active Projects row linking `job-autofill/` and the plan.

- [ ] `npm test` and `npm run check` green; run `evals.mjs run docs/plans/job-autofill-extension/eval.md`; all 48 automated pass; `python3 second-brain/brain.py index && check`.
- [ ] Manual cases (U14, U22, U23, U24, U26, F17, D1–D6) with the user; record evidence.
- [ ] Final todo: `Feature done: Job application autofill extension`.
