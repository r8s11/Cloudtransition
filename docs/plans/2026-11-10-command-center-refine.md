# Command Center refinement — implementation plan

**Goal:** Refine `dashboard-app/` into the "Personal Command Center — Deterministic-First Dashboard" without changing the Orizuru visual world.

**Approved scope (Roosevelt, 2026-11-10, via form):** identity, landing on Today, grouped navigation, deterministic-first Run/Quick tools, Today order, and "replace the Second Brain tab with something more useful or just remove it". Masthead name: "Command Center", with CloudTransition as the small secondary line.

**Meaning of "Deterministic-First" used here:** values read from files and no-model tools lead; model-backed and paid-API tools come second and say so on the card. No workspace file defines the phrase; this reading was shown in the form and not corrected.

**Stack:** FastAPI + Jinja2, plain CSS (`static/style.css`, tokens in `static/tokens.css`), vanilla JS (`static/app.js`). No build step.

**Status (2026-11-10): complete.** Every task below was carried out and checked in one session: 309 tests pass, `/` and `/reader` return 200, `/second-brain` returns 404, and Today, Run and Overview were inspected at 1280px and 390px. The boxes are left as written; nothing remains to resume. Two additions beyond the list: the brand stacks above its week line under 640px so the name never wraps, and `.brand-issue` was raised to 0.9 alpha (4.7:1).

**Follow-up (same day):** a browser regression pass found one older defect on Run and fixed it. `static/app.js` split `provider:id` on every colon, so model ids that contain a colon themselves (`…:free`) missed the catalogue lookup and their cards offered low/medium/high efforts that the server rejects with 400. `splitModel()` now splits at the first colon only; all 22 OpenCode and both OpenRouter entries offer Default only, as `docs/plans/codex-runs/eval.md` U1 requires. The same pass confirmed arrow-key traversal across the four groups, whole-group wrapping from 768px to 1200px (two rows), no horizontal overflow at eight widths, and the Metrics toolbar sticking exactly under the new masthead (111px desktop, 172px phone).

## Global constraints

- Orizuru stays: vermilion masthead, paper faces, Inter + JetBrains Mono, no glass, no new animation.
- The files stay the database; no new state store, no new write endpoint.
- `tests/test_interviews.py` and `tests/test_design_contracts.py` assert the literal tuples `("interviews", "Interviews")` and `("agents", "Agents")` in `templates/index.html`, and `.nav-tab { … min-height: 44px` inside the 640px media block. Keep both.
- `app.js` finds tabs with `.section-nav [role="tab"]`; wrappers inside the tablist are fine, the selector must keep matching.
- Bump the `?v=` asset query in `templates/index.html` when JS/CSS ships.
- Done means: `/` returns 200, `venv/bin/python -m pytest tests/ -q` passes, screenshots at 1280 and 390 show no horizontal overflow.

## Tasks

### 1. Identity
- [ ] `templates/index.html`: `<title>Command Center &mdash; CloudTransition</title>`; `apple-mobile-web-app-title` = `Command`; masthead outer element becomes `<header class="masthead">`; brand becomes `<h1 class="brand-name">Command Center</h1>` with `.brand-issue` reading `CloudTransition · Week {{ current_week }}`; footer first line `Command Center · CloudTransition · The Orizuru — one uncut sheet`.
- [ ] `static/manifest.webmanifest`: `name` = `Command Center`, `short_name` = `Command` (14 characters truncates on an iOS home screen).
- [ ] `app.py`: module docstring and `FastAPI(title=…)` say `Command Center`.
- [ ] `templates/pages/overview.html`: delete the "Fresh Start Next Week" banner and the "2026 Learning & Career Dashboard / Full-time worker · 10-15 hrs/week" hero (both contradict `TASKS.md`/`routine.md`). Replace with the standard `.page-header` (`<h2>Overview</h2>` plus one descriptive line with no claims).
- [ ] `static/style.css`: delete the now-unused `.hero*`, `.restart-banner*`, `.banner-icon` rules (including `.hero-title` in the 640px block); give `h1.brand-name` no default margin.

### 2. Landing on Today
- [ ] `templates/index.html`: the active tab is chosen by `pid == "today"`, not `loop.first`.
- [ ] `templates/pages/overview.html` loses `class="page active"`; `templates/pages/today.html` gains it.
- Check: `/` with no hash shows Today; `/#overview` still shows Overview.

### 3. Grouped navigation
- [ ] `templates/index.html`: replace the flat `pages` list with `nav_groups`:
  - Operate: today, overview, tasks, projects
  - Career: interviews, career, money
  - Learning: skills, education, books
  - System: run, agents, metrics, workspace-map, mission-control, then the Reader link
