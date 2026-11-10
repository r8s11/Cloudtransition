# dashboard-app — Agent Guide

FastAPI + Jinja2 dashboard that reads workspace `.md`/`.yml` files live on every page load. No database, no build step, no state of its own — **the workspace files are the database.** One write endpoint (task checkbox toggle) edits markdown files in place.

## Run and verify (do this after every change)

```bash
cd dashboard-app
launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard   # restart the always-on :8000 server (see Phone access)
venv/bin/uvicorn app:app --port 8011 --reload                       # or a scratch server; :8000 belongs to launchd
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/          # expect 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/reader    # expect 200
venv/bin/python -c "import app; print('import OK')"                      # syntax check
venv/bin/python -m pytest tests/ -q                                      # design contracts
```

A change is not done until `/` returns 200 and `pytest tests/` passes. Templates hot-reload; `app.py` changes need a server restart (or run uvicorn with `--reload`).

`tests/test_design_contracts.py` gates the visual system against regressions the
audit found: muted-ink contrast below WCAG AA, blanket `prefers-reduced-motion`
overrides that kill the sanctioned crease animation, and layout-property
transitions (`width`/`margin`) that reintroduce jank. Change a token and the
contrast assertion tells you immediately whether it still clears 4.5:1.

## File map

| File | What lives there | Typical edit |
| --- | --- | --- |
| `app.py` | `REALMS` config, parsers, `build_context()`, routes | Add a realm, add context data |
| `interview_editor.py` | Line-targeted writes to `interviews/job-applications.yml` (status/priority, next action, timeline signal, `interview_notes` / `interview_questions` / `interview_preparation`, new application); re-parses as a guard | Change how tracker edits are written |
| `triage_jev.py` | The "Triage inbox" card: Jev answers two questions per unchecked `## Inbox` item (does a `###` section fit, which one), and `decide()` holds the 0.7/0.3 Noul and 0.5 Choice thresholds that turn those answers into file-or-hold. Sends item text plus section headings only — never section contents | Change the triage rules, questions or thresholds |
| `leads_jev.py` | Job leads, second opinion: one Jev question per `requirements:` line on a tracker row, judged against the resume variant that row names. `score()` counts met (>=0.7) / thin / missing (<=0.3) into apply / gap story / skip. Email and phone are stripped from every request, and nothing is written | Change the lead questions or bands |
| `agents.py` | Read-only loader for the Forge agent roster, each agent's memory and recent events, and the newest valid Scout scan (`build_agents_view()`) | Change when the Agents tab data changes |
| `templates/index.html` | Thin shell: head, nav tabs, `{% include %}` list, run-output and interview-mode dialogs | Add/remove a tab |
| `templates/interview_sheet.html` | Standalone printable prep sheet (its own document, print CSS) | Change what prints |
| `templates/pages/<tab>.html` | One file per tab: overview, today, agents, education, books, tasks, projects, skills, career, run, … | Change what a tab shows |
| `templates/_macros.html` | Shared Jinja macros (`metric_table`, `task_check`) | Rarely |
| `templates/reader.html` | Standalone markdown file browser | Rarely |
| `static/app.js` | Tab navigation, local project forms, runner grids + output dialog, Today capture/brain forms, `data-map-query` Workspace map deep links | Change shared interactivity |
| `workspace_content.py` | Read-only file access for `/workspace-file/…` and live artifact rows; imports scope/privacy rules from `visual-second-brain/refresh-index.py` | Change what may be opened |
| `static/fonts/` | Self-hosted Inter variable + JetBrains Mono (OFL); `@font-face` at the top of `style.css` | Rarely |
| `static/metrics.js` | Read-only server operations controller: polling, host selection, history, workload filters, logs | Change Metrics interactivity |
| `metrics.py` | Local project checks, Linux/Windows host normalization, bounded historical queries | Change performance collection |
| `server_activity.py` | Container/process/service workloads, actual target probes, Loki activity and coverage | Change operational collection |
| `static/style.css` | All styles; design tokens are CSS vars in `:root` (`--accent`, `--green`, …) | Change appearance |
| `static/manifest.webmanifest`, `static/icon-*.png` | Home-screen install; opens `/#today` | Rarely |
| `launchd/com.cloudtransition.dashboard.plist` | Always-on loopback server for phone access | Rarely |
| `DESIGN.md` | Visual design rationale and conventions | Read before styling work |

## Data sources → tabs

