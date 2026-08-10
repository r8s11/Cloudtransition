# CLAUDE.md — Plans Directory

This file provides guidance to Claude Code when working in the `plans/` directory.

## What This Directory Is

Strategic learning, project, and career roadmap documents. Plans describe **direction over weeks-to-years** — they are intentionally separate from:

- `../TASKS.md` — active task list (what's due now, with statuses)
- `../progress/` — execution logs and progress tracking
- `../goals/` — high-level career goal documents

A "plan" is a study/work curriculum or a multi-month roadmap. A "task" is a single actionable item. Don't conflate them.

## Master Plan

**Phase since 2026-06-09: employed** (full-time contractor at Ross, computer refresh / Intune). **Refocus 2026-07-15 — two lanes:** IT management pays the bills; DevOps is the journey. There is no active job-search plan; the direction is:

- **Intune/MD-102** — work-driven; topics in the order the refresh project surfaces them. No standalone study plan; the job + builds cover it.
- **Project block (1×/week, alternating):** Week A = IT Mgmt Playbook (`../IT Mgmt /`, its own repo — MANIFEST.md is the module tracker); Week B = Bogatyr (`../bogatyr-build-guide/`). All builds tutorial-format (HTML guides).
- **DevOps block (1×/week): automation builds** — one manual step from the Ross work log → small Python/PowerShell tool + tutorial guide. This replaced the AZ-104 keep-alive block on 2026-07-15.
- **Language track:** Russian archived 2026-07-15 (`archive/`); Bogatyr's language module swaps to **French** (locked 2026-08-10, Arabic dropped).

Superseded, kept as reference:
- [job-search-plan-2026-05.md](job-search-plan-2026-05.md) — the income-track plan that landed the Ross role; **re-open at contract end**
- [year-plan-2026-2027.md](year-plan-2026-2027.md) — the SNHU-era spine (school discontinued 2026-05-24)

Capacity check before suggesting new commitments: ~2–3 hr/wk study total around a full-time job, plus a move (~Jun 19) and debt paydown. Don't propose more.

## Plan Inventory

| File | Purpose |
|---|---|
| `az104-study-plan.md` | **Shelved (2026-07-15).** Was the background keep-alive; replaced by weekly automation builds. Reopen when a cert window appears. |
| `job-search-plan-2026-05.md` | Closed — landed the Ross contract (Jun 2026). Re-open at contract end. |
| `year-plan-2026-2027.md` | Superseded (was master while SNHU was active). Reference. |
| `regeneron-cloud-devops-roadmap_2.md` | Deep curriculum for the Regeneron Lead Cloud DevOps target — 7 phases of books, courses, labs, capstone. Self-paced reference now. |
| `devops-learning-plan.md` | Earlier general DevOps learning plan (predecessor to the Regeneron roadmap). |
| `azure-az204-plan.md` | Azure AZ-204 Developer cert prep. |
| `sc900-study-plan.md` | Shelved reference — pre-employment (Apr 2026) SC-900 plan; revisit only if a security lane opens. |
| `sql_plan.md` | SQL learning plan. |
| `react_plan.md` | React fundamentals plan. |
| `books-reading-plan.md` | Reading list / sequencing for technical books. |
| `archive/Learning Plan + Russian V2.md` | **Archived 2026-07-15** — Russian track dropped (replacement: **French**, locked 2026-08-10). Kept for reference. |
| `weekly-goals.md` | Weekly goal-setting template. |
| `week1-daily-guide.md` | First-week daily breakdown (likely from the original 20 hr/wk plan). |

## Naming Convention

- `<topic>-plan.md` or `<topic>-roadmap.md`
- Add a year range only when the plan is calendar-bound: `year-plan-2026-2027.md`
- Cert plans use the cert name: `azure-az204-plan.md`, `sc900-study-plan.md`
- Avoid generic names like `plan.md` or `study.md`

## When to Create vs. Update vs. Delete

**Create** a new plan only for a genuinely new initiative — a new cert, a new domain, a new multi-month project. Don't churn-create planning docs.

**Update** an existing plan when:
- Scope, pace, or timeline shifts (e.g., re-pacing the Regeneron roadmap from 20 hrs/wk to 5 hrs/wk)
- New context arrives (e.g., starting school changes the calendar)
- A phase completes and the next phase needs detail

**Don't delete** old plans even when superseded. Move them mentally to "reference" status — they capture prior thinking the user may want to revisit. If the user explicitly asks to clean up, ask which to archive vs. delete.

## Working in This Directory

- **Always reference current capacity.** Full-time job + move + debt paydown leaves ~2–3 hr/wk for study. Intune/MD-102 (work-aligned) outranks everything else; AZ-104 is a keep-alive block.
- **Don't duplicate curriculum content.** The Regeneron roadmap holds the deep book/course/lab lists. The year plan references those by phase number, not by re-listing them. Maintain that separation.
- **Pacing is honest.** The user works full-time (Ross contract) and is on a debt-paydown phase. Don't propose 20 hr/wk plans — realistic study capacity is ~2–3 hr/wk, work-aligned topics first.
- **Plan files describe direction, not deadlines.** Specific deadlines (assignment due dates, cert exam dates) belong in `../TASKS.md` or course-specific trackers under `../College Planning/`.
