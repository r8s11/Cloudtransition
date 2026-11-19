---
feature: Interviews Waiting status and Update application layout
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Interviews Waiting status and Update application layout

Roosevelt tracks applications on the Command Center Interviews page, read from and written back to `interviews/job-applications.yml`. This adds a `waiting` status ("Applied or interviewed; waiting to hear back") whose rows sit in their own Waiting card at the bottom of the page, above Closed threads, counted in Tracked but not as active work and never offered on Today. It also regroups the per-row "Update application" panel into labelled sections sized to their content.

## Build contract

- Build only after `status: approved`. Editing this file or the mockup resets every result; changing what a case checks needs the user's re-approval (`status: review`).
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/interview-waiting-status/eval.md`
- Manual cases: `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/interview-waiting-status/eval.md <ID> pass|fail "<what you observed + evidence path>"`. Save screenshots under `docs/plans/interview-waiting-status/eval-evidence/`.
- Any code change after an automated case passed makes it stale. Done = every automated case passing; manual cases are advisory and only block when recorded as `fail`.
- Automated cases run with `bash -c` from the repo root; exit 0 = pass.
- New tests live in `dashboard-app/tests/test_interview_waiting.py` and use temporary tracker copies; they never write the real `interviews/job-applications.yml`.

## Traceability

| Requirement (from RD) | Cases |
| --- | --- |
| 1. `waiting` accepted by the tracker, labelled "Waiting" | U1, U2, F1 |
| 2. Waiting card below New leads and Agents, above Closed threads, with explanation | U3 |
| 3. Status change to/from Waiting moves the row without reload and updates counts | U5 |
| 4. Tracked includes Waiting; In conversation and New leads exclude it; Waiting count shown | U3, U6 |
| 5. Today never picks a Waiting row | U7 |
| 6. Waiting rows keep row controls and can be reopened | U5, U8 |
| 7. Update application panel grouped and sized; phone, tablet, desktop | U9 |
| 8. Closed threads, other statuses, write path and other tracker readers unchanged | R1, R2, R3, R4, R5 |

## Usage — every way to use the feature

### U1 — Status endpoint accepts `waiting`
- **Setup:** temporary copy of a tracker with one `applied` application (fixture built inside the test).
- **Steps:** POST `/api/interviews/field` (the existing status endpoint) with that company/role, `field: "status"`, `value: "waiting"` and header `X-Requested-With: XMLHttpRequest`.
- **Expected:** HTTP 200; JSON `row.status == "waiting"`, `row.status_label == "Waiting"`; the file's entry now reads `status: "waiting"` with every other line byte-identical.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_status_endpoint_accepts_waiting`

### U2 — Waiting appears in every status picker
- **Setup:** real app context.
- **Steps:** render the Interviews page.
- **Expected:** the Add application status select and each row's status select include an option `value="waiting"` with text `Waiting`, placed after `Offer` and before `Rejected`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_waiting_option_is_offered`

### U3 — Waiting rows render in their own card at the bottom
- **Setup:** fixture tracker with one each of `interviewing`, `applied`, `new_lead`, `waiting`, `rejected`.
- **Steps:** call `build_interview_view` and render `pages/interviews.html` with it.
- **Expected:** `interview_waiting` holds exactly the waiting row; `interview_active` holds interviewing + applied; `interview_leads` holds new_lead only. In the HTML, the card `data-interview-section="waiting"` (title "Waiting", count badge `1`, note "Applied or interviewed; waiting to hear back. Not counted as active work.") comes after `data-interview-section="leads"` and `id="interviewAgents"` and before the Closed threads card.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_waiting_rows_get_their_own_bottom_card`

### U5 — Reopening a Waiting row
- **Setup:** as U4, row already Waiting.
- **Steps:** choose Status → Interviewing.
- **Expected:** row moves back into In conversation; counts reverse; file shows `status: "interviewing"`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_waiting_round_trip_restores_counts`

### U6 — Pipeline counts
- **Setup:** U3 fixture.
- **Steps:** read `interview_counts` and the rendered Pipeline card.
- **Expected:** `tracked == 4`, `active == 2`, `leads == 1`, `waiting == 1`, `closed == 1`; the Pipeline card shows five stats in order Tracked, In conversation, New leads, Waiting, High priority, each with `data-interview-count`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_counts_include_waiting_only_in_tracked`

### U7 — Today ignores Waiting rows
- **Setup:** fixture with a `waiting` row whose next step is dated tomorrow and an `applied` row dated in 5 days.
- **Steps:** call `next_interview_action(rows, today)`; then with only the waiting row.
- **Expected:** first call returns the applied row; second returns `None`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_today_never_picks_waiting`

### U8 — Waiting rows keep their controls
- **Setup:** U3 fixture rendered.
- **Steps:** inspect the Waiting row's markup.
- **Expected:** it has the `Interview mode` button, the Posting link when `job_url` exists, and the `Update application` panel with all four forms (`data-interview-select`, `data-interview-next-form`, `data-interview-signal-form`, `data-interview-notes-form`).
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_waiting_row_keeps_controls`

### U9 — Update application panel is grouped
- **Setup:** U3 fixture rendered.
- **Steps:** inspect one row's `details.interview-tools`.
- **Expected:** four `fieldset` groups with legends in this order: "Status and priority", "Next action", "Log a signal", "Interview notes"; Next action uses a `textarea` (rows=3, grows with content) so long actions are readable; date inputs carry class `interview-field-date`; every existing `data-interview-*` hook and `name` attribute is still present.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_update_panel_is_grouped`

## Failure — every way it could go wrong

### F1 — Unknown status still rejected
- **Setup:** tracker copy.
- **Steps:** POST `/api/interviews/field` with `field: "status"` and values `waiting_list` and `WAITING`.
- **Expected:** HTTP 400 with the existing invalid-status error; file bytes unchanged.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_unknown_status_still_rejected`

### F3 — No Waiting rows
- **Setup:** fixture without any waiting row.
- **Steps:** render the page.
- **Expected:** no Waiting card is rendered, the Waiting stat shows `0`, and no empty heading appears.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_no_waiting_card_when_empty`

## Regression — what this feature must not break

### R1 — Existing test suite still passes
- **Expected:** full dashboard suite green, including `tests/test_interviews.py`, `tests/test_interview_endpoints.py`, `tests/test_interview_editor.py`, `tests/test_interview_agents.py`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/ -q`

### R2 — The app imports and the client script parses
- **Expected:** zero errors. No typecheck or build step exists; import and a syntax check stand in.
- **Verify:** `cd dashboard-app && venv/bin/python -c "import app" && node --check static/app.js`

### R3 — Closed threads unchanged
- **Expected:** rejected/withdrawn rows still go only to the collapsed Closed card, sorted newest signal first, excluded from all live counts.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interviews.py -k "closed"`

### R4 — Today's interview action unchanged for live rows
- **Expected:** soonest upcoming / most recent overdue selection stays as today.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interviews.py -k "next_interview_action or today"`

### R5 — Career page still lists every application
- **Expected:** `pages/career.html` renders all tracker rows, waiting included, with their status label.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_interview_waiting.py -k test_career_page_lists_waiting_rows`

