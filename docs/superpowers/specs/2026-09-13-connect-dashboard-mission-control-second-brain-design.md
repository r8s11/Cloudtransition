# Connect Dashboard, Mission Control, and Second Brain — Design

**Date:** 2026-09-13
**Status:** Approved (dashboard-as-shell; proxy mission control + serve second brain)
**Scope:** `dashboard-app` (FastAPI, :8000) becomes the single shell hosting all three systems.

## Problem

Three systems live in this workspace but are disconnected:

1. **Dashboard** — `dashboard-app` (FastAPI + Jinja2, `localhost:8000`) — the Orizuru career
   dashboard built across the previous sessions.
2. **Mission Control** — `agentic-os` (Hono node server, `localhost:8787`) — live mission
   board, approvals queue, transitions. Serves its own `www/index.html`.
3. **Second Brain** — `robonugget-second-brain-app/index.html` — a static, self-contained
   reference page (mermaid diagram, template cards, demo dashboard form). No server, no
   build step; the only external dependency is the Mermaid CDN `<script>`.

There is no way to reach Mission Control or Second Brain from the dashboard.

## Goal

One URL (`localhost:8000`) hosts all three. The Orizuru dashboard is the shell:

- **Second Brain** is served by FastAPI itself at `/second-brain` and embedded in a tab.
- **Mission Control** is embedded in a tab via a reverse proxy at `/mission-control`,
  forwarding to the agentic-os server on `:8787`. All API calls land back through the
  proxy (the dashboard's JS calls root-absolute `/api/*`).
- Navigation gains two tabs: **Mission Control** and **Second Brain**.

## Architecture

```
dashboard-app/app.py                       (FastAPI, :8000)
├── GET /second-brain          → serves robonugget-second-brain-app/index.html (HTMLResponse)
├── GET /mission-control/(path)*  → reverse proxy → 127.0.0.1:8787/(path)
│      · HTML responses rewritten: "/api/ → "/mission-control/api/
│      · /mission-control/api/*  forwarded as-is, JSON passthrough
│      · :8787 unreachable → 502 with an inline "Mission Control offline" page
└── GET /                      → index.html (existing) — now with 9 tabs incl. the two new ones

dashboard-app/templates/pages/
├── mission-control.html   ← iframe src="/mission-control/"   (dark command-center)
└── second-brain.html      ← iframe src="/second-brain"       (RoboNuggets reference page)

templates/index.html       ← two new (id,label) entries in the `pages` list
static/style.css           ← iframe styling + 502 offline state (uses existing tokens)
```

### Components

- **`serve_second_brain()`** — reads `WORKSPACE / "robonugget-second-brain-app" / "index.html"`,
  returns `HTMLResponse` with `media_type="text/html"`. Missing file → 404 page. Static and
  deterministic; no new dependency.
- **`proxy_mission_control(path)`** — stdlib `urllib.request` forward to
  `http://127.0.0.1:8787/{path}`. Two modes:

  - Path starts with `/mission-control/api/` → strip prefix, forward, stream JSON content
    byte-for-byte (Content-Type preserved).
  - Any other path (HTML, or the bare mount) → forward, and in the returned HTML replace
    `"/api/` with `"/mission-control/api/` so the dashboard's inline fetch calls stay
    inside the proxy. Only `/api/` references are rewritten; nothing else.
  - Timeout ~3s. On `URLError`/`TimeoutError` → `HTMLResponse` status 502 with a small
    Orizuru-styled offline card ("Mission Control offline — start agentic-os:
    `cd agentic-os && npm start`" in `apps/api`).

### Data flow

1. User opens `localhost:8000` → Orizuru dashboard, tabs list now includes Mission Control
   and Second Brain after Money.
2. Second Brain tab → iframe loads `/second-brain` → the static RoboNuggets page renders.
3. Mission Control tab → iframe loads `/mission-control/` → proxy fetches `:8787/`, rewrites
   `"/api/` → `"/mission-control/api/` → returns HTML. The embedded page's polling
   (`/api/missions`, `/api/approvals`, `/api/transitions`) now hits `/mission-control/api/*`,
   which the proxy forwards to `:8787`. Actions (create mission, resolve approval, transition)
   follow the same rewritten path. All rule logic still lives in agentic-os Core — the proxy
   never re-implements anything (local-only, no external calls posture preserved).

### Error handling

- `:8787` down → 502 offline card inside the tab (poll-friendly; the iframe shows the card,
  the agentic-os page is never "blank").
- Unknown mission-control subroute → agentic-os returns its own 404, proxied back.
- Second brain file missing → FastAPI 404 page.

## Testing

- `venv/bin/python -c "import app"` — syntax/import OK (server restart needed after app.py
  change; templates hot-reload).
- `agentic-os`: `npm start` (from `agentic-os/apps/api`) → Mission Control on `:8787`.
- Verify: `/` 200 + both new tabs present in nav; `/second-brain` 200 + returns the
  RoboNuggets `<title>`; `/mission-control/` 200 (proxied HTML contains the rewritten
  `mission-control/api` references); `/mission-control/api/missions` proxied JSON from
  agentic-os; `:8787` stopped → `/mission-control/` returns 502 offline card. No leaked
  Jinja in any response.

## Out of scope (explicit)

- No changes to `agentic-os` code, Hono routes, Core, storage, policy, runtime, or config.
  The proxy is transparent; everything agentic-os serves is passed through.
- No new Python or npm dependencies.
- No iframe-clicking behavior changes (approvals and transitions are operated inside the
  agentic-os UI exactly as before, now through the proxy origin).
- No authentication (localhost-only posture unchanged).