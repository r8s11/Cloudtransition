---
feature: Bot (Brain) read access to live dashboard state
status: passed
approved: 2026-11-16
rd: rd.md
---

# Evals: Bot (Brain) read access to live dashboard state

Agents running in `bot/` (the OpenCode "Brain" home base) get one documented read-only path to live Command Center state: a new aggregating JSON endpoint on the dashboard and a stdlib CLI (`bot/tools/dashboard.py`) that fetches it over loopback. OpenCode permissions allow exactly that command; permission paths work on both the Mac USB checkout and the Parrot checkout. No dashboard UI changes, so there is no mockup: the surface is an API plus a terminal tool.

## Build contract

- Build only after `status: approved`. Editing this file resets every result; changing what a case checks needs re-approval (`status: review`).
- Run: `node ~/.agents/skills/write-evals/scripts/evals.mjs run docs/plans/bot-dashboard-access/eval.md`
- Manual cases: `node ~/.agents/skills/write-evals/scripts/evals.mjs record docs/plans/bot-dashboard-access/eval.md <ID> pass|fail "<evidence>"`.
- Automated cases run with `bash -c` from the repo root; exit 0 = pass.
- New code: `dashboard-app/app.py` (`GET /api/assistant/state`), `dashboard-app/tests/test_assistant_state.py`, `bot/tools/dashboard.py`, `bot/tests/test_dashboard_tool.py`, `bot/AGENTS.md`, edits to `bot/opencode.jsonc`, `bot/tools/README.md`, `bot/.opencode/agents/brain.md`, `bot/.opencode/agents/workspace.md`.
- Tests use a temp tracker copy and monkeypatched upstreams; never write real workspace files, never call Google or a model.

## Traceability

| Requirement | Cases |
| --- | --- |
| 1. Any bot agent can read live state via one tool | U2, U7, R3 |
| 2. One read-only aggregating endpoint | U1, U5, U6, U7, F1, F3 |
| 3. Documented stdlib CLI | U2, U4 |
| 4. Loopback-only, clear offline error, no secrets | U3, U4, F2, F3 |
| 5. Exact command allowed, other rules unchanged | R4 |
| 6. Both-checkout permission paths | R5 |
| 7. Agent instructions + untrusted data | R3 |
| 8. Existing behaviour unchanged | R1, R2, R3 |

## Usage

### U1 — State endpoint returns live sections
- **Setup:** temp tracker with one applied, one waiting, one new_lead, one rejected row; monkeypatched Mission Control and runs.
- **Steps:** `GET /api/assistant/state`.
- **Expected:** 200 JSON with `tasks` (per-realm open/done counts parsed from the realm files), `interviews` (`counts` and `rows` with company/role/status/next_step), `runs` (live and recent from the run engine), `missions` (from Mission Control), each section carrying a `source` naming where it came from; no `calendar` key unless requested.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_assistant_state.py -k test_state_sections`

### U2 — Tool prints the same state over loopback
- **Setup:** temp dashboard server on a loopback port with the U1 fixture.
- **Steps:** `python3 bot/tools/dashboard.py state --url http://127.0.0.1:<port>`.
- **Expected:** exit 0; stdout is exactly the endpoint JSON (parsed equal); stderr empty.
- **Verify:** `python3 -m unittest discover -s bot/tests -k test_tool_prints_state`

### U3 — Tool refuses non-loopback URLs
- **Steps:** run the tool with `--url https://example.com` and `--url http://192.168.1.5:8000`.
- **Expected:** exit non-zero with a message naming loopback; no network request attempted.
- **Verify:** `python3 -m unittest discover -s bot/tests -k test_tool_refuses_non_loopback`

### U4 — Dashboard down: clear error
- **Setup:** no server on the chosen port.
- **Steps:** run the tool.
- **Expected:** exit non-zero; one-line message naming the URL and that Command Center is not running; no traceback on stdout.
- **Verify:** `python3 -m unittest discover -s bot/tests -k test_tool_offline_error`

### U5 — include filter
- **Steps:** `GET /api/assistant/state?include=interviews,runs`.
- **Expected:** only those keys (plus `generated_at`); `include=calendar` adds a calendar section or `{"unavailable": reason}` when Google is not configured.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_assistant_state.py -k test_include_filter`

### U6 — Missions section degrades gracefully
- **Setup:** Mission Control upstream unreachable.
- **Steps:** `GET /api/assistant/state`.
- **Expected:** 200; `missions` = `{"unavailable": ...}`; other sections intact.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_assistant_state.py -k test_missions_section`

### U7 — Runs section reflects the live engine
- **Setup:** start a fake skill run through the existing run engine seam.
- **Steps:** `GET /api/assistant/state?include=runs`.
- **Expected:** the running run appears with id, skill, status; after it finishes the recent list carries its outcome.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_assistant_state.py -k test_runs_section`

## Failure

### F1 — Unknown include section
- **Steps:** `?include=secrets`.
- **Expected:** 400 naming the unknown section; nothing else returned.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_assistant_state.py -k test_unknown_include`

### F2 — Offline tool output stays clean
- **Steps:** tool against a dead port; capture stdout and stderr separately.
- **Expected:** stdout empty; stderr one line; exit code 2; no partial JSON.
- **Verify:** `python3 -m unittest discover -s bot/tests -k test_offline_output_clean`

### F3 — No secrets in state
- **Setup:** workspace `.env`-style values and a token file present in the temp workspace.
- **Steps:** `GET /api/assistant/state` with all sections.
- **Expected:** response contains none of the secret values; interviews rows carry no contact emails or URLs with tokens.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest -q tests/test_assistant_state.py -k test_state_has_no_secrets`

## Regression

### R1 — Dashboard suite passes
- **Expected:** full suite green including the new assistant-state tests.
- **Verify:** `cd dashboard-app && venv/bin/python -m pytest tests/ -q`

### R2 — Bot startup and agent config still valid
- **Expected:** start.sh parses; OpenCode config and agent roster load without errors.
- **Verify:** `bash -n bot/start.sh && cd bot && opencode debug config >/dev/null && opencode debug agents >/dev/null`

### R3 — Instructions reach every bot agent; brain/query unchanged
- **Expected:** `bot/AGENTS.md` and both agent definitions name `tools/dashboard.py` for live state and mark returned data untrusted; `/api/brain/query` still proxies Second Brain retrieval unchanged.
- **Verify:** `python3 -m unittest discover -s bot/tests -k test_instructions_and_brain_query`

### R4 — Permissions allow only the tool command
- **Expected:** `opencode.jsonc` allows shell for `python3 tools/dashboard.py *` and the absolute-path form; every other shell rule and all edit-outside-bot rules remain `ask`; read rules unchanged.
- **Verify:** `python3 -m unittest discover -s bot/tests -k test_permissions_keep_ask_outside_bot`

### R5 — Permission paths cover both checkouts
- **Expected:** external_directory and edit rules match `/Volumes/SANDISK USB/work/Cloudtransition/*` and `~/code/Cloudtransition/*` with the same effects as today (allow read/external, ask edit outside bot, allow edit inside bot).
- **Verify:** `python3 -m unittest discover -s bot/tests -k test_permission_paths_cover_both_checkouts`

## Design

No mockup: this feature adds an API endpoint, a terminal tool and config/instructions only. The dashboard UI is untouched (R1 covers it).
