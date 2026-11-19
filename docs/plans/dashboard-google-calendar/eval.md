---
feature: Google Calendar agenda and automatic dashboard publishing
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Google Calendar in Command Center

See upcoming events on Today. Automatically create Google Tasks for explicitly dated local items and Calendar events for explicitly timed items from enabled, nonprivate sources. Preserve local files, separate grants and duplicate protection.

## Build contract

- The user approved this contract and mockup on 2026-11-14. Approval does not authorize OAuth, enabling APIs, enabling live automation or publishing real account data.
- Nine automated cases and four manual cases. Commands run from the Cloudtransition workspace root. Integration tests live in `dashboard-app/tests/test_google_calendar.py`, source tests in `test_calendar_sources.py`, provider/policy tests in `test_calendar_provider.py`; all use isolated synthetic files, clocks and provider-boundary fixtures, never real network, tokens or live background services. Existing `calendar_tests/` supplies legacy CLI coverage. Do not copy provider logic into test fakes or assert source-text wiring.
- Run `node ~/.agents/skills/write-evals/scripts/evals.mjs lint docs/plans/dashboard-google-calendar/eval.md` and `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/dashboard-google-calendar/eval.md` after implementation. The runner currently invalidates results after unrelated workspace changes and can report other features globally even with a directory argument. Report that separately, not as a failing Calendar behavior or a reason to falsify evidence.
- Manual evidence: `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/dashboard-google-calendar/eval.md ID pass|fail "sanitized evidence path"`. Store private account evidence outside shared retrieval; screenshots under `eval-evidence/` must use synthetic content or explicit sanitization. Manual checks are advisory unless recorded failing. No pixel-perfect match, repeated neighboring feature suites or new global all-evals prerequisite.
- Keep legacy CLI preview/publish approvals intact. This feature adds an explicit, persistent automation policy; it does not silently authorize unattended use of an old CLI fingerprint.
- Build must include user setup documentation and source/destination disclosure. All RD requirements are mapped below; none intentionally unmapped.

## Traceability

| Requirement | Cases |
| --- | --- |
| Seven-day agenda, all-day/timed/recurring instances, named timezone and Tasks distinction | U1 |
| Capture and scheduling in Today/Tasks/interviews; local task remains authoritative | U2, R1 |
| Automatic creation from selected TASKS/interview/extra-realm sources without an open browser | U3 |
| Date-only Tasks, timed events, no inferred dates/durations, undated/complete/fenced exclusions | U2, F2 |
| Initial backlog, policy confirmation, allowed sources and destinations, persistent Pause | U3, F1, F4 |
| Separate OAuth, setup steps, CSRF and no GET mutation | F1, R1 |
| No private path/content/token disclosure | F2, R1 |
| No duplicates after restart, overlap or uncertain success; safe partial failure | F3 |
| Create-only conflicts, external edits and local-save survival | F4 |
| Independent outages and honest stale/loading/empty/reconnect states | U1, F1, F3 |
| Existing CLI, toggle/interview editor/reader/tab/run behavior stays working | R1, R2 |
| Focused, cheaper checks with no weakened safety or fabricated live proof | R1, R2 |

## Usage

### U1 — Read an honest upcoming agenda
- **Setup:** `test_calendar_provider.py::test_agenda` creates two permitted calendars, paginated recurring instances, cancelled events, an all-day event spanning a timezone boundary, a missing title, an inert HTML title, and one mapped Google Task with a fake clock.
- **Steps:** Request agenda for its seven-day display window; change selected calendars and refresh with one source failing.
- **Expected:** Sort actual occurrences by local date/time; display all-day without timezone drift, cancelled instances excluded, untitled event labeled, Task/Event and source distinguished. Bound pages/window and expose truncation if capped. Titles remain text, Google links use safe https URLs. Zero results says No upcoming events; failure says Unavailable or Last updated with explicit stale state, never empty success. No publishing or login from reading. Successful sources remain visible when another fails.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q -k test_agenda`

### U2 — Save and schedule underlying local work through every entry point
- **Setup:** `test_calendar_sources.py::test_schedule_sources` and HTTP integration cases create TASKS.md, a permitted extra realm and an interview YAML with multiple next actions. Use duplicate titles, Unicode, completed entries, fenced examples and source line movement; source files are isolated.
- **Steps:** Capture undated work; add a date via Today; add a timed schedule via Tasks; schedule an interview action; read the same source through other views; toggle and reload.
- **Expected:** Undated capture saves once to Inbox without Google creation. Valid date/timed fields persist in structured source metadata and survive reload/toggle. Rendered titles hide metadata. Interview scheduling preserves other steps, hand-written notes/comments and unrelated YAML. All eligible next actions are discoverable, not only the first displayed one. Same underlying item retains one identity across Today/Inbox/Projects/Tasks. Dates are not inferred from prose, status, headings or history. Completed/fenced/malformed entries are not sent. Existing optimistic/stale edit protections remain intact.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q -k test_schedule_sources`

