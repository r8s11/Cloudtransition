# Folded Atlas Implementation Plan

> **For agentic workers:** Use the executing-plans workflow inline. Steps use checkbox syntax for tracking.

**Goal:** Add the approved optional folded-paper WebGL layer without changing file-finding behavior.

**Architecture:** Keep the existing HTML application and state. A locally imported module owns one Three.js scene and its complete lifecycle. The dashboard mounts only the dedicated public enhancement asset folder; standalone serves that same folder normally.

**Tech Stack:** Existing HTML/CSS/JavaScript, pinned Three.js r180 ES modules and MIT license, existing FastAPI StaticFiles.

**Spec:** rd.md and the user-approved eval.md in this directory.

## Global Constraints

- Preserve the paper/vermilion world, current copy, query semantics, 56px virtualized rows, schema 2, and privacy boundary.
- No index regeneration, new storage, external runtime requests, paid services, or changes to file authorization.
- Cap DPR at 1.5. Honor reduced motion live. Phone stays static; pause rendering when hidden/offscreen/working. Release GPU resources on teardown.
- Use an optional local module; module failure must not prevent core map operation.
- Browser verification replaces new permanent wiring tests. Run the existing relevant test suites once after edits, per repository policy. No automatic commits or worktree changes.

## Review Focus

- Failed module or context creation: the useful map must still load.
- Resize/hidden iframe/context loss: no background render loop or leaked resources.
- Fast topic changes: last state wins without reordering filter results.
- Result rows/details at small widths: no stolen focus or corrupted virtualization offsets.
- Reduced motion changed during a transition: immediate static pose and no leftover animation loop.

## Task 1 — Optional scene and integration

**Files:** Modify visual-second-brain/visual-second-brain.html and dashboard-app/app.py. Create visual-second-brain/assets/atlas.js, pinned three.module.min.js, three.core.min.js, and LICENSE.three.txt.

**Interface:** `createAtlas(host, motionButton)` returns `{ update({ topic, working, available }), dispose() }`. The module owns observers, resize, visibility, motion preferences, context loss, and page lifecycle. HTML alone owns search/filter state and renders all controls/content. No exported existing API changes.

- [x] Record unchanged index/scoping hashes and baseline query results; observe missing sculpture in the rendered incumbent.
- [x] Vendor Three.js r180 and its license locally, with no install/build step.
- [x] Add a narrow StaticFiles mount at /workspace-map/assets with no symlink following; do not alter workspace-file authorization.
- [x] Add a bounded desktop sculpture rail and compact phone fallback, outside virtualized row calculations. Keep useful content first in DOM order.
- [x] Build an angular folded BufferGeometry with paper PBR faces and one vermilion underside; light with directional key and hemisphere fill, using a perspective camera.
- [x] Hook topic/working/available state into the optional module after useful map render. Use one cancellable requestAnimationFrame loop, short last-target transitions, bounded idle movement, and manual pause.
- [x] Prove actual WebGL rendering, optional-module failure, GPU denial, context loss, preference change, resize, and teardown in the browser.

## Task 2 — Verify and document

**Files:** Update visual-second-brain/README.md and CODE.md. Add design rationale in visual-second-brain/DESIGN.md and a surface brief in docs/briefs/visual-second-brain.brief.md. Store sanitized proof under this plan's eval-evidence/.

- [x] Compare desktop, phone, tablet, zoom, and embedded composition against the approved mockup.
- [x] Exercise approved U/F/R/D cases with direct browser helpers and bounded browser scripts. Record only observed outcomes; name any missing real-device proof.
- [ ] Run the project test suite via `dashboard-app/venv/bin/python -m unittest discover -s visual-second-brain/tests`, and dashboard suite via `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q` after final edits.
- [x] Run Impeccable detector once over changed product UI, fix actionable findings, retain the approved palette/type identity.
- [x] Document dependency version/license, static fallback, pause/reduced-motion behavior, and unchanged snapshot model. Refresh department links.
- [ ] Run the approved eval, then record the observed manual evidence and check this eval directory. Do not rerun unrelated feature evals or claim their failures resolved.

## Execution decisions

Native inline execution follows the user approval to build. No additional product/design decision is needed. Existing repo tool policy overrides skill defaults requesting new permanent wiring tests, routine commits, or per-step broad suites.

Ruling: Keep Three.js in assets/vendor/ so the existing vendor exclusion also keeps it out of future workspace indexes; no indexer rule changes. An existing Unicode fixture assumed composed filenames, but this filesystem returns decomposed names. Preserve production paths and check file identity for both indexed absolute and relative paths instead. The initial suite showed this fixture failure; a one-off diagnostic confirmed unequal code points but equal NFC strings. Dashboard regression suite: 320 passed.

Ruling: Observe the canvas stage, not the entire sculpture rail, for visibility. A 5px sliver of the motion-control region could remain visible after the canvas scrolled out; the old observer still rendered 273 draw calls in 350ms. The stage observer produced zero draw calls and zero pending animation frames in the same geometry. Hidden-state handling was exercised with a controlled document.hidden/visibilitychange injection because this managed headless browser kept document.hidden false even for background targets. Full teardown disposed two geometries, five materials, one shadow target, and the GL context.

Final test and eval status is recorded by the runner and the files under eval-evidence/, rather than rewriting this plan after verification and invalidating the runner's workspace hash.
