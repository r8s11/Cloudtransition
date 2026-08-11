# Tasks

_Last updated: 2026-08-10 (repo review: corrected IT Mgmt commit/module status, flagged missing Bogatyr build dir)_

> Phase: **employed — perform, build, pay down.** Operational view: [DASHBOARD.md](DASHBOARD.md). Rhythm: [routine.md](routine.md).

## Active

### 🚨 SECURITY — `pstools` secrets exposure (found 2026-08-10, OUTRANKS EVERYTHING)

`~/work/pstools` is tracked + pushed to `github.com/r8s11/pstools`. An unauth fetch returns 404 — that proves only "not publicly readable", **not** Private (equally consistent with deleted/renamed/transferred). A former employer's AD structure and a default password are on GitHub and in git history. Detail: [freelance/monetization-plan.md](freelance/monetization-plan.md).

- [ ] **Authenticated check**: `gh repo view r8s11/pstools --json visibility,collaborators,forks` — confirm real visibility, collaborators, and any forks. The 404 is not evidence
- [ ] Decide the disclosure question: is `Peakstarter1!` (`Newaduser.ps1:172`) still a live password pattern at that employer? If yes, notify them — **highest-priority action regardless of repo visibility**
- [ ] Rotate the credential / confirm it's dead. Purge can't recall existing clones, forks, or caches, so rotation is required either way
- [ ] Mark `pstools` as private source material — **never** push to Gitea, never use as product input
- [ ] Optional cleanup: `git filter-repo` + force-push + remote GC *can* purge reachable history — but treat it as defense-in-depth after rotation, not as the fix
- [ ] Any product version = rewritten from scratch in a clean repo, tokenized (cleaner provenance than trusting a scrub)

### 🔴 $3,000 income sprint (locked 2026-08-10, target: 2–4 weeks — TOP PRIORITY)

Full plan + rate sheet: [freelance/profiles-2026-08.md](freelance/profiles-2026-08.md). Runs on the existing weekend "Money" slot + evenings ([routine.md](routine.md)) — parallel to Ross, not instead of it. **Define the target before tracking it:** $3,000 *received* ≈ $3,000 billed direct / $3,333 via Upwork. $3,000 *spendable after 25–30% tax reserve* ≈ **$4,000–4,800 billed**. (The earlier "$3,600–4,200" figure was wrong — it nets ~$2,350–2,740.) Count **cash received and its date**, not invoices sent.

