---
feature: Workspace map Opening Fold
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Opening Fold

The Atlas root becomes an authored cover with a one-time fold intro and continuity transitions, without changing search, data or routes.

## Build contract

- Build only after this design/study/eval is approved.
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/workspace-opening-fold/eval.md`
- Save screenshots, interaction assertions and frame timing under `eval-evidence/`.
- Motion never delays data, focus or input. No remote runtime dependency, new route or index change.

## Traceability

| Requirement | Cases |
| --- | --- |
| Approved sculpture unchanged, local pinned libraries | R1, R2 |

## Usage

## Failure

## Regression

### R1 — Fold geometry and existing tests
- **Setup:** Builder creates tests/test_atlas_fold.mjs against the pure fold function.
- **Expected:** Progress 1 equals the approved sculpture vertices exactly; progress 0 is flat; all values finite; input unchanged. Constellation and index privacy tests still pass.
- **Verify:** `node --test visual-second-brain/tests/test_atlas_fold.mjs visual-second-brain/tests/test_constellation.mjs && python3 -m unittest discover -s visual-second-brain/tests`

### R2 — Modules parse, libraries local and pinned
- **Expected:** Modules and inline scripts parse. GSAP and Flip are the pinned 3.15.1 files, and every script source is a relative local path.
- **Verify:** `node --check visual-second-brain/assets/atlas.js && node --check visual-second-brain/assets/constellation.js && grep -q "GSAP 3.15.1" visual-second-brain/assets/vendor/gsap.min.js && grep -q "Flip 3.15.1" visual-second-brain/assets/vendor/Flip.min.js && node -e 'const fs=require("fs"),vm=require("vm");const h=fs.readFileSync("visual-second-brain/visual-second-brain.html","utf8");for(const m of h.matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(m[1]);const s=[...h.matchAll(/<script[^>]*\ssrc="([^"]+)"/g)].map(m=>m[1]);if(s.length!==2||s.some(u=>!/^assets\/vendor\/[A-Za-z.]+\.js$/.test(u)))throw new Error("unexpected script sources: "+s.join(", "));'`

## Usage — smoke (added 2026-11-17 after manual-case trim)

### U100 — Surface responds (smoke)
- **Setup:** dashboard test client; no live services beyond the local app.
- **Steps:** GET /workspace-map/ through the dashboard test client.
- **Expected:** 200 and the HTML contains 'id=\\"fold-ghosts\\"' (the view container/title).
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; t=TestClient(app.app).get('/workspace-map/').text; assert 'id=\"fold-ghosts\"' in t"`

## Failure — smoke (added 2026-11-17 after manual-case trim)

### F100 — File serving stays inside the workspace (smoke)
- **Setup:** dashboard test client.
- **Steps:** GET /api/file?path=../../etc/passwd.
- **Expected:** 400; no file content outside the workspace is served.
- **Verify:** `cd dashboard-app && venv/bin/python -c "from fastapi.testclient import TestClient; import app; r=TestClient(app.app).get('/api/file', params={'path':'../../etc/passwd'}); assert r.status_code==400"`