- [ ] Markup per group: `<div class="nav-group" role="presentation"><span class="nav-group-label" aria-hidden="true">…</span><div class="nav-group-tabs" role="presentation">tabs…</div></div>`. Screen readers keep the flat tab list they had.
- [ ] `static/style.css`: inactive tabs lose their individual outlines (hover fill only); active tab keeps the fold-white pill; groups are separated by one crease line; group label is the existing mono kicker style at 10px. Reader keeps its dashed outline (it leaves the sheet). At ≤640px the row stays one horizontal scroller with 44px tabs.
- Check: one row at 1280px (measure `.section-nav` height in the screenshot); groups wrap as whole units between 901px and 1279px.

### 4. Second Brain tab
- [ ] Remove it: the tab only framed a static RoboNuggets reference page. The useful deterministic lookup ("Ask the workspace", "Save a memory") already lives on Today and stays there.
- [ ] Delete `templates/pages/second-brain.html`, its `{% include %}`, the `/second-brain` route, `serve_second_brain()` and `SECOND_BRAIN_FILE` in `app.py` (no other consumer: grep of `dashboard-app/`, `visual-second-brain/`, `tools/arms/` found none).
- [ ] `CODE.md`: the `robonugget-second-brain-app/` row no longer says "served by the dashboard".

### 5. Deterministic-first Run and Quick tools
- [ ] `app.py`: `runner_engine(cfg: dict) -> dict` returning `{"tier": "local"|"api"|"model", "label": str}`:
  - `cfg.get("engine") == "jev"` → `api`, `Jev API · paid`
  - `kind == "shell"` → `local`, `No model · $0`
  - `providers == ["opencode"]` → `model`, `Model · OpenCode free`
  - otherwise → `model`, `Model · Claude by default`
- [ ] `SKILL_RUNNERS["triage-inbox"]` gains `"engine": "jev"`. Today it is `kind: "shell"`, so the card says "Local tool · $0" while it calls the paid Jev API. That label is wrong and is the one behavioural fix in this plan.
- [ ] `_skill_catalog_payload()` adds `"engine": runner_engine(cfg)` to each skill.
- [ ] Drop the trailing "Deterministic, no model, $0." / "No model, $0." from the five local blurbs (the tag now carries it).
- [ ] `QUICK_TOOLS = ("brain-index", "triage-inbox", "plan-today")` (local, then API, then model).
- [ ] `static/app.js` `renderItem`: title row holds `h4` plus `<span class="run-tag run-tag-<tier>">label</span>`; the footer status no longer says "Local tool · $0" (plain "Ready").
- [ ] `static/style.css`: `.run-item-title` (wrapping flex row) and `.run-tag` in the badge vocabulary. Local is the quiet neutral tag; `api` uses the ochre ink, `model` the vermilion ink, so cost is the marked state.
- [ ] `templates/pages/run.html`: order is (1) "Local tools" open: `trail-build,resume-build,brain-index,arms-report,artifact-catalog`; (2) "Model and API runs" open, with the Refresh models button: `triage-inbox,scout-scan,plan-today,update-sheet,youtube-summary`; (3) collapsed "Dashboard design runs": `impeccable-audit,impeccable-polish,ui-ux-review`; (4) Recent runs. Rewrite the rules list (the "Audit runs with defaults" line is stale: Audit has pickers).
- [ ] Test `tests/test_run_engine.py`: a shell runner whose argv runs a `*_jev.py` script is never tier `local`; every plain shell runner is `local`; every `claude`/`opencode-agent` runner is `model`.

### 6. Today order
- [ ] `templates/pages/today.html`: Daily, Next up, Capture, Inbox, Routine, Recent artifacts, Quick tools, Second brain. Blocks move whole; no markup inside them changes.

### 7. Verify
- [ ] `venv/bin/python -m pytest tests/ -q`
- [ ] Restart, then `sh dashboard-app/screenshot.sh today 1280`, `today 390`, `run 1280`, `run 390`, `overview 1280`; look at each.
- [ ] `impeccable detect --json` once over the changed templates and CSS.

### 8. Docs
- [ ] `dashboard-app/CLAUDE.md`: add-a-tab recipe (`nav_groups`), Run-tab recipe (`engine`), Today data-source line order, file map.
- [ ] `dashboard-app/DESIGN.md`: navigation groups and run tags.
- [ ] `PRODUCT.md`: the dashboard's name is now Command Center (that sentence only; other drift in that file is reported, not repaired).

## Review focus

1. A deep link to a removed tab (`/#second-brain`) must fall back to Today, not a blank sheet.
2. A catalogue payload from a stale server (no `engine` field) must still render cards.
3. Long tag plus long title at 390px must wrap, not overflow the card.
4. Arrow-key tab traversal must cross group boundaries in visual order.
5. An already-installed home-screen icon keeps the old name until it is re-added; nothing in code can change that.
