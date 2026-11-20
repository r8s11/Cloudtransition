# Failure-state browser acceptance

**F1 PASS · F3 PASS · F4 PASS · D4 PASS.** No product bug found.

Tested the scratch dashboard route `http://127.0.0.1:8014/workspace-map/` in Chromium at 1440×1000 and 390×844. This report does not claim production `:8000` was restarted or standalone behavior was tested. The assigned cases use the direct map route.

## Method and privacy

- Each injection intercepted browser responses only. No source, index, refresh script, or product file was changed.
- Missing module: returned HTTP 404 for the local `atlas.js` request.
- Denied WebGL: prepended instrumentation returning `null` for WebGL context creation.
- Lost context: allowed a successful real render, then called `WEBGL_lose_context.loseContext()`.
- Counted WebGL creation attempts, GL draw API calls, animation-frame schedules/callbacks, and context-loss events. Draw counts are not frame counts.
- After fallback settled, compared counters across 900 ms and two resize events. No counter increased in any desktop failure state.
- Index injections returned HTTP 503, malformed JSON, schema 99, or the original metadata with only `files: []` changed.
- Loading delayed the intercepted index response by 2200 ms, then returned the real snapshot.
- Every captured run had zero uncaught page exceptions and zero attempted external requests.
- Detail screenshots hide private preview, metadata, and paths. Empty-state evidence substitutes `/local/workspace/` for the absolute workspace path.
- Browser evaluation globals were isolated from injected page globals. Initial probe waits therefore failed; successful probes read counters through shared DOM attributes. This was a probe/tool issue, not a product failure.

## F1 — Independent visual fallback: PASS

| Injection | Observed fallback | Bounded counters, start → end | Search and details |
| --- | --- | --- | --- |
| Missing local module | Static fold; no canvas or motion control; one module request | attempts 0 → 0; draws 0 → 0; RAF schedules/callbacks 1/1 → 1/1 | `DASHBOARD.md`: `2 of 542 files`; actual `DASHBOARD.md` details opened |
| Denied WebGL | Static fold; removed canvas; hidden motion control | attempts 2 → 2; draws 0 → 0; RAF 1/1 → 1/1 | Same successful search/details |
| Lost rendered context | 104 draw API calls occurred before fallback; one loss event; removed canvas | attempts 1 → 1; draws 104 → 104; RAF 9/6 → 9/6; loss 1 → 1 | Same successful search/details |

All three states retained normal map counts (`542 of 542 files`). Topic filtering produced `Topic: agent` and `152 of 542 files`. Reset then allowed the requested file search. Details retained `Copy full path`, preview content, and dashboard file actions. No visual failure produced an index error. Missing-module console contained only the expected injected 404 resource error. Denied/lost-context console contained no warnings or errors. No uncaught exceptions occurred.

Phone missing-module fallback also retained filtering, search, and details. Phone has no GPU scene by design; actual denied/lost GPU paths were exercised at desktop width.

Screenshots:
- [Missing module, desktop](failure-missing-1440-state.png) · [details](failure-missing-1440-details-redacted.png)
- [Denied context](failure-denied-1440-state.png) · [details](failure-denied-1440-details-redacted.png)
- [Successful render before loss](failure-lost-1440-rendered.png) · [fallback after loss](failure-lost-1440-state.png) · [details](failure-lost-1440-details-redacted.png)
- [Phone fallback](failure-missing-390-state.png) · [phone details](failure-missing-390-details-redacted.png)

## F3 — Distinct index errors: PASS

Both widths displayed these exact state titles:

| Injection | Observed title | Recovery |
| --- | --- | --- |
| HTTP 503 | `Index unavailable` | Explains HTTP 503, reconnecting USB, and rebuilding the index |
| Invalid JSON | `Index file is damaged` | Explains `not valid JSON`, atomic refresh replacement, and rebuild command |
| Schema 99 | `Index format is out of date` | Identifies `schema 99` and gives rebuild command |

Every state had blank success counts, disabled search, no selected topic, no canvas, and a hidden sculpture host. Error messages remained visible without a visual-loading overlay. The 503 console contained only the expected resource error; invalid/schema runs had no warning/error console messages. All had zero uncaught exceptions.

Screenshots:
- 503: [desktop](failure-503-1440-state.png) · [phone](failure-503-390-state.png)
- Invalid JSON: [desktop](failure-invalid-1440-state.png) · [phone](failure-invalid-390-state.png)
- Schema mismatch: [desktop](failure-schema-1440-state.png) · [phone](failure-schema-390-state.png)

## F4 — No match, reset, and empty snapshot: PASS

At both widths, `zzzz-no-match-zzzz` displayed `No files match. Remove a filter or try a different word.` Counts were honestly `0 of 542 files`. Reset cleared the query and restored `Topics`, real topic tiles, and `542 of 542 files`. Phone reset was reachable through Filters.

The intercepted empty snapshot displayed `This snapshot has no files`, include-list guidance, and the rebuild command. Counts stayed blank. No records, selected topic, canvas, or success state appeared. These runs had no warning/error console messages or uncaught exceptions.

Screenshots:
- No match: [desktop](failure-no-match-1440-no-match.png) · [phone](failure-no-match-390-no-match.png)
- Reset recovery: [desktop](failure-no-match-1440-reset.png) · [phone](failure-no-match-390-reset.png)
- Empty snapshot: [desktop](failure-empty-1440-state.png) · [phone](failure-empty-390-state.png)

## D4 — Study comparison: PASS

Compared observed states against approved mockup sections `loading`, `empty`, `error`, and `fallback`, plus its empty-snapshot study.

- **Loading:** `Loading index…`, blank count, empty results, disabled search, no sculpture, no spinner, and no fake rows. Real content appeared after the controlled response arrived. This matches the study's quiet wait for real data, while retaining incumbent wording instead of its illustrative `Loading snapshot…`.
- **No match:** Same recovery sentence as the study. Reset restored actual content. No scene competed with recovery text.
- **Error/empty snapshot:** Incumbent recovery text remained readable inside the paper note treatment. Commands wrapped at phone width rather than clipping. Data failures did not show a decorative scene.
- **Fallback:** Static fold read as a pose diagram. No motion control appeared without motion. Useful topic and search controls stayed primary.
- Both widths had no horizontal document overflow in every injected state. Phone search and controls remained above the fallback and recovery content.

Loading screenshots: [desktop](failure-loading-1440-loading.png) · [phone](failure-loading-390-loading.png). Recovery screenshots: [desktop](failure-loading-1440-state.png) · [phone](failure-loading-390-state.png). Other state comparisons use the linked F1/F3/F4 screenshots above.

## Restoration and scope

Removed interception by leaving the scoped runs, then loaded the unmodified route again. Observed `Topics`, `542 of 542 files`, enabled search, and a real rendered canvas: [restored route](failure-restored-1440.png). Closed the uniquely named browser tab.

Structured evidence: [failure-proof.json](failure-proof.json). No eval result was recorded. No build, formatter, linter, suite, provider, refresh, or production restart ran.
