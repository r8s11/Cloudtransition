# Forge — memory index

_Last updated: 2026-11-16_

Dedicated memory for Forge. Append-only events live in `log.jsonl`.

## Run history
- 2026-11-09T22:28:16Z — identity verification on subagent session start. No teammates invoked, no jobs handled, no paid step. Outcome: ok.
- 2026-11-09T22:43:13Z — free search scan on Roosevelt's "go". Scout invoked. 40 unique listings found and scored (36 primary IT support/desk-side/service desk/sysadmin/EUC; 4 secondary junior cloud/Azure/M365). Top match: BlackRock Technical Support Associate (93). Dice partial (no citable per-job URLs); one query hit HTTP 429. No job descriptions read, no CV work, no paid step. Outcome: ok. Outputs: `workspace/agents/scout/outputs/scan-2026-11-09.{json,md}`.
- 2026-11-10T18:08:00Z — Scout free scan run (prior session, logged retroactively). Outputs: `workspace/agents/scout/outputs/scan-2026-11-10.{json,md}`. No paid step.
- 2026-11-11T18:00:00Z — Scout free scan run (prior session, logged retroactively). 25 new listings scored (22 primary / 3 secondary), 74 prior listings excluded as already scored. Top: CAIS IT Support Associate (92). Outputs: `workspace/agents/scout/outputs/scan-2026-11-11.{json,md}`. No paid step.
- 2026-11-11T18:08:00Z — review pass on Roosevelt's "go". No teammate invoked: scan was 8 minutes old, so re-running Scout would duplicate work. Top 5 surfaced for review; promotion awaits Roosevelt's explicit pick. No paid step. Outcome: ok.
- 2026-11-12T17:00:00Z — promotion (paid), two jobs on Roosevelt's pick "2 and 5". Job Reader → CV Adapter. Stable Rock Tier 2 Support Engineer (86) and NYC DSS Desktop Support Specialist (84). Both CVs 2 pages, docx+pdf, no Two Sigma, no AI-tool claims. Two bookkeeping artifacts missing after interrupted CV Adapter calls: stable-rock tailored JSON, nyc-dss .md summary.
- 2026-11-12T17:00:00Z — AI-evidence draft finished at `workspace/agents/forge/outputs/master-md-ai-evidence-final.md` (3 insertions, anchors verified). Paste into `resume/master.md` still pending — Forge cannot write it.
- 2026-11-12T00:00:00Z — free scan on Roosevelt's "go". Scout invoked. 44 new unique listings (43 primary / 1 secondary), 99 prior excluded. Top: Legora Workplace Technology Specialist (86), Stable Rock Tier 2 Support Engineer (86), BETSOL IT Support Engineer (84), Lendbuzz IT Systems Administrator (84), NYC DSS Desktop Support Specialist (84). Source failures: LinkedIn returned no results; Robert Half NYC URL 404; NYC cityjobs keyword filter broken. No paid step. Outputs: `workspace/agents/scout/outputs/scan-2026-11-12.{json,md}`.
- 2026-11-11T18:15:00Z — promotion (paid). CAIS IT Support Associate (92). Job Reader → CV Adapter. Outputs: `workspace/agents/job-reader/outputs/cais-it-support-associate-2026-11-11.json`, `workspace/agents/cv-adapter/outputs/Roosevelt-Segura-CAIS-IT-Support-Associate.{docx,pdf}` (2 pages). Withheld unproven keywords: AI tools, runbooks, MFA, least privilege, PowerShell/Power Automate, financial services.
- 2026-11-16T20:07:00Z — state audit on Roosevelt's "go" for LEDA-6 (Run job pipeline for new listings and submit applications). No teammate invoked: a second Forge run already owns LEDA-6 (task 01a1e5ec-29a6, running since 19:53:49Z) and Scout/Job Reader/CV Adapter had 0 queued runs, so starting a parallel pipeline would have duplicated paid work. Posted the audit as a comment on LEDA-6 instead. Findings: three Forge runs earlier today (19:43/19:46/19:51Z) failed `agent_error.context_overflow` — prompt 41k–47k tokens vs the 8,192 model limit on `alibaba-token-plan/auto`, which is why nothing had dispatched. scan-2026-11-12 rows 3 (BETSOL) and 5 (NYC DSS) are already-submitted jobs; CAIS and Stable Rock have CVs built but no application-received mail. Gmail ingest broken ~25 h (re-ran `ingest_all.py --source gmail` 20:04:55Z → `GmailError`, 0 pages, 0.006 s = token/auth failure; fix needs interactive `--gmail-login`). No job description read, no CV work, no paid step, no application submitted. Outcome: ok.

