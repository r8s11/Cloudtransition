---
feature: Command Center shortcuts and numbers on Today
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Command Center shortcuts and numbers on Today

Adds one **Shortcuts** card to the middle of the Command Center's Today page (a Find-a-file field that opens the Workspace map, plus Apps, Files and Folders tiles) and two numbers to the **Daily** card (Job search, Money). For Roosevelt, the only user, on the Mac and on the phone over the tailnet. Read-only; lives in `dashboard-app/`.

## Build contract

- Build only after `status: approved`. Editing this file or the mockup resets every result; changing what a case checks needs the user's re-approval (`status: review`).
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/command-center-shortcuts/eval.md`
- Manual cases: `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/command-center-shortcuts/eval.md <ID> pass|fail "<what you observed + evidence path>"`. Save screenshots under `docs/plans/command-center-shortcuts/eval-evidence/`.
- Any code change after an automated case passed makes it stale. Done = every automated case passing; manual cases are advisory and only block when recorded as `fail`.
- Automated cases run with `bash -c` from the repo root; exit 0 = pass.
- New tests live in `dashboard-app/tests/test_shortcuts.py`. They render Today through the app with a temporary workspace or monkeypatched `SHORTCUTS`; no network, no model call.
- Manual cases run against the real dashboard at `http://127.0.0.1:8000/#today` after `launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard`, at 1280×900 and 390×844.

## Traceability

| Requirement (from RD) | Cases |
| --- | --- |
| Shortcuts card mid-page, between Inbox and Routine | U1, R3 |
| Apps, Files and Folders tiles from one `SHORTCUTS` list | U1, U2, U3 |
| ARMS review tile: links to the loopback app when it runs, placeholder `Not running` when it does not | U7 |
| A tile that cannot be opened is a marked placeholder, never a dead link; access is not widened | F1 |
| Daily: Job search counts from the tracker | U5 |
| Daily: Money debt count, marked placeholder when it cannot be read | U5, F2 |
| Comments and recipe for adding a tile or widget | U6 |
| Same address, survives a restart (existing LaunchAgent) | R5 |
| Recent artifacts keeps working (existing) | R1, R3 |
| Read-only, Orizuru vocabulary, phone layout | R1 |

## Usage — every way to use the feature

### U1 — Today shows the Shortcuts card with its three groups
- **Setup:** default workspace.
- **Steps:** 1. Render `/`.
- **Expected:** the HTML has a card titled `Shortcuts` (`id="shortcutsTitle"`) that appears after the Inbox card and before `id="routineTitle"`. Inside it, in order: a form `id="mapFindForm"` with a search input labelled `Find a file`, then group headers `Apps`, `Files`, `Folders`. One row per entry of `app.SHORTCUTS`, in list order.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_card_position_and_groups`

### U2 — App and file tiles open their target
- **Setup:** default workspace and current map index.
- **Steps:** 1. Render `/`. 2. Request the `href` of every Apps and Files row that is not a placeholder.
- **Expected:** the first three Apps rows are `/workspace-map/`, `/reader`, `/mission-control/` with `target="_blank" rel="noopener noreferrer"`. Files rows are `/workspace-file/TASKS.md`, `/workspace-file/DASHBOARD.md`, `/workspace-file/resume/master.md`, `/workspace-file/interviews/job-applications.yml`. `/workspace-map/`, `/reader` and every `/workspace-file/…` href answer 200 (`/mission-control/` is not requested: it depends on agentic-os being up).
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_app_and_file_tiles_resolve`

### U3 — Folder tiles point the Workspace map at their folder
- **Setup:** default workspace and current map index.
- **Steps:** 1. Render `/`.
- **Expected:** each Folders row has `href="#workspace-map"` and `data-map-query="folder=<url-encoded folder>"`; `IT Mgmt` renders as `folder=IT%20Mgmt`. The six folders are `resume`, `interviews`, `artifacts`, `docs/plans`, `IT Mgmt`, `second-brain/memories`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_folder_tiles_carry_map_query`

### U5 — Daily carries the Job search and Money numbers
- **Setup:** `command_centre()` called with `interview_counts={"tracked": 27, "active": 6, "leads": 21}` and a tracker with two debts; then with the real `finance/tracker.yml` shape (`debts: []`).
- **Steps:** 1. Read the `daily` rows.
- **Expected:** a row `Job search` with `href="#interviews"` and value `27 live · 6 in conversation · 21 new leads`, placed directly after `Tasks`. A row `Money` with `href="#money"` placed directly after `Projects`: value `2 debts on file` for the two-debt tracker; for `debts: []` the value is `No debts entered yet` and the row has `placeholder: True`. `Interview mode` stays the first row when an interview action exists.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_daily_job_search_and_money_rows`

