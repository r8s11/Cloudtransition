# Command Center Browser Assets

## Overview

Browser controllers connect the Jinja-rendered dashboard to same-origin APIs. Scripts use classic browser globals and private IIFEs rather than a bundled module graph. Metrics stays read-only; task, capture, interview, memory, and runner actions delegate writes or execution to the backend. [app.js:animateBars] [app.js:bindTaskCheck] [metrics.js:fetchSnapshot] [cards-parser.js:window.CardDataParser]

## Interface

| Source | Public or integration boundary |
| --- | --- |
| [app.js](./app.js) | Globals `animateBars(scope)`, `paintTaskCheck(box, done)`, `sameTaskChecks(box)`, `bindTaskCheck(box)`, `updateRoutineReviewProgress()`, `setRoutineSaveStatus(message, isError = false)`. Other controllers communicate through DOM selectors and events. |
| [metrics.js](./metrics.js) | Private controller activates when `#page-metrics` exists; controls `#metrics-refresh`, `#metrics-host`, `#metrics-window`, `#metrics-live`. Exports no globals. |
| [work-search.js](./work-search.js) | Private Career controller for seven-day activity reports, explicit completed-activity entry/editing, and field/activity/week clipboard actions. |
| [cards-parser.js](./cards-parser.js) | Browser global `window.CardDataParser` exposes static normalization, validation, aggregation, and statistics methods. It is not an ES-module export. |
| [manifest.webmanifest](./manifest.webmanifest) | Install metadata: Command Center, standalone display, scope `/`, start URL `/#today`, and local icon URLs. |
| [style.css](./style.css), [tokens.css](./tokens.css) | Stylesheet assets, not JavaScript interfaces. Font assets and their licenses live under `fonts/`. |

### DOM and HTTP contracts

