# Project Monetization Plan

_Created 2026-08-10. Companion to [profiles-2026-08.md](profiles-2026-08.md) (the $3,000 cash sprint).
**Different time horizon:** the sprint is hourly work for cash in 2–4 weeks. This is IP/product work — months, not weeks. Do not fund the $3,000 target from this plan._

---

## Asset inventory (surveyed across all of `~/work/`, 2026-08-10)

| Asset | Size / state | Monetizable? |
| --- | --- | --- |
| **IT Mgmt Playbook** (public tree) | 55 files, **~40k words**, vendor-neutral by design | ✅ **Primary asset** — but publishing is gated, see blockers |
| `IT Mgmt/Employer-IT-Playbook-Private/` | 107 files, ~73k words | ❌ **Never publish.** Now gitignored (was untracked by luck only) |
| `~/work/pstools/` | 27 PowerShell/AD/Intune scripts | ❌ **Not as-is** — contains live secrets, see incident below. Rewrite-from-scratch only |
| `~/work/dellwarranty/` | TS + Docker warranty lookup | 🟡 Small utility; complements hardware-lifecycle work |
| `~/work/piggy/` | Per-paycheck envelope budget app, local-only, from a real 94-sheet workbook | 🟡 Real product idea, consumer lane |
| `~/work/Debt-Waterfall-Flow/` | Debt payoff tool, TanStack + Cloudflare, DESIGN.md | 🟡 Consumer lane; also directly useful to your own debt goal |
| `~/work/WODCard/` | React + FastAPI fitness card game | 🟡 Consumer lane, early |
| `~/work/salsatd/`, `Salsa/`, `salsasegura-mobile/` | Salsa app ecosystem | 🟡 Consumer lane, niche audience you actually have |
| `~/work/Azure/md-102-tutorial.md`, `rust1/part1-foundations.md` | 11.6KB + 36.9KB tutorial content | 🟡 Content assets, not products yet |
| `dashboard-app/`, `Python/*`, `vanilla/`, `cards/`, `DotInfo/`, `Bellocampo/`, `VueResume/`, `bloom-react-D3-familyTree/` | small / personal | ❌ Learning + personal tooling |

---

## 🔴 Incident: `pstools` contains live secrets, already pushed

**Status: not publicly readable; visibility unconfirmed.** All affected files are tracked and pushed to
`github.com/r8s11/pstools` (local HEAD `94b6a89` == origin). An unauthenticated fetch returns HTTP 404 —
that proves only that the URL is **not publicly readable**. It does *not* prove the repo is Private: 404 is
equally consistent with deleted, renamed, or transferred. GitHub also returns 404 for private repos
specifically to avoid confirming existence. **An authenticated visibility + collaborator/fork check is still
required.** Regardless of outcome, the material is on GitHub's servers and in git history.

| File | Exposure |
| --- | --- |
| `Newaduser.ps1:172-173` | Plaintext default password `Peakstarter1!` via `ConvertTo-SecureString -AsPlainText` |
| `run.ps1:13` | Real personal address `rdiels@peakscientific.com` |
| `Offboarding.ps1:264`, `ReplacestreetandCity.ps1:5` | Live AD structure `OU=...,DC=peakscientific,DC=local` |
| `platoknowb4.md` / `.ps1`, `newhire.html` | Employer onboarding doc: naming convention, org units, tenant group `942970-AllUsers`, site name |

This is a **former employer's** internal directory design and a default credential.

**Required actions (in order):**

- [ ] **Authenticated check** (`gh repo view r8s11/pstools --json visibility,collaborators,forks`) — confirm actual visibility, collaborator list, and whether any fork exists. The 404 is not sufficient evidence
- [ ] If `Peakstarter1!` is still a live password pattern at that employer, notify them — this outranks everything else here
- [ ] Treat `pstools/` as **private source material**. It is not a product input
- [ ] Purge is **possible but not sufficient**: `git filter-repo` + force-push + remote ref/GC cleanup can remove the secrets from reachable history. It cannot recall existing clones, forks, or third-party caches — so **credential rotation and notification are required either way**, and are the higher-priority action
- [ ] Prefer rewriting any product version from scratch in a clean repo (tokenized: `[IdP]`, `[Domain]`, `<username>`) over trusting a scrub of this one — cleaner provenance, and no dependency on the purge having been complete
- [ ] Never push `pstools` to Gitea or anywhere else in current form

---

## 🔴 Blocker: the playbook is _not_ verified anonymized

**Correct description: "vendor-neutral by design, name-free by convention — unverified."**
Do **not** describe it as "anonymized" in any listing, README, or sales copy until the screen below exists.

Evidence, from the repo's own `00-meta/BLUEPRINT.md`:

