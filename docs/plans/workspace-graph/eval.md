---
feature: Workspace map Graph view
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Workspace map Graph view

Local graph alongside Atlas, using the current privacy-filtered snapshot.

## Build contract

- Build after user approval. No new backend or dependency.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/workspace-graph/eval.md`
- Record browser observations and screenshots under `eval-evidence/`.
- Existing unrelated stale evals are outside this change.

## Traceability

| Requirement | Cases |
| --- | --- |
| Add Graph, preserve Atlas and deep links | R1 |
| Offline, no new dependencies or data store | R2 |

## Usage

## Failure

## Regression

### R1 — Index scope and privacy remain intact
- **Expected:** Existing indexer tests pass. No index/schema or file-serving change.
- **Verify:** `python3 -m unittest discover -s visual-second-brain/tests`

### R2 — Browser script parses
- **Expected:** Inline JavaScript parses without a build tool; no package installation required.
- **Verify:** `node -e 'const fs=require("fs"),vm=require("vm");const html=fs.readFileSync("visual-second-brain/visual-second-brain.html","utf8");for(const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(m[1]);'`

## Usage — smoke (added 2026-11-17 after manual-case trim)

### U100 — Surface responds (smoke)
- **Setup:** dashboard test client; no live services beyond the local app.
- **Steps:** GET /workspace-map/ through the dashboard test client.
- **Expected:** 200 and the HTML contains 'id=\\"vGraph\\"' (the view container/title).
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; t=TestClient(app.app).get('/workspace-map/').text; assert 'id=\"vGraph\"' in t"`

## Failure — smoke (added 2026-11-17 after manual-case trim)

### F100 — File serving stays inside the workspace (smoke)
- **Setup:** dashboard test client.
- **Steps:** GET /api/file?path=../../etc/passwd.
- **Expected:** 400; no file content outside the workspace is served.
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; r=TestClient(app.app).get('/api/file', params={'path':'../../etc/passwd'}); assert r.status_code==400"`
