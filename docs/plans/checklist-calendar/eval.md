---
feature: Checklist items in Google Calendar
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Checklist items in Google Calendar

## Build contract

Build only after the user approves this exact eval. Proposed interface: local CLI preview and explicit publication of selected TASKS.md items as dated Google Tasks visible in Calendar. No dashboard UI, event creation or automatic/bidirectional synchronization. Fixture file `calendar_tests/fixtures.py` creates synthetic Markdown, isolated private state and fake official Tasks service; no real accounts or private workspace tasks in tests. Implementation filenames/commands must be documented before execution, without changing these requirements.

Run `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/checklist-calendar/eval.md`; record manual cases only after observing them. Check with `check docs/plans/checklist-calendar` (directory, not file). Evidence must be sanitized and kept out of shared indexes. No live task write without separate OAuth and exact title/date/list approval. Preserve the approved personal-KB eval and no-spend gate.

## Traceability

| Requirement | Cases |
| --- | --- |
| Source TASKS.md checkboxes and selected-only preview | U1, U2, F1, F2 |
| Calendar-visible tasks, not meeting events | U3, F3, R3 |
| Explicit scheduled date; no invented times | U2, U3, F3 |
| Preview and approve exact outgoing batch | U2, U3, F2, F4 |
| Idempotence and interrupted/uncertain insert recovery | U4, F5, F6 |
| Separate Tasks permissions and private token/state | F4, R3, R4 |
| Source Markdown and dashboard behavior preserved | R1, R2, R5 |
| One-way add only, no background writes or changes to unrelated items | U3, F4, R3 |

## Usage

### U1 — List only real unchecked checklist items
- **Setup:** calendar_tests/fixtures.py has headings, nested boxes, Unicode, checked x/X entries, duplicate titles, malformed lines and fenced checkbox examples.
- **Steps:** Run list/preview from outside the workspace with its absolute CLI path.
- **Expected:** Real unchecked Markdown checkboxes appear with heading, source location and selection identity. Completed boxes and code examples are excluded. No source modification, network request, login or remote write occurs. Empty lists show an explicit no-items state.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_list_checklist_items`

### U2 — Preview an exact selected batch
- **Setup:** Synthetic TASKS.md and two existing task-list choices returned by a fake service; explicit per-item dates.
- **Steps:** Select two items, destination and date(s); create preview without publishing.
- **Expected:** Preview lists every outgoing title, scheduled day, destination and notes/opaque marker. Unselected contents are absent from payload and approval artifacts. No automatic date inference, attendees or start/end times. An approval identifier/fingerprint binds the exact outgoing set and current source content; preview itself makes no write.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_preview_selected_batch`

### U3 — Publish only an explicitly approved preview
- **Setup:** Approved synthetic preview and fake Tasks service.
- **Steps:** Publish the selected batch with matching approval; inspect requests and original Markdown bytes.
- **Expected:** Each selected item is created once in the selected task list, needsAction with the exact approved title, date and notes. Selected day survives Google RFC3339 date encoding. No Calendar event or unrelated task is created/updated/deleted. TASKS.md is unchanged. Output maps successes to source items and real returned IDs.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_publish_approved_batch`

### U4 — Repeat publication without duplicates
- **Setup:** Successfully published synthetic batch, persisted private mappings, same source/task list after a process restart.
- **Steps:** Publish again; reorder unrelated source lines; repeat.
- **Expected:** Existing mapped tasks are reported already published, without another insert. Line-number shifts alone do not cause duplicate creation. Identical titles from distinct source entries are not conflated; ambiguity requires a new selection/preview.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_repeat_publish_idempotent`

## Failure

### F1 — Missing source and ambiguous selection fail safely
- **Setup:** Missing/unreadable TASKS.md, invalid selection IDs, duplicate titles and malformed checkbox entries.
- **Steps:** List/select/publish each invalid case.
- **Expected:** Concise error or explicit no-items state as appropriate, nonzero exit for invalid selection, no guessed task and no remote write. Never fall back to a different file or publish all entries.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_missing_and_ambiguous_source`

### F2 — Source or preview edits invalidate approval
- **Setup:** Valid preview; change title/date/destination/selected set, mark a selected checkbox complete, delete its source or introduce duplicate ambiguity before publish.
- **Steps:** Attempt publication with the old approval for each mutation.
- **Expected:** Refuse before any insert, explain that preview is stale, require review of a new exact batch. Unrelated line shifts may resolve by unique source identity but never silently change approved payload.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_stale_preview_rejected`