- **V3** — anonymization has **no automated screen**; the rule is discipline-only
- **V3 violation still live**: `10-day1-takeover/10.2-stakeholder-map.md:26` has a `[Stakeholder_Name]` column, which `STYLE-GUIDE.md:44` forbids
- `tools/validate.py` **was never built** — BLUEPRINT Steps 2–14 are all unexecuted, so token closure, MANIFEST sync, and the name screen are entirely manual
- A preliminary grep for known employer names (Ross, Foundation Medicine, MGH, Ventus, Jounce) across the public tree came back **clean** — encouraging, but only covers names I could guess. It is not a substitute for the real screen

**Publishing gate — all four before _any_ module goes public, including the 2–3 samples:**

1. [ ] Build the name/confidentiality screen (BLUEPRINT Step 2–4 validator, or a minimal standalone version)
2. [ ] Fix V3: replace the `[Stakeholder_Name]` column in 10.2 with an anonymized `Ref` (`S-01`)
3. [ ] **Human read-through** of every module slated for publication — automation catches patterns, not judgment
4. [ ] Verify the publish pipeline excludes `Employer-IT-Playbook-Private/` (gitignore fixed 2026-08-10; re-verify at export time)

---

## Lane A — Services (fast, highest $/hr) ⭐ start here

The playbook's real leverage is **delivery speed on consulting work**, not unit sales. A client paying for
"document our IT department" or "we inherited an IT mess, where do we start" is a **$1,500–5,000
engagement** you deliver far faster because 55 modules of structure already exist.

Stacks directly onto the Upwork profile already launching in the cash sprint — same profile, higher-ticket
service line.

- [ ] Add an "IT SOP / documentation buildout" and "Day-1 IT takeover audit" service line to the Upwork profile
- [ ] Price as fixed-scope packages, not hourly — the playbook makes you fast, and hourly punishes that
- [ ] Deliver **client-tokenized output**, never the playbook itself; the repo stays clean for the next client
- [ ] Sell the _outcome_ (documented department, prioritized risk register) — not the document

**Concerns to hold while doing this:** deliverables must be built for the client from tokenized templates,
with no content traceable to any prior employer. That constraint is exactly why Lane A works and
`pstools`-as-product does not.

---

## Lane B — Publish `chinola.app/playbook` (lead-gen, $0 direct) 🎬 starting now

Not revenue. It's the credibility artifact that makes Lane A closeable — proof you can do the work.

- [ ] **Gate first:** complete all four publishing-gate items above. Non-negotiable
- [ ] Pick 2–3 sample modules with the widest appeal and least sensitivity — candidates: `30.1 universal SOP template`, `10.1 discovery audit`, `80.1 backup-restore verification` (the only FINAL module)
- [ ] Static export to `chinola.app/playbook` (subpath, not subdomain — per the long-standing TASKS entry)
- [ ] Each page ends with a Lane A call-to-action
- [ ] Keep the full 55-module library unpublished — samples create the reason to hire you

---

## Lane C — Digital product (slow, months to ramp)

40k words is already book-length. Real, but it needs an audience Lane B has to build first.

- [ ] **Gate:** same four publishing-gate items
- [ ] Options: Gumroad / Lemon Squeezy template pack ($49–149) · Leanpub or Amazon KDP ebook · Notion template port
- [ ] **Sequence after Lane B**, so the module set is chosen from what visitors and clients actually ask about — don't guess the packaging before there's demand signal
- [ ] Expect months to meaningful revenue, and effectively $0 in the first weeks

---

## Lane D — Consumer apps (separate audience, slowest)

`piggy`, `Debt-Waterfall-Flow`, `WODCard`, `salsatd`/`Salsa`. Different audience, different skills, no
overlap with Lanes A–C. **Do not start these while the $3,000 sprint is live** — they compete for the same
evenings and pay back far slower.

- Strongest candidates if/when this lane opens: **`piggy`** (built from a real 94-sheet workbook — genuine
  differentiation, and local-only/no-server is a real privacy selling point) and **`Debt-Waterfall-Flow`**
  (a tool you need for your own debt plan; dogfooding is free product research)
- Park until the sprint closes and Lane A has recurring work

---

## Sequenced next actions

1. **`pstools` incident** — confirm repo private, assess the live-password question. Outranks all monetization work
2. **Gitea push** of the playbook — `.gitignore` fix landed 2026-08-10; verify the private folder is absent from the pushed tree afterward
3. **Build the confidentiality screen + fix V3** — unblocks Lane B and Lane C
4. **Lane A service line** onto the Upwork profile — the only lane that pays inside the sprint window
5. **Lane B publish** once the gate is green
6. **Lane C** after Lane B produces demand signal
7. **Lane D** parked

## Honest expectation setting

Lane A can plausibly contribute to the $3,000 sprint. Lanes B, C, and D **cannot** — B is $0 by design,
C needs months and an audience, D needs both plus a different skill set. Fund the sprint from hourly work;
build the IP lanes on top of it.
