# Lane A — Productized IT Services

_Created 2026-08-10. Expansion of Lane A in [monetization-plan.md](monetization-plan.md)._
_Parent cash plan: [profiles-2026-08.md](profiles-2026-08.md) — Lane A is the **only** monetization lane that can contribute inside the $3,000 window._

---

## The thesis in one line

You are not selling a document. You are selling **a documented IT department**, and the
playbook is why you can deliver it in days instead of months.

Clients never see the playbook. They receive tokenized, client-specific output built from it.
The repo stays clean for the next engagement — that's the whole asset model
(`00-meta/ADOPTION-GUIDE.md` already describes this as "bind the tokens, don't edit the playbook").

## Why this beats hourly

The playbook makes you roughly 5–10× faster at documentation work than someone starting from
a blank page. Hourly billing converts that advantage into _fewer hours billed_ — you get
punished for the asset you spent a year building. Fixed-scope pricing converts it into margin.

So: **fixed-price packages, always.** If a client insists on hourly, the rate must assume no
playbook exists.

---

## What you can actually sell (grounded in what's built)

| Family | Built | Sellable as |
| --- | --- | --- |
| `10-day1-takeover` | 5 files, 3.3k words | Discovery audit, stakeholder map, risk register, 30-60-90 |
| `20-hardware-lifecycle` | 10 files, 8.4k words | Asset schema, intake→retire SOP set — **your deepest family** |
| `30-sop-engine` | 5 files | The SOP template + governance model everything else instantiates |
| `40-saas-lifecycle` | 5 files, 2.7k words | SaaS inventory, renewal ops, offboarding |
| `50-tool-mappings` | 5 files, 3.8k words | Intune, Jamf, Snipe-IT, Jira SM, ABM |
| `60-people-lifecycle` | 4 files, 3.0k words | Joiner/mover/leaver, access recertification |
| `70-change-incident` | 5 files, 3.8k words | Change mgmt, incident response, post-incident review |
| `80-continuity-ops` | 4 files, 3.7k words | Backup verification, vendor contracts, budget, reporting |

Roughly 40k words across 9 families. That is a genuine consulting inventory, not a pitch deck.

---

## The three packages

### P1 — "Day-1 IT Takeover Audit" · $1,500–2,500 · ~1 week

**For:** a company that just lost its only IT person, acquired a team, or hired a first IT manager.

**Deliverables:** discovery audit report (from 10.1), stakeholder map with anonymized refs (10.2),
prioritized risk register (10.3), 30-60-90 plan (10.4).

**Why it sells:** it's the cheapest way for a panicking company to find out how bad things are.
Low commitment for them, high signal for you — and it _generates_ P2 and P3 scope.

**This is your wedge. Lead with it.**

---

### P2 — "IT Operations Documentation Buildout" · $3,000–5,000 · 2–3 weeks

**For:** a 20–150 person company running IT on tribal knowledge.

**Deliverables:** SOP engine (30.1 template + governance), 6–10 SOPs chosen from
20.x/40.x/60.x, an asset register schema (20.1), a tool-mapping doc for their stack (50.x).

**Why it sells:** the pain is real and recurring — onboarding takes a week, offboarding gets
missed, nobody knows what's licensed. Note **one P2 clears the $3,000 target on its own.**

---

### P3 — "Fractional IT Ops" · $1,000–2,000/mo retainer

**For:** a P1 or P2 client who now has documentation and needs it maintained.

**Deliverables:** monthly SOP review, access recertification (60.4), renewal calendar (40.4),
backup-restore verification (80.1), an operational report (80.4).

**Why it sells:** it's the natural follow-on, it's recurring, and it's the only one that
compounds. **Don't pitch it cold — earn it from P1/P2.**

---

## Positioning

Most freelance IT on Upwork is break/fix and helpdesk, competing on hourly rate against a
global pool. You are selling **IT management** — process, governance, documentation — against
almost no competition at this price point, because the people who can do it are usually
employed full-time.

