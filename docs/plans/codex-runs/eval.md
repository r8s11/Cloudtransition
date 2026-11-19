---
feature: Codex, OpenCode and OpenRouter models for Run executions
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Codex, OpenCode and OpenRouter models for Run executions

Selectable Codex, OpenCode and OpenRouter execution models in the existing local dashboard Run workflow.

## Build contract

- Build only after user approval and status approved. Case changes require re-review.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/codex-runs/eval.md`.
- Record manual cases with the same runner's record subcommand and evidence under eval-evidence/. Never claim fixtures prove account entitlement.
- Code changes stale prior results. Done requires every automated case passing against the current tree; manual cases are advisory and only block when recorded as failing.
- No paid model calls, credentials changes or security-setting changes without separate explicit permission.

## Traceability

| RD requirement | Cases |
| --- | --- |
| 3 Codex/OpenCode/OpenRouter dispatch and effort | F1 |
| 6 Logs, output and failures | F3 |
| 7 Validation, locking, timeouts | F1, F3, R1 |

## Usage

## Failure

### F1 — Invalid selections cannot launch processes
- **Setup:** Builder adds dashboard-app/tests/test_codex_runs.py::test_invalid_selection_rejected covering hostile and unknown IDs for all providers, wrong provider/model pairings and unsupported effort.
- **Steps:** POST invalid selections, including OpenCode with non-default effort, OpenRouter with non-default effort, a Codex model selected under provider opencode, an OpenCode model under provider openrouter, OpenRouter selection with no API key, and missing CSRF header.
- **Expected:** 400 for invalid selections, 403 without CSRF; no executor launch and no running history item. Strings are never interpreted as shell code.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_codex_runs.py -q -k invalid_selection_rejected`

### F3 — Provider failure, timeout and duplicate submit
- **Setup:** Builder adds dashboard-app/tests/test_codex_runs.py::test_failure_lifecycle_and_duplicate using isolated real subprocess fixtures for nonzero exit, delayed exit and concurrent requests, parametrized for codex, opencode and openrouter executables.
- **Steps:** Execute a failing fixture, a timeout fixture and simultaneous same-skill submits for each provider.
- **Expected:** Nonzero/timeout ends failed and records output/duration; controls permit another explicit attempt. Same-skill conflict returns 409 with only one active execution. No automatic retries/provider fallback.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_codex_runs.py -q -k failure_lifecycle_and_duplicate`

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

## Usage — smoke (added 2026-11-17 after manual-case trim)

### U100 — Surface responds (smoke)
- **Setup:** dashboard test client; no live services beyond the local app.
- **Steps:** GET /api/skills/catalog through the dashboard test client.
- **Expected:** 200 and the catalogue lists the codex provider runners.
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; r=TestClient(app.app).get('/api/skills/catalog'); assert r.status_code==200 and 'codex' in r.text"`