### U6 — The next widget is easy to add
- **Setup:** built feature.
- **Steps:** 1. Read the comment above `SHORTCUTS` in `app.py`, the comment above the card in `templates/pages/today.html`, and the Recipes section of `dashboard-app/CLAUDE.md`.
- **Expected:** `app.py` has a comment that starts `# Add a tile:` directly above `SHORTCUTS`; `today.html` names `SHORTCUTS` in the comment above the card; `dashboard-app/CLAUDE.md` has a recipe line starting `**Add a Today shortcut:**`.
- **Verify:** `grep -q "^# Add a tile:" dashboard-app/app.py && grep -q "SHORTCUTS" dashboard-app/templates/pages/today.html && grep -q "^\*\*Add a Today shortcut:\*\*" dashboard-app/CLAUDE.md`

### U7 — ARMS review tile follows whether the app is running
- **Setup:** `SHORTCUTS` monkeypatched to one `port` tile, first on a port with a listening loopback socket, then on a closed port. The real list carries `ARMS review` on port 8790 as the fourth Apps row.
- **Steps:** 1. Build the shortcut groups for each.
- **Expected:** listening: the row is a link to `http://127.0.0.1:<port>/` that opens in a new tab, note `Mac only`. Closed: the row is a placeholder with no link and the value `Not running`. The check never raises and waits at most 0.2 s.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_port_tile_follows_listener`

## Failure — every way it could go wrong

### F1 — A tile whose target cannot be opened is a placeholder, not a dead link
- **Setup:** `SHORTCUTS` monkeypatched to hold a missing file (`nope/x.md`), a private file (`College Planning/README.md`) and a folder with no indexed files (`no-such-folder`).
- **Steps:** 1. Render `/`.
- **Expected:** status 200. Each of the three rows renders as a non-link element (`<span`, no `href`) with class `is-placeholder` and the value `Not available`. None of the three paths appears in any `href`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_unavailable_tiles_are_placeholders`

### F2 — Money tracker missing or malformed never breaks Today
- **Setup:** tracker path pointed at (a) a missing file, (b) a file containing `debts: "oops"`, (c) invalid YAML.
- **Steps:** 1. Build the Daily rows for each.
- **Expected:** no exception. The `Money` row has `placeholder: True`; value `No money tracker yet` for (a) and `Tracker unreadable` for (b) and (c).
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_money_row_survives_bad_tracker`

## Regression — what this feature must not break

### R1 — Existing test suite still passes
- **Expected:** full suite green, including `test_today_daily_list_starts_with_the_interview_action` and `tests/test_workspace_content.py`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/ -q`

### R2 — The app imports and the Workspace map tests pass
- **Expected:** zero errors. This repo has no typecheck or build step; import plus the neighbour's unit tests stand in for it.
- **Verify:** `cd dashboard-app && venv/bin/python -c "import app" && cd .. && python3 -m unittest discover -s visual-second-brain/tests`

### R3 — Today's existing cards keep their order
- **Steps:** 1. Render `/`.
- **Expected:** card titles appear in this order: `Daily`, `Next up`, `Capture`, `Inbox`, `Shortcuts`, the Routine card (`id="routineTitle"`), `Recent artifacts`, `Quick tools`, `Second brain`. Recent artifacts rows still link to `/workspace-file/artifacts/…`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_today_card_order_unchanged`

### R4 — Existing Daily rows are unchanged
- **Steps:** 1. Build the Daily rows.
- **Expected:** `Tasks`, `Routine`, `Projects`, `Recent artifacts`, `Workspace map`, `Mission Control`, `Second brain`, `Metrics` keep their labels, hrefs and relative order; `Metrics` keeps `placeholder: True`.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/test_shortcuts.py -q -k test_existing_daily_rows_unchanged`

### R5 — The page keeps its always-on address
- **Steps:** 1. Read the installed LaunchAgent. 2. Request the page.
- **Expected:** `RunAtLoad` is `true` and `http://127.0.0.1:8000/` answers 200.
- **Verify:** `plutil -extract RunAtLoad raw ~/Library/LaunchAgents/com.cloudtransition.dashboard.plist | grep -qx true && curl -fsS -o /dev/null http://127.0.0.1:8000/`

