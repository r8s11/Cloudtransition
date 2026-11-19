# Calendar U5/U6 re-verification — 2026-11-10

The previously recorded no-login/no-approval failures were incorrect. The user authorized Tasks setup and the exact one-item publication on 2026-11-06; see U5-live.md and U6-auth.md.

Fresh read-only account verification with the existing Tasks token:
- `tasks.get` returned id `bjJxRko4UXRnR2pjZk11Tg`, `needsAction`, due `2026-11-09T00:00:00.000Z`, not deleted.
- Tasks token scope is exactly `https://www.googleapis.com/auth/tasks`; mode 0600.
- Separate Gmail token scope is exactly `https://www.googleapis.com/auth/gmail.readonly`; its bytes were identical before and after the Tasks read/refresh.
- No OAuth consent, key change, creation, update, deletion or republish was performed.

Fresh native Safari verification at Google Calendar day view 2026-11-09:
- Window/web area title: Monday, November 9, 2026.
- Compared the saved approved preview title privately with AX button labels (did not copy titles into shared evidence).
- Exactly one distinct AX element matched that title, labelled `task`, `Not completed`, `All day` on the selected day. It is not an event with attendees or duration.
- The 2026-11-06 repeat-publish evidence already records `already_published` with the same ID. A fresh write was unnecessary and was not attempted.

Result: U5/U6 pass. Original authorization and repeat-publish evidence remain in U5-live.md and U6-auth.md; current account existence/scope/grid visibility are freshly observed here.
