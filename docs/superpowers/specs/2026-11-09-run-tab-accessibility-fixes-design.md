# Run tab accessibility fixes — design doc

**Date:** 2026-11-09  
**Scope:** `dashboard-app/static/app.js`, `dashboard-app/static/style.css`, `dashboard-app/tests/test_design_contracts.py`  
**Size:** small change set (5 related fixes in one feature area)

## Intent / why
Five findings on the Run tab degrade keyboard/screen-reader use and state clarity:
1. Run button loses focus when a run starts (`disabled = true` drops focus).
2. History list rebuilt every 2s poll destroys focus/selection inside rows.
3. Failed poll leaves UI stuck on "Running…" with no retry/re-enable.
4. Live regions rewritten every poll, causing repeated/overlapping announcements.
5. Status text below 12px type-size floor; state-color contrast untested.

## Goals
- Run button keeps focus and announces "Starting… / Running…" in place.
- History rows update in place by run id; only append/remove on set change.
- After 3 consecutive failed polls, announce "Lost contact, retrying…" and re-enable Run buttons; keep polling.
- Live regions only mutate when text changes; single page-level region announces start/finish transitions.
- `.run-status` ≥ 13px, `.run-log-status`/`.run-log-time/.dur/.out` ≥ 12px; add contrast contract test for `--yellow/--green/--red` on paper surfaces.

## Non-goals
- Changing the polling interval, the API shape, or the native `<dialog>` output viewer.
- Touching the `tools/arms/static/app.js` variant (no run-status code there).

## Approach (single sensible way per finding)
1. Replace `btn.disabled = true/false` with `aria-disabled="true/false"` + `is-disabled` class; guard click handler (`aria-disabled === "true" → return`). Style `[aria-disabled="true"]` for opacity/cursor.
2. Keep a `Map<runId, row>`; on each poll, update existing row cells in place (status text/duration/output visibility); append new rows / remove gone rows only when the run set changes.
3. Add `failCount`; reset on success; on catch, increment, and at ≥3 announce via page-level live region and set all Run buttons `aria-disabled="false"`; keep polling.
4. Only write status `textContent`/`className` when the string differs; add one page-level `aria-live="polite"` region used solely for start/finish transitions.
5. Raise font sizes per table above; add test asserting `--yellow/--green/--red` ≥ 3:1 on every washi face.

## What's left to the builder
None — all five fixes are fully specified above. Proceed to implement.
