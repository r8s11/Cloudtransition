# CLAUDE.md — College Planning

This file provides guidance to Claude Code when working in the `College Planning/` directory.

## What This Directory Is

SNHU degree planning workspace: degree program research, transfer credit mapping, certification-to-credit logic, and per-term course trackers. The user has done extensive prior research here — build on it, don't redo it.

## Active Enrollment

- **Currently enrolled in CS BS** at SNHU.
- **Considering switch to Cybersecurity BS** (more overlap with the DevOps roadmap).
- **First active term:** 2026 C-3 (May 4 – Jun 28, 2026) — ENG-190 + FYE-101.

## Existing Artifacts

**Degree program catalogs (PDFs):**
- `Computer Science (BS).pdf` — current program
- `Cybersecurity (AS).pdf` / `Cybersecurity (BS).pdf` — alternative under consideration
- `Information Technologies (BA).pdf` / `Information Technologies (BS).pdf`
- `Data Analytics (AS).pdf` / `Data Analytics (BS).pdf`

**Transfer credit research:**
- `Southern New Hampshire University _ Saylor Academy.pdf` — Saylor Academy → SNHU credit equivalencies
- `SNHU Transfer Courses from Sophia _ Sophia Learning.html` (and `.mhtml`) — Sophia transfer mappings
- `Microsoft Exam AZ-900 Certified_ Azure Fundamentals.pdf` — AZ-900 → 3 IT elective credits documentation
- `audit-4354432-A001ZQ8B.pdf` — Credit for Prior Learning (CPL) audit
- `Roosevelt Segura FC (AS.CS).pdf` — prior CC transcript (FC = Foothill College / Bronx CC?)

**Existing plans / analyses:**
- `education-plan.md` (and `.pdf`) — primary education plan summary
- `education-data.yml` — structured education data
- `program-overlaps.md` — comparison of degree programs by course overlap
- `snhu-plan.md` — SNHU-specific plan (also at repo root)
- `View Experiences.pdf` — experience-to-credit mapping reference
- `README.md` — directory summary

## Per-Course Tracker Convention

**Naming:** `<course-code-lowercased>-tracker.md` — e.g., `eng190-tracker.md`, `fye101-tracker.md`, `cs100-tracker.md`.

**Structure (template — see `eng190-tracker.md` for the full pattern):**
1. Header — term, section, textbook, platform
2. Course competencies (from syllabus)
3. Grade distribution table
4. Topic / thesis / project summary (where applicable)
5. Module-by-module checklist with due dates, deliverables, point values, hours estimate, notes
6. Policy reminders (late policy, participation, AI usage)
7. Running grade tally
8. Related files

**One tracker per active course.** Don't combine courses into one file. When a term ends, the tracker becomes a historical reference — keep it, don't delete.

## Working in This Directory

- **Don't redo prior research.** Before proposing degree comparisons or transfer logic, check `education-plan.md`, `program-overlaps.md`, `snhu-plan.md`, and the catalog PDFs. The user has spent significant time here already.
- **Reference the year plan.** [../plans/year-plan-2026-2027.md](../plans/year-plan-2026-2027.md) is the strategic spine that schedules courses against DevOps roadmap phases. Course choices for future terms should respect that calendar.
- **Cybersecurity BS switch is open.** If the user asks about course planning or program choice, both CS BS and Cyber BS are live options. Don't assume the switch has happened or hasn't.
- **CPL and transfer credits are real money.** When the user asks about saving time or cost, check whether existing certs (AWS CCP, AZ-900) or experience can map to credits before suggesting they take a course.
