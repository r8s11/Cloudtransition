# Purpose & context**

> **Purpose & context** Roosevelt is a contractor at a retail company's NYC office (40 hrs/week, as of Jul 2026) with an ~80-minute each-way commute. His primary goal is to position for an IT Manager / Infrastructure Manager role. The main vehicle is an employer-agnostic IT Management Operational Playbook hosted as a GitHub repository of Markdown files — a portfolio artifact demonstrating management-level operational thinking. **Standing constraint:** Two Sigma (Feb–Apr 2026) and PSM Partners...

_Saved: 2026-11-09T19:47:19Z_

**Purpose & context**

Roosevelt is a contractor at a retail company's NYC office (40 hrs/week, as of Jul 2026) with an ~80-minute each-way commute. His primary goal is to position for an IT Manager / Infrastructure Manager role. The main vehicle is an employer-agnostic IT Management Operational Playbook hosted as a GitHub repository of Markdown files — a portfolio artifact demonstrating management-level operational thinking.

**Standing constraint:** Two Sigma (Feb–Apr 2026) and PSM Partners/IHI (Jun–Oct 2023) must never appear in any generated text, templates, case studies, commit messages, or portfolio-adjacent content. These roles are tracked privately outside the repository.

Background: Roosevelt has 6+ years in IT support, holds AZ-900 (2021) and AWS Cloud Practitioner (2023), and has a prior arc oriented toward Full-Stack Cloud DevOps. That direction has been set aside in favor of IT management positioning. He has also parked most side projects (MTA station app, CMDB backend, home lab SSH jump box, Bet Register buyer outreach, Russian study, Cascade project) until after the AZ-104 exam.

---

**Current state**

*Playbook architecture (primary active project):*
- Repository uses a two-layer system: an **architecture layer** (this chat — owns sequencing, spec cards, MANIFEST tracking, blueprint decisions) and an **execution layer** (a separate smaller-model session that writes one module at a time using paste-ready spec cards and AGENT-CONTRACT.md as its system prompt).
- **Taxonomy:** 11 numbered families — 00-meta, 10-day1-takeover, 20-hardware-lifecycle, 30-sop-engine, 40-saas-lifecycle, 50-tool-mappings, 60-people-lifecycle, 70-change-incident, 80-continuity-ops, 90-case-studies.
- **Five modules at FINAL status:** 10.1, 20.1, 30.1, 40.1, 70.1.
- **Locked skeletons:** Universal SOP Template (30.1) inherited by all procedure modules; canonical asset schema (20.1) as field dictionary for all hardware modules.
- **Notation rule (critical):** `[Token_Name]` = org-portability placeholder, must be declared in TOKENS.md before use; `<field>` = fill-in-at-use-time value, no declaration needed; anything in square brackets not in TOKENS.md is a defect.
- **Key governance files:** TOKENS.md, STYLE-GUIDE.md, MODULE-SPEC-CARDS.md, ADOPTION-GUIDE.md, TAXONOMY.md, AGENT-CONTRACT.md. CLAUDE.md was deleted after a security leak (it had published excluded employer names in a public repo); AGENT-CONTRACT.md is the sanitized replacement.
- **60-people-lifecycle family** was built with three modules (role provisioning matrix, onboarding SOP, offboarding SOP) after being identified as a phantom family referenced in governance files but never built on disk.
- **70-change-incident** was renumbered from 60 to free the 60 range for people-lifecycle.

*AZ-104 (secondary active item):*
- Kept active as the only item with an external deadline and clear career payoff.
- Study strategy: treat it as open-book (Microsoft Learn in split pane), build a lookup index rather than memorize, do all topics hands-on in Azure portal + PowerShell/Az CLI, define sessions by artifact completion rather than time. Caution: prep materials predating the Apr 17, 2026 skills-measured update may have outdated domain weights.

---

**On the horizon**

*Playbook gaps identified, spec cards already issued:*
- **80-continuity-ops family (new):** backup/restore verification, vendor contract management, budget and refresh planning, operational reporting.
- **60-people-lifecycle additions:** access review recertification (60.4).
- **70-change-incident additions:** service desk operations (70.4), security incident response (70.5).
- **20-hardware-lifecycle additions:** stockroom count SOP (20.8), asset register staging for pre-CMDB Excel work (20.9), peripheral request SOP (20.10).
- Module 20.3 (Desk Move / IMAC SOP) spec card is complete.
- Four orphaned 10.1 discovery streams still need downstream module owners resolved.

*Parked for post-AZ-104 revisit (unpark one at a time):*
MTA station checklist React app, CMDB backend build (PostgreSQL 16 / FastAPI / Docker Compose), home lab SSH jump box, buyer discovery outreach (Bet Register), publishing existing projects for credibility (Bitácora, 100-question Intune test, home lab docs, PowerShell bundles), Russian study. Cascade is a deliberate freeze of record — excluded from the revisit list.

---

**Key learnings & principles**

- **Security discipline:** Never publish excluded employer names anywhere in the repo, even in private instruction files. CLAUDE.md was a near-miss; AGENT-CONTRACT.md is the safe pattern.
- **Schema design:** Required fields must reflect state-conditional logic — marking disposal fields as required on assets in Ordered state is a defect, not a policy.
- **Conceptual precision:** "Takeover" in 10-day1-takeover means an IT manager assuming department ownership, not a corporate acquisition — conceptual drift in execution is an audit finding.
- **Placeholder discipline:** Every `[Token_Name]` must exist in TOKENS.md before it appears in a module. Undeclared tokens are defects caught at audit.
- **Architecture before execution:** Spec cards and blueprint decisions precede any module writing. This prevents orphaned modules and schema mismatches.
- **Commute as a study window:** Long commute time is a practical asset for mobile-friendly learning (Microsoft Learn, lookup index building).
- **Focus constraint:** Limiting active threads to two at a time (playbook + AZ-104) reflects a deliberate decision given the difficulty of juggling many simultaneous projects.

---

**Approach & patterns**

- Works in short 10–20 minute mobile sessions during commute; prefers data-dense formatting, tables, and terse bullets.
- Communicates concisely; directs pace through short replies ("Spec," "OK," "Fix").
- Architecture decisions and spec card issuance happen in this chat; execution (module writing/fixing) happens in a separate agent session using paste-ready spec cards.
- Audit cycle: paste module contents → Claude grades against acceptance checklist → FIX or REWRITE verdict with numbered fix list.
- Projects are parked with enough cold-resume detail that they can be picked up months later without loss of context.
- Sessions defined by artifact completion rather than time, to work around time-blindness tendencies.

---

**Tools & resources**

- GitHub (Markdown-based playbook repo)
- Microsoft Learn (AZ-104 study, open-book exam format)
- Azure portal, PowerShell / Az CLI (hands-on labs)
- Docker Compose, PostgreSQL 16, FastAPI, SQLAlchemy (parked CMDB project)
- React (parked MTA app)