- **Today tab** ← `build_today_view()`: today's routine folds, the live `routine.md` Working rhythm, Weekly Review, Rules and Key Dates, open `## Inbox` items and the top `NEXT_UP_COUNT` (3) open items of `TASKS.md`, ranked by `select_next_up()` from routine.md's lanes — security → income/job search → debt → the live project week (odd = Playbook, even = Bogatyr) → DevOps → the waiting project — with file order breaking ties; reference-only sections (Inbox, Recurring, Someday, Waiting On, the elapsed $3,000 sprint) are excluded. Plus the `QUICK_TOOLS` runners. Weekly Review checkboxes write through `/api/tasks/toggle`, restricted to that section. `command_centre()` adds **Daily** (six destinations, each with a number read from the same source as its tab; Metrics is marked "not read here" rather than polled), **Recent artifacts** (eight newest `artifacts/` files via `workspace_content.artifact_entries()`, read live, opened sandboxed in a new tab) and the Workspace map snapshot age plus refresh command. Each source fails on its own.
- **Workspace map tab** ← iframe of `/workspace-map/` (the `visual-second-brain/` viewer and its `workspace-index.json`, which is a snapshot: refresh with `venv/bin/python ../visual-second-brain/refresh-index.py`). `/workspace-file/<relative path>` serves only indexed files or live artifacts that still pass the privacy rules (403 denied, 404 missing, 503 index unavailable); HTML/SVG get a CSP `sandbox` with no network. Links with `data-map-query="folder=artifacts"` set the iframe's filters.
- **Tasks tab** ← every file in `REALMS` (top of `app.py`); parses `- [ ]` / `- [x]` checkboxes, headings become categories
- **Skills tab** ← `skills/skills-inventory.yml`
- **Agents tab** ← `agents.py`: `.opencode/agents/*.md`, `workspace/agents/<slug>/memory/index.md` plus the newest five valid `log.jsonl` events, and the newest `workspace/agents/scout/outputs/scan-*.json` with a `jobs` list. Missing roster definitions, a missing memory summary and a missing or unreadable scan render explicit empty states; a `log.jsonl` with no valid objects shows a message, while a missing log renders nothing and partially malformed lines are skipped. The table sorts by score with missing scores last; full JSON/Markdown open through the existing `/api/file` output dialog. The scan card is `scout-scan`, an `opencode-agent` runner whose picker offers only OpenCode's free models; `/api/skills/run` rejects a non-OpenCode provider but does not re-validate that a hand-crafted `opencode:<id>` is free.
- **Career tab** ← `goals/career-goals.yml`, `interviews/job-applications.yml`, `networking/contacts.yml`
- **Interviews tab** ← `build_interview_view()` reads `active_applications` from `interviews/job-applications.yml`: one row per application with status/priority badges, contacts, the latest `timeline` entry and the first `next_steps` item (marked overdue against today). Split into “In conversation” (offer/onsite/interviewing/assessment/screening/applied), “New leads”, and a collapsed “Closed threads” card for `rejected`/`withdrawn` — closed rows are kept for history, stay out of every count (`tracked` covers live threads only), and can be reopened from their own status select. Missing fields stay blank, and no progress is inferred beyond the file. Each row is editable in place — status/priority selects, next action, “Log signal” (appends to `timeline`) and free-form notes stored under a separate `interview_notes` key so the hand-written job-fit `notes:` survives — plus an “Add application” form. Writes go through `/api/interviews/{field,next-step,timeline,text,create}`; `interview_editor.py` edits only the lines it owns (comments and neighbours untouched) and re-parses the file before the atomic write, returning the rebuilt row so `app.js` updates in place (status changes move the row between cards).
- **Interview mode** (dialog in `index.html`, opened by a row's “Interview mode” button) ← `GET /api/interviews/detail?company=&role=`: who you are talking to (contacts incl. `mailto:`), the resume recorded under `resume:`, the posting `job_url:`, the prep/JD files listed under `interview_prep:` (linked only if they exist), the hand-written job-fit `notes:`, the last four `timeline` entries newest-first, and three editable blocks written to the entry — `interview_questions`, `interview_preparation`, `interview_notes` — each saved by its own button via `/api/interviews/text`, so nothing reloads mid-call. `interview_preparation` is deliberately its own key: `interview_prep` holds a list of file paths on some entries, and `set_text_block()` refuses to turn structured data into prose. Nothing is inferred — a missing resume/posting/contact simply does not render.
- **Today → Interview mode** ← `next_interview_action()` picks the application whose first `next_steps` date is nearest (soonest upcoming; when all have passed, the most recent, marked overdue). `command_centre()` puts it first in `daily` with `interview_key = "company|role"`; `today.html` renders it as `data-interview-open`, and `app.js` switches to the Interviews tab and opens the same dialog — no reload. Rows whose status is `rejected`/`withdrawn` are never picked (`INTERVIEW_CLOSED_STATUSES`), so Today does not point at a closed thread.
- **Prep sheet** ← `GET /interviews/sheet?company=&role=` renders `interview_sheet.html`: a standalone printable page (contacts, details, file paths, job fit, questions and preparation as checkboxes, last signals, ruled notes; preparation in two print columns) with no app chrome or scripts beyond a Print button. One letter page at the content the tracker is written with today; more text will spill to a second page rather than shrink.
- **Education tab** ← `College Planning/education-data.yml`
- **Books tab** ← `Books/books-data.yml`
- **Overview/Projects tabs** ← hardcoded lists in `build_context()` (`projects`, `success_metrics`, `learning_matrix`) — edit them there
- **Metrics tab** ← `metrics.collect_all_metrics()`: Parrot/Flatbush performance plus `server_activity.collect_server_activity()` workloads, probes, and logs. `/api/metrics/history?window=1h|6h|24h` supplies retained utilization. Local project checks remain a collapsed secondary context.

## Tailnet host observability

The server reads Prometheus at `http://parrot.tail9aa23.ts.net:9091` and Loki at
`http://parrot.tail9aa23.ts.net:3100`; browsers use only same-origin APIs.
Tailscale access is required. No new listeners, remote configuration, automatic
Beszel registration, or monitoring credentials are introduced.

- **Current performance:** both hosts show CPU, memory, system-volume usage, uptime, OS, and exporter identity. The selected host adds pressure/wait/swap/load or Windows queue length, process/thread counts, physical/Tailscale throughput, individual volumes, and physical-disk IO. Missing/nonfinite readings render as `—`, not zero. CPU/network rates use five-minute windows; interface groups are not additive.
- **Platform selection:** Parrot uses native `node_*`; Flatbush prefers native `windows_*` over compatibility/duplicate exporters. Host identity uses `host="parrot"` / `host="flatbush"` or exact known instance identities. Do not combine duplicate jobs or treat Prometheus/Loki service health as host-exporter health.
- **History:** `1h`, `6h`, and `24h` windows return at most 150 points per series, using Prometheus's clock. CPU, memory, and system-volume utilization keep missing-sample gaps; empty windows are not filled. The dashboard collection timestamp uses the dashboard server's clock. Invalid windows return 422.
- **Workloads:** real cAdvisor containers, native Windows processes (name/PID, CPU cores, private working set, threads, uptime), and Windows service state/start mode/PID. Fresh native sources win; replaced container IDs and duplicate scrapes are not summed. cAdvisor health `0` is ambiguous and stays unknown. Parrot per-process/systemd data and Flatbush container performance are currently not exported; do not fabricate them.
- **Target health:** reachability comes from actual HTTP/TCP `probe_success`, with target, probe kind, and latency—not merely exporter `up`. An exporter being down means its readings are cleared; it does not establish that the machine itself is offline.
- **Activity:** latest eight log entries per host plus 15-minute counts and source breakdowns. Error counts describe only severity-indexed events; unindexed severity is explicit. Counts and recent-log availability are independent. No log entries does not mean no work occurred.
- **Bounds/privacy:** collection caps containers/probes at 100 and processes/services at 500 per host. Queries omit command-line/path/account labels before transfer. Log messages cap at 800 characters and redact known bearer/password/token forms; this is not a security assessment or a comprehensive secret scanner. No GPU utilization, AI-job progress, token usage, or cost telemetry is currently exported.
- **Source states:** absent telemetry is pending/not exported; query failure is unavailable; exporter `up=0` is down with current usage cleared. Sources fail independently. A log or history outage must not erase successful host performance; an upstream outage must not erase successful local project checks.
- **Interaction:** snapshot polling runs every 15 seconds and history every 60 seconds only while Metrics is active, visible, and Live is checked. Refresh now works while paused. Snapshot collection is single-flight with a 12-second browser deadline; failed/malformed responses clear current readings and retain the last successful collection time. History cancellation/generation guards keep the newest range authoritative.
- **Rendering:** tables initially show 20 rows with search/state filters and Show more. Log expansion and keyboard focus survive incoming snapshots; all telemetry is inserted as text, never HTML. Sticky host/history/Live controls sit below the measured masthead at every breakpoint.
- **Local context:** local salsatd probe failure means **Unavailable**, not a production outage. Projects without probes say **Not monitored**; the dashboard API reports **Responding**. No fabricated security-pass or duplicate salsatd response fields remain. `/api/metrics` returns `timestamp`, `projects`, `infrastructure`, and `activity`.
- **Verification:** `tests/test_infrastructure.py`, `test_host_history.py`, `test_server_activity.py`, `test_process_activity.py`, and `test_project_metrics.py` cover normalization, identity/source precedence, freshness, down/unknown/zero semantics, bounds, credential redaction, container replacement, and project scope. Browser smoke covers live hosts/ranges, workload filtering/expansion, independent failures/recovery, empty history, inert log markup, timeout, range cancellation, polling/pause, and responsive containment.
- **Density and hierarchy:** the operator rejected excessive padding. Metrics-only sheet gutters stay 16px desktop/12px phone; host panels use 12px padding and sections 16px spacing. CPU busy is the single emphasized host KPI; memory and volume remain secondary. Keep readable typography, 44px controls, table-local horizontal scroll, and other tabs' spacing unchanged. Asset query versions in `templates/index.html` must change when shipping JS/CSS.

## Recipes

**Add a study-track realm:** append one dict to `REALMS` in `app.py` (`id`, `name`, `file` relative to workspace root, `color`, `icon`). The file must contain markdown checkboxes. Missing files render as an empty realm — no crash, but don't point at deleted files.

**Add a new tab:** (1) add `(id, label)` to the `pages` list in `templates/index.html`, (2) create `templates/pages/<id>.html` with a `<div class="page" id="page-<id>" role="tabpanel" aria-labelledby="tab-<id>">` wrapper, (3) add its `{% include %}` in `index.html`, (4) supply any data via `build_context()`.

**Use the `metric_table` macro in a partial:** start the file with `{% from "_macros.html" import metric_table %}` — macros do not flow through `{% include %}`.

**Add a Run-tab button:** add an entry to `SKILL_RUNNERS` in `app.py`. `kind: "shell"` runs a fixed `argv` with no shell (e.g. `resume-build` → `sh resume/build.sh [YYYY-MM]`; Python scripts use `sys.executable`); the script may call an API itself, as `triage-inbox` does with Jev; `kind: "claude"` runs `claude -p`; `kind: "opencode-agent"` runs `opencode run --standalone --agent <agent> -m <model> <prompt>`; `agent` selects the OpenCode agent and `providers: ["opencode"]` limits its picker to OpenCode models — the run endpoint rejects a non-OpenCode provider, but it does not re-check that a hand-crafted `opencode:<id>` is free. Prompts may use `{input}`, `{today}` and `{week}` (so a literal brace must be doubled). A form field comes from `input_label` + `input_pattern`; add `input_optional` to allow blank, and `input_argv` to append the validated value to a shell `argv`. `pages/run.html` must stay in the `index.html` include list or the Run tab is empty. To also show it on Today, add its id to `QUICK_TOOLS`; any element with `data-run-grid` (optionally `data-skills="a,b"`) renders runners.

**Headless skill buttons:** Run features `/impeccable audit`, `/impeccable polish`, `/ui-ux-pro-max` review, and `/youtube-summarizer`. Audit and review are `read_only: True`, restricting Claude to Read/Glob/Grep/Skill with `dontAsk`; audit uses fixed defaults. Polish has a `permissions` block instead: `dontAsk` plus an allowlist (edits only under `templates/` and `static/`, Bash only `sh dashboard-app/screenshot.sh <tab> <width>` and `venv/bin/python -m pytest`, `--add-dir` for the impeccable skill's reference files); anything else is denied, not prompted. In `--allowedTools`, `Edit(path)` rules also cover Write; `Write(path)` rules are ignored, and a Bash `curl … -o` rule was still denied, which is why `screenshot.sh` does the 200 check itself. Review, polish, and video have per-button model and effort pickers (`options: True`); video requires a validated URL. Other runners remain under Other workspace tools. Add a new runner id to the relevant Run-page `data-skills` list as well as the catalog. Model aliases come from `ALLOWED_MODELS`; efforts are default/low/medium/high.

**Run records:** `POST /api/skills/run` accepts only catalog ids and allowlisted options, requires the CSRF header, and rejects duplicate in-flight runs atomically. A card with `providers` rejects a model from another provider before launch. Commands execute as argv (no shell), from the workspace, with a 30-minute deadline and no interactive permission prompts or bypass flags. Output is `dashboard-app/runs/<uuid>.txt`, shown beside the button and in its Output dialog. New `runs.log` entries are JSON lines for start/completion, including id, timestamp, complete command (model/effort included), exit code, duration, and output path; historical plain-text lines remain untouched. If the start event cannot be logged, the command does not start. Recent-run status is in memory and resets when the server restarts; output files and the log remain.

**Screenshots:** `sh dashboard-app/screenshot.sh <tab> <width>` checks `:8000` returns a successful HTTP response, then headless Chrome writes `runs/shots/<tab>-<width>.png` (gitignored) and prints the path. Requires Node 24 and Chrome. Uses Chrome's DevTools pipe to set a true 390px/1280px viewport before navigating; `--window-size` alone silently clamps narrow desktop windows and crops the phone screenshot. Browser process and temporary profile are removed afterward.

**Polish verification (2026-11-04):** Run `1e7d959574e44d839509167f75a287fa` completed with exit 0. Its UI edits tighten desktop tabs, wrap long project badges, hide repeated task-category pills, add disclosure affordances and Run-note spacing, simplify the fold graph, and bump asset versions. Independent browser verification covered Today/Tasks/Run/Overview at 390px and 1280px (no horizontal overflow), opening run output and Escape dismissal; 119 tests passed. The runner's final report omitted its applied changes and discussed remaining design-hook findings instead; do not use that report alone as the change ledger.

**Organizer endpoints:** `POST /api/capture` `{text}` appends `- [ ] text` to `## Inbox` in `TASKS.md` (created above `## Active` if missing). `GET /api/brain/query?q=` and `POST /api/brain/remember` `{title, summary, body}` shell out to `second-brain/brain.py` (argv, no shell) and relay its JSON; brain.py refuses credentials.

## Phone access

The LaunchAgent keeps uvicorn on `127.0.0.1:8000` while the USB drive is mounted; `tailscale serve --bg --https=443 http://127.0.0.1:8000` publishes it to the tailnet only (not Funnel) at `https://roosevelts-macbook-air.tail9aa23.ts.net/`. The phone needs the Tailscale app signed in to the same account; then Share → Add to Home Screen. Every tailnet device can trigger Run buttons, including `claude --permission-mode acceptEdits`, so keep the tailnet to your own devices.

- Install/restart/remove commands are in the plist header. Logs: `~/.local-routines/dashboard/`.
- After editing `app.py`: `launchctl kickstart -k gui/$(id -u)/com.cloudtransition.dashboard`.
- Stop phone access: `tailscale serve --https=443 off`. Status: `tailscale serve status`.

## Gotchas

- `POST /api/tasks/toggle` and `POST /api/capture` require header `X-Requested-With: XMLHttpRequest` (CSRF guard) and write through `_atomic_write` under `_FILE_WRITE_LOCK`. Don't "simplify" any of that.
- Toggle sends the task `text` with its line number. A capture shifts later lines in `TASKS.md`, so the server follows the text to its new line and returns 409 when the match is ambiguous. Routine uses the same atomic writer, but only accepts checkboxes in the `Weekly Review` section of `routine.md`. Render checkboxes with the `task_check` macro so they carry `data-text`.
- `#runOutputDialog` lives in `index.html` outside the tab panels. A modal inside a hidden panel opens at zero size.
- `GET /api/file` deliberately resolves paths and rejects anything outside the workspace or off the extension allowlist, and `/api/file` + `/api/files` (Reader, Run output) also refuse anything `workspace_content.privacy_violation()` flags: secret names, private/employer paths, work logs, College Planning — including copies nested deeper such as `.trail/cache/College Planning/`. Keep those checks.
- Progress bars start at `transform: scaleX(0)` and animate to `data-width` via `animateBars()` in `app.js` — setting `width` inline in a template will break the animation.
- Always use `venv/bin/python` / `venv/bin/uvicorn`, never system python. Under launchd, start through `venv/bin/python -m uvicorn`: the `venv/bin/uvicorn` sh script fails with "Operation not permitted" on the removable volume.
- `OPENROUTER_API_KEY` and `TYPESAFE_API_KEY` (Jev, for the Triage inbox card and `leads_jev.py`) come from the process environment; `app.py` reads an optional gitignored `dashboard-app/.env` at startup without overriding real env vars. After adding a key, restart the LaunchAgent so the server re-reads it — shell-spawned runs inherit the server's environment, so a key that is only in your shell rc is not visible to them. `triage_jev.py` exits 2 when the key is missing and 3 on an API failure, and never writes `TASKS.md` in either case.
- A card's `context_files` are inlined into the prompt only for OpenRouter, whose chat API cannot read files; Claude/Codex/OpenCode read them locally. Inlining skips paths outside the workspace and privacy-flagged paths, and is bounded by `CONTEXT_MAX_FILE_CHARS` / `CONTEXT_MAX_CHARS`.
