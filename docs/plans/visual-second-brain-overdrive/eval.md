---
feature: Visual Second Brain Folded Atlas
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Visual Second Brain Folded Atlas

Add one real, lit paper sculpture to the existing private Workspace map. Preserve file finding, offline operation, and privacy. Review this contract and the static mockup before implementation.

## Build contract

- Build only after `status: approved`. Changes to requirements, expected behavior, or mockup require renewed review.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/visual-second-brain-overdrive/eval.md`
- Record observed manual checks with `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/visual-second-brain-overdrive/eval.md <ID> pass|fail "<observation and evidence path>"`.
- Save evidence under `eval-evidence/` beside this file. Never record a pass from source inspection alone.
- Any source change stales prior automated results. Every automated case must pass; a recorded manual failure blocks completion. Disclose unexercised real-device checks.
- Commands run from the workspace root. No paid services, data transfer, or index regeneration is authorized.

## Traceability

| Requirement | Cases |
| --- | --- |
| F — Local-only dependencies and unchanged privacy | R1 |

No requirements are unmapped. Authentication, submission concurrency, rate limiting, and rollback cases do not apply: this is a read-only local visual enhancement with no new endpoint or persistent state.

## Usage — every way to use the feature

## Failure — graceful degradation and boundary states

## Regression — existing behavior remains intact

### R1 — Existing map test suite passes
- **Setup:** Workspace root with dashboard virtual environment available; no refresh operation.
- **Steps:** Run the complete Visual Second Brain unittest suite.
- **Expected:** All existing scope, privacy, and refresh-safety tests pass with exit code 0.
- **Verify:** `dashboard-app/venv/bin/python -m unittest discover -s visual-second-brain/tests`

## Usage — smoke (added 2026-11-17 after manual-case trim)

### U100 — Surface responds (smoke)
- **Setup:** dashboard test client; no live services beyond the local app.
- **Steps:** GET /workspace-map/ through the dashboard test client.
- **Expected:** 200 and the HTML contains '<title>Workspace map</title>' (the view container/title).
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; t=TestClient(app.app).get('/workspace-map/').text; assert '<title>Workspace map</title>' in t"`

## Failure — smoke (added 2026-11-17 after manual-case trim)

### F100 — File serving stays inside the workspace (smoke)
- **Setup:** dashboard test client.
- **Steps:** GET /api/file?path=../../etc/passwd.
- **Expected:** 400; no file content outside the workspace is served.
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; r=TestClient(app.app).get('/api/file', params={'path':'../../etc/passwd'}); assert r.status_code==400"`
