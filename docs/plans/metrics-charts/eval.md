---
feature: Metrics page graphs and charts
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Metrics page graphs and charts

Adds graphs and charts to the dashboard **Metrics** tab for Parrot and Flatbush: capacity bars and sparklines on the host cards, network and disk I/O rate history, storage capacity bars, ranked workload bars, a probe up/down timeline and log volume by severity. Read-only; data comes from the existing Parrot Prometheus and Loki. Charts are added alongside the existing tables, not in place of them.

## Build contract

- Build only after `status: approved`. Editing this file or the mockup resets every result; changing what a case checks needs the user's re-approval (`status: review`).
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/metrics-charts/eval.md`
- Manual cases: `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/metrics-charts/eval.md <ID> pass|fail "<what you observed + evidence path>"`. Save screenshots under `docs/plans/metrics-charts/eval-evidence/`.
- Any code change after a case passed makes it stale. Done = `evals.mjs check docs/plans/metrics-charts` prints PASS.
- Automated cases run with `bash -c` from the repo root; exit 0 = pass.
- New backend tests live in `dashboard-app/tests/test_metric_charts.py` and use a fake `_fetch_json` with synthetic Prometheus/Loki payloads; no network.
- Manual UI cases run against the real dashboard (`http://127.0.0.1:8000`, Metrics tab) with live telemetry, at 1280×900 and 390×844, and are compared with the named mockup section.

## Traceability

| Requirement (from RD) | Cases |
| --- | --- |
| Network & disk I/O rate history; interface groups separate, not summed | U2, F1, F5 |
| Workloads ranked bars, CPU/memory switch, respects filters, not-exported states | F7 |
| Probe up/down timeline + latency; log volume by known severity, unknown separate | U5, U6, F2 |
| History windows 1 h / 6 h / 24 h; current-only where no history | F4 |
| Orizuru design system, hand-built SVG, no chart library/CDN | D1–D5, R4 |
| Bounded queries, unchanged polling cadence, one failing source isolated | F1, F2, F6 |
| Existing tables and metrics tests unchanged | R1, R3 |

## Usage — every way to use the feature

### U2 — Network and disk I/O rate history for the selected host
- **Setup:** Fake range payload with physical (`en*/eth*/wl*`) and Tailscale receive/transmit rates and per-device disk read/write rates for Parrot, including one device with no activity.
- **Steps:** Call the new rate-history collector for `6h`; request `/api/metrics/rates?window=6h`.
- **Expected:** Response has, per host, separate `physical` and `tailscale` series for receive and transmit (never summed together) and per-device read/write series. Points are bounded by the existing history point cap and aligned to the window step. Devices with no samples are listed as idle, not drawn as zero lines.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_rate_history_keeps_interface_groups_separate`

### U5 — Probe up/down timeline with current latency
- **Setup:** Fake range payload of `probe_success` for 3 probes over `6h`: one always up, one with a down interval, one with missing samples.
- **Steps:** Call the probe-history collector; open Service reachability on the real dashboard.
- **Expected:** Backend returns per probe a sequence of `1`, `0` or `null` per step, keyed by service, kind and target. UI draws filled cells for up, marked cells for down and empty dashed cells for no sample, plus current probe duration. A missing sample is never shown as up or down.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_probe_history_distinguishes_up_down_and_missing`

### U6 — Log volume over time by known severity
- **Setup:** Fake Loki matrix for Flatbush with `Error`, `Warning`, `Information` and unlabelled series, timestamps offset from the window step and with sparse buckets.
- **Steps:** Call the log-volume collector for `6h`.
- **Expected:** Counts are bucketed onto the window's steps by timestamp (not by array position), grouped by reported level, unlabelled lines counted under `unknown`, and no severity is inferred from message text. Totals equal the sum of input counts.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_log_volume_buckets_by_timestamp_and_keeps_unknown`

## Failure — every way it could go wrong

### F1 — Prometheus range query fails
- **Setup:** Fake fetch returns `None` for every range query while instant queries succeed.
- **Steps:** Call history, rate-history and probe-history collectors; load the UI with the same condition.
- **Expected:** Each collector returns `status: "unavailable"` with empty series, never stale or zero-filled values. UI shows the current snapshot, "History unavailable" in place of sparklines, current-only rates text, and current probe status badges instead of a timeline.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_range_failures_are_unavailable_not_zero`

### F2 — Loki unreachable
- **Setup:** Fake Loki fetch returns `None`; Prometheus succeeds.
- **Steps:** Call the log-volume collector and load the UI.
- **Expected:** Log volume reports unavailable; every Prometheus-backed chart still renders.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_loki_failure_isolated_from_prometheus_charts`

### F4 — Invalid window parameter
- **Setup:** None.
- **Steps:** Request `/api/metrics/rates?window=7d` and `?window=1h;drop`.
- **Expected:** HTTP 400 with an error message; no Prometheus or Loki request is made. Existing `/api/metrics/history` behavior is unchanged.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_chart_endpoints_reject_unknown_windows`

### F5 — Invalid samples and gaps
- **Setup:** Fake payloads with `NaN`, `+Inf`, negative rates, out-of-window timestamps and a missing stretch.
- **Steps:** Call the rate, probe and log collectors.
- **Expected:** Invalid samples are dropped; gaps stay gaps (no interpolation); remaining points keep their timestamps.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_invalid_samples_dropped_and_gaps_preserved`

### F6 — Slow source
- **Setup:** Fake fetch where the rate-history request raises a timeout and the others succeed.
- **Steps:** Call the combined chart-data function.
- **Expected:** Only the timed-out section is unavailable; others are returned; total call completes without waiting for more than one bounded request timeout per source.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_slow_source_only_blanks_its_section`

### F7 — Large data volumes
- **Setup:** Fake snapshot with 200 containers, 40 disk devices and 30 probes; 24 h window.
- **Steps:** Call collectors and render the page.
- **Expected:** Backend series stay within the existing point cap per series; ranked bars show the top 10 with a count of the rest; devices beyond a fixed limit are listed by name, not drawn; the page has no horizontal scroll at 390 px.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_metric_charts.py -q -k test_large_inputs_are_bounded`

## Regression — what this feature must not break

### R1 — Existing test suite still passes
- **Expected:** full dashboard suite green.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q`

### R2 — Syntax and build checks
- **Expected:** Python modules compile and the metrics script parses; there is no frontend build step.
- **Verify:** `dashboard-app/venv/bin/python -m py_compile dashboard-app/app.py dashboard-app/collectors/metrics.py dashboard-app/collectors/server_activity.py && node --check dashboard-app/static/metrics.js`

### R3 — Existing metrics data and tables unchanged
- **Steps:** Run existing host-history, infrastructure, process and server-activity tests; open Metrics.
- **Expected:** All existing tests pass unmodified. Every existing table (resources, network, volumes, disks, processes, containers, services, probes, logs, coverage) is still present with the same columns.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_host_history.py dashboard-app/tests/test_infrastructure.py dashboard-app/tests/test_process_activity.py dashboard-app/tests/test_server_activity.py -q`

### R4 — Design contracts hold
- **Expected:** Existing design-contract tests pass (muted-ink contrast, no wildcard reduced-motion, no layout-property transitions, progress via transform, tokens not inline colors). No chart library, CDN or external image is added.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests/test_design_contracts.py -q`

