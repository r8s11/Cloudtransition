# Google Calendar in Command Center

## User request (verbatim)

> I would like to incorporate my Google Calendar into this dashboard. I want to be able to see my events and as well as to have whatever is going on on the dashboard be able to add it to the calendar as well as a task.I believe there are already something cute or waiting to be tested. And I know the evals are being too harsh so I wanna lower some of the evals so I can get this working. And let me know what I need to do.

## Answers received on 2026-11-14

- Publishing: **Automatically publish dashboard changes to Calendar and Google Tasks**, rather than approve each item separately.
- Routing: **Dated items become Google Tasks; explicitly timed items become Calendar events. Undated items stay local until scheduled.** The same item does not automatically become both.
- Sources: TASKS.md, interview tracker next actions, and other task realms. Individual extra files must be chosen before enabling. Private academic records stay excluded.
- The proposed boundary shown with those choices was create-only automation: edits show a conflict, not silent remote overwrites/deletions; Pause stops new writes; review the initial backlog before enabling.

## Existing work and evidence

- `CALENDAR-README.md` describes a working CLI, not a dashboard calendar. `calendar_model.py`, `calendar_google.py` and `calendar_cli.py` create dated Google Tasks from explicitly approved TASKS.md previews.
- `docs/plans/checklist-calendar/eval.md` has 17 cases (15 automated, two manual). Its saved results recorded passes on November 13, including separate OAuth and real Calendar visibility. The current runner reports 15 automated results stale after workspace changes. Stale evidence is not a newly observed behavioral failure.
- Separate owner-only Tasks credentials and token files exist under `~/.local-routines/personal-kb/calendar/`. Their current grant validity has not been tested in this planning session. Do not discard or widen that token.
- Today capture already appends to TASKS.md Inbox. Today Next up, Inbox, Projects and Tasks can represent the same underlying checkbox. Deduplicate by source identity, not screen row.
- `app.py:136-228` configures REALMS; `parse_tasks_from_file()` currently exposes title, category, completion, realm and line, not structured schedules. Interview next steps already have an optional ISO date and task title. A next-action date does not prove an interview appointment time.

## Intent

See an upcoming agenda inside Today and automatically send explicitly scheduled local work to the selected Google destination. Keep workspace files authoritative for local tasks. No LLM or paid model call is needed.

## Approaches

1. Embed/link Google Calendar only: cheap display, but no reliable task publishing or dashboard automation. Rejected because it misses the requested workflow.
2. Reuse the existing publisher and add a dashboard agenda plus opt-in automatic creation. Selected through the scope forms. Keep the tested private state and duplicate safeguards; replace per-batch CLI interaction with a persistent, explicitly approved automation policy.
3. Full two-way synchronization: changes/deletions/completions propagate both ways. Not selected; it introduces destructive conflict decisions beyond this request.

## Proposed interface

Extend Today rather than redesign navigation. Keep the current Daily/Next up/Capture/Inbox ordering, placing an Upcoming calendar card immediately after Daily. Show the next seven calendar days in a named display timezone, with explicit Event/Task labels, all-day labels, source calendar names and links to open items in Google. Calendar events and Google Tasks are distinct API sources; do not claim Calendar events.list returns Tasks. Google Tasks shown in the agenda are those created and tracked by this integration; importing every unrelated Google task is not required.

The card contains Refresh, Pause automation, last successful refresh and Settings. Settings expands inline with connection state, selected read calendars, one writable owned event calendar, one existing Tasks list, timezone, named allowed source files and the initial backlog preview. The final Enable automation action states exactly what future qualifying items will disclose. Adding a source or changing destinations requires renewed policy confirmation. An existing back catalogue is not published silently.

Capture gains an optional date and optional start/end times. Save without a date remains a local-only task. A Schedule action on Today task rows, Tasks realm rows and interview next actions edits the same local schedule; repeated dashboard views never create separate identities. Explicitly timed items require a start, end and IANA timezone; no guessed duration. Keep local checkbox toggling independent from Google availability.

## Scheduling contract (proposal for review)

- For Markdown, use a trailing structured annotation on the checkbox: `<!-- calendar: {"date":"2026-11-16"} -->`; timed example: `<!-- calendar: {"start":"2026-11-16T14:00","end":"2026-11-16T15:00","timezone":"America/New_York"} -->`. Preserve other source text and comments. Hide this metadata in rendered titles, but retain it during checkbox writes and stale-source validation. This syntax is a proposed new explicit field, not a claim that existing files already contain it.
- For interview next actions, reuse `next_steps[].date` for date-only Tasks; the scheduling control adds structured start/end/timezone fields only when explicitly entered. Do not infer meetings from application status, historical timeline dates, free text or a follow-up due date. Read all actual next-action entries, not just the first one shown in the current row. Preserve neighboring YAML and all other keys.
- Do not parse arbitrary prose dates or invent dates from headings, current week, file modification times or natural language. Existing undated items show Needs date. Existing interview actions with structured dates qualify after backlog review.
- Completed, fenced, malformed, missing, disabled-source and privacy-denied items never become new remote items. Repeated source views and unrelated line movement must not duplicate existing remote items. Ambiguous identical entries remain Needs review instead of guessing.

## Automation behavior

