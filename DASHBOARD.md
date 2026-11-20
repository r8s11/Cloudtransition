# Career Dashboard

**At-a-glance operational view.** Phase: **job search — apply, earn, build.**

*Last updated: 2026-11-18 (Ross ended 2026-10-30; job search reopened full-time)*

---

## Current Context


|                           |                                                                                                                                                                                                                                                                                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Job status**            | **Between roles.** Ross contract (computer refresh, NY Ross Buying Office) ran Jun 2026 – 2026-10-30.                                                                                                                                                                                                              |
| **Job search**            | **OPEN, full-time** — 10 applications a week. Tracker: [interviews/job-applications.yml](interviews/job-applications.yml). Leads: [interviews/job-leads-2026-11.md](interviews/job-leads-2026-11.md). Filter (from the Oct leads file): NYC on-site or US remote, $70K floor,$95–115K target, contract-to-hire OK. |
| **Income meanwhile**      | Freelance IT — Lane A fixed-scope packages first, hourly gigs second. Count cash received, not billed.                                                                                                                                                                                                             |
| **Life priorities**       | 1) Land the next role. 2) Freelance cash. 3) Debt plan (still not set up). 4) Confirm move status + do the address pass.                                                                                                                                                                                           |
| **Paused until an offer** | IT Mgmt Playbook · Bogatyr/French · MD-102.                                                                                                                                                                                                                                                                        |
| **Format rule**           | Builds, not courses: every Saturday block ships an artifact.                                                                                                                                                                                                                                                       |


---

## The Frame for This Phase

1. **Apply:** 10 a week, weekday mornings, logged the same day. Screens are the known weak point — every booked screen gets written prep.
2. **Earn:** freelance work covers the gap. Fixed-scope over hourly.
3. **Build:** one SalsaSegura.com block and one DevOps automation block each Saturday keep the portfolio moving.
4. **Pay down:** weekly debt check; set the plan.

---

## Active Workstreams

### 🚨 SECURITY — `pstools` secrets exposure (2026-08-10, outranks everything)

`~/work/pstools` is pushed to `github.com/r8s11/pstools` with a former employer's AD structure (`DC=peakscientific,DC=local`), a real personal address, and a plaintext default password (`Newaduser.ps1:172`). Unauth fetch = 404, which proves only "not publicly readable" — **visibility is unconfirmed** pending an authenticated check. Credential rotation/notification is required regardless, since purging history can't recall existing clones or forks. Actions: [TASKS.md](TASKS.md) · detail: [freelance/monetization-plan.md](freelance/monetization-plan.md).

### 1. Job search (top priority)

2 applications a day from the latest leads file. Tailored résumés in `resume/tailored/` for top leads; standard variants in `resume/2026-10/` otherwise ([resume/CLAUDE.md](resume/CLAUDE.md)). [job-autofill](job-autofill/README.md) fills the forms. Checklist: [TASKS.md](TASKS.md).

### 2. Freelance — Lane A productized IT services

Fixed-scope packages built on the playbook: **P1** Day-1 Takeover Audit $1,500–2,500 (the wedge) · **P2** IT Ops Documentation Buildout **$3,500–5,000** · **P3** Fractional IT Ops $1,000–2,000/mo retainer. Sell the documented department, never the playbook itself; clients get tokenized copies. Hourly lanes (Upwork, TaskRabbit, local flat-rate): [freelance/profiles-2026-08.md](freelance/profiles-2026-08.md). Full plan: [freelance/lane-a-services.md](freelance/lane-a-services.md). The Aug–Sep $3,000 sprint window has elapsed.

### 3. Saturday project block — SalsaSegura.com

Source: [`../Salsa`](../Salsa) (active; last commit 2026-11-17). Its own backlog lives there — [docs/TODO.md](../Salsa/docs/TODO.md) and [docs/ROADMAP.md](../Salsa/docs/ROADMAP.md) — so pick each Saturday's task from those, not from this workspace.

### 4. DevOps block — automation builds (Saturday)

One manual step from the job search or home lab → small Python/PowerShell tool → tutorial-format guide.

### 5. Debt paydown

List debts → pick avalanche/snowball → automate minimums + the extra payment.

### 6. Paused / shelved / archived

- **IT Mgmt Playbook** — paused. State at pause: confidentiality gate GREEN, structural backlog 123 → 5 word-cap warnings, human read-through still the publish gate. Say **"vendor-neutral by design"**, not "anonymized". MANIFEST.md is the source of truth for module status.
- **Bogatyr** — paused. ⚠️ `bogatyr-build-guide/` does not exist on disk; Phase 1 is unverified. French replaces Russian when it resumes.
- **MD-102** — paused; revisit after an offer.

- AZ-104 (shelved 2026-07-15) · SC-900 (reference) · SNHU (College Planning kept) · Russian (archived).

---

## Quick Links

- [TASKS.md](TASKS.md) — active task list
- [routine.md](routine.md) — weekly rhythm
- [interviews/job-applications.yml](interviews/job-applications.yml) — application tracker
- [resume/](resume/) — variants ([resume/CLAUDE.md](resume/CLAUDE.md)); **address pass pending move confirmation**
- [freelance/](freelance/) — income plans and templates
- [IT Mgmt Playbook](IT%20Mgmt%20/) — paused
- [plans/](plans/) — study/roadmap plans ([plans/CLAUDE.md](plans/CLAUDE.md) has the inventory)

### Reference

- [plans/job-search-plan-2026-05.md](plans/job-search-plan-2026-05.md) — the spring 2026 search plan that landed Ross
- [plans/regeneron-cloud-devops-roadmap_2.md](plans/regeneron-cloud-devops-roadmap_2.md) — the DevOps long-game curriculum, self-paced
- [College Planning/](College%20Planning/) — SNHU materials for a future return

---

## Targets


| Horizon                 | Milestone                                                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Weekly**              | 10 applications sent and logged · every booked screen prepped                                                          |
| **2026-11-30**          | \~40 applications this month · count screens and second rounds; if screens but no second rounds, rework interview prep |
| **Mid-Dec → early Jan** | Holiday slowdown: keep 10/week, shift spare hours into freelance and Saturday builds                                   |
| **Offer accepted**      | Re-plan trigger: rewrite routine.md, unpause Playbook / MD-102 as the role dictates, close out the tracker             |


---

## Update Cadence

- **Weekly (Sunday, ~15 min):** the review in [routine.md](routine.md), then check off TASKS.md.
- **On any offer or final-round news:** update Current Context immediately and re-plan.