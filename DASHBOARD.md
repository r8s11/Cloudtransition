# Career Dashboard

**At-a-glance operational view.** Phase: **employed — perform, build, pay down.**

_Last updated: 2026-08-10 (repo review: verified IT Mgmt Playbook state, flagged missing Bogatyr dir)_

---

## Current Context

| | |
|---|---|
| **Job status** | **EMPLOYED** — full-time contractor at Ross, computer refresh project (started Jun 2026). Open-ended; no contract news yet. |
| **The two lanes** | **IT management pays the bills** — the job, the [IT Mgmt Playbook](IT%20Mgmt%20/), MD-102 depth. **DevOps is the journey** — Python/PowerShell automation now, cloud lane long-term. Both run weekly; the first outranks the second when time collides. |
| **Job search** | **CLOSED** — close-out complete (withdrawals sent, LinkedIn updated). Reopens only on a contract-end signal. |
| **Life priorities** | 1) **$3,000 net income sprint (locked 2026-08-10, 2–4 wk target)** — freelance IT/TaskRabbit/local flat-rate + contingent staffing-agency/gig-app fallbacks (none instant — see plan), see [freelance/profiles-2026-08.md](freelance/profiles-2026-08.md). 2) Perform at Ross. 3) Debt paydown — income is flowing; set the plan now. 4) Confirm move status + do the address pass. |
| **Format rule** | All project work is **tutorial-driven** (HTML build guides, learn by building) — the Bogatyr format, applied to every project. |
| **Language track** | Russian **archived** (2026-07-15 → `plans/archive/`). **Replacement: French — locked 2026-08-10.** Arabic is off the table. |

---

## The Frame for This Phase

1. **Perform:** reputation at Ross sets up extensions, conversion, references. The job comes first.
2. **Build the bills lane:** the [IT Mgmt Playbook](IT%20Mgmt%20/) turns refresh-project experience into a portable, vendor-neutral IT-management portfolio. Every module drafted is career capital that outlives the contract.
3. **Keep the journey warm:** the weekly DevOps block is a *build*, not a course — one manual step from work becomes one small Python/PowerShell tool with a tutorial guide.
4. **Pay down:** income has been flowing since June. The debt plan is overdue — list, pick a method, automate.

---

## Active Workstreams

### 🚨 SECURITY — `pstools` secrets exposure (2026-08-10, outranks everything)
`~/work/pstools` is pushed to `github.com/r8s11/pstools` with a former employer's AD structure (`DC=peakscientific,DC=local`), a real personal address, and a plaintext default password (`Newaduser.ps1:172`). Unauth fetch = 404, which proves only "not publicly readable" — **visibility is unconfirmed** pending an authenticated check. Credential rotation/notification is required regardless, since purging history can't recall existing clones or forks. Actions: [TASKS.md](TASKS.md) · detail: [freelance/monetization-plan.md](freelance/monetization-plan.md).

### 0. 🔴 $3,000 income sprint (top priority, 2026-08-10 → ~end of Aug)
Freelance IT work (Upwork, TaskRabbit, local flat-rate) stacked with an IT-staffing-agency backstop, run on the weekend Money slot + evenings — alongside Ross, not instead of it. Plan + rate sheet + running total: [freelance/profiles-2026-08.md](freelance/profiles-2026-08.md). Checklist: [TASKS.md](TASKS.md).

### 0b. Lane A — productized IT services (the monetization lane that pays now)
Fixed-scope packages built on the playbook: **P1** Day-1 Takeover Audit $1,500–2,500 (the wedge) · **P2** IT Ops Documentation Buildout **$3,500–5,000** · **P3** Fractional IT Ops $1,000–2,000/mo retainer. Sell the documented department, never the playbook itself; clients get tokenized copies. ⚠️ **No single $3,000 P2 clears the sprint** — single-engagement clearance needs ~$4,000+ billed direct, and the cash may land after the window. Lane A covers *part* of the $3,000; hourly lanes cover the rest. Full plan: [freelance/lane-a-services.md](freelance/lane-a-services.md).

