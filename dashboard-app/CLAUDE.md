# dashboard-app — Agent Guide

FastAPI + Jinja2 dashboard that reads workspace `.md`/`.yml` files live on every page load. No database, no build step, no state of its own — **the workspace files are the database.** One write endpoint (task checkbox toggle) edits markdown files in place.

## Run and verify (do this after every change)

```bash
cd dashboard-app
venv/bin/uvicorn app:app --port 8000        # start (venv already has all deps)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/          # expect 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/reader    # expect 200
venv/bin/python -c "import app; print('import OK')"                      # syntax check
```

A change is not done until `/` returns 200. Templates hot-reload; `app.py` changes need a server restart (or run uvicorn with `--reload`).

## File map

| File | What lives there | Typical edit |
|---|---|---|
| `app.py` | All backend code: `REALMS` config, parsers, `build_context()`, routes | Add a realm, add context data |
| `templates/index.html` | Thin shell: head, nav tabs, `{% include %}` list | Add/remove a tab |
| `templates/pages/<tab>.html` | One file per tab: overview, education, books, tasks, projects, skills, career | Change what a tab shows |
| `templates/_macros.html` | Shared Jinja macros (`metric_table`) | Rarely |
| `templates/reader.html` | Standalone markdown file browser | Rarely |
| `static/app.js` | All client JS: tab nav, progress-bar animation, realm filters, checkbox toggle | Change interactivity |
| `static/style.css` | All styles; design tokens are CSS vars in `:root` (`--accent`, `--green`, …) | Change appearance |
| `DESIGN.md` | Visual design rationale and conventions | Read before styling work |

## Data sources → tabs

- **Tasks tab** ← every file in `REALMS` (top of `app.py`); parses `- [ ]` / `- [x]` checkboxes, headings become categories
- **Skills tab** ← `skills/skills-inventory.yml`
- **Career tab** ← `goals/career-goals.yml`, `interviews/job-applications.yml`, `networking/contacts.yml`
- **Education tab** ← `College Planning/education-data.yml`
- **Books tab** ← `Books/books-data.yml`
- **Overview/Projects tabs** ← hardcoded lists in `build_context()` (`projects`, `success_metrics`, `learning_matrix`) — edit them there

## Recipes

**Add a study-track realm:** append one dict to `REALMS` in `app.py` (`id`, `name`, `file` relative to workspace root, `color`, `icon`). The file must contain markdown checkboxes. Missing files render as an empty realm — no crash, but don't point at deleted files.

**Add a new tab:** (1) add `(id, label)` to the `pages` list in `templates/index.html`, (2) create `templates/pages/<id>.html` with a `<div class="page" id="page-<id>" role="tabpanel" aria-labelledby="tab-<id>">` wrapper, (3) add its `{% include %}` in `index.html`, (4) supply any data via `build_context()`.

**Use the `metric_table` macro in a partial:** start the file with `{% from "_macros.html" import metric_table %}` — macros do not flow through `{% include %}`.

## Gotchas

- `POST /api/tasks/toggle` requires header `X-Requested-With: XMLHttpRequest` (CSRF guard) and writes the markdown file atomically via temp-file + `os.replace`. Don't "simplify" either.
- `GET /api/file` deliberately resolves paths and rejects anything outside the workspace or off the extension allowlist. Keep that check.
- Progress bars start at `width: 0` and animate to `data-width` via `animateBars()` in `app.js` — setting `width` inline in a template will break the animation.
- Always use `venv/bin/python` / `venv/bin/uvicorn`, never system python.
