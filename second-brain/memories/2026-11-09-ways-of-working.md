# ways of working

> --- name: ways-of-working description: Working rhythm, audit cycle, architecture-vs-execution split, and the principles the playbook work runs on sources: [backfill] aliases: [] --- ## Approach & patterns - [stated] Works in short 10–20 minute mobile sessions during commute; prefers data-dense formatting, tables, and terse bullets - [stated] Communicates concisely; directs pace through short replies ("Spec," "OK," "Fix") - [stated] Architecture decisions and spec card issuance happen in this...

_Saved: 2026-11-09T19:47:21Z_

---
name: ways-of-working
description: Working rhythm, audit cycle, architecture-vs-execution split, and the principles the playbook work runs on
sources: [backfill]
aliases: []
---
## Approach & patterns
- [stated] Works in short 10–20 minute mobile sessions during commute; prefers data-dense formatting, tables, and terse bullets
- [stated] Communicates concisely; directs pace through short replies ("Spec," "OK," "Fix")
- [stated] Architecture decisions and spec card issuance happen in this chat; execution (module writing/fixing) happens in a separate agent session using paste-ready spec cards
- [stated] Audit cycle: paste module contents → grade against acceptance checklist → FIX or REWRITE verdict with numbered fix list
- [stated] Projects are parked with enough cold-resume detail that they can be picked up months later without loss of context
- [stated] Sessions defined by artifact completion rather than time

## Key learnings & principles
- [stated] Security discipline: never publish excluded employer names anywhere in the repo, even in private instruction files — CLAUDE.md was a near-miss, AGENT-CONTRACT.md is the safe pattern
- [stated] Schema design: required fields must reflect state-conditional logic — marking disposal fields as required on assets in Ordered state is a defect, not a policy
- [stated] Conceptual precision: "Takeover" in 10-day1-takeover means an IT manager assuming department ownership, not a corporate acquisition — conceptual drift in execution is an audit finding
- [stated] Placeholder discipline: every `[Token_Name]` must exist in TOKENS.md before it appears in a module; undeclared tokens are defects caught at audit
- [stated] Architecture before execution: spec cards and blueprint decisions precede any module writing, preventing orphaned modules and schema mismatches
- [stated] Long commute time is treated as a practical asset for mobile-friendly learning (Microsoft Learn, lookup index building)

## Tools & resources
- [stated] GitHub (Markdown-based playbook repo)
- [stated] Microsoft Learn (AZ-104 study, open-book exam format)
- [stated] Azure portal, PowerShell / Az CLI (hands-on labs)
- [stated] Docker Compose, PostgreSQL 16, FastAPI, SQLAlchemy (parked CMDB project)
- [stated] React (parked MTA app)
