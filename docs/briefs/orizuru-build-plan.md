# Orizuru Build — Implementation Plan

**Date:** 2026-09-13
**Brief:** `docs/briefs/dashboard.brief.md`
**Roll key:** `296b5a32` (bolder re-roll, Orizuru won challenger)
**User decision:** Fold column = this week's steps 1..N, not fixed 32. Approve proceed.

---

## Scope

Replace the "Atmospheric Glass" visual world with The Orizuru across the entire dashboard app. The backend engine (`app.py` routes, toggle logic, parsers) and client behavior (`app.js` ARIA tabs, toggle with revert, `animateBars`) are **untouchable invariants**. Only CSS, templates, and minor context additions change.

---

## Files Changed

| File | Action |
| --- | --- |
| `dashboard-app/static/style.css` | **Full replacement** (1,981 lines → Orizuru) |
| `dashboard-app/templates/index.html` | **Major edit**: fold-column shell, Orizuru nav |
| `dashboard-app/templates/pages/overview.html` | Restyle: crease-pattern stats, first viewport |
| `dashboard-app/templates/pages/tasks.html` | Restyle: fold/unfold toggle (checkbox → crease fold) |
| `dashboard-app/templates/pages/education.html` | Restyle components |
| `dashboard-app/templates/pages/books.html` | Restyle components |
| `dashboard-app/templates/pages/projects.html` | Restyle components |
| `dashboard-app/templates/pages/skills.html` | Restyle components |
| `dashboard-app/templates/pages/career.html` | Restyle components |
| `dashboard-app/templates/pages/money.html` | **New**: empty-state placeholder |
| `dashboard-app/templates/_macros.html` | Restyle metric_table |
| `dashboard-app/templates/reader.html` | Restyle inline CSS to Orizuru palette |
| `dashboard-app/DESIGN.md` | **Replace** with Orizuru design rationale |
| `dashboard-app/app.py` | **Minor edit**: add routine fold parser + money context |

---

## Design Decisions

### 1. Fold column — this week's steps, not a fixed 32

The numbered margin column contains *this week's actual folds* (Workday Mon–Fri, Project Block, DevOps Block, Weekend Review), numbered 1..N in order. Gold dot on today's step. The crane's 32-step sequence is the year's metaphor; each week contributes its own folds. This keeps the column honest to the files-as-database principle (routine.md is the source).

### 2. Money tab — new empty-state page

No money/debt YAML exists yet. The page shows a clear empty state with instructions to create the YAML source. Consistent with how career.html already handles missing data.

### 3. Reader.html — restyle to Orizuru

Its inline CSS (870 lines) gets the Orizuru palette: vermilion accent, washi background, gold active states. Layout/function stays; visual tokens unify.

### 4. CSS-only washi texture

Layered `repeating-linear-gradient` + `radial-gradient` noise to suggest kozo fiber — no external images. Anti-goal compliance: no image assets, no gradients used as data.

### 5. Weekly fold mapping

A new `parse_routine_folds()` function reads the "The working rhythm" table from `routine.md` → returns `fold_steps` (list of `{day, step_num, label, is_today}`) to `build_context()`. Gold dot is derived from `date.today()`.

---

## Execution Order

### Phase A — Design system (`static/style.css`)

- Orizuru CSS vars: `--vermilion: #b3212e`, `--fold-white: #f4ead8`, `--gold: #c9a227`, `--sumi: #171512`, `--washi-fiber: <layered gradients>`
- All component classes (`.card`, `.grid-*`, `.stat-box`, `.progress-track`, `.badge`, `.task-item`, `.realm-pill`, `.ring-*`, `.metric-row`, `.matrix-table`, `.book-row`, `.cert-card`, `.phase-card`, `.timeline-*`, `.skill-row`, `.net-goal`, `.empty-state`, `.restart-banner`, `.hero`, `.masthead`, `.section-nav`, `.nav-tab`, `.main`, `.footer`, `.page`, `.page-header`)
- Fold column component: `.fold-column`, `.fold-step`, `.fold-step.active`, `.fold-step.gold`
- Crease-line texture on cards
- Responsive: fold column stacks below on mobile (≤768px)

### Phase B — Shell + fold column (`templates/index.html`)

- Two-column wrapper: `.sheet-layout` → `.fold-column` (left) + `.sheet-faces` (right, contains all pages)
- Fold steps rendered from `fold_steps` Jinja variable (new, from app.py)
- Gold dot on today
- Nav tabs restyled as sheet-face labels
- Masthead: "CloudTransition · Issue No. N" in sumi ink on vermilion ground
- Add Money to pages list

### Phase C — Page templates (all 8 pages + `_macros.html`)

- `overview.html`: first viewport = fold column + gold dot + page titles orbiting; stats as "crease density" (fold count per domain); year progress rings restyled in fold-white on washi
- `tasks.html`: checkbox → fold crease toggle (visual snap); task-done-row = collapsed fold state
- `education.html`, `books.html`, `projects.html`, `skills.html`, `career.html`: restyle cards, badges, progress bars, rings, tables to Orizuru materials
- `money.html`: empty state (vermilion paper, "Add money/tracker.yml to enable this fold")
- `_macros.html`: metric_table rows get sumi-ink text, fold-white crease separators

### Phase D — Backend (`app.py`)

- Add `parse_routine_folds(today)` → reads `routine.md` "The working rhythm" table, maps to Mon–Sun steps, returns `fold_steps` list with `{day, label, step_num, is_today}` dicts
- Add `money` empty state to `build_context()` return
- Add routine parser: try `Path(WORKSPACE / "routine.md").read_text()`, extract the rhythm table rows; fallback to a static 7-step week if parse fails

### Phase E — Verify

- `venv/bin/uvicorn app:app --port 8000`
- `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/` → 200
- `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/reader` → 200
- `venv/bin/python -c "import app; print('import OK')"` → OK
- Update `DESIGN.md` with Orizuru rationale

---

## What Does NOT Change

| Invariant | Location |
| --- | --- |
| Atomic tempfile toggle | `app.py:614-618` (`tempfile.NamedTemporaryFile` + `os.replace`) |
| X-Requested-With CSRF guard | `app.py:589` |
| Path allowlist + extension check | `app.py:562-582` |
| Progress bar animate from zero (GPU-accelerated `transform: scaleX(0) → scaleX(pct)`, driven by `data-width` in `app.js:87-99`) | `app.js:87-99` (`animateBars()`) |
| Toggle revert logic | `app.js:120-168` |
| ARIA tab pattern | `app.js:1-85` |
| Realm filter pills | `app.js:98-117` |
| `venv/bin/uvicorn app:app --port 8000` | CLAUDE.md run command |

---

## Verification

A change is not done until all of these pass:

```
venv/bin/uvicorn app:app --port 8000 &
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/          # expect 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/reader    # expect 200
venv/bin/python -c "import app; print('import OK')"                      # expect OK
```
