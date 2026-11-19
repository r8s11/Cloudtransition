# Checklist items in Google Calendar

## User request (verbatim)

> While you at it, make a feature where it will add my check list items as calendar events
>
> events or items

Scope answers:
- Source: Workspace `TASKS.md`.
- Destination clarification: “I would like the task to go directly into the calendar but not necesarly as event.”
- Publishing policy: Preview and approve selected items.

## Approved scope

Create dated **Google Tasks**, which appear on the Google Calendar grid, rather than meeting events. The Tasks API `due` field means scheduled day and discards time. Do not invent a meeting start, duration, attendee or reminder. A missing date requires explicit user selection before publishing.

Proposed entry point is a local CLI preview/publish flow, not a new dashboard screen. Select unchecked `TASKS.md` checkboxes, choose a date and an existing Google task list, inspect exactly what will be transmitted, then approve that batch. The existing dashboard stays unchanged. If a dashboard button is desired, revise scope and add a mockup before building.

## Existing behavior

`dashboard-app/app.py:169-207` parses Markdown checkboxes, completion, nearest heading and line numbers; preserve those conventions. The existing task toggle follows unique text if a line moves and rejects ambiguity. It must keep working. Do not import the dashboard web app into a standard-library preview CLI just to parse Markdown.

## Boundaries

- One-way creation only. Checking a local item does not automatically complete/delete/edit its remote task; later synchronization is not authorized.
- Preview performs no writes or login and needs no Google SDK. It displays selected titles, scheduled dates, destination and any notes/opaque deduplication marker that will be sent.
- Completed boxes, malformed boxes, unselected items and fenced code examples are not published. Reject ambiguous selections rather than guessing.
- Require explicit dates; no natural-language/LLM inference or implicit today. API dates are day-only and must retain the selected local calendar day across time zones/DST.
- Publication requires an approved preview bound to the selected task contents, selected task-list ID and exact outgoing fields. Changed/moved ambiguous tasks, changed destination, edited dates or added items require a new preview/approval.
- Persist source-to-remote mapping privately. Repeating an approved batch or restarting after success must not create duplicates. For an ambiguous insert timeout, reconcile by an opaque marker or report uncertain state; never blindly retry a possibly successful create.
- Do not modify TASKS.md, unrelated Google tasks or any Calendar event. No attendees, email notifications, recurring scheduling or background publishing.
- Google Tasks write scope is `https://www.googleapis.com/auth/tasks` (Google describes this as create/edit/organize/delete all tasks; application uses only operations needed for list selection, reconciliation and selected creation). Explain this breadth at consent. Do not request Calendar scopes.
- Existing Gmail token remains exactly gmail.readonly and is never overwritten, expanded or reused as a Tasks token. Task OAuth/token files and publishing state are owner-only, internal-disk and gitignored; no raw tasks in shared logs/evidence/indexes.
- Feature approval authorizes building only. Separate interactive Tasks login and exact batch approval precede any live write. Do not send credentials or highly sensitive task contents through chat for approval; use the local preview.

## Acceptance and sources

See eval.md. No GUI requested in the proposed scope, so no HTML mockup. Real Calendar visibility and external publishing remain manual, permission-gated checks, not fixture claims.

Official docs consulted through Context7:
- https://developers.google.com/workspace/tasks/reference/rest/v1/tasks — scheduled date is the calendar-grid day; time cannot be read/written.
- https://developers.google.com/workspace/tasks/reference/rest/v1/tasks/insert — create in a selected task list; write scope required.
- https://developers.google.com/workspace/tasks/auth — available OAuth scopes and their breadth.
