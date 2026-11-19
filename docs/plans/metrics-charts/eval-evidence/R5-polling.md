# R5 polling cadence — live dashboard http://127.0.0.1:8000/#metrics (2026-11-10)

Method: managed Chromium tab `mr-live`, 1280x900, Live checked, History = Last hour, fresh page load.
Request times are `performance.getEntriesByType("resource")` `startTime` seconds since navigation (same page, no proxy). All requests to `/api/metrics*` are listed; nothing else is hidden.

## A. Metrics active, Live on, 195 s observed (>= 3 min window requirement: 3 x 60 s history/chart cycles plus 3 further)
```
/api/metrics                       @ 0.2 15.3 30.2 45.2 60.2 75.2 90.2 105.2 120.2 135.2 150.2 165.2 180.2 195.2   -> every 15 s (14 requests)
/api/metrics/history?window=1h     @ 0.2 60.2 120.2 180.2                                                           -> every 60 s
/api/metrics/rates?window=1h       @ 0.2 60.2 120.2 180.2                                                           -> every 60 s (the new chart-data endpoint)
```
Snapshot interval 15.0 s, history/rates interval 60.0 s. No other `/api/metrics*` requests.

## B. Metrics not the active page (hash switched to #today at ~201 s)
Status text: "Live refresh paused". Requests between 201 s and 281 s (80 s observed): **0**.

## C. Return to Metrics
Hash back to #metrics at ~288 s: one `/api/metrics` + `history` + `rates` request at 287.8-287.9 s (immediate refresh on resume), cadence resumes.

## D. Tab hidden
Managed headless Chromium and a headed Chromium window (minimised through the OS window control) both kept `document.visibilityState` = "visible" (automation disables occlusion/backgrounding), so a real hidden tab could not be produced here.
Substitute, labelled as emulation: `document.hidden` overridden to `true` and a `visibilitychange` event dispatched.
- Status text: "Live refresh paused". Requests in the next 45 s: **0**.
- Restoring `document.hidden` + `visibilitychange`: immediate refresh (361.9 s: snapshot, history, rates) and "Auto-refresh · 15 s" returns.
This exercises the same `document.hidden` branch of `syncPolling()` the browser would, but is not a true background-tab observation.

## E. Live toggle
Live unticked: "Live refresh paused", **0** requests in the next 40 s. Live re-ticked: immediate snapshot + history + rates at 405 s, status "Auto-refresh · 15 s".

## Verdict inputs
Snapshot 15 s, history and chart data 60 s, none while Metrics is inactive or Live is off; hidden-tab case observed only by emulation.
