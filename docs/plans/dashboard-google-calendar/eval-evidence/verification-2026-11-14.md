# Calendar integration verification — 2026-11-14

## Automated proof

`node ~/.agents/skills/write-evals/scripts/evals.mjs lint docs/plans/dashboard-google-calendar/eval.md`: 13 cases; nine automated, four manual; lint passed.

Final `evals.mjs run docs/plans/dashboard-google-calendar/eval.md`: U1, U2, U3, F1, F2, F3, F4, R1 and R2 passed. The R1 commands ran the complete dashboard suite and existing CLI suite. Earlier failures exposed an order-dependent test assertion and an unrelated ambiguous YAML application blocking valid edits; both were fixed without changing real tracker data or weakening target ambiguity checks. Later UI proof also covered immediate conflict visibility while paused.

The dashboard import succeeded. LaunchAgent restarted; `/` and `/reader` returned successful HTTP responses through R2. No OAuth or live publication ran.

## Actual browser surface

Browser used an isolated synthetic FastAPI fixture on loopback 8011, the real templates/static files/source writers/CalendarService, temporary source files and a fake provider. No Google credentials or real account data were used. Fixture server and throwaway script were removed after verification.

- Desktop 1280×900: Upcoming calendar follows Daily, with paper/ink/vermilion tokens, real fonts, named timezone, Event/Task and all-day distinctions. `D1-desktop.png` captures the actual card, not the mockup.
- Mobile 390×844, reduced motion enabled: document width and scroll width were both 390px. Scheduling inputs, selects and buttons measured 44px high. Long task title wrapped. `D2-mobile.png` captures an inline date schedule with visible focus.
- Today: undated and dated captures persisted separately. Undated capture had no calendar metadata. Dated capture stored explicit date and opaque identity. Local save and Google outcome were distinct messages.
- Today/Tasks: scheduling date-only and explicit start/end/IANA events saved successfully. Shared checkbox data retained the current raw metadata and source line.
- Interviews: individual next-action schedules saved with sibling actions retained. Existing next-action edit tests pass, including files with unrelated duplicate YAML blocks. Ambiguous applications remain excluded rather than guessed.
- Keyboard: Enter submitted capture and scheduling. Save schedule retained keyboard focus after the asynchronous write. Inline Close returned focus to its Schedule button. Accessibility tree exposed labels, grouped settings, named buttons and polite live regions. Actual VoiceOver speech was not tested.
- HTML-shaped agenda title remained inert text: zero image elements appeared inside the agenda. No browser errors were reported.
- Settings: explicit calendar/list/timezone/source disclosure and sanitized backlog appeared before Enable. Source/destination identifiers were shown. Enabling used the reviewed policy; Pause disabled it and both feedback regions reported the paused state.
- Actual service worker ticks published eligible synthetic tasks through the fake provider without manual `run_once` from the browser. Outcomes appeared as Added to Google. `D3-published.png` records these synthetic results, not Google account proof.
- Paused source edit: changing a previously published interview action date showed Needs review immediately, preserved the Google link and kept automation disabled. `D3-conflict.png` records this state.
- Empty source returned No upcoming events. Provider failure returned Unavailable, never empty success. Refresh recovered the normal agenda. Disconnected fixture exposed connection/setup guidance. `D3-states.png` captures the paused provider-failure state; the other screenshots cover success/conflict.

## Manual limits

U4 remains unperformed: real Calendar consent, real event visibility and exact approved Task/event creation require separate user authorization and setup. No grant was widened, no API was enabled, no real backlog was activated and nothing was deleted remotely.

D2 screen-reader speech remains unverified; keyboard, accessibility-tree/live-region semantics, target sizes and reduced-motion layout were measured. No pixel-perfect comparison was required.

The existing eval runner can invalidate results after unrelated workspace changes. Saved command results describe the code exercised at verification time; no global hashes or legacy CLI eval contracts were changed.
