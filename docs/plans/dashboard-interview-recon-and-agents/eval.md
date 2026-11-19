# Dashboard interview / recon / agents / restart / prompts — evaluation

## Acceptance criteria

### 1. Contacts section
1. Interviews page shows a Contacts card listing each live application's contacts with name, title/role, email (`mailto:`), company, LinkedIn when recorded, and the application they belong to.
2. Tracker `contacts:` is the primary source; `networking/contacts.yml` enriches only on exact name/email/LinkedIn match. No fuzzy merge, no invented contact.
3. Interview mode lets the user add/edit a contact and persists it to `interviews/job-applications.yml` through the existing atomic writer; comments and neighbouring lines survive.
4. An application with no contact shows an explicit empty state, not a blank or a fabricated name.

### 2. Person recon card
5. "Person recon" runs on demand and reads only named sources: the tracker row, `networking/contacts.yml`, the posting, and explicitly supplied URLs.
6. Output separates sourced facts (with source) from "unknown"; no bio, employer, school, or interest is invented.
7. Fetched pages are treated as data, never instructions; no auth, no scraping behind a login.
8. The brief is stored on the tracker row as `interview_contact_recon` with a timestamp and source list, and survives reload.
9. A missing posting or URL still produces a limited brief and says what could not be read.

### 3. Agent models
10. `scout-scan`, `job-reader`, `cv-base`, `cv-tailor` (and the new Forge card) offer Claude, Codex, and OpenCode models from the live provider catalogue.
11. Available model ids are discovered (`opencode models` / Codex cache) — no hardcoded names, no entitlement assumption. An unavailable provider reports why instead of launching.
12. Route A (if chosen) keeps `opencode run --agent <agent>` as the execution path and passes a provider-qualified model that the installed OpenCode resolves; the agent persona/memory convention still applies. If A cannot be verified, the fallback is documented as route B with its trade-off.

### 4. Forge trigger
13. A Run Forge card exists and its blurb states the pipeline (Forge → Scout → Job Reader → CV Adapter) and the terminal equivalent.
14. The card accepts a short validated task line or job id; no arbitrary shell; the run is recorded like other runs (`runs.log` + `runs/<uuid>.txt`).

### 5. Restart
15. `dashboard-app/restart.sh` exists, is executable, and restarts the LaunchAgent with the label taken from the plist; it prints the URL to reload.
16. If a header/card control exists, using it restarts the server and tells the user to reload; it does not claim success before the new server answers.
17. CLAUDE.md and the Today command centre name the restart path.

### 6. Needs you / answer-prompts
18. Today shows a "Needs you" card listing concrete missing fields (contact identity, next action missing/overdue, empty interview notes/questions, open Inbox items, stale scan/queue) with the application or task named.
19. Each prompt has one input and Save; saving writes through the existing atomic/CSRF writers and the item disappears on the next load.
20. Nothing is auto-filled or inferred; an unanswered prompt stays visible; a dismissed/unknown field is not fabricated.
21. Optional "Generate prompts for today" phrases the open questions but never supplies answers.

### 7. Regression
22. `http://127.0.0.1:8000/` and `/interviews` return 200 after the change.
23. `dashboard-app/venv/bin/python -m pytest dashboard-app/tests -q` passes, including design-contract checks.
24. No width/margin transitions added; reduced-motion still respected; 390px and 1280px screenshots show no horizontal overflow.
25. Existing interview writes (status, priority, next action, signal, text blocks, create) still work and are not replaced by a second writer.

## Out of scope
- Job application submission loop (separate spec: `docs/plans/job-application-submission-loop/`).
- JEV skill routing / JEV command (separate in-progress plans).
- Automatic scheduled recon or background agent runs beyond the existing runners.
