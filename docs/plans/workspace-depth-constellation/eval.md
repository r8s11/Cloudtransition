---
feature: Workspace map Depth Constellation
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Depth Constellation

Real 3D graph rendering over the same local file index, alongside reliable 2D and Atlas.

## Build contract

- Build only after this design/study/eval is approved.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/workspace-depth-constellation/eval.md`
- Save screenshots, interaction assertions, GPU-loss observations and timing under `eval-evidence/`.
- Never silently drop files to meet performance targets. No remote runtime dependencies or new backend.

## Traceability

| Requirement | Cases |
| --- | --- |
| Real dimensional nodes, complete membership identity | R1 |
| Offline, privacy, no new backend | R1, R2 |

## Usage

## Failure

## Regression

### R1 — Layout boundaries and privacy tests
- **Setup:** Builder creates tests/test_constellation.mjs against the pure coordinate/layout function.
- **Expected:** Each input file has one stable path, finite deterministic coordinates and only real, deduplicated membership edges. Empty input is empty; input remains unchanged. Existing index scope/privacy tests pass.
- **Verify:** `node --test visual-second-brain/tests/test_constellation.mjs && python3 -m unittest discover -s visual-second-brain/tests`

### R2 — Browser modules parse without a package installation
- **Expected:** New module and existing inline JavaScript parse; existing local assets suffice.
- **Verify:** `node --check visual-second-brain/assets/constellation.js && node -e 'const fs=require("fs"),vm=require("vm");for(const m of fs.readFileSync("visual-second-brain/visual-second-brain.html","utf8").matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(m[1]);'`

## Usage — smoke (added 2026-11-17 after manual-case trim)

### U100 — Surface responds (smoke)
- **Setup:** dashboard test client; no live services beyond the local app.
- **Steps:** GET /workspace-map/ through the dashboard test client.
- **Expected:** 200 and the HTML contains 'constellation' (the view container/title).
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; t=TestClient(app.app).get('/workspace-map/').text; assert 'constellation' in t"`

## Failure — smoke (added 2026-11-17 after manual-case trim)

### F100 — File serving stays inside the workspace (smoke)
- **Setup:** dashboard test client.
- **Steps:** GET /api/file?path=../../etc/passwd.
- **Expected:** 400; no file content outside the workspace is served.
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; r=TestClient(app.app).get('/api/file', params={'path':'../../etc/passwd'}); assert r.status_code==400"`
