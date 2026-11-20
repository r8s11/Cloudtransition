# U5 — Real task publication (2026-11-06)

- User approved the exact batch: one item (TASKS.md line 105), 📃My Tasks, scheduled day 2026-11-09, fingerprint cf729d0f…ff8a. Preview stored owner-only in the private calendar runtime.
- First `calendar_cli.py publish`: `published`, task id `bjJxRko4UXRnR2pjZk11Tg`, failed 0, uncertain 0.
- Identical second publish: `already_published`, same id, failed 0, uncertain 0.
- Read-only Tasks list of that list: exactly one task with the opaque marker; status needsAction; due 2026-11-09T00:00:00.000Z.
- Calendar grid observation (Safari, Google Calendar day view Monday, November 9, 2026): the task appears once in the all-day row as a checkable task (circle icon, "task: … Not completed" in accessibility tree, single element ref), not as a timed event. Private screenshot: `U5-calendar-2026-11-09.png` (mode 600, ignored).
- No cleanup deletion performed; the task stays in 📃My Tasks.

## Re-inspection 2026-11-10 (local files only; no Google call made)

- Supersedes `U5-calendar-task.md`, an erroneous "blocked / no Tasks login" note written 2026-11-09 without consulting this file or the saved token. A Tasks login and an approved live publish both exist (above and `U6-auth.md`); U5 is not blocked on any missing approval.
- Private publication state `~/.local-routines/personal-kb/calendar/state.json` (mode 600, last written 2026-11-06T02:08:36) still maps exactly one source entry to status `published`, task id `bjJxRko4UXRnR2pjZk11Tg`, task list id `MDkyMzczNTAzNjc5OTQ0MjQwNDU6MDow`. The task id and list match the 2026-11-06 publish output.
- The approved preview `preview-live-u5.json` (mode 600) still carries approval fingerprint `cf729d0f8ef26d4ed7c857b2bf9f975fbeef37a81c58fe63529ae3c545f1ff8a`, equal to the approved fingerprint recorded above.
- Private screenshot `U5-calendar-2026-11-09.png` still exists (191,826 bytes, mode 600) and `.gitignore` line 44 ignores this whole evidence directory.
- `calendar_model.py`, `calendar_google.py` and `calendar_cli.py` were last modified 2026-11-06 01:04-01:21, before the 02:08 live publish; the code that published is the code under test now.
- Not re-observed today: a fresh live read of the Tasks list or the Calendar grid (the day, 2026-11-09, is past). That would be a new account read; it was deliberately not made without Roosevelt's say-so. If wanted, it is one read-only `tasks.get` of the id above that prints only status and due date, never the title.
- No deletion, edit or second publish was performed.
