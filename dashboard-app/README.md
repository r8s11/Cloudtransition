# Command Center Blueprint

## System Overview

Command Center is a FastAPI application that renders workspace Markdown and YAML through Jinja2. Workspace files remain the durable task and application records; the server also keeps transient run/catalogue state and writes runner logs and output files. It is not a database-backed application. [app.py:app] [app.py:build_context] [app.py:_RUNS]

The browser handles tabs, task edits, interview preparation, runner controls, and telemetry rendering. The backend mediates workspace access, subprocess execution, and upstream HTTP requests. [app.py:toggle_task] [app.py:interview_text] [app.py:_execute_run] [app.py:api_metrics]

## Interface

### Local Interface & Invariants

| Source | Boundary |
| --- | --- |
| [app.py](./app.py) | `app` ASGI entry point; `REALMS` checklist sources; `build_context()`, `build_today_view()`, `build_interview_view()` assemble page data. |
| [core/interview_editor.py](./core/interview_editor.py) | `set_field()`, `set_next_step()`, `append_timeline()`, `set_text_block()`, `add_application()` transform tracker text; `InterviewEditError` rejects edits. Persistence belongs to callers. |
| [core/workspace_content.py](./core/workspace_content.py) | `indexed_paths()`, `artifact_entries()`, `privacy_violation()`, `resolve_file()`, `file_headers()` enforce indexed/live-artifact access; `ContentError` carries HTTP status and message. |
| [core/agents.py](./core/agents.py) | `discover_agents()`, `load_state()`, `load_hub()`, `load_memory()`, `load_latest_scan()`, `job_id()`, `load_job_reading()`, `base_cv_path()`, `application_agents()`, `scout_leads()`, `build_agents_view()` read agent definitions, hub config and outputs; nothing writes. |
| [core/skills.py](./core/skills.py) | `discover_skills()`, `agent_matrix()`, `skill_access()`, `approved_skills()` mirror OpenCode skill discovery and evaluate agents' resolved `skill` rules; nothing writes. |
| [collectors/metrics.py](./collectors/metrics.py) | `collect_salsatd_metrics()`, `collect_project_metrics()`, `collect_infrastructure_metrics()`, `collect_metric_history()`, `collect_all_metrics()` return local checks and tailnet telemetry. |
| [collectors/server_activity.py](./collectors/server_activity.py) | `collect_server_activity(fetch_json, prometheus_url, loki_url)` returns host workloads, probes, logs, coverage, source states, and limits. `resolve_host()`, `redact()`, `clean_text()` normalize identity and display data. |
| [collectors/metric_charts.py](./collectors/metric_charts.py) | `collect_rate_history()`, `collect_probe_history()`, `collect_log_volume()`, `collect_chart_history()` return bounded historical chart sections. |
| [scripts/triage_jev.py](./scripts/triage_jev.py) | `main()` files Inbox tasks using Jev answers. `--payload` prints requests without API calls; `--dry-run` calls the API without writing. |
| [scripts/leads_jev.py](./scripts/leads_jev.py) | `main()` judges tracker requirements against résumé evidence. Flags: `--payload`, `--company`, `--limit`, `--json`, `-v`/`--verbose`. No file writes; `--json` output includes a text banner. |
| [scripts/screenshot.sh](./scripts/screenshot.sh) | `sh dashboard-app/scripts/screenshot.sh <tab> <width>` from workspace root; tab uses lowercase letters/digits/hyphens, width is 320–2560. Produces a 2400-pixel-high viewport PNG, not a stitched full page. |
| [tailwind.config.js](./tailwind.config.js) | `module.exports` defines class-based dark mode and theme extensions; it supplies no build command. |

Citations in the form `[file:symbol]` name the source boundary supporting a contract. Internal helpers are implementation references, not additional public APIs.

### HTTP boundaries

