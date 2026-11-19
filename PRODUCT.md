# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Roosevelt — single user, acting alone. Situation: IT professional in a job-search
transition after the Ross contract ended, managing a career, income, learning track,
and a heavy task load across many active workstreams. Russian learning is inactive.
Job: open one page and immediately know what is active, what is due, what is on track,
and be able to act on it without opening files or grepping the workspace.

## Product Purpose

A productivity dashboard that is the at-a-glance operational view of the workspace:
tasks, projects, career & income, learning progress, and (new) routine & schedule.
Success means the markdown/yml files stay the single source of truth while the dashboard
renders them live and lets Roosevelt act (check a task, view a realm) in place.

## Positioning

The workspace files are the database. The incumbent (`dashboard-app/`) has no database,
build step, or state of its own — it reads workspace `.md`/`.yml` files live on every
page load and has exactly one write endpoint that edits markdown in place, atomically.
Every value shown is the same plaintext, version-controlled file the user and their
agents already edit. A neighboring product could not truthfully copy the claim that
the dashboard is just a live view of the source of truth.

## Operating Context

- Local web app. Incumbent stack: FastAPI + Jinja2 + Tailwind, run with
  `dashboard-app/venv/bin/uvicorn app:app --port 8000`. A change is done only when `/`
  returns 200.
- Data sources map to tabs: **Tasks** ← every `REALMS` file in `app.py` (parses
  `- [ ]` / `- [x]`; headings become categories) · **Skills** ←
  `skills/skills-inventory.yml` · **Career** ← `goals/career-goals.yml`,
  `interviews/job-applications.yml`, `networking/contacts.yml` · **Education** ←
  `College Planning/education-data.yml` · **Books** ← `Books/books-data.yml` ·
  **Overview/Projects** ← hardcoded lists in `build_context()`.
- The operational truth lives in `TASKS.md`, `DASHBOARD.md`, and `routine.md` at the
  repo root; `routine.md` already holds the weekly rhythm data for a future Routine tab.
- Many tools write the workspace files (agents, editors, the dashboard's own toggle), so
  the dashboard must always mirror whatever is currently true in the files, never a cache.
- Single-user, local-only tool. No authentication, no external network dependency,
  no AI/provider logic inside the product itself.

## Capabilities and Constraints

Confirmed capability surface (existing + agreed):

- Task/project management — task toggle, realm filtering, progress bars (Tasks + Projects tabs)
- Career & income tracking — career goals, applications, contacts (Career tab; income tracking not yet a view)
- Learning progress — skills inventory, education data, books (Skills / Education / Books tabs)
- Routine & schedule — **agreed, not yet built**; `routine.md` is the data source

Confirmed requirements:

- Adaptive layout: the dashboard must work well on phone, tablet, and desktop (responsive web).
- The files remain the source of truth; never introduce a separate state store.

Hard constraints on any implementation:

- One write endpoint only; it requires `X-Requested-With: XMLHttpRequest` and writes the
  markdown file atomically via temp-file + `os.replace`.
- File reads resolve paths and reject anything outside the workspace or off the
  extension allowlist.
- Progress bars animate from `width: 0` to `data-width` — set inline in a template and
  the animation breaks.
- Always `venv/bin/python` / `venv/bin/uvicorn`, never system python.

## Brand Commitments

The dashboard is named **Command Center** (masthead, page title, home-screen install). The incumbent visual world is
"Atmospheric Glass" (recorded in `dashboard-app/DESIGN.md`): dark glassmorphism, deep
blue surface, frosted translucent cards, Inter type. Voice is personal and direct — a
single operator's command view, not a broadcast.

The operations surfaces (**Interviews, Run, Agents**) take the category standard on
purpose (chosen 2026-11-17): a modern dark dashboard played straight, at the craft level of
Linear, Vercel, Grafana and GitHub, with a light touch of *Oblivion*-style glass (thin
light edges, restrained translucent layering). No sci-fi greebles or neon. Every other
tab keeps the washi sheet in `dashboard-app/DESIGN.md`.

## Evidence on Hand

- `dashboard-app/` — working FastAPI + Jinja2 + Tailwind implementation with tabs:
  overview, education, books, tasks, projects, skills, career; `DESIGN.md` (Atmospheric
  Glass), `CLAUDE.md` (agent guide), `app.py`, `templates/`, `static/`.
- Data files: `TASKS.md`, `DASHBOARD.md`, `routine.md`, `skills/skills-inventory.yml`,
  `goals/career-goals.yml`, `interviews/job-applications.yml`, `Books/books-data.yml`,
  `College Planning/education-data.yml`.
- An archived single-file prototype exists at `archive/dashboard.html`.
- No testimonials, customers, public users, or external metrics exist; the product is
  single-user and must not fabricate any.

## Product Principles

1. **The files are the database.** The dashboard renders truth that lives in
   version-controlled plaintext; never duplicate state into a separate store that can
   drift from the source.
2. **At-a-glance beats exhaustive.** The operative view is the product; detail and tools
   live one step away, not stacked on the first screen.
3. **Trusted local single-user tool.** Prefer simplicity and safety over multi-user or
   network features; local-only is a feature, not a limit.
4. **Portable and open.** Markdown/yml input means any part of the workspace can feed the
   dashboard and nothing is locked into a proprietary format.
5. **Mirror the whole workspace.** Whatever the user or their agents edit is equally
   visible here, and the dashboard must always reflect the current file state.

## Accessibility & Inclusion

Single-user local tool; no confirmed accessibility standard was established. Apply by
construction: readable contrast in light and dark, keyboard-operable controls, semantic
markup and ARIA tab roles (already the incumbent pattern), and responsive layout across
phone, tablet, and desktop sizes.