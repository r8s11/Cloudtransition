# CV Adapter — memory index

_Last updated: 2026-11-17_

Dedicated memory for CV Adapter. Append-only events live in `log.jsonl`.

## Base CVs built

- **2026-11-11** — `resume/master.md` (sha256 f7697e6b…a398ee) → `outputs/base-cv.json`. 9 roles, 50 experience bullets (+3 military), 11 skill rows, 2 certifications, 6 projects, all with `source_lines`. Master-only items flagged, not dropped: Two Sigma, PSM Partners, Pillar Biosciences, IT Management Playbook.

## CVs tailored

- **2026-11-11** — `cais-it-support-associate-nyc` (CAIS, IT Support Associate, NYC hybrid) → `outputs/cais-it-support-associate-2026-11-11.json` + `Roosevelt-Segura-CAIS-IT-Support-Associate.docx` / `.pdf` (2 pages). Changed headline, summary, bullet selection/wording/order, skills row order. Roles omitted: the three master-only ones. Not claimed: AI-tool use, runbooks/KB articles, MFA, least privilege, PowerShell, Power Automate, financial services, offboarding.
- **2026-11-17** — `6sense-it-support-specialist` (6sense, IT Support Specialist, remote) → `outputs/tailored-6sense-it-support-specialist.json` + `outputs/tailored-6sense-it-support-specialist.md`. Changed headline, summary, bullet selection/wording/order, skills row order. Roles included: ross, peak, foundation-medicine, ventus, jounce, mgh. Roles omitted: the three master-only ones. Not claimed: AI/Copilot/Claude, responsible AI, MFA, PowerShell, Workato, Iru, CrowdStrike, 1Password, Claude Enterprise, Zoom Rooms, executive support, offboarding/leaver lifecycle, KB articles/runbooks, ITIL/Okta/Apple/security certifications.

## Standing notes

- `resume/master.md` holds the only permitted facts. Master-only roles stay off variants unless the user changes that decision.
- Posting keywords absent from master.md stay off the page; they are listed in the tailored JSON `keyword_map` with a reason.
