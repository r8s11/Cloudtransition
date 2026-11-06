---
feature: Codex, OpenCode and OpenRouter models for Run executions
status: passed
approved: 2026-11-06
rd: rd.md
mockup: mockup.html
---

# Evals: Codex, OpenCode and OpenRouter models for Run executions

Selectable Codex, OpenCode and OpenRouter execution models in the existing local dashboard Run workflow.

## Build contract

- Build only after user approval and status approved. Case changes require re-review.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/codex-runs/eval.md`.
- Record manual cases with the same runner's record subcommand and evidence under eval-evidence/. Never claim fixtures prove account entitlement.
- Code changes stale prior results. Done requires every case passing against the current tree.
- No paid model calls, credentials changes or security-setting changes without separate explicit permission.

## Traceability

| RD requirement | Cases |
| --- | --- |
| 1 Selectable Codex/OpenCode/OpenRouter, retained defaults, update button | U1, U3, R3 |
| 2 Local visible model catalogues, free-only for opencode/openrouter | U1, F2 |
| 3 Codex/OpenCode/OpenRouter dispatch and effort | U1, U2, F1 |
| 4 Inputs, prompt and skill intent | U2 |
| 5 Permissions | F4 |
| 6 Logs, output and failures | U2, F2, F3, D3 |
| 7 Validation, locking, timeouts | F1, F3, R1, R3 |
| 8 UI/accessibility/states | U4, D1, D2, D3 |

## Usage

### U1 — Select provider-labelled models
- **Setup:** Installed model catalogues and / Run tab, configurable UI/UX review card.
- **Steps:** Open Model, select each listed Codex entry, each listed OpenCode free entry and each listed OpenRouter free entry, switch back to Claude, then inspect effort options.
- **Expected:** Visible catalogue entries only; provider-labelled choices (Codex entries, OpenCode free entries such as opencode/beam-free, OpenRouter free entries such as nvidia/nemotron-3-super-120b-a12b:free); existing Claude default retained; Codex effort options match each model; OpenCode offers Default effort only; OpenRouter offers Default effort only; incompatible selection resets to Default; no run starts on selection.
- **Verify:** manual — capture catalogue response and desktop selector/effort screenshots; record exact IDs and exclusions.

### U2 — Execute Codex, OpenCode and OpenRouter through the existing run lifecycle
- **Setup:** Builder creates temporary isolated executable fixtures and disposable workspace; no authenticated model access. OPENROUTER_API_KEY not set (to exercise the unconfigured path).
- **Steps:** Launch a configurable card through /api/skills/run using Codex; repeat using OpenCode; repeat using OpenRouter; poll /api/skills/runs and open each output. Repeat each with a validated input card.
- **Expected:** One process per provider each uses the selected model (and supported effort for Codex), correct prompt/input/workspace context; running then done status; provider/model/duration and readable output appear in history and runs.log. Claude is not launched. Skill references resolve for each provider rather than being treated as inert slash commands. OpenRouter with no API key returns 400 before launch with an actionable message.
- **Verify:** manual — run an isolated end-to-end harness with the real HTTP routes and local executable fixtures; capture lifecycle/output/log evidence and resolved prompts; remove temporary artifacts.

### U3 — Provider selection applies to shared configurable cards
- **Setup:** Run tab and Today organizer controls rendered from the same catalogue.
- **Steps:** Select Codex, OpenCode and OpenRouter on configurable AI cards in Run, including Other workspace tools; exercise the corresponding shared Today runner.
- **Expected:** Catalogue capability rules and selected provider are honored consistently; no duplicate independent runner path; fixed Audit and deterministic tools remain unchanged.
- **Verify:** manual — capture Run/Today requests using temporary executor fixtures, including same-skill duplicate handling.

### U4 — Keyboard and narrow screen
- **Setup:** Run tab at 390x844 and desktop; model catalogue available.
- **Steps:** Tab to Model and Effort, change with keyboard, activate Run using a local executable fixture and open output.
- **Expected:** Labels identify provider/model/effort; focus visible; no page overflow or clipped selected label; status announced; no unwanted run from selection alone.
- **Verify:** manual — capture keyboard focus, accessibility tree and mobile screenshot plus request count.

## Failure

### F1 — Invalid selections cannot launch processes
- **Setup:** Builder adds dashboard-app/tests/test_codex_runs.py::test_invalid_selection_rejected covering hostile and unknown IDs for all providers, wrong provider/model pairings and unsupported effort.
- **Steps:** POST invalid selections, including OpenCode with non-default effort, OpenRouter with non-default effort, a Codex model selected under provider opencode, an OpenCode model under provider openrouter, OpenRouter selection with no API key, and missing CSRF header.
- **Expected:** 400 for invalid selections, 403 without CSRF; no executor launch and no running history item. Strings are never interpreted as shell code.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_codex_runs.py -q -k invalid_selection_rejected`