### F3 — Invalid or absent dates never invent calendar time
- **Setup:** Missing date, impossible day, datetime passed where day required, leap date, timezone/DST boundary and overlong title/notes.
- **Steps:** Build preview and attempt publish.
- **Expected:** Invalid dates and over-provider-limit fields are rejected before network writes, not silently truncated. Explicit valid scheduled day is preserved independent of machine timezone. No implicit today, duration, start time or unsupported Tasks-API scheduled-time promise.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_date_and_payload_boundaries`

### F4 — Missing auth or approval and embedded instructions remain inert
- **Setup:** Missing/revoked Tasks token, wrong scopes, absent approval and task text demanding shell execution, token exposure or publishing other items.
- **Steps:** Run preview, unattended KB ingest and task publication.
- **Expected:** No browser from unattended operations; no insert without exact approval and Tasks token. Source instructions execute nothing and cannot change destination, dates, permissions or approved set. Secrets are masked or publication rejected, and the exact sanitized payload is visible before approval. Gmail credentials are never used to acquire write access implicitly.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_auth_approval_and_untrusted_text`

### F5 — Partial API failure preserves completed item mappings
- **Setup:** Three approved items; fake insert succeeds for one, then returns a known 401/403/429/5xx on another.
- **Steps:** Publish, report partial outcome and restart after service recovery.
- **Expected:** Successful IDs remain mapped; failed items are not labeled published. Do not blindly repeat a potentially non-idempotent insert. Recovery only creates remaining explicitly approved items, never duplicates successes or touches unrelated tasks. Safe diagnostics exclude credentials and source bodies.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_partial_publish_recovery`

### F6 — Uncertain insert and concurrent publish do not duplicate tasks
- **Setup:** Fake insert creates a remote task then times out before local success persistence; two publishers race on one batch; interrupted local write.
- **Steps:** Restart/reconcile using the opaque source marker, and run concurrent publication.
- **Expected:** Reconcile a unique already-created remote task or stop as uncertain; never blindly insert again. Ambiguous matches fail closed. Concurrency serializes or refuses overlap. State remains valid, with pending/uncertain truth preserved after interruption.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_uncertain_insert_and_concurrency`

## Regression

### R1 — Neighboring behavior suites pass
- **Setup:** Complete synthetic test environment; no real tokens or API calls.
- **Steps:** Run new and directly neighboring suites.
- **Expected:** All pass without credentials or network. Do not weaken unrelated tests to force a pass.
- **Verify:** `python3 -m unittest discover -s calendar_tests && python3 -m unittest discover -s kb_tests && dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q`

### R2 — CLI build and stdlib preview remain local
- **Setup:** New CLI module documented in the implementation and all fixture tests.
- **Steps:** Compile the feature through its dedicated test and exercise preview with Google SDK imports unavailable.
- **Expected:** Syntax/import checks pass; list/preview needs no Google SDK/network/login. Optional publishing dependencies live in the private environment. No frontend build applies.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_cli_build_and_stdlib_preview`

### R3 — Gmail, KB schedule and Calendar events are untouched
- **Setup:** Existing KB/Gmail config and fixture scheduled jobs, fake Google services with mutation spies.
- **Steps:** Preview and publish selected Tasks, then run normal KB ingest/search.
- **Expected:** Existing read-only Gmail token and scopes, six-hour raw ingest policy, no-spend summary gate and existing jobs are unchanged. No Calendar events API, mail mutation, unrelated task mutation or background publication is called.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_existing_kb_and_google_boundaries`

### R4 — Private task state never enters git, shared retrieval or HTTP readers
- **Setup:** Synthetic task-token, approval, publication mapping, private error log and source-text canaries.
- **Steps:** Check Git ignore, shared index eligibility and real dashboard file routes.
- **Expected:** Credentials, approvals and private task content are neither indexed, served nor committed, including symlink aliases. Logs contain safe IDs/counts/categories only. Curated docs and TASKS.md remain accessible under existing policy.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_private_task_state_boundaries`

### R5 — Local checklist and dashboard toggles keep working
- **Setup:** Synthetic TASKS.md with completed/unchecked entries and original bytes; existing dashboard task-toggle tests.
- **Steps:** Preview/publish selections; exercise current toggle semantics after unrelated line movement.
- **Expected:** Calendar feature never edits Markdown or breaks existing checkbox parsing, heading labels, unique-text resolution or ambiguous-toggle refusal. No automatic remote completion/deletion is inferred from local checkbox changes.
- **Verify:** `python3 -m unittest discover -s calendar_tests -k test_source_and_dashboard_preserved`

## Design

No new graphical surface proposed. CLI list/preview/error/success states are checked by U1/U2/U3/F1/F2/F5. Real Calendar rendering is U5, not a locally fabricated mockup. Any later dashboard UI needs its own reviewed mockup and design cases before implementation.