Say this: _"I don't fix your laptops. I build the system so laptop problems stop recurring."_

**Proof you can lead with:** 10+ years across finance/healthcare/biotech · currently running
enterprise Windows refresh + Intune/Autopilot at scale · HIPAA-regulated environment
experience · AWS CCP + AZ-900 · bilingual EN/ES · U.S. Army veteran.

**Never named:** current or former employers, in any listing, proposal, or sample.

---

## Sourcing, in priority order

1. **Upwork** — add these as a service line on the profile already launching. Search
   "IT documentation", "SOP", "IT policy", "asset management", "offboarding process".
   Filter for _process_ work, not helpdesk tickets.
2. **Warm network** — the highest-conversion channel and currently empty
   ([networking/contacts.yml](../networking/contacts.yml) has zero contacts). 5 messages:
   _"I'm taking on freelance IT operations/documentation projects — know anyone drowning in
   tribal knowledge?"_
3. **MSPs** — they routinely subcontract documentation work they don't want to staff. Higher
   ticket, repeat business, no platform fee.
4. **Local small business** — Nextdoor/FB posts for P1 at the low end of the range.

---

## Proposal shape (fixed-scope, every time)

> **Scope:** [exact deliverables, itemized]
> **Timeline:** [X] weeks, [N] milestones
> **Price:** $[X] fixed — milestone 1 at [Y]%, remainder on delivery
> **Excluded:** implementation, tool licensing, ongoing support (available as P3)
> **You provide:** [access, SME time, tool inventory]

Non-negotiables:

- Written scope before work starts. Documentation projects are the classic scope-creep victim.
- Milestone payments — never one lump on delivery.
- Deliverables are **client-tokenized copies**. You never hand over the playbook.
- Every SOP delivered gets the client's own frontmatter and token bindings.

---

## Confidentiality rules (carry these into every engagement)

The `pstools` incident is the cautionary case: a former employer's AD structure, email
convention, and a default password went into a repo and are now permanently in its git history.

1. Client data never enters the playbook repo. Ever.
2. Client work lives in a **separate per-client repo**, private, with the same pre-commit gate
   (`tools/hooks/pre-commit` + `PLAYBOOK_EXCLUSION_LIST`).
3. Add each new client's name to the denylist at `~/.config/playbook-exclusions.txt` on day 1.
4. Anything flowing _back_ into the playbook is rewritten generic and tokenized —
   never paste-then-scrub.
5. Case studies (90.x) are anonymized and only published with written permission.

---

## Sequencing

**Week 1** — add the P1/P2 service line to the Upwork profile; write the P1 proposal template;
send 5 warm-network messages.
**Week 2** — 8–10 targeted proposals/week; land the first P1 at the low end of the range to buy
a review.
**Week 3–4** — deliver P1; ask for a review immediately; pitch P2 as the natural follow-on.
**Month 2+** — raise P1 to the top of its range once 2–3 reviews exist; introduce P3 to
delivered clients.

**Realistic:** the first P1 closes in weeks 2–3 and contributes to the $3,000 sprint. The first
P2 more likely lands month 2. Don't bank the sprint on P2.

---

## Honest risks

- **No reviews yet.** First engagement prices low to buy social proof. Accept that once.
- **Documentation is a hard sell** to companies that don't already feel the pain — which is why
  P1 (cheap, diagnostic, urgent-feeling) is the wedge rather than P2.
- **Capacity.** These run on evenings + the weekend Money slot alongside a full-time contract.
  Two concurrent engagements is the realistic ceiling; one is safer.
- **Scope creep** is the #1 margin killer in documentation work — the written-scope rule above
  is the whole defense.
- **Ross comes first.** If an engagement threatens delivery at the day job, the engagement
  gets rescheduled.

## Tracking

Log engagements and revenue against the sprint total in
[profiles-2026-08.md](profiles-2026-08.md) (**net received**, not gross billed).
