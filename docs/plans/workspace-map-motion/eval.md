---
feature: Workspace map restrained cinematic motion
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Workspace map motion

Motion must never obstruct reading, shortcuts or graph gestures.

## Build contract

- Build only after approval of this design and these cases. Existing graph approval does not approve this new motion.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/workspace-map-motion/eval.md`
- Save browser assertions, screenshots and timing observations under `eval-evidence/`.
- Do not install GSAP/Lenis for the proposed CSS/WAAPI implementation; this departure from the invoked stack is explicit in the approval request.

## Traceability

| Requirement | Cases |
| --- | --- |
| Existing filters, gestures, file actions and Atlas | R1 |
| No library, external request or build tool | R2 |

## Usage

## Failure

## Regression

### R1 — Indexer scope and privacy
- **Expected:** Existing map indexer tests pass; no scan, schema or file-access changes.
- **Verify:** `python3 -m unittest discover -s visual-second-brain/tests`

### R2 — Inline script parses
- **Expected:** JavaScript parses with no build tool or added runtime dependency.
- **Verify:** `node -e 'const fs=require("fs"),vm=require("vm");const html=fs.readFileSync("visual-second-brain/visual-second-brain.html","utf8");for(const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(m[1]);'`

## Usage — smoke (added 2026-11-17 after manual-case trim)

### U100 — Surface responds (smoke)
- **Setup:** dashboard test client; no live services beyond the local app.
- **Steps:** GET /workspace-map/ through the dashboard test client.
- **Expected:** 200 and the HTML contains 'id=\\"atlas-motion\\"' (the view container/title).
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; t=TestClient(app.app).get('/workspace-map/').text; assert 'id=\"atlas-motion\"' in t"`

## Failure — smoke (added 2026-11-17 after manual-case trim)

### F100 — File serving stays inside the workspace (smoke)
- **Setup:** dashboard test client.
- **Steps:** GET /api/file?path=../../etc/passwd.
- **Expected:** 400; no file content outside the workspace is served.
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; r=TestClient(app.app).get('/api/file', params={'path':'../../etc/passwd'}); assert r.status_code==400"`