| Method | Path | Handler / contract |
| --- | --- | --- |
| GET | `/` | `dashboard()` renders `index.html` and warms the runner catalogue. |
| GET | `/reader` | `reader()` renders the file browser. |
| GET | `/agents/skills` | `skill_registry()` renders the read-only Skill Registry; asks `opencode debug agents` (about 4 s). |
| GET | `/workspace-map` | `workspace_map_redirect()` redirects to trailing-slash URL. |
| GET | `/workspace-map/` | `workspace_map()` serves the external workspace viewer. |
| GET | `/workspace-map/workspace-index.json` | `workspace_map_index()` serves the index; missing index returns 503. |
| GET | `/workspace-file/{path:path}` | `workspace_file()` serves eligible files; optional `download` changes disposition. |
| GET | `/api/workspace/artifacts` | `workspace_artifacts()` returns artifact rows. |
| GET | `/mission-control`, `/mission-control/{path:path}` | `mission_control()` delegates to loopback Mission Control proxy. |
| GET | `/api/files` | `api_files()` returns eligible Markdown file metadata. |
| GET | `/api/file?path=…` | `api_file()` returns `{path, content}` for an allowed workspace text file. |
| POST | `/api/tasks/toggle` | `toggle_task(ToggleRequest)` changes one checkbox; body: `realm`, `line`, `done`, optional `text`. |
| POST | `/api/capture` | `capture(CaptureRequest)` appends `text` to the task Inbox. |
| GET | `/api/brain/query?q=…` | `brain_query()` invokes retrieval; query length 2–200. |
| POST | `/api/brain/remember` | `brain_remember(RememberRequest)` delegates `title`, `summary`, `body` to the memory CLI. |
| GET | `/api/interviews/detail?company=…&role=…` | `interview_detail()` returns the matching tracker row and agent state. |
| GET | `/interviews/sheet?company=…&role=…` | `interview_sheet()` renders printable preparation. |
| POST | `/api/interviews/field` | `interview_field(InterviewFieldRequest)` updates `field`/`value` for `company`/`role`. |
| POST | `/api/interviews/next-step` | `interview_next_step(InterviewNextStepRequest)` replaces next action using `task` and optional `date`. |
| POST | `/api/interviews/timeline` | `interview_timeline(InterviewSignalRequest)` appends `date`, `stage`, optional `notes`. |
| POST | `/api/interviews/text` | `interview_text(InterviewTextRequest)` saves `field`/`text` for `company`/`role`. |
| POST | `/api/interviews/create` | `interview_create(InterviewCreateRequest)` adds an application; defaults to `new_lead`, `medium`. |
| GET | `/api/career/work-search?start=YYYY-MM-DD` | Returns a seven-day report with completed activities, missing fields, and copy-ready text. Defaults to the current Monday; the user can choose any claim-week start. |
| POST | `/api/career/work-search` | Upserts a completed activity by UUID in the tracker's `work_search_activities` section. Requires the CSRF header and a nonfuture activity date. |
| GET | `/api/skills/catalog` | `api_skill_catalog()` returns provider/model availability and runner metadata. |
| POST | `/api/skills/catalog/refresh` | `api_skill_catalog_refresh()` rebuilds the catalogue; unlike write/run endpoints, it does not check the CSRF header. |
| POST | `/api/skills/run` | `api_skill_run(RunRequest)` admits `skill`, optional `model`, `effort`, `input`; returns a run record before background execution. |
| GET | `/api/skills/runs` | `api_skill_runs()` returns process-local runs newest first. |
| GET | `/api/metrics` | `api_metrics()` returns `timestamp`, `projects`, `infrastructure`, `activity`. |
| GET | `/api/metrics/history?window=1h` | `api_metrics_history()` accepts `1h`, `6h`, `24h`; invalid window returns 422. |
| GET | `/api/metrics/rates?window=1h` | `api_metrics_rates()` returns chart sections for the same windows; invalid window returns 400. |

All handlers in this table are defined in `app.py`; the handler names are the exact source citations.

## Subdirectories & System Boundaries

- `core/`: workspace readers and writers imported by `app.py` (interview editor, workspace content, agents, work search, calendar sources and service).
- `collectors/`: tailnet telemetry (`metrics`, `server_activity`, `metric_charts`), imported lazily by the Metrics endpoints.
- `scripts/`: standalone CLIs run by path (`triage_jev.py`, `leads_jev.py`, `screenshot.sh`); tests import them as `scripts.<name>`.
- `docs/`: one-off reports (`2026-11-12_DRIFT_REPORT.md`, historical `claude-usage.html`) and the [agent registry](./docs/agent-registry.md) reference.
- [Static component contract](./static/README.md): JavaScript controllers and browser asset boundary.
- [Templates](./templates/index.html): Jinja shell, [shared macros](./templates/_macros.html), [reader](./templates/reader.html), [prep sheet](./templates/interview_sheet.html), and tab partials in `templates/pages/`.
- [LaunchAgent configuration](./launchd/com.cloudtransition.dashboard.plist): starts `venv/bin/python -m uvicorn app:app` on `127.0.0.1:8000`; host-specific paths, drive-presence keepalive, and home-directory logs.
- `tests/`: existing verification suite; no production contract generated for test-only directories.