### U3 — Enable policy once and publish automatically without a browser
- **Setup:** `test_calendar_provider.py::test_automatic_policy` creates configured fake account/calendar/list choices and isolated persisted policy/state, with pre-existing backlog plus new eligible source items. Fake worker clock, no browser.
- **Steps:** Start disabled; preview backlog; explicitly enable named sources/destinations; advance through a reconciliation interval; restart service and repeat; edit a source file while no browser is open.
- **Expected:** No write before activation. Backlog preview lists outgoing sanitized titles, schedules and destinations; final activation binds reviewed backlog and future create-only rule. New eligible work publishes within one 60-second interval while service is running. Date-only creates exactly a needsAction Google Task; explicit start/end/timezone creates exactly one attendee-free event, not also a Task. Unselected files/destinations never publish. Policy persists, destination/source expansion requires confirmation, IDs/outcomes are recorded privately and repeated views/passes do not repeat creates.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q -k test_automatic_policy`

## Failure

### F1 — Refuse unauthorized configuration or writes
- **Setup:** Provider and HTTP `test_authorization` cases supply missing/revoked/wrong-scope grants, disabled/read-only destinations, cross-origin writes, missing CSRF, forged source/calendar/list IDs and malicious file paths.
- **Steps:** Read agenda, submit settings/schedule/activation, try mutating via GET, then run worker with rejected authorization.
- **Expected:** Missing connection shows Connect or Reconnect, not a broken Today page or automatic browser login. Missing-CSRF/invalid-origin mutations fail before writes; forged/disallowed inputs fail before provider calls. GET never enables/schedules/publishes. 401/403 pauses affected publishing; unaffected local/read sources remain available. Token and provider response secrets never enter HTML or errors. Calendar grant never widens existing Tasks/Gmail grants. Docs explain actual scope breadth, tailnet visibility and reconnection.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q -k test_authorization`

### F2 — Reject unsafe schedules and private sources before transfer
- **Setup:** Source and HTTP `test_schedule_privacy` cases supply invalid/leap dates, missing/negative event duration, unknown timezone, nonexistent/ambiguous DST local times, conflicting date/timed fields, oversized titles, duplicate source ambiguity, source mutation, College Planning and secret/employer-private paths, symlink aliases and embedded instructions.
- **Steps:** Preview, save and run each invalid/forbidden configuration; inspect captured outgoing payloads and real file-reader/index policy helpers with private canaries.
- **Expected:** Invalid/ambiguous inputs show actionable errors and make no provider write; no silently chosen DST occurrence, time/date/duration or truncated payload. Source text executes nothing. Privacy-denied files cannot be enabled, read through new APIs or indexed with runtime state. Allowed payload contains only sanitized title, required schedule and opaque identity: no notes, contacts, adjacent contents or secrets. Failed schedule save leaves source bytes unchanged.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q -k test_schedule_privacy`

### F3 — Keep outcomes truthful without duplicate publication
- **Setup:** `test_calendar_provider.py::test_publication_recovery` injects a success followed by 429/5xx, timeout after remote creation, failed local success persistence, overlapping worker passes, restarted process and ambiguous marker matches for Tasks and Calendar services.
- **Steps:** Publish, interrupt/restart and reconcile; issue concurrent refresh/scheduling requests and recover provider availability.
- **Expected:** Known successes remain mapped; only eligible unsent work advances. Timeout/5xx uncertainty is reconciled by existing Task markers or deterministic Calendar identity, never blind reinsert. Ambiguous or unverifiable outcomes remain Needs review. Worker overlap is refused/serialized; 429/network failures defer without hot retries. No one provider outage blocks local capture or discards successful agenda data. Logs exclude source text, grants and provider bodies; failed items never claim success.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q -k test_publication_recovery`

### F4 — Pause and conflicts do not destroy local or remote work
- **Setup:** `test_calendar_provider.py::test_pause_conflicts` creates published and pending items, persisted policy, a provider outage and remote edits; simulate source title/date edits, completion, deletion and unrelated line shifts.
- **Steps:** Pause while work is queued, restart, capture locally during outage and change published sources; resume under unchanged policy.
- **Expected:** Pause survives restart and prevents unsent creates; already-started requests may finish and UI says so. Local captures and checkbox changes survive outages. Published source edits show Needs review with Google link; no silent remote update/delete, replacement creation, completion mirroring or local overwrite. Source deletion never deletes remote data. Unique source identities survive unrelated movement; ambiguous duplicates stop instead of guessing. Resume never uses changed source/destination scope without renewed policy confirmation.
- **Verify:** `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q -k test_pause_conflicts`

## Regression

### R1 — Existing calendar and dashboard suites pass once
- **Setup:** Synthetic isolated tests; no live services, keys or account data. Update true contract tests only when the reviewed feature intentionally changes that contract; never weaken privacy/toggle tests.
- **Steps:** Run current calendar CLI tests and complete dashboard suite, including new integration tests.
- **Expected:** Both suites pass. Legacy CLI still requires exact-batch approval and never auto-publishes. Existing local toggle, unique-text conflict handling, interview editors, readers/private-path restrictions, tab navigation and runners retain tested behavior. No requirement to rerun unrelated KB/map/agent suites for this feature.
- **Verify:** `python3 -m unittest discover -s calendar_tests && dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q`

### R2 — Imports and real dashboard routes remain available
- **Setup:** After implementation restart the dashboard LaunchAgent once using its documented command; server listens on loopback 8000. Run from workspace root. No frontend build/typecheck exists for this Python/Jinja app.
- **Steps:** Import app and exercise both documented GET smoke routes with normal connection success or failure.
- **Expected:** Import exits zero; / and /reader return 200. Missing or unavailable Google does not crash initial rendering, open consent or publish as a side effect. No new listener or paid service is required.
- **Verify:** `dashboard-app/venv/bin/python -c "import sys; sys.path.insert(0, 'dashboard-app'); import app; print('import OK')" && curl -fsS -o /dev/null http://127.0.0.1:8000/ && curl -fsS -o /dev/null http://127.0.0.1:8000/reader`