### F2 — Missing catalogue and missing executable
- **Setup:** Isolated server with missing, corrupt and empty Codex catalogue; missing, empty and corrupt `opencode models` output; missing/corrupt OpenRouter curated catalogue; temporary PATH without codex and without opencode.
- **Steps:** Load catalogue then try an otherwise valid request for each provider using isolated configuration.
- **Expected:** Claude options still work. Missing catalogue does not invent model IDs; explanation visible per provider. A disappeared executable produces failed status with actionable output; no Claude fallback and no credentials shown.
- **Verify:** manual — capture each catalogue state, HTTP result, history status and error output with no real provider calls.

### F3 — Provider failure, timeout and duplicate submit
- **Setup:** Builder adds dashboard-app/tests/test_codex_runs.py::test_failure_lifecycle_and_duplicate using isolated real subprocess fixtures for nonzero exit, delayed exit and concurrent requests, parametrized for codex, opencode and openrouter executables.
- **Steps:** Execute a failing fixture, a timeout fixture and simultaneous same-skill submits for each provider.
- **Expected:** Nonzero/timeout ends failed and records output/duration; controls permit another explicit attempt. Same-skill conflict returns 409 with only one active execution. No automatic retries/provider fallback.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_codex_runs.py -q -k failure_lifecycle_and_duplicate`

### F4 — Permission parity is enforced or denied
- **Setup:** Disposable workspace and sentinel files inside/outside each card scope; installed Codex sandbox policy, OpenCode read-only mechanism and OpenRouter (no local sandbox) behavior inspected without model calls.
- **Steps:** Exercise read-only and polish constraints using an isolated permission probe for Codex, OpenCode and OpenRouter; confirm all providers run on all cards without refusal.
- **Expected:** All providers allowed on all cards — no permission refusals. Claude enforces read-only sandboxes and file/command allowlists; non-Claude providers (Codex, OpenCode, OpenRouter) run without machine-enforced boundaries (the user accepts this when choosing them). Read-only cards do not prevent non-Claude writes; polish command/template allowlist does not restrict non-Claude providers. No dangerous bypass or trust changes.
- **Verify:** manual — confirm OpenCode and OpenRouter run on polish and read-only cards without 400 refusal; capture sentinel behavior showing non-Claude writes are not blocked.

## Regression

### R1 — Dashboard suite
- **Setup:** Existing dashboard tests and new meaningful behavior cases.
- **Steps:** Run full dashboard suite.
- **Expected:** All existing behavior tests and new cases pass.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q`

### R2 — Syntax and template load
- **Setup:** No standalone frontend build or typecheck exists for this FastAPI/Jinja/static-JS app.
- **Steps:** Check JavaScript syntax and Python compilation; template rendering is covered by R1 and browser cases.
- **Expected:** Both commands exit zero.
- **Verify:** `node --check dashboard-app/static/app.js && dashboard-app/venv/bin/python -m py_compile dashboard-app/app.py`

### R3 — Claude, deterministic tools and shared neighbors
- **Setup:** Isolated local executor fixtures and dashboard routes.
- **Steps:** Run existing Claude selection, fixed Audit and a shell tool; inspect Today and Metrics.
- **Expected:** Claude model/effort semantics preserved; Audit retains fixed defaults; shell runs have no model and no provider selection. Output viewing/polling/CSRF and Today actions remain functional; Metrics still loads.
- **Verify:** manual — capture commands, API results and browser evidence using fixtures; no real paid model calls.

## Design

### D1 — Default and mobile match mockup
- **Setup:** Open mockup.html sections Default and Mobile.
- **Steps:** Compare rendered Run controls at 1440x1000 and 390x844 with mockup.
- **Expected:** Existing paper/vermilion design, Inter/mono roles and labelled native selectors preserved; controls wrap without horizontal scroll. Document justified differences.
- **Verify:** manual — save desktop/mobile implementation and mockup screenshots under eval-evidence/.

### D2 — Loading empty and error states match mockup
- **Setup:** Open mockup sections Loading, Empty and Error.
- **Steps:** Delay catalogue; return no entries for any provider; simulate provider failure through isolated fixture.
- **Expected:** Loading does not start runs; missing provider catalogues explain why while retaining Claude and the available providers; failed run identifies provider/model and recovery without silent fallback.
- **Verify:** manual — capture screenshots and status announcements for all three states.

### D3 — Running and completed states match mockup
- **Setup:** Open mockup section Running and success; isolated executable fixture.
- **Steps:** Start and complete a Codex run, an OpenCode run and an OpenRouter run; open output.
- **Expected:** Running action disabled; selected provider/model stays identifiable; completed history shows readable output path and duration; keyboard output access remains usable.
- **Verify:** manual — capture running/completed/output screenshots.
