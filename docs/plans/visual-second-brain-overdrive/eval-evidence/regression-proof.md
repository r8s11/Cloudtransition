# Folded Atlas regression proof

2026-11-12. Managed headless Chromium, 1440×1000 CSS pixels. Tested scratch dashboard `http://127.0.0.1:8014/workspace-map/`, embedded `http://127.0.0.1:8014/#workspace-map`, and standalone `http://127.0.0.1:8766/visual-second-brain.html`. Production port 8000 was intentionally not exercised. Only loopback requests were allowed. No source/index refresh, real file mutation, package install, build, suite, or eval recording was performed. The owned browser tab was closed.

## Results

| Case | Result | Observed proof |
| --- | --- | --- |
| U2 | PASS | Real snapshot has 542 files; all 17 rendered topic/untagged counts match index-derived counts. Career 128, agent 152. Rapid career→agent handlers leave `?topic=agent`, label agent, 152 results. `DASHBOARD.md` while agent remains selected correctly yields zero, not a global-search count. Clear restores 152; Reset restores 542 and neutral label. Repeated with atlas.js response held pending and after it loaded; input/results never waited for the module. |
| U3 | PASS | Both routes render DASHBOARD.md preview and paths equal to the index. Dashboard has Copy full path, Open `/workspace-file/DASHBOARD.md`, and Download with `?download=1`. Standalone has Copy only. Both produce `Copied` plus `Full path copied to the clipboard.` Actual Clipboard API readback equals the indexed path. Escape closes details and restores row 0, DASHBOARD.md, in both routes. No Open/Download navigation was needed. |
| U4 | PASS | Both direct routes preserve URL, title, count, pose label, and mounted row content across reload for career, query, and root-folder links. Counts are 128, 2, and 24 respectively. Root URL normalizes to `?folder=.&group=folder`, retaining semantics. Nested folder tiles navigate docs→plans→codex-runs with counts 28→21→3. Breadcrumbs return to docs, then All folders. Folder state remains neutral (`All topics`). Embedded map loads 542 files with embedded class, viewport/scroll widths both 1032px. |
| R2 | PASS, inherited font caveat | Cold/cache-disabled loads render canvas and useful content on both routes. atlas.js, vendor/three.module.min.js, and vendor/three.core.min.js return 200 on both routes. No JavaScript page errors or syntax/runtime exceptions. Dashboard console is clean. Standalone emits two inherited font resource 404s, detailed below; do not describe its console as clean. README requires only loopback Python HTTP serving; no build/typecheck claim was invented. |
| R3 | PASS | Every collected virtualized DOM path equals the independent index-derived expected set across career, document, root, nested folder, combined filters, query, and date checks. Chips and Reset preserve existing group behavior. Injected 10,000-record boundary mounts only 27 rows at the top and 20 at the end. ArrowDown selects row 9999, clamps there, ArrowUp reaches 9998, and Enter selects the correct last record. Compact/Standard/Large tile widths are 170/261/352px; result rows stay 56px and spacer stays 560000px. |
| D2 | PASS | Compared approved selected/success study with real career and copy states. Results occupy 1080px reading width beside a 288px sculpture. Details occupy a 360px drawer and omit the sculpture. Copy confirmation remains directly below the action, inside details; no dialog or decorative celebration. Canvas has pointer-events:none. Four canvas samples 150ms apart are identical in selected work state, and four more are identical during query work. Preview content equality was checked before evidence masking. |

No failing assigned case was observed. Standalone font-resource errors were reported immediately to Main; Main confirmed they are incumbent behavior and do not fail R2's JavaScript/module acceptance criterion.

## Exact-path filter comparisons

These are independent source-index expectations, not app `VIEW` counts. Each mounted row's name/folder was mapped back to its index relative path. The entire virtual list was scrolled and collected before set comparison. JSON stores exact paths plus expected/actual SHA-256 and equality results.

| Filter | Expected and observed paths |
| --- | ---: |
| topic=career | 128 |
| type=document | 258 |
| group=folder, folder=. | 24 |
| group=folder, folder=docs/plans/codex-runs | 3 |
| topic=career, type=document, folder=resume, date=365 | 80 |
| q=DASHBOARD.md | 2 |
| type=document, date=1 | 0 |
| topic=career, date=7 | 2 |

Combined chip exercise began with q=resume, career, document, resume folder, past year, folder grouping. Removing career yielded 80 matching paths; removing document yielded 99; removing past year retained the correct 99. Root-folder and resume-folder chips also cleared correctly. Reset cleared query/topic/folder/type/date while retaining `?group=folder` and 542 files.

Large fixture used deterministic copies of the first valid indexed record, unique names `boundary-00000.md` through `boundary-09999.md`, and unique `atlas-proof/` relative paths. It existed only in intercepted responses. No fabricated path was copied, opened, downloaded, or written as a source file. Final visible range was rows 9980–9999. Selection/detail title was `boundary-09999.md`, aria-current row 9999.

## Delivery console caveat

Standalone requests these incumbent absolute font URLs and receives 404:

- `http://127.0.0.1:8766/static/fonts/InterVariable.woff2`
- `http://127.0.0.1:8766/static/fonts/JetBrainsMono.woff2`

System/local fallback remains usable. All optional JavaScript modules loaded successfully from the current `assets/vendor/` layout after Main's integration update. No JavaScript errors were suppressed.

## Evidence

- `regression-proof.json` — compact observations, exact expected paths, path hashes, URL/reload states, action/clipboard/focus checks, module responses, console caveat, virtual-list metrics.
- `regression-proof-dashboard-copy.png`, `regression-proof-standalone-copy.png` — copy success and action differences.
- `regression-proof-career.png`, `regression-proof-career-copy.png` — selected hierarchy and success feedback.
- `regression-proof-large-end.png` — reachable final synthetic record.
- `regression-proof-embedded.png` — embedded map only, excluding dashboard content.
- `regression-proof-selection.webm` — real browser capture of selection, details, copy, typing, clear/reset. VP9, 1440×1000, 30fps, 29.366 seconds; metadata verified using ffprobe.
- `regression-proof-video-thumbnail.png` — extracted and inspected recording frame.

Privacy: preview text was visually masked only for screenshots/recording, after exact equality checks; no preview bodies were saved into JSON. Clipboard readback was limited to the task-produced indexed DASHBOARD.md workspace path. Rapid selection used the two already-rendered native tile click handlers back-to-back, retaining the second element reference after the first replaces the tile DOM. This exercises deterministic event interruption, not a claim that both tiles remain simultaneously visible to a pointer user.
