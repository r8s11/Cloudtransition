---
feature: Workspace map Graph Overdrive
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: 3D Observatory

Upgrade only the real 3D Graph scene. Atlas, the independent 2D renderer and all file actions retain their approved behavior.

## Build contract

- Build production only after explicit approval of requirements, study and eval.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/workspace-3d-observatory/eval.md`
- Save browser assertions, timing, GPU counters and screenshots under `eval-evidence/`.
- Study measurements are not production proof. Report physical-device coverage honestly.

## Traceability

| Requirement | Cases |
| --- | --- |
| Identity, membership, privacy and unchanged neighbors | R1, R2 |

## Usage

## Failure

## Regression

### R1 — Existing geometry and privacy contracts
- **Expected:** Existing Atlas fold, constellation identity/membership/determinism and index privacy tests pass. No file identity or relationship is lost or created by decorative placement.
- **Verify:** `node --test visual-second-brain/tests/test_atlas_fold.mjs visual-second-brain/tests/test_constellation.mjs && python3 -m unittest discover -s visual-second-brain/tests`

### R2 — Local modules parse
- **Expected:** Changed modules and inline scripts parse. Runtime resources stay local; pinned Three.js r180 and GSAP 3.15.1 remain unchanged. No new dependency or network service.
- **Verify:** `node --check visual-second-brain/assets/constellation.js && node --check visual-second-brain/assets/atlas.js && node -e 'const fs=require("fs"),vm=require("vm");const h=fs.readFileSync("visual-second-brain/visual-second-brain.html","utf8");for(const m of h.matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(m[1]);'`

## Usage — smoke (added 2026-11-17 after manual-case trim)

### U100 — Surface responds (smoke)
- **Setup:** dashboard test client; no live services beyond the local app.
- **Steps:** GET /workspace-map/ through the dashboard test client.
- **Expected:** 200 and the HTML contains 'id=\\"atlas-stage\\"' (the view container/title).
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; t=TestClient(app.app).get('/workspace-map/').text; assert 'id=\"atlas-stage\"' in t"`

## Failure — smoke (added 2026-11-17 after manual-case trim)

### F100 — File serving stays inside the workspace (smoke)
- **Setup:** dashboard test client.
- **Steps:** GET /api/file?path=../../etc/passwd.
- **Expected:** 400; no file content outside the workspace is served.
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; r=TestClient(app.app).get('/api/file', params={'path':'../../etc/passwd'}); assert r.status_code==400"`
