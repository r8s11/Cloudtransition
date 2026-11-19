# Job application submission loop — evaluation

## Acceptance criteria

### Functional
1. Given a job already read by Job Reader and a profile, the loop opens the form in an isolated browser profile and reads every control (label, options, required, file-box target).
2. Field mapping reuses a cached mapping when the form is unchanged; a changed form is re-mapped.
3. Filling uses real input events; dropdowns and date pickers are operated, not text-injected.
4. Read-back verifies every value; a mismatch fails the fill and holds the form (no submit).
5. Multi-page forms walk pages and repeat the loop per page.
6. Submit occurs only with explicit user approval and only when all wanted values present and no required box empty; post-click confirmation required before counting.
7. `applications/applied.csv` records each sent application with fixed columns, newest first, including one sentence on the company and one on fit.
8. `applications/manual.csv` records each blocked form with reason and link.
9. A form blocked by a code/robot-check/sign-in stays open in the browser profile; `/resume` (or `resume`/`reconcile`) finishes and records it exactly once.
10. A Submit clicked with no confirmation seen is reconciled, never sent twice.
11. A required question the profile cannot answer holds the form and does not submit.
12. Written answers naming a number/tool/company not in the profile are refused; unsupported keywords are listed, not stuffed.

### Safety / invariants
13. Work authorization, education, and dates are copied from the profile and never altered to fit a form.
14. No account creation or sign-in occurs without explicit user setup; refused passwords are not retried; no account is created in a rehearsal; no marketing boxes ticked.
15. No "prove you are human" test is attempted; no email read beyond one verification email for account creation.
16. No invented facts in tailored or written content.
17. User data never leaves the machine except the form submission; site-knowledge (control kinds) may be shared, user data never.

### Cost / reuse
18. A second run of an unchanged form reuses its mapping and remembered answers; Claude is not re-asked for reused answers.
19. Remembered answers are invalidated when profile, drafts, or voice guide change.

### Integration
20. Reuses Agentic OS storage/policy/runtime packages; no parallel persistence store.
21. Records are plain CSV with fixed column names, readable by user and scripts.
22. Dashboard "Needs you" triage surfaces blocked forms, code/sign-in waits, and unconfirmed submissions (if dashboard integration in scope).

## Out of scope (this spec)
- Workday/account-based boards (separate `/accounts` track; may be a follow-on).
- Gmail inbox triage (`/inbox`) — separate.
- Resume/cover tailoring already exists in CV Adapter; only its attachment to forms is in scope here.
- Daily scheduling OS integration (decide in design).