EGM scope retains this root and `static/`. Templates, launch configuration, and fonts have no source extensions recognized by bootstrap's directory filter. Hidden directories, symlinks, ignored output/cache directories, and the virtual environment are excluded. Existing guidance remains in `CLAUDE.md`; no agent instructions are replaced.

## Invariants

### Workspace records and edits

- Workspace location derives from the module path, not process working directory. Missing or nonmapping YAML yields `{}`; malformed YAML can raise. [app.py:WORKSPACE] [app.py:load_yaml]
- Task parsers preserve raw Markdown, source order, realm, and one-based line numbers. `select_next_up()` applies category lane ranking; `build_today_view()` supplies open task-realm items. [app.py:parse_tasks_from_file] [app.py:select_next_up] [app.py:build_today_view]
- Task, capture, interview, remember, and run POSTs require `X-Requested-With: XMLHttpRequest`. This header check is not user authentication. [app.py:toggle_task] [app.py:capture] [app.py:_csrf_ok] [app.py:brain_remember] [app.py:api_skill_run]
- Task/capture/interview writes hold the process-local `_FILE_WRITE_LOCK` and replace a sibling temporary file via `_atomic_write()`. This does not coordinate independent CLI writers. [app.py:_FILE_WRITE_LOCK] [app.py:_atomic_write] [app.py:_interview_write]
- A stale task line follows an exact unique text match; missing or ambiguous matches return 409. Routine edits are restricted to Weekly Review checkboxes. Capture collapses whitespace and accepts 1–300 characters. [app.py:toggle_task] [app.py:capture] [app.py:CAPTURE_MAX]
- Interview edits require an exact unique company/role pair. Status/priority use `STATUSES`/`PRIORITIES`; prose uses `TEXT_BLOCKS`, separate from structured `interview_prep` and hand-written `notes`. Editor functions reparse their output; they do not persist it. [core/interview_editor.py:_find] [core/interview_editor.py:STATUSES] [core/interview_editor.py:PRIORITIES] [core/interview_editor.py:set_text_block] [core/interview_editor.py:_validate]
- Closed applications remain historical rows but leave live counts and Today recommendations. [app.py:build_interview_view] [app.py:next_interview_action]
- Career's **Weekly work-search report** uses explicit completed-activity records, not application statuses, planned actions, or inferred timeline events. Choose an application to prefill employer and position, then enter the actual date, type, description, address, and contact result. Save one record per activity; **Edit activity** corrects the same UUID, and **New activity** starts another. Copy individual fields, one activity, or the week. Missing fields remain “Not recorded”; use “Not applicable” only when accurate. No claimant identity is stored, no government form is submitted, and recorded counts do not determine eligibility. `work_search.py` rewrites only its owned YAML section and preserves application prose and other sections.
- File APIs check workspace containment and privacy. Indexed content additionally rejects symlink components and requires current scope plus index membership, except recognized live artifacts. Active-document responses use sandbox CSP; some same-origin resources remain allowed. [app.py:api_file] [core/workspace_content.py:resolve_file] [core/workspace_content.py:file_headers] [core/workspace_content.py:NO_NETWORK_CSP]

### Runners and telemetry