- 2026-11-16T20:50:00Z — scan review on Roosevelt's "go" (chat). Scout dispatch runs on LEDA-6 were all cancelled (first blocked on local_directory mutex by the 19:53Z issue run), but `scan-2026-11-16.{json,md}` completed on disk: 17 new listings after dedup vs 143 prior + applied companies. Top 5 surfaced for pick: Vanta IT Ops (80), Cohere IT Support (79), Judge Group L2 (78, $35-45/hr onsite), Vercel IT Ops (78), Novus Desktop/Endpoint (76). No paid step. Outcome: ok.

- 2026-11-18T13:45:00Z — wayfinder charting on Roosevelt's "@wayfinder". Map: `.scratch/job-hunting-pipeline/map.md` (local-markdown tracker, `.scratch/`). 9 decision/task tickets; research subagents fired for 04 (ingest) and 05 (sources) on throwaway branches. No paid step. Key new constraints from Roosevelt: free models/routers only for all four agents; macOS cron trigger; 24h-scoped Gmail ingest; all sources to be fixed plus new Scout tooling; dedup seen+applied must be combined.

- 2026-11-18T14:25:00Z — both research subagents (tickets 04 ingest, 05 sources) failed: "OpenCode Go weekly usage limit reached." No findings, empty branches only, no PRs; working branch restored to `main`. Awaiting Roosevelt's choice: free-model retry, Extra Usage, wait for reset, or inline research. No paid step.

- 2026-11-18T14:35:00Z — Roosevelt chose free-model retry after the Go weekly limit killed both research agents; he picked `opencode-go/hy4-flash-free` specifically. Both research subagents relaunched on it for tickets 04 and 05, reusing their empty branches. Findings pending; no paid step.

- 2026-11-18T15:00:00Z — wayfinder research tickets 04 (ingest) and 05 (sources) resolved and recorded on the map; both agents ran on free `opencode-go/hy4-flash-free`. Key new facts: Gmail ingest already incremental and currently fresh (11-18T18:35:32Z) so ticket 03 is verify-first; daily cron likely only needs scan+shortlist; Scout gets ATS/USAJOBS/Socrata sources, LinkedIn replaced, Robert Half/cityjobs/Dice repaired. Frontier: 01, 02, 03, 06, 07, 09. No paid step.

## Roosevelt's preferences
- 2026-11-11: picks promotion targets by numbered option from Forge's shortlist (chose "1" = top-scored listing).
- Two Sigma role stays master-only (Oct 2026 decision) — excluded from tailored CVs even when it is the strongest evidence.
- Standing gap: no AI-tool usage recorded anywhere in the fact base; needs `resume/master.md` update before any CV claims it.
- 2026-11-16 (hard constraint): dedup must exclude not only prior-scan listings but companies already applied to. Confirmed applied: InfoTrack Systems Administrator (11-05), Stripe IT Support Engineer (11-09), BlackRock Associate TPM (11-10), NYC DSS Desktop Support Specialist ref 789790 (11-11), BETSOL IT Support Engineer NJ/NY (11-12), Eon (11-12), Stability AI (11-12), Nightingale Veterinary Partners (11-12).
- 2026-11-16: in practice "submission" means Roosevelt sends it — past paid promotions delivered CVs and he applied manually (inbox confirmations match). The pipeline's deliverable is a ready-to-send package plus the apply URL.

## Provisional configuration (needs Roosevelt confirmation)
- Sources used for the 2026-11-09 scan (not yet fixed): Indeed, LinkedIn Jobs, Dice, Built In NYC, Robert Half, NYC city jobs, Greenhouse/Ashby/Lever.
- Default target track: primary IT support / desktop / service desk / systems admin / EUC in NYC metro; secondary junior cloud / Azure / M365 admin.
- Profile source of truth: `resume/master.md` plus `goals/career-goals.yml`.
- Paid promotion has run once (CAIS, 2026-11-11); always requires Roosevelt's explicit pick.