- [ ] Publish Upwork profile ($45–50/hr to start) + submit 8–10 proposals today
- [ ] Start TaskRabbit account/background check today (multi-day lead time — don't let it be the bottleneck)
- [ ] Post local flat-rate offer ($50–75) on Nextdoor/FB groups/personal socials
- [ ] Message 5 friends/former colleagues asking for freelance IT referrals
- [ ] Apply to 1–2 gig-delivery apps as a contingency (not guaranteed): background check takes 1–7 business days, and NYC access is capped/zoned post minimum-pay-standard — apply now, don't expect week-1 shifts
- [ ] Register with 1–2 NYC IT staffing agencies (ONIT, TEKsystems) for short-term/weekend desktop-support work — also runs its own hiring timeline, not instant
- [ ] Track running total in [freelance/profiles-2026-08.md](freelance/profiles-2026-08.md)

### Status catch-up (this week, ~30 min)

- [ ] Confirm move status: done / delayed / date — then update DASHBOARD.md
- [ ] If moved: address pass — resumes ([resume/CLAUDE.md](resume/CLAUDE.md)), LinkedIn, bank, USPS
- [x] Pick the Bogatyr replacement language: **French** (locked 2026-08-10; Arabic dropped, Russian archived 2026-07-15)

### Debt plan (overdue — income flowing since June)

- [ ] List all debts: balance, APR, minimum payment
- [ ] Pick a method (avalanche = highest APR first, snowball = smallest balance first) and set the monthly number
- [ ] Automate minimums + the extra payment

### IT Mgmt Playbook (project block — Week A)

- [x] **First git commit** — stale flag; repo actually has 9 commits, last 2026-07-27
- [ ] **Commit pending work-in-progress** in `IT Mgmt /`: modified `.gitignore` (now excludes the private folder — fixed 2026-08-10), `00-meta/BLUEPRINT.md`, `00-meta/TOKENS.md`, `10-day1-takeover/10.3-risk-register.md`, `MANIFEST.md`; untracked `20-hardware-lifecycle/20.8–20.10`, `60-people-lifecycle/60.4`, `70-change-incident/70.4–70.5`, `80-continuity-ops/`
- [ ] **Push to Gitea** — then verify `Employer-IT-Playbook-Private/` (107 files, ~73k words) is absent from the pushed tree. It was untracked by luck only until the gitignore fix
- [ ] Per MANIFEST, the build order's first pass is essentially done (DRAFT/REVIEW across the board, 80.1 is FINAL) — pick modules to mature DRAFT→REVIEW→FINAL, not new drafts
- [ ] Feed real Ross refresh patterns into 20.x hardware-lifecycle modules — **vendor-neutral + tokenized, no employer specifics**. `pstools` is the cautionary case: employer domain/OU/password went into a repo and is now permanently in git history. Write generic from the start; never paste-then-scrub

### Monetization — playbook → income (plan: [freelance/monetization-plan.md](freelance/monetization-plan.md))

**Publishing gate — automated portion is BUILT and GREEN as of 2026-08-10:**

- [x] **Confidentiality screen built** — `IT Mgmt/tools/validate.py` (stdlib, check sets A–D). Set D is the publishing gate: name columns, emails, directory DNs, credential patterns, private IPs, UNC paths, + employer denylist. Scans **raw markdown including code fences** (that's where the `pstools` secrets hid)
- [x] **Pre-commit hook wired** — `tools/hooks/pre-commit`, validates the **staged snapshot** via `git checkout-index` (not the worktree — staging a secret then cleaning the worktree copy would otherwise commit it). Fails closed if the denylist env var is unset. Activate in a fresh clone: `git config core.hooksPath tools/hooks`
- [x] **V3 fixed** — `10.2` Name column → anonymized `Ref` (`S-01`); also fixed the broken `10.1-people-process.md` link
- [x] **Denylist created** at `~/.config/playbook-exclusions.txt` (outside the repo, never committed). **Add `export PLAYBOOK_EXCLUSION_LIST=~/.config/playbook-exclusions.txt` to your shell rc** — without it the hook blocks every commit
- [x] Confidentiality gate **GREEN**: 0 blockers across 53 files
- [ ] **Human read-through** of each module slated for publication — automation catches patterns, not judgment. Still required, still the real gate
- [ ] Verify export pipeline excludes `Employer-IT-Playbook-Private/` at export time (gitignored now, but re-check when the static export is built)
- [ ] ⚠️ Keep describing the playbook as **"vendor-neutral by design"** — the automated screen raises confidence but doesn't make it "certified anonymized"

**Structural backlog — CLEARED 2026-08-10 (123 findings → 5):**

- [x] `SOP ID:` → `ID:` sweep across 22 SOP files + V4 effective-date fix + missing keys added (BLUEPRINT Steps 9–10)
- [x] Declared `[Prior_Employer]` + `[Migration_Batch_ID]`; converted 12 per-record values to `<angle>` fill-ins (Steps 6–8); `30.4` format is now `SOP-<domain>-<###>`
- [x] MANIFEST row added for `00-meta/AGENT-CONTRACT.md` (00.6); TAXONOMY keys capitalized (Step 11)
- [x] `### Cap Exceptions` table added to STYLE-GUIDE + machine-read by C5 (Step 5) — only the pre-authorized 20.7/1600 is listed
- [ ] **Your call: 5 word-cap warnings** — 70.4 (956w), 70.5 (964w), 80.1 (808w), 80.2 (844w), 80.4 (1155w) against the 800 cap. Trim, or add rows to the Cap Exceptions table. Left visible rather than silently excepted
- [ ] Once those are decided: flip the hook to `--gate all` and add CI

**Lane A — services (fast, the only lane that pays inside the sprint) → full plan: [freelance/lane-a-services.md](freelance/lane-a-services.md):**

- [ ] Add the P1/P2 service line to the Upwork profile — **fixed-scope packages, never hourly** (hourly punishes you for the playbook's speed advantage)
- [x] **P1/P2 proposal templates + 5 warm-network messages written** → [freelance/lane-a-templates.md](freelance/lane-a-templates.md) (also: 15-min discovery-call script with package routing, and a per-engagement confidentiality checklist)
- [ ] Send the 5 warm-network messages — highest-conversion channel and currently empty ([networking/contacts.yml](networking/contacts.yml) has zero contacts). Log each with a date; follow up **once** after 5–7 days
- [ ] Search Upwork for "IT documentation", "SOP", "IT policy", "asset management", "offboarding process" — process work, not helpdesk
- [ ] Approach 2–3 MSPs about subcontracted documentation work (no platform fee, repeat business)
- [ ] Per-client repo + denylist entry on day 1 of any engagement — client data never touches the playbook repo

Packages: **P1** Day-1 Takeover Audit $1,500–2,500 (~1wk, the wedge) · **P2** IT Ops Documentation Buildout **$3,500–5,000** (2–3wk) · **P3** Fractional IT Ops $1,000–2,000/mo (earn from P1/P2, don't pitch cold). ⚠️ **A $3,000 P2 does not clear the sprint** — via Upwork it returns $2,700, ~$1,890–2,025 after tax reserve. Single-engagement clearance needs **$4,000+ billed direct**. Track **cash received + date**, not billings.

**Lane B — publish chinola.app/playbook (lead-gen, $0 direct) — STARTING:**

- [ ] Gate must be green first
- [ ] Pick 2–3 sample modules (candidates: 30.1 universal SOP template, 10.1 discovery audit, 80.1 backup-restore — the only FINAL one)
- [ ] Static export to chinola.app/playbook (subpath, not subdomain); Lane A call-to-action on each page

**Lane C — digital product (slow, after Lane B):**

- [ ] Gumroad/Lemon Squeezy pack ($49–149) or Leanpub/KDP ebook — sequence after Lane B so packaging follows real demand signal, not guesswork

### Bogatyr (project block — Week B)

- [ ] ⚠️ **`bogatyr-build-guide/` not found on disk** — the "Phase 1 tutorial built" claim (below, Done log) can't be verified. Confirm whether it's lost, uncommitted elsewhere, or was never actually built before doing anything else in this lane.
- [ ] Swap the Russian track in the Phase 1 guide + `_context` for **French** — blocked on confirming/rebuilding the missing `bogatyr-build-guide/` dir above
- [ ] Then: Phase 2 tutorial (SRS flashcard drill), same tutorial format

### DevOps block — automation builds (weekly)

- [ ] Seed the candidate list: pull 3 manual steps from the Ross work log that could be scripted
- [ ] Build #1: pick the smallest one → Python or PowerShell tool + tutorial-format guide

### Ross (ongoing)

- [ ] Work log daily — 3 bullets (feeds MD-102 prep, playbook modules, automation candidates, resume)

---

## Recurring (weekly, light)

- [ ] ~10-min review: check off done items, jot work-log highlights, note next week's A/B project
- [ ] One project block (alternating: Playbook / Bogatyr)
- [ ] One DevOps automation block

---

## Waiting On

- [ ] Contract clarity from Ross (duration, extension, conversion) — on any signal, update [DASHBOARD.md](DASHBOARD.md) and re-plan

---

## Someday

- [ ] **MD-102 exam** — decide date at the ~Sep 2026 checkpoint from on-the-job readiness
- [ ] AZ-104 exam — **shelved 2026-07-15**; reopen when a cert window appears (then AZ-400/AZ-204 decision)
- [ ] SC-900 — pre-employment plan kept in [plans/sc900-study-plan.md](plans/sc900-study-plan.md); revisit only if a security lane opens
- [ ] SNHU (or other degree path) — revisit once stable
- [ ] Renew or let lapse: AWS CCP (decide closer to expiration)
- [ ] Side projects (WODCard, SalsaSegura, SalsaTD)
- [ ] Publish IT Mgmt Playbook online via chinola.app/playbook — static export from tools/preview/ (see claude/docsaros-frontend-preview-0c60c8), subpath not subdomain
- [ ] Open source contribution (one small PR)

---

## Done

- [x] **Job-search close-out complete** — withdrawals sent to all 5 interviews, LinkedIn "Open to Work" off, tracker closed (confirmed 2026-07-15)
- [x] **Refocus locked (2026-07-15):** two lanes (IT mgmt pays / DevOps journey), alternating project blocks, automation-build DevOps block, Russian archived
- [x] IT Mgmt Playbook scaffolded — grown well past initial ~10 modules; MANIFEST now covers the full build order at DRAFT/REVIEW/FINAL (2026-07-09 → 07-27, 9 commits)
- [x] **Job landed — full-time contractor at Ross, computer refresh project (Jun 2026)** 🎉
- [x] Job search ran 2026-04 → 2026-06: ~35 IT apps, 5 interviews reached, offer accepted
- [x] Bogatyr build plan locked (2026-05-23); Phase 1 tutorial claimed built — ⚠️ **unverified: no `bogatyr-build-guide/` exists on disk as of 2026-08-10**
- [x] Resume folder organized; 7 variants + dated batches (2026-06-09)
- [x] LinkedIn: headline, summary, certs, keywords

---

## Closed out — SNHU (discontinued 2026-05-24)

Not attending. Materials kept in [College Planning/](College%20Planning/) for a possible future return. ENG-190 was completed through Module 3 before withdrawal.

## Deprecated (kept as reference; do not act on)

- Active-application rhythm (8–10/week, tiers) — **job search is closed**; plan preserved in [plans/job-search-plan-2026-05.md](plans/job-search-plan-2026-05.md) for contract-end re-ignition
- AZ-104 weekly keep-alive block — replaced 2026-07-15 by the automation-build DevOps block
- Russian language track — archived 2026-07-15 ([plans/archive/](plans/archive/)); Bogatyr's language module swaps to **French** (locked 2026-08-10)
- SNHU year plan ([plans/year-plan-2026-2027.md](plans/year-plan-2026-2027.md)) — superseded