- Model values split at the first colon. Admission revalidates the fresh provider catalogue, effort, card provider restrictions, and input pattern; shell cards reject model overrides. Catalogue availability does not establish authenticated entitlement. [app.py:_parse_model] [app.py:api_skill_run] [app.py:_fetch_skill_catalog]
- Duplicate admission and reservation share `_RUNS_LOCK`: one running job per skill, but different skills may run concurrently. Run tracking is process-local; output/log retention is separate from the 50-completed-record memory limit. [app.py:api_skill_run] [app.py:MAX_RUNS_KEPT]
- Commands use argv, workspace cwd, and a 1800-second execution deadline. Permission boundaries differ by provider: Claude tool allowlists and Codex sandboxes do not become equivalent OpenCode restrictions. `plan-today` asks for no edits but lacks `read_only=true`. [app.py:_resolve_run] [app.py:_execute_run] [app.py:SKILL_RUNNERS]
- Initial run-log failure prevents launch. Output writing and completion logging can fail outside execution error handling; a recorded start is not proof of successful completion. [app.py:api_skill_run] [app.py:_execute_run]
- Missing/nonfinite telemetry stays missing. Native Windows sources outrank compatibility sources; history keeps gaps and caps each metric at 150 points. Host-exporter loss does not prove host failure. [collectors/metrics.py:_rank] [collectors/metrics.py:collect_infrastructure_metrics] [collectors/metrics.py:collect_metric_history] [collectors/metrics.py:HISTORY_MAX_POINTS]
- Activity sections fail independently. Bounds per host include 100 containers/probes, 500 processes/services, eight recent log rows, and 800-character messages. cAdvisor health zero remains unknown. Redaction is pattern-based, not a universal secrecy guarantee. [collectors/server_activity.py:collect_server_activity] [collectors/server_activity.py:LIMITS] [collectors/server_activity.py:_container_health] [collectors/server_activity.py:redact]
- Jev triage files only at fit probability ≥0.7 and choice confidence ≥0.5. Lead scoring uses met ≥0.7, missing ≤0.3, thin otherwise. `--payload` makes no API call; `--dry-run` still sends data. Missing API keys currently produce exit 3 in both CLIs. [scripts/triage_jev.py:decide] [scripts/triage_jev.py:main] [scripts/leads_jev.py:classify] [scripts/leads_jev.py:main]

## Side Effects

- Import reads optional `.env` without overriding existing environment values. Content helpers load workspace index/catalog modules and maintain a process-local index cache. Never include credentials in documentation. [app.py:_load_env_file] [core/workspace_content.py:_load_module] [core/workspace_content.py:indexed_paths]
- Rendering reads workspace records and agent outputs. Catalogue warming starts a daemon thread; provider discovery reads local catalogues and can execute `which` and `opencode models --standalone`. [app.py:build_context] [core/agents.py:build_agents_view] [app.py:_warm_skill_catalog] [app.py:_resolve_executable] [app.py:_load_opencode_models]
- HTTP edits persist task Markdown and application YAML. Brain operations launch `second-brain/brain.py`; remember delegates durable memory writes to that CLI. [app.py:toggle_task] [app.py:capture] [app.py:_interview_write] [app.py:_brain]
- Runs append JSON events to workspace `runs.log`, execute local CLIs or OpenRouter HTTP requests, and write `runs/<id>.txt`. Model/API jobs may incur charges and transfer prompts or declared context. [app.py:_log_run] [app.py:_execute_run] [app.py:_run_openrouter] [app.py:_workspace_context]
- Jev requests POST to `https://api.typesafe.ai/v1/systemone`. Triage sends Inbox text and destination headings; lead review sends requirements and parsed résumé evidence with regex contact redaction. Triage writes `TASKS.md` directly after successful decisions; it does not use the server's atomic writer or lock. Lead review writes no files. [scripts/triage_jev.py:build_payload] [scripts/triage_jev.py:post_systemone] [scripts/triage_jev.py:main] [scripts/leads_jev.py:build_payload] [scripts/leads_jev.py:redact] [scripts/leads_jev.py:main]
- Collectors read Prometheus on Parrot port 9091, Loki port 3100, and local development health on ports 7071/8080. They do not configure remote services. Mission Control proxies loopback port 8787 and returns 502 offline HTML on upstream failure. [collectors/metrics.py:PARROT_PROMETHEUS] [collectors/metrics.py:PARROT_LOKI] [collectors/metrics.py:collect_salsatd_metrics] [app.py:MISSION_CONTROL_UPSTREAM] [app.py:proxy_mission_control]
- Screenshot helper probes port 8000, launches macOS Chrome through Node/DevTools pipes, writes `runs/shots/<tab>-<width>.png`, then removes its temporary profile. [scripts/screenshot.sh:writeFileSync] [scripts/screenshot.sh:finally]
- `docs/claude-usage.html` is a standalone historical page, not live provider quota telemetry. Its `nextReset()` uses browser-local 18:00; its `addEntry()` is scoped inside an IIFE despite an inline onclick reference. [docs/claude-usage.html:nextReset] [docs/claude-usage.html:addEntry]

## System Verification

Run from `dashboard-app/` using the existing virtual environment:

```sh
venv/bin/python -m pytest tests/ -q
```

For runtime changes, project guidance additionally requires `/` to return 200. A scratch server avoids restarting the always-on instance:

```sh
venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8011 --reload
```

Startup/rendering can warm catalogues; do not trigger runner buttons or Jev live modes merely to verify documentation. The documented test command is not a claim that live paid APIs were exercised.
