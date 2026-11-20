# Routine — 2026 (job search: apply, earn, build)

_Last updated: 2026-11-18 (Ross ended; job search reopened)_

**Current context:** Ross contract ended 2026-10-30. Job search is open and full-time: 10 applications a week. Freelance IT work brings in cash meanwhile. One DevOps build and one SalsaSegura.com build a week keep skills and portfolio moving. IT Mgmt Playbook, Bogatyr/French and MD-102 are paused until an offer lands.

> Operational view: [DASHBOARD.md](DASHBOARD.md). Active list: [TASKS.md](TASKS.md). Tracker: [interviews/job-applications.yml](interviews/job-applications.yml).

---

## The working rhythm

| Slot                               | What                           | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ---------------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Workday (Mon–Fri, mornings)**    | Job search: 2 applications/day | Pull from the latest leads file ([interviews/job-leads-2026-11.md](interviews/job-leads-2026-11.md)). Top leads get a tailored résumé in `resume/tailored/`; the rest use a standard variant from `resume/2026-10/` ([resume/CLAUDE.md](resume/CLAUDE.md)). [job-autofill](job-autofill/README.md) fills the forms; review before submitting. Log each application in the tracker the same day. Screens booked → prep in `interviews/` that day. |
| **Afternoons (2–3×/week)**         | Freelance income               | Fixed-scope packages first ([freelance/lane-a-services.md](freelance/lane-a-services.md)), hourly gigs second ([freelance/profiles-2026-08.md](freelance/profiles-2026-08.md)). Count cash received and its date, not invoices sent.                                                                                                                                                                                                             |
| **Project block (Sat, 60–90 min)** | SalsaSegura.com                | One shippable change per block in [`../Salsa`](../Salsa). Pick it from [docs/TODO.md](../Salsa/docs/TODO.md) or [docs/ROADMAP.md](../Salsa/docs/ROADMAP.md).                                                                                                                                                                                                                                                                                       |
| **DevOps block (Sat, 45–60 min)**  | Automation build               | One manual step from the job search or home lab → small Python/PowerShell tool → tutorial guide. A build, not a course.                                                                                                                                                                                                                                                                                                                          |
| **Weekend (Sun, \~30 min)**        | Money + review                 | Weekly review below, debt check, plan next week's 10 applications.                                                                                                                                                                                                                                                                                                                                                                               |

**Weekly totals:** ~10 hr job search + freelance as it comes + ~2.5 hr build + 30 min admin.

---

## Weekly Review (~15 min, Sunday)

- [ ] Applications sent this week: count vs 10 in [job-applications.yml](interviews/job-applications.yml)
- [ ] Screens/interviews: any booked → prep scheduled; any rejections → note the stage
- [ ] Leads: enough `new_lead` rows for next week's 10? If not, refresh the leads file
- [ ] Freelance: cash received this week (amount + date)
- [ ] Debt: payments on track?
- [ ] [TASKS.md](TASKS.md): check off, refresh; next SalsaSegura and DevOps task picked

---

## Rules

1. **The job search comes first.** Ten applications a week, done in the mornings before anything else.
2. **Same-day tracking.** Every application, screen and rejection goes in the tracker the day it happens.
3. **The screen stage is the known weak point.** Every booked screen gets written prep in `interviews/` before the call.
4. **Freelance is cash, not the career.** Fixed-scope packages over hourly; track money received, not billed.
5. **Builds, not courses.** Every Saturday block produces an artifact: a SalsaSegura change, a tool, a tutorial page.
6. **Debt payments are part of the routine**, not a someday project. Weekly check, automated payments.
7. **Paused lanes stay paused.** Playbook, French and AI-102 wait for an accepted offer; that offer is the re-plan trigger.
8. **Rest is productive.** Zero days are allowed. Hit 10 a week, not 10 a day.

---

## Key Dates Ahead

| Date                    | Event                   | What to do                                                                                                                           |
| ----------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **2026-10-30**          | Ross contract ended     | Done. Job search reopened; `resume/master.md` already shows Jun 2026 – Oct 2026                                                      |
| **2026-11-30**          | Month-end check         | Applications vs \~40 target; screen and interview counts; if screens but no second rounds, rework interview prep before sending more |
| **Mid-Dec → early Jan** | Holiday hiring slowdown | Keep 10/week; move spare hours into freelance, and the Saturday builds                                                               |
| **Offer accepted**      | Re-plan trigger         | Rewrite this routine; unpause Playbook / AI-102 as the new job dictates; close out the tracker                                       |