### 1. Ross computer refresh (the job)
Work log daily (3 bullets). It feeds everything: MD-102 readiness, playbook modules, automation candidates, resume bullets.

### 2. Project block — two builds, alternating weeks
- **Week A — [IT Mgmt Playbook](IT%20Mgmt%20/):** the "pays the bills" artifact, and the **primary monetizable asset** (~40k words across 9 families). 14 commits. ✅ **Confidentiality gate GREEN** (`tools/validate.py` set D + staged-snapshot pre-commit hook); **structural backlog cleared 2026-08-10, 123 findings → 5** (all word-cap warnings awaiting your trim-vs-except call). Still say **"vendor-neutral by design"**, not "anonymized" — human read-through is the remaining publish gate. Income: [freelance/lane-a-services.md](freelance/lane-a-services.md) · [freelance/monetization-plan.md](freelance/monetization-plan.md).
- **Week B — Bogatyr:** ⚠️ **`bogatyr-build-guide/` does not exist on disk.** "Phase 1 tutorial built" is unverified/stale — either it was never committed, lost, or the claim is wrong. `theRussian.txt` (root) holds the original "Bogatyr Systems" game-design doc but is not a tutorial build. Treat Week B as **not started** until confirmed otherwise.

### 3. DevOps block — automation builds (weekly)
One manual step from the Ross work log → small Python/PowerShell tool → tutorial-format guide. This **replaces** the AZ-104 block.

### 4. Debt paydown (start now)
List debts → pick avalanche/snowball → automate minimums + the extra payment.

### 5. Shelved / archived
AZ-104 plan (shelved 2026-07-15 — reopens when a cert window appears) · SC-900 plan (pre-employment relic, reference) · SNHU (College Planning kept) · Russian (archived) · side projects.

---

## Quick Links

- [TASKS.md](TASKS.md) — active task list
- [routine.md](routine.md) — weekly rhythm
- [IT Mgmt Playbook](IT%20Mgmt%20/) — MANIFEST.md is the source of truth for module status
- Bogatyr — no `bogatyr-build-guide/` on disk; see Week B note above before trusting this link
- [plans/](plans/) — study/roadmap plans ([plans/CLAUDE.md](plans/CLAUDE.md) has the inventory)
- [resume/](resume/) — variants ([resume/CLAUDE.md](resume/CLAUDE.md)); **address pass pending move confirmation**
- [interviews/job-applications.yml](interviews/job-applications.yml) — closed out, archived in place

### Reference (superseded, kept)
- [plans/job-search-plan-2026-05.md](plans/job-search-plan-2026-05.md) — re-open at contract end
- [plans/regeneron-cloud-devops-roadmap_2.md](plans/regeneron-cloud-devops-roadmap_2.md) — the DevOps long-game curriculum, self-paced
- [College Planning/](College%20Planning/) — SNHU materials for a future return

---

## Targets

| Horizon | Milestone |
|---|---|
| **Now → end of Jul** | Move status confirmed + address pass done · debt plan running · ~~first IT Mgmt Playbook commit~~ (done — 9 commits) · ~~language picked (French/Arabic)~~ (done — French) · confirm/rebuild Bogatyr Phase 1 |
| **~Sep 2026 (3-month mark)** | Decide MD-102 exam date from on-the-job readiness · ~~playbook core modules (10.x, 20.x, 30.1) at DRAFT+~~ (done — most of the build order is DRAFT/REVIEW already) — next is maturing DRAFT→REVIEW→FINAL · ask about contract runway |
| **Contract-end signal** | The re-plan trigger: refresh resumes (with Ross + Intune depth), re-open the pipeline early — don't wait for the last week. |

---

## Update Cadence

- **Weekly (~10 min):** check off TASKS.md, jot work-log highlights, note which alternating week (A/B) is next.
- **On any contract news:** update Current Context immediately and re-plan.
