# Agentic OS Mission Control Dashboard — Design

**Date:** 2026-09-12
**Status:** Approved (approach A)
**Project:** `agentic-os` (TypeScript npm workspace)

## Problem

Agentic OS Phase 2 built missions, plans, persistence (SQLite), policy, and
approvals behind a CLI. The only way to observe or act on the system is shell
commands. There is no operational view — no way to see the state of missions,
work a pending approvals queue, or drive transitions from a monitor.

This design adds the **mission control dashboard**: a local, live, widget-based
command center in the spirit of the command-center dashboards popularized for
agentic orchestrators. It is the first step toward the fuller command-center
(video reference: "The NEW Agentic OS standard for Claude 5 Models", Jay E |
RoboNuggets — the dashboard section, which also demonstrates that a dashboard
is buildable by simply pointing an agent at a prompt + the repo).

## Goals

- A browser dashboard served locally that shows live mission state.
- Approve/reject approvals and transition missions **from the dashboard**, with
  all actions going through the exact same Core validation and storage layer as
  the CLI (never re-implementing rules or SQL in the API or frontend).
- Fit the existing workspace shape: `apps/api` becomes a real Hono server
  (hono + @hono/node-server are already declared dependencies), a static HTML
  dashboard is served from it, no frontend build step.
- Keep the "local only, no external network calls, no AI/provider logic"
  posture.

## Non-goals (v1)

- No AI/model calls, no model router integration, no connectors.
- No drag-to-reflow widget grid (the video's reflowable widgets are a later
  milestone). v1 uses a fixed responsive CSS grid.
- No calendar / email / timezone / YouTube demo widgets. All widgets are live
  from real persisted data.
- No authentication (localhost-only server).

## Architecture

```
apps/api/src/
├── index.ts            # createApp(db, opts): Hono app (routes + static) — testable without a port
├── mission-service.ts  # MissionService: facade over Core + storage repos
└── server.ts           # bootstrap: load config → Database.open → createApp → serve localhost:8787

apps/api/www/
└── index.html          # mission-control dashboard (vanilla JS/CSS, no build step)
```

### Components

- **`MissionService`** — the only component the HTTP layer talks to. It composes
  the same repositories the CLI uses (`SqliteMissionRepository`,
  `SqlitePlanRepository`, `SqliteTransitionRepository`,
  `SqliteApprovalRepository`) plus Core's domain functions
  (`createMission`, `transitionMission`, `canTransition`). It never writes raw
  SQL. Adds `createApprovalRequest` so the dashboard can *issue* approvals, not
  just act on seeded ones.
- **`createApp(db, opts)`** — pure function returning a Hono app. Routes call
  `MissionService`. Serves `www/index.html` at `/`. Accepts a clock for tests.
- **`server.ts`** — reads `config/agentic-os.yaml` (same loader as the CLI),
  opens the database (`Database.open`), builds the app, listens on
  `localhost:8787` (PORT env override).

### Data contract

| Method | Route | Request | Response |
|---|---|---|---|
| GET  | `/api/missions` | `?status=` | `Mission[]` |
| GET  | `/api/missions/:id` | — | `Mission` or 404 |
| GET  | `/api/missions/:id/plan` | — | `Plan` latest or `null` |
| GET  | `/api/missions/:id/history` | — | `MissionTransitionRecord[]` |
| POST | `/api/missions` | `{title, description?, priority, acceptanceCriteria: string[], id?}` | `Mission` (201) |
| POST | `/api/missions/:id/transition` | `{to: MissionStatus, reason?}` | `Mission` or 400 (illegal) / 404 |
| GET  | `/api/approvals` | `?status=` | `ApprovalRecord[]` |
| POST | `/api/approvals` | `{missionId, capability, action, reason, risk, runId?}` | `ApprovalRecord` (201) |
| POST | `/api/approvals/:id/resolve` | `{status: "approved"\|"rejected"}` | `ApprovalRecord` or 400 (not resolvable) / 404 |
| GET  | `/` | — | `www/index.html` |

Error shape: `{ error: string }` with the appropriate status code.

## Dashboard UI (v1)

Dark command-center aesthetic (reuse the `#131722` / `#7c9eff` palette already
present in `robonugget-second-brain-app/index.html`). Static `index.html` with
vanilla JS; layout is a responsive CSS grid of widget panels.

**Widgets (all live from the API):**

1. **Mission board** — lane per live status (`queued`, `running`,
   `awaiting_approval`, `paused`, `failed`, `completed`, `cancelled`). Cards
   show title, priority badge (critical=red, high=orange, medium=blue, low=gray),
   created date. Clicking a card selects the mission (opens detail panel).
2. **Approvals queue** — pending approvals as cards (capability/action, reason,
   risk, mission id). **Approve** / **Reject** buttons POST resolve; card leaves
   the queue on success. Empty state: "all clear".
3. **Mission detail panel** — for the selected mission: full fields, acceptance
   criteria list, latest plan tasks, transition-history timeline. Includes a
   **transition control**: `<select>` of legal next-statuses (derived from
   Core's transition matrix, exposed via the API response), reason input, and a
   button that POSTs the transition.
4. **New mission form** — title, description, priority, acceptance criteria
   (multi-line, one per line). POSTs to `/api/missions`, then refreshes the board.

**Behavior:**

- Poll `/api/missions` + `/api/approvals` every 5s.
- Actions are committed only on server success; re-render from the server
  response (no optimistic UI).
- Errors render as an inline strip, not console-only.
- `/plan` and `/history` are fetched only for the selected mission (progressive
  loading, keeps polling light).

## Testing

- Extended existing pattern: `apps/api/src/*.test.ts` using
  `Database.memory()` and `createApp` with an in-memory DB. No ports needed —
  Hono `app.request()` drives requests directly.
- Serve tests: list missions, get single (404 path), create mission, transition
  legal + illegal (400), approvals list / create / resolve legal + illegal
  (400), static `/` returns the dashboard HTML, plan + history paths.
- Existing suite (`npm test`) must stay green.

## Out of scope (explicit)

- Any change to `packages/core`, `packages/storage`, `packages/policy`, or
  `packages/config` behavior. New code lives in `apps/api` only.
- Hono dependency is already declared; `npm install` is required (node_modules
  currently lacks hono).