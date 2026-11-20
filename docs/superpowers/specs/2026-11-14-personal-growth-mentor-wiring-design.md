# Personal Growth Mentor wiring — design

_Status: approved · 2026-11-14 · scope chosen by Roosevelt: “2 and 3”, option B_

## Intent

The `personal-growth-mentor` agent already has OpenCode/Claude/Codex definitions
and a skill, but no durable state and no dashboard entry point. Wire it like the
Forge team: on-disk memory under `workspace/agents/`, a roster entry on the
Agents tab, and one OpenCode run card that starts a mentor check-in.

## Goals

- Durable mentor memory: `workspace/agents/personal-growth-mentor/memory/`
  (`index.md`, `log.jsonl`), documented in `workspace/agents/README.md` and
  `AGENTS.md`.
- Agents tab shows Personal Growth Mentor with description, memory summary and
  recent events, after the four job-hunting agents.
- One **Mentor check-in** card on the Agents tab using the existing
  `opencode-agent` runner path, free OpenCode models only, one text input for
  the goal or situation.
- Mentor runs read their own memory first, answer with diagnosis + next action,
  then update only their own memory files.

## Non-goals

- Forge/orchestrator routing to the mentor.
- A general redesign of the Agents tab or new mentor outputs directory.
- Scheduling, automatic check-ins, new UI frameworks, new API endpoints.
- Editing agent definitions or other workspace files from the mentor run.

## Approaches considered

1. **Roster + run card on the existing Agents tab (chosen).** Reuses
   `agents.py`, the roster cards, `SKILL_RUNNERS`, `/api/skills/run`, CSRF,
   single-flight, output log. Smallest change that makes state and runtime real.
2. **Roster visibility only.** Less code, but no way to start a mentor run from
   the dashboard; rejected because Roosevelt picked option B.
3. **Separate mentor page or generalized agent dashboard.** Cleaner separation
   from the job-hunting team, but a larger refactor for one new card; rejected.

## Design

### State and routers

- Create `workspace/agents/personal-growth-mentor/memory/index.md` with the same
  shape as the other agents: title, `_Last updated: 2026-11-14_`, pointer to
  `log.jsonl`, empty starting sections for current focus, commitments and run
  history. No invented goals or commitments.
- Create an empty `workspace/agents/personal-growth-mentor/memory/log.jsonl`.
- `workspace/agents/README.md`: add the mentor to the table and state that it is
  independent of the Forge job-hunting pipeline; outputs column `—` because
  mentor answers stay in the run output and durable notes stay in memory.
- `AGENTS.md`: point the `personal-growth-mentor` state cell at
  `workspace/agents/personal-growth-mentor/` and mention it in the state list.

### Dashboard roster

`dashboard-app/agents.py`:

- Add `"personal-growth-mentor"` to `ROSTER_ORDER` after `cv-adapter`.
- Add `AGENT_LABELS["personal-growth-mentor"] = "Personal Growth Mentor"` so the
  existing name fallback works (its definition has no `Your name is …` line).
- No loader changes: `load_roster()` and `load_memory()` already read the
  definition and the new memory files, including empty/missing states.

### Run card

`dashboard-app/app.py`, new `SKILL_RUNNERS["mentor-checkin"]`:

- `label`: "Mentor check-in"; `icon`: "🌱" if the existing icon rendering
  accepts it, otherwise a text symbol consistent with the other cards.
- `kind`: `"opencode-agent"`; `agent`: `"personal-growth-mentor"`;
  `options`: `True`; `providers`: `["opencode"]`; `read_only`: `False`.
- `input_label`: "Goal or situation"; `input_type`: `"text"`;
  `input_pattern`: `r"^.{3,1000}$"` (required, bounded free text; the current
  runner input is a single-line field).
- Prompt: include `{today}` and `{input}`; instruct the mentor to read its own
  `memory/index.md` and `memory/log.jsonl` first, read only relevant workspace
  context, diagnose the real goal and bottleneck, give one concrete next action
  and accountability checkpoint, update `index.md`, append one JSON event to
  `log.jsonl`, never invent facts/commitments, stay inside professional
  boundaries, and write no files outside its own memory directory.

`dashboard-app/templates/pages/agents.html`:

- Keep the Scout scan card and Scout runner unchanged.
- Add a separate “Mentor check-in” card with a short blurb and
  `data-run-grid data-skills="mentor-checkin"`, so `app.js` renders the existing
  input, model/effort picker, Run button, status and output dialog.

### Tests

- `tests/test_agents.py`: mentor definition without `Your name is …` gets the
  label and sorts after `cv-adapter`; existing missing/empty memory behavior is
  unchanged.
- `tests/test_agents_runner.py`: card config is OpenCode-only and targets
  `personal-growth-mentor`; `_resolve_run()` builds
  `opencode run --standalone --agent personal-growth-mentor -m <model> …`;
  missing/invalid input is rejected; a non-OpenCode model is rejected.

### Docs and verification

- Update `dashboard-app/CLAUDE.md` Agents tab/source notes for the mentor state
  and runner.
- Run `venv/bin/python -m pytest tests/ -q` and
  `venv/bin/python -c "import app; print('import OK')"` from `dashboard-app`.
- Restart the dashboard with the documented `launchctl kickstart` command and
  check `/` returns 200; no live paid model call is part of verification.

## Builder calls

- One single-line goal/situation input, not a new textarea UI: it reuses the
  validated runner input path and keeps this slice small.
- Mentor answers are not written to a new `outputs/` directory; the run output
  remains in `dashboard-app/runs/`, durable state in the mentor memory files.
- The Agents page keeps its current job-hunting scan sections; only the roster
  and one new run card change.
