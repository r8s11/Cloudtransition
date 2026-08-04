# CLAUDE.md — Interviews Directory

This file provides guidance to Claude Code when working in the `interviews/` directory.

## What This Directory Is

Interview preparation workspace: per-company prep folders, behavioral question banks, technical prep notes, and post-interview reflections.

## Existing Layout

**Per-company folders:**
- `Jane St/` — Jane Street prep materials

**Per-role / per-application files:**
- `call-prep-desktop-support-associate.md` — recruiter-call prep template (desktop support role)
- `two-sigma-talking-points.md` — Two Sigma-specific talking points (Two Sigma Desktop Support role ended; this remains as reference)
- `Job Application for Staff Full Stack Engineer, Console at Materialize.mhtml` — saved JD

**Cross-cutting:**
- `interview-prep-star.md` — STAR-method behavioral framework reference
- `job-applications.yml` — structured tracker of applications (status, dates, contacts)
- `Credentials -  Microsoft Learn.pdf` — credential verification reference

## Per-Company Convention

When prepping for a specific company, create a folder: `<Company Name>/` (or kebab-case if preferred — match what's already there).

Inside that folder:
- `prep.md` or `<company>-prep.md` — main prep notes
- JD copy (PDF or markdown)
- Recruiter info (email threads, contacts)
- Behavioral STAR drafts specific to this role
- Technical question/answer prep
- Post-interview reflection

Don't sprawl interview content across the root of `interviews/` — once a company is more than one file, create a folder.

## STAR Method Format

For behavioral question prep, structure answers as:

- **Situation** — context (where, when, role, stakes). 1-2 sentences.
- **Task** — what you specifically were responsible for. 1 sentence.
- **Action** — what you did (use "I", not "we"). 3-5 specific actions.
- **Result** — outcome with metrics if possible (uptime %, users affected, time saved, dollar impact).

Reference: `interview-prep-star.md` for the user's working STAR examples.

## Working in This Directory

- **Resume tie-in.** Interview prep should reference the right resume variant from [../resume/](../resume/) for the role being targeted (devops-cloud, it-engineer, systems-infra, internal-mobility, general). Pull bullet points from the matching variant — don't invent new accomplishments.
- **Job posting context.** Active and considered job postings live at [../resume/jobrequierements.txt](../resume/jobrequierements.txt). Read it when tailoring prep to a JD.
- **Tone for reflections.** After interviews, capture honestly: what worked, what bombed, what to fix. Constructive, not harsh self-judgment. The goal is iteration, not punishment.
- **Track applications.** Use `job-applications.yml` for the running tracker. New applications get a row there before any folder/prep work begins.
- **Career context.** The Two Sigma Desktop Support Engineer role ended (per [../resume/CLAUDE.md](../resume/CLAUDE.md)). The user is actively job-searching while starting school in May 2026 — interview prep is high priority.
- **Target trajectory.** Long-term aim is a Regeneron-class Lead Cloud DevOps role by end of 2027 (see [../plans/year-plan-2026-2027.md](../plans/year-plan-2026-2027.md)). Near-term interviews may be for stepping-stone roles (IT engineer, systems admin, cloud-adjacent support).