- Default off. One explicit local setup review grants the configured create-only rule for future qualifying items from the displayed source allowlist. This is not consent to publish unrelated data or accept Google permissions.
- Run a single bounded server-side reconciliation pass every 60 seconds while the dashboard service runs, including when no browser is open. No job or API write runs merely from a GET request. Pause persists across service restarts and blocks queued items not yet sent. An already-started request may finish; the UI says so.
- Local edits save first. Google outage never rolls back or loses a captured task. Report local save and remote outcome separately.
- Persist policy, intents and returned IDs privately. Reuse Tasks publication identity/reconciliation where compatible; keep legacy CLI approval semantics intact. Any additional state must meet the existing private-runtime rules.
- Date-only -> needsAction Google Task, in the configured existing list. Timed -> Calendar event with explicit start/end/timezone, in the configured owned calendar, no attendees or invitations. Send only sanitized title and required scheduling/opaque identity fields, never notes, contacts, preparation files, task category contents or adjacent source text.
- Retries must not duplicate items, including after timeout, restart, concurrent browser activity or worker overlap. Preserve known successes and uncertain outcomes. Use deterministic Calendar IDs/reconciliation and the existing Tasks pending-marker mechanism. No blind insert after an uncertain outcome.
- Source changes after successful publication show Needs review and a Google link. Do not create a replacement automatically, update/delete the remote item, mirror completion or import Google edits into workspace files. Deleted sources leave already-created remote items untouched. These are deliberate create-only limits, not synchronization promises.
- Google 401/403 pauses affected publishing and requests reconnection; 429/network failures defer to the next bounded pass without hot retries. Calendar reads, Tasks writes and local operations fail independently. A failed refresh must not present old data as current or say No events.

## Permissions, privacy and reachability

- Separate Calendar OAuth from Gmail and the existing Tasks grant. Request Calendar list read access and the narrowest event read/create permissions compatible with selected calendars. Proposed scopes: `calendar.calendarlist.readonly`, `calendar.events.readonly` and `calendar.events.owned`; explain that the write scope also permits modifying/deleting owned-calendar events, although this feature does not do so. Exact scope behavior must be verified before consent.
- Retain Tasks-only authorization. Do not merge Calendar scopes into the Tasks token, reuse Gmail tokens, or follow documentation examples that delete an existing token to change scopes.
- Use Desktop OAuth with a temporary Mac loopback callback. Initial consent happens on the Mac; phone access uses server-held tokens and same-origin dashboard APIs. No tokens in browser storage, shared indexes, chat, logs or HTTP file readers.
- All new mutating dashboard requests require existing same-origin/CSRF protections and server-side source/destination allowlists. GET cannot enable, schedule or publish. Scheduler cannot discover arbitrary workspace files or follow paths/symlinks outside permitted sources.
- Exclude privacy-denied paths including College Planning, credentials, employer-private content and sensitive records. Other realms can be supported without enabling them wholesale. Show excluded files as unavailable with a reason. This exclusion is consistent with the choice shown in the source-selection form.
- Tailnet devices already reach this dashboard. Enabling a source discloses its eligible titles to the connected Google account, and tailnet dashboard viewers can see the selected agenda. Explain that before enabling; do not broaden network exposure.

## Lean eval policy

Keep a focused 13-case contract: nine automated, four manual. Run calendar behavior tests, the dashboard suite and import/HTTP smoke; do not repeat unrelated KB/map/agent suites as a prerequisite to this integration. Reuse existing CLI tests rather than restating each as another gate. Visual checks cover usable state/flow and the existing design system, not pixel-identical screenshots. Real consent and a single deliberately approved real Task/event remain manual; do not manufacture account-level proof.

Leave the approved legacy checklist CLI eval unchanged. Global eval-workspace staleness is a separate runner behavior; do not edit its stored hashes or declare stale tests passing. Record actual focused results and report a global gate separately. No lowering of consent, source privacy, CSRF, date correctness or duplicate protection.

## What the user needs to do after build approval

1. Enable Google Calendar API in the chosen Google Cloud project. Keep Google Tasks API enabled. Use an existing Desktop OAuth client only if its configuration is appropriate; otherwise create a Calendar-specific Desktop client.
2. In Google Auth Platform, configure the consent audience and add your account as a test user when the app is External/Testing. Review the actual scopes in the consent screen. Keep client JSON on the Mac in an owner-only private directory; never paste it into chat.
3. Connect Calendar on the Mac. Reconnect Tasks only if its existing authorization is rejected; no need to repeat a valid prior login.
4. Choose read calendars, the owned event destination, Tasks list, timezone and individual nonprivate source files. Review the backlog locally and confirm Enable automation. Do not enable real automation merely to test fixtures.
5. For real proof, approve one harmless dated task and one harmless timed event with exact destination/date/time locally. Verify both in Google. No cleanup deletion without consent.

Official references: [Python setup](https://developers.google.com/workspace/calendar/api/quickstart/python), [event listing](https://developers.google.com/workspace/calendar/api/v3/reference/events/list), [event creation](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), [Calendar scopes](https://developers.google.com/workspace/calendar/api/auth), [Tasks day-only due field](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks).

## Scope and implementation boundary

Expected touchpoints: calendar helpers/private runtime, dashboard app routes and service lifecycle, Today/Tasks/interview row templates, shared JS/CSS and asset query versions, interview editor schedule writes, privacy/source allowlists, existing calendar/dashboard tests, calendar guide and Code router. Reuse current patterns. No new database, listener, frontend build, paid service, LLM parser, remote deletion, two-way sync, recurring event creation or invitation flow.

`mockup.html` is a self-contained synthetic design reference, not a working Google connection. `eval.md` is the build contract. The user approved this contract and mockup on 2026-11-14. This approves implementation only, not OAuth, API enablement, live policy activation or remote publication.
