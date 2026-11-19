# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Directory Is

Resume management directory containing multiple resume variants, each tailored to a different job target. Also contains LinkedIn profile copy, a GitHub profile README, job postings for reference, and a template for drafting new position entries.

## Resume Variants

Seven active resume variants are maintained in parallel, each emphasizing different aspects of the same work history:

- **devops-cloud** — Highlights automation, CI/CD, cloud tools, scripting. Targets: DevOps Engineer, Cloud Engineer, SRE
- **it-engineer** — Highlights user support scope, ITSM tools, stakeholder management. Targets: IT Engineer, Systems Administrator, Technical Support Engineer
- **systems-infra** — Highlights AD, networking, server management, infrastructure projects. Targets: Systems Engineer, Infrastructure Engineer, Platform Engineer
- **service-desk** — Highlights M365 / Entra ID / Intune MDM, Apple/macOS administration, ITIL-aligned ITSM workflows, escalation depth. Targets: L2/L3 Service Desk / Help Desk Engineer, Tier 2/3 Support Engineer
- **it-support-tech** — Highlights PC/mobile-device support, SOP adherence, ticket resolution, end-user device management, AV support, customer service. Targets: IT Support Technician, Help Desk Specialist, Tier 1/2 Support
- **internal-mobility** — Leads with a "What I've Built" section showcasing projects (Jira SM, GitHub Enterprise, SQL Server infra). Targets: internal growth into infrastructure/platform/cloud ops roles
- **general** — Strips tech jargon, frames everything as transferable business skills. Targets: non-IT roles — operations, support, coordination, project-based positions

A **service-industry** variant also exists as a `.docx` only.

Each variant may also have a **`-remote`** companion (e.g., `resume-2026-05-devops-cloud-remote.md`) — same target role, layered with explicit remote-work signals (100% Remote header tag, async/distributed-team phrasing in summary, Remote Collaboration skills row covering Zoom/Teams/Slack/ScreenConnect/Bomgar/Intune Remote Actions/VPN, per-role Remote/Hybrid annotations, remote-keyword ATS block).

## File Naming Convention

`resume-YYYY-MM-role-target.md` for markdown source, `.docx` for finalized exports.

Example: `resume-2026-03-devops-cloud.md` / `resume-2026-04-it-engineer.docx`

When iterating on a variant within the same month, append `-v2`, `-v3`, etc. (e.g., `resume-2026-04-it-engineer-v2.docx`, `-v3.docx`).

## Directory Layout

- **`<variant>/`** — per-variant working folder at the resume root (one per active variant: `devops-cloud/`, `it-engineer/`, `systems-infra/`, `service-desk/`, `it-support-tech/`, `internal-mobility/`, `general/`, `service-industry/`). Contains the markdown source and any in-progress drafts for that target.
- **`YYYY-MM/`** — dated batch folder containing the `.docx` exports for that month across all variants (e.g., `2026-03/`, `2026-04/`). New month = new batch folder.
- **`files/`** — older flat batch of `.docx` exports (legacy; supplanted by the dated batch convention but kept for reference).

## Key Supporting Files

- `current-job-template.md` — Template with writing guide for drafting a new position entry (action verbs, bolding conventions, tailoring tips per variant)
- `linkedin-copy.md` — LinkedIn headline, about section, and ATS keyword list
- `github-profile-readme.md` — GitHub profile README draft
- `jobrequierements.txt` — Job postings being actively targeted or considered (used for resume tailoring)

## Resume Editing Conventions

When editing resumes, follow these patterns already established across all variants:

- **Bold 1-3 bullets per role** for biggest-impact achievements (things built, led, or introduced from scratch)
- Use strong action verbs: Deliver, Manage, Maintain, Troubleshoot, Implement, Deploy, Establish, Lead, Build, Design
- Include scope metrics: user counts, SLA percentages, team/location reach, systems managed
- Technical skills tables use `| Category | Technologies |` format
- ATS keyword blocks go in HTML comments at the bottom: `<!-- ATS Keywords: ... -->`
- Contact line format: `Brooklyn, NY 11232 | mail@roosevelt.info | chinola.app | GitHub | LinkedIn`
- Version/target footer: `_Resume version: [Target] — [Month Year]_`

## When Tailoring to a Job Posting

1. Read the target job posting (often pasted inline or stored in `jobrequierements.txt`)
2. Identify which resume variant is the closest match
3. Mirror the posting's language in the summary and bullet points where the experience genuinely applies
4. Adjust the Technical Skills table to lead with the most relevant category for that role
5. Reorder or reword project bullets to emphasize what the posting values most

## Current Status

As of 2026-11-18, the user is **job searching full-time** (10 applications/week). The Ross contract (computer refresh, NY Ross Buying Office) ended 2026-10-30; `master.md` lists it as "Jun 2026 – Oct 2026". Current standard variants are in `2026-10/` (`devops-cloud`, `it-support-tech`, `service-desk`, `systems-infra`); posting-specific résumés go in `tailored/YYYY-MM/`. Leads and the tracker live in `../interviews/`.

Pending resume work: **address update across all variants after the mid-June 2026 move** — the contact-line convention above may carry a stale address.