- Tabs use `.section-nav [role="tab"]`, `data-page`, `[role="tabpanel"]`, and `#page-{page}`. Arrow keys wrap; Home/End jump. Selection changes classes, ARIA, focus, and URL hash. [app.js:DOMContentLoaded] [app.js:activateTab]
- Fold controls use `.fold-column`, `.fold-step[data-fold-label]`, and `#fold-focus-card`; optional neural SVG renders category counts. Realm pills filter `.realm-section`. [app.js:data-fold-enhanced] [app.js:.realm-pill]
- `.task-check[data-realm]` carries realm, text, line, and done state. `bindTaskCheck()` POSTs `{realm,line,done,text}` to `/api/tasks/toggle`. [app.js:bindTaskCheck]
- `[data-copy-prompt]` copies referenced template text. Future-prompt selection uses `#promptGenBar`, `#promptSelCount`, `#generatePromptBtn`, `#clearSelectionBtn`, and `.task-select-input[data-realm='prompts']`. [app.js:data-copy-prompt] [app.js:promptGenBar]
- `[data-run-grid]` enables runner cards; optional `data-skills` restricts and orders cards. GET `/api/skills/catalog`, POST `/api/skills/catalog/refresh`, POST `/api/skills/run`, and GET `/api/skills/runs` provide catalogue/admission/status. Run body: `{skill,model,effort,input}`. [app.js:loadCatalog] [app.js:data-run] [app.js:poll]
- `#runOutputDialog` displays output fetched from `/api/file?path=…`. `[data-output]`, `data-output-label`, and `[data-close-output]` connect opening, title, and closing. [app.js:runOutputDialog] [app.js:data-output]
- Today forms require `#captureForm`; `#brainAskForm` and `#brainSaveForm` share that initializer. Capture POSTs `/api/capture`; memory retrieval GETs `/api/brain/query`; memory storage POSTs `/api/brain/remember`. [app.js:#captureForm] [app.js:#brainAskForm] [app.js:#brainSaveForm]
- `[data-map-query]` changes `#workspaceMapFrame.src` to `/workspace-map/?…`. [app.js:data-map-query]
- `#page-interviews` rows identify company/role in data attributes. Controls POST `/api/interviews/field`, `/next-step`, `/timeline`, `/text`, and `/create`. These suffixes share `/api/interviews`. [app.js:data-interview-select] [app.js:data-interview-next-form] [app.js:data-interview-signal-form] [app.js:data-interview-notes-form] [app.js:#interviewAddForm]
- Optional `#interviewMode` fetches `/api/interviews/detail?company=…&role=…`; `[data-interview-save]` writes questions, preparation, or notes. `[data-agent-fill]` only fills a runner input; it does not start a model call. [app.js:#interviewMode] [app.js:data-interview-save] [app.js:data-agent-fill]
- Career `#workSearch` GETs `/api/career/work-search?start=YYYY-MM-DD` and POSTs completed activity fields with the CSRF header. The form retains its UUID after saving to prevent retry duplicates; **New activity** generates another. Failed report reads clear stale results; clipboard failures use the incumbent legacy copy fallback, then expose the selected field/activity/report text if copying remains blocked. All record values render as text.
- Metrics GETs `/api/metrics`, `/api/metrics/history?window=…`, and `/api/metrics/rates?window=…`. Snapshot validation requires host data, a projects array, and a parseable timestamp; historical responses must match the selected window. [metrics.js:fetchSnapshot] [metrics.js:fetchHistory] [metrics.js:fetchCharts]

`CardDataParser` includes `parseHostCard()`, `parseProjectCard()`, `parseVolumeCards()`, `parseDiskCards()`, `parseActivityCards()`, `parseChartCards()`, `parseApiResponse()`, `validateSnapshotResponse()`, `validateHistoryResponse()`, `validateChartsResponse()`, `processAllCards()`, `getCardStatistics()`, `calculateCompleteness()`, and `validateDataIntegrity()`. These are static methods, not evidence of live-controller use. [cards-parser.js:CardDataParser]

## Invariants

- Keep globals required by dynamically inserted task rows. Checkboxes match duplicated renderings by realm and text, optimistically paint all copies, and revert on request failure. Only routine toggles disable all copies while saving. [app.js:sameTaskChecks] [app.js:bindTaskCheck]
- Task, runner, capture, remember, and interview writes send JSON with `X-Requested-With: XMLHttpRequest`. This is a backend header contract, not browser-side authorization. [app.js:bindTaskCheck] [app.js:data-run] [app.js:post]
- Runner model values split at the first colon; model IDs may contain further colons. Refresh preserves only still-valid model/effort selections and retains typed input. Empty catalogues block Run. [app.js:splitModel] [app.js:restoreRunnerState] [app.js:renderItem]
- Runner polling uses two-second intervals while runs are active. Output rendering uses text APIs, strips ANSI/control characters for display, and exposes original raw output separately. Older output responses cannot overwrite a newer output request. [app.js:poll] [app.js:parseRunOutput] [app.js:renderRunOutput] [app.js:outputRequest]
- Metrics polls only while its page is active, document visible, and Live checked: snapshot every 15 seconds; history/charts every 60 seconds. Pause stops timers, not existing requests; manual refresh remains available. [metrics.js:syncPolling]
- Snapshot fetches are single-flight with a 12-second deadline. History aborts predecessors and guards response generations with a 12-second deadline; chart requests do the same with 15 seconds. Failed current snapshots clear usage rather than presenting stale readings as current. [metrics.js:fetchSnapshot] [metrics.js:fetchHistory] [metrics.js:fetchCharts]
- Missing telemetry is not zero or proof of host downtime. Non-up hosts lose current readings. Chart gaps remain visible; workload displays preserve explicit unknown/unavailable states. [metrics.js:renderOverview] [metrics.js:renderHistory] [metrics.js:renderActivity]
- Telemetry renders through text and SVG DOM APIs. Log expansion and focused entries survive refreshes by identifier. Table pagination starts at 20 and grows by 20. [metrics.js:renderSnapshot] [metrics.js:renderActivity] [metrics.js:selectHost]
- No scanned controller uses localStorage, sessionStorage, IndexedDB, or cookies. Selected host, filters, runner refresh snapshots, and response generations remain in memory. [app.js:capturedRunnerState] [metrics.js:syncPolling]
- `CardDataParser.validateHistoryResponse()` and `validateChartsResponse()` compare against externally assigned static `currentWindow`; the class does not initialize it. `processAllCards()` expects normalized `snapshotData.hosts`, not an unmodified raw snapshot. Completeness measures presence, not health, and missing arrays can yield `NaN`. [cards-parser.js:CardDataParser.validateHistoryResponse] [cards-parser.js:CardDataParser.validateChartsResponse] [cards-parser.js:CardDataParser.processAllCards] [cards-parser.js:CardDataParser.calculateCompleteness]
- Request-generation protection is not universal: interview detail and brain forms lack the metrics/output cancellation guards. Do not assume all concurrent UI requests are ordered. [app.js:openFor] [app.js:#captureForm]

## Side Effects

- Scripts register event listeners, modify DOM/ARIA/focus, update URL hash with `history.replaceState`, use timers, and write selected prompts to the clipboard. [app.js:activateTab] [app.js:data-copy-prompt] [app.js:announce]
- Same-origin POSTs can persist workspace records, store memory, or start paid/model jobs through the backend. Successful application creation reloads the page. [app.js:data-run] [app.js:#brainSaveForm] [app.js:/api/interviews/create]
- Metrics starts GET requests and observers; masthead resize updates `--ops-sticky-top`. It does not issue mutation requests. [metrics.js:fetchSnapshot] [metrics.js:ResizeObserver]
- `CardDataParser` assigns a browser global and creates normalized objects; aggregation stamps `metadata.lastUpdated` with `Date.now()`. [cards-parser.js:window.CardDataParser] [cards-parser.js:CardDataParser.processAllCards]

## Verification

From `dashboard-app/`, use the existing project suite:

```sh
venv/bin/python -m pytest tests/ -q
```

For controller or style changes, also inspect the actual dashboard at phone and desktop widths. From workspace root, the existing helper captures the running port-8000 server:

```sh
sh dashboard-app/scripts/screenshot.sh today 390
sh dashboard-app/scripts/screenshot.sh today 1280
```

Screenshot capture does not prove task persistence, provider execution, polling recovery, or keyboard behavior. Test those interactions only when they belong to the change; do not launch paid jobs for a documentation check.
