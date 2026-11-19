# Google Calendar dashboard implementation plan

> **For agentic workers:** Execute the approved contract using independent source/provider implementation and inline dashboard integration. Parent owns integration and verification.

**Goal:** Show an honest seven-day agenda and create explicitly scheduled Google Tasks/events automatically from an explicitly enabled source policy.

**Architecture:** Keep source files authoritative. A source module validates and edits structured schedules. A private service persists opt-in policy and outcomes, calls Google through the existing Google-enabled Python environment, and reconciles every 60 seconds without a browser. Dashboard uses same-origin endpoints and existing paper/ink components.

**Tech Stack:** FastAPI, Jinja, vanilla JavaScript, Python standard library, installed Google clients in `.kb-venv`.

**Spec:** `rd.md`, approved `eval.md`, `mockup.html`.

## Global constraints

- Build approval does not authorize live OAuth, API enablement, policy activation or remote writes.
- Default off; create-only; date-only Tasks, explicit start/end/IANA events, undated local.
- Separate Calendar and Tasks grants; private owner-only state outside workspace retrieval.
- No arbitrary source paths, private academic/employer sources, blind uncertain retries, remote update/deletion or invitations.
- Source allowlist/destination expansion requires fresh backlog confirmation. GET never enables or publishes.
- Skip mid-flight suites; run focused Calendar and complete dashboard checks once after integration, then fix observed failures.

## Task 1 — Source schedules and identity

**Files:** new `dashboard-app/calendar_sources.py`, `tests/test_calendar_sources.py`.

- [x] Implement strict date/time/DST validation, metadata split/annotation, registry/privacy checks and all-action collection.
- [x] Implement unique stable identities and conservative ambiguity/conflict behavior.
- [x] Implement stale-checked Markdown and line-targeted interview schedule edits preserving neighboring bytes.
- [x] Cover source scheduling/privacy with isolated synthetic tests.

**Interfaces:** `split_metadata`, `validate_schedule`, `annotate`, `source_choices`, `collect`, `schedule_item` as recorded in worker contract.

## Task 2 — Private provider and automatic service

**Files:** new root `calendar_bridge.py`, `dashboard-app/google_calendar.py`, `tests/test_calendar_provider.py`.

- [x] Implement explicit separate Calendar login, bounded choices and paginated seven-day agenda.
- [x] Reuse Tasks grant/private state; publish Tasks with marker recovery and events with deterministic IDs.
- [x] Implement persisted disabled-by-default policy, exact-backlog confirmation, pause, conflicts and bounded 60-second worker.
- [x] Cover agenda, policy, authorization, recovery and pause with isolated providers and clock.

**Interfaces:** `CalendarService.snapshot/refresh/preview/enable/pause/run_once/start/stop`. Config fields: `calendars`, `event_calendar`, `tasklist`, `timezone`, `sources`.

## Task 3 — Dashboard integration

**Files:** `app.py`, `templates/_macros.html`, `templates/pages/today.html`, `templates/pages/interviews.html`, `templates/index.html`, new `templates/_calendar.html`, new `static/calendar.js`, `static/style.css`, `static/app.js`, new `tests/test_google_calendar.py`.

- [x] Wire service lifecycle and read/refresh/preview/enable/pause/schedule endpoints with source validation, existing file lock and atomic writer.
- [x] Strip metadata only from displayed titles; preserve raw stale-check text during toggles.
- [x] Add agenda after Daily, inline settings with explicit disclosure/backlog review, and accessible scheduling in Today/Tasks/Interviews/capture.
- [x] Preserve current navigation/design tokens and bump changed asset versions.
- [x] Add endpoint and capture regression tests; expose approved test names across focused integration/source/provider modules.

## Task 4 — Proof and setup docs

**Files:** `CALENDAR-README.md`, `CODE.md`, this feature's RD/eval/evidence, dashboard guide if needed.

- [x] Run existing CLI tests and complete dashboard suite; lint/run focused eval.
- [x] Restart LaunchAgent and verify import, `/`, `/reader`, missing-connection behavior.
- [x] Verify actual desktop/mobile surface, inline settings/scheduling, keyboard focus, inert titles, honest connection/error states and reduced motion.
- [x] Document exact separate consent command, scopes, source/destination review, private state and create-only limits. Do not claim unapproved live proof.
- [x] Update router and approval wording, and record measured evidence.
