# Metrics page graphs and charts

## User request (verbatim)

> work on design graphs and charts for metric

## Answered scope (2026-11-06)

- **Where:** the dashboard **Metrics** tab (`dashboard-app/templates/pages/metrics.html`, `static/metrics.js`, `metrics.py`, `server_activity.py`) — Parrot and Flatbush server operations.
- **Which metrics:** all five areas — Host overview, Network & disk I/O, Storage capacity, Workloads, Reachability & logs.
- **Time:** history where available, using retained Prometheus samples and the existing 1 h / 6 h / 24 h window; current reading only where no history exists.
- **Scope:** design (mockup + acceptance checks) for approval, then build in the dashboard.

## Requirements

1. **Host overview** — each host card shows CPU, memory and system-volume utilization as a capacity bar plus a sparkline of the selected history window. A host with no telemetry (e.g. Flatbush `pending`) shows an explicit no-data state, never a zero bar.
2. **Network & disk I/O** — receive/send rates (physical and Tailscale interface groups, kept separate, not summed) and per-device read/write rates as time-series charts for the selected host and window. Requires new bounded Prometheus range queries.
3. **Storage capacity** — one horizontal bar per mounted volume: used vs available, absolute sizes and percent as text, read-only volumes marked. Current reading (no history required).
4. **Workloads** — ranked horizontal bars for the top containers and processes by CPU cores, switchable to memory. Respects the existing filter box and state filter. Areas whose exporter is absent (e.g. processes `not_exported`) say so.
5. **Reachability & logs** — a per-probe up/down timeline over the window with current latency, and log volume over time grouped by known severity, with unknown severity shown separately rather than guessed.

## Constraints

- Follow the Orizuru design system (`dashboard-app/DESIGN.md`, tokens in `static/style.css`): calm, flat washi faces, sumi ink, existing series colors (`--accent` CPU, `--blue` memory, `--metrics-success-ink` disk). No dark console, glass, gradients or external chart images/CDNs. Hand-built inline SVG, as the existing Performance history chart does; no new chart library.
- Honesty rules already used on the page stay: gaps mean missing samples (no interpolation across gaps), missing is not zero, values are real Prometheus/Loki data, read-only console.
- Accessibility: every chart has a role/label and an equivalent table or text alternative; series are distinguishable without color (line style, labels, patterns); keyboard reachable controls; `prefers-reduced-motion` honored; contrast held on washi.
- Responsive: desktop and mobile (≤900 px) layouts; charts reflow, no horizontal page scroll.
- Performance and load: bounded queries and point counts like the existing history endpoint; no extra polling faster than the current 15 s snapshot / 60 s history cadence; one failing source does not blank other charts.
- Existing tables remain available (charts add to them, they do not remove data), and existing metrics/activity tests keep passing.
