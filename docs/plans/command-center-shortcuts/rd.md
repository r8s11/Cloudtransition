# Command Center: shortcuts and numbers on Today

Date: 2026-11-12. Owner: Roosevelt. Target: `dashboard-app/` (the Command Center, `http://127.0.0.1:8000`).

## Request (verbatim)

> Adapt the following to my command center
>
> - My recent agent-made artifacts (scan a folder like output/artifacts/), each opening on click
> - Shortcut tiles for my daily micro-apps and key folders
> - A slot for the numbers I care about: fill with real data where you can read it, and mark placeholders clearly where you cannot
> - Room to grow: comment the file so future widgets are easy to add
>
> Serve it locally so it always opens at the same address (for example with a tiny static server kept alive by pm2), and tell me how to make that survive a restart.
>
> When it is running, give me the address and a one-line summary of every section on the page.

The same message carried two more starter prompts (router files, visual second brain) and the seven "visual command centre" principles. Principle 5 applies here: "The second brain is the centrepiece. Link your visual memory map from the middle of the page."

## What already exists (checked 2026-11-12, not rebuilt)

| Asked for | Where it lives today |
| --- | --- |
| Recent artifacts, one click | Today → **Recent artifacts**: eight newest files of `artifacts/`, read live, opened sandboxed through `/workspace-file/` |
| Numbers slot with marked placeholders | Today → **Daily**: one row per destination with a number from the same parser as its tab; the Metrics row is an italic placeholder |
| Comments for future widgets | `app.py` above `command_centre()`, and each card in `templates/pages/today.html` |
| Same address, survives a restart | LaunchAgent `com.cloudtransition.dashboard` (`RunAtLoad`, `KeepAlive` on the drive path) keeps `127.0.0.1:8000`; no pm2 needed |
| Router files | `AGENTS.md` (master) and `OPERATIONS.md`, `CODE.md`, `MONEY.md`, `LEARNING.md`, `CONTENT.md`, `HEALTH.md`; every pointer resolves |
| Visual second brain | `visual-second-brain/` (Workspace map tab, `refresh-index.py`) |

## Gaps to build

1. **Shortcuts card on Today**, placed mid-page between Inbox and Routine.
   - **Find a file**: one search field. Submitting opens the Workspace map tab with that text as its query. This is the centrepiece link of principle 5.
   - **Apps**: full-page versions that open in a new tab: Workspace map (`/workspace-map/`), Reader (`/reader`), Mission Control (`/mission-control/`). Plus **ARMS review** (`http://127.0.0.1:8790/`, added at review on 2026-11-12): a link while the app runs, a `Not running` placeholder while it does not. It works on the Mac only.
   - **Files**: `TASKS.md`, `DASHBOARD.md`, `resume/master.md`, `interviews/job-applications.yml`, opened through `/workspace-file/`.
   - **Folders**: `resume`, `interviews`, `artifacts`, `docs/plans`, `IT Mgmt`, `second-brain/memories`. A folder tile opens the Workspace map filtered to that folder (a browser cannot open Finder).
   - One list in `app.py` (`SHORTCUTS`) defines every tile. A tile whose target cannot be opened (missing, moved, private, or not in the map index) renders as a marked placeholder with no link, never as a dead link.
2. **Two more numbers in Daily.**
   - **Job search** → Interviews tab: live, in-conversation and new-lead counts from `interviews/job-applications.yml` (the same `interview_counts` the Interviews tab shows).
   - **Money** → Money tab: number of debts listed in `finance/tracker.yml`. The file holds no debts today, so the row is a marked placeholder until it does.
3. **Comments and docs**: a one-line "add a tile" note above `SHORTCUTS` and in the card; the recipe in `dashboard-app/CLAUDE.md`; router lines in `CODE.md` and `CONTENT.md`.

## Boundaries

- Read-only. No new write endpoint, no new state, no new server, no new dependency.
- Orizuru stays: rows in the existing `daily-row` vocabulary, no new colour, no animation.
- Tiles never widen `/workspace-file/` access: availability is decided by `workspace_content.resolve_file()` and the map index.
- Not built: per-folder file counts, opening Finder, pm2.

## Review outcome (2026-11-12)

Roosevelt approved the evals as written, kept all five assumptions (Job search row, Money row, Apps, Files and Folders tiles), and added the ARMS review tile and a one-page trim of `CODE.md`.
