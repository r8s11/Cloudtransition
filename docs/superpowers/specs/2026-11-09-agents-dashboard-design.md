# Agents in the dashboard — design

_Status: approved · 2026-11-09 · scope chosen by Roosevelt: “Agents tab + free scan”_

## Intent

The Forge job-hunting team now exists as four OpenCode agents with on-disk
memory and one real Scout scan. The web dashboard is the operational surface
for the workspace, so the team should be visible there and the free search pass
should be startable there. Paid promotion stays out of this slice.

## Goals

- An **Agents** tab in `dashboard-app` that shows the team, each agent's role
  boundary and memory summary, recent run events, and the latest Scout scan.
- The latest scan rendered as a ranked jobs table with the posted facts
  (score, title, company, location, salary, source, URL) and links to the full
  JSON and Markdown outputs.
- One **Run Scout scan** button on the tab, with an OpenCode free-model picker,
  using the existing run log, output file, CSRF guard, single-flight rule and
  30-minute deadline.
- Missing files, malformed JSONL, and absent scans render as explicit empty
  states — never as invented data.

## Non-goals

- Job Reader, CV Adapter, promotion, CV library, source settings, scheduled
  scans, or any paid work.
- Editing agent definitions or agent memory from the dashboard.
- Replacing the existing Mission Control tab (that is the agentic-os embed).
- Adding the scan results to `interviews/job-applications.yml` or changing the
  job tracker.

## Anti-goals

- Fabricating a job, score, salary, status or timestamp.
- Running a scan on page load, in the background, or more than once at a time.
- Hiding a failed or denied run behind a success state.
- Copying job descriptions or CV content into dashboard state.

## Constraints

- The workspace files are the database; the tab reads them on each page load.
- Only the existing `/api/skills/run` write path is used for the button.
- No new listener, database, build step, or JavaScript framework.
- Privacy rules in `workspace_content.privacy_violation()` still apply to any
  file link.
- The run path keeps its “argv, no shell, no interactive prompts, no bypass
  flags” invariant.

## Approaches considered

1. **Server-rendered tab + existing runner (chosen).** `build_context()` reads
   the agent files, memory, logs and latest scan; a new `opencode-agent` runner
   kind launches `opencode run --agent scout -m <picked model>`. One page load,
   no client state, reuses the run log, model picker and output dialog.
2. **Client-side fetch of a new `/api/agents` endpoint.** More moving parts for
   data that changes only when a scan finishes. Rejected.
3. **Hardcoded shell card with `opencode run --agent scout` in `argv`.**
   Duplicates executable resolution and bypasses the model/provider boundary.
   Rejected.
4. **Embed an agent UI or reuse Mission Control.** The agentic-os embed is a
   different system and shows none of this team's files. Rejected.

## Design

### Data loader

New module `dashboard-app/agents.py`:

- `load_roster()` — read `.opencode/agents/*.md`, parse the YAML frontmatter
  (`description`, `mode`) and the agent name from the file's `Your name is X`
  line (fallback: filename title). Order: Forge, Scout, Job Reader, CV Adapter;
  unknown files appended.
- `load_memory(slug)` — read `workspace/agents/<slug>/memory/index.md` as text;
  read the last N valid JSON objects from `log.jsonl`.
- `load_latest_scan()` — newest `workspace/agents/scout/outputs/scan-*.json`
  whose `jobs` is a list; return its `scan_id`, `generated_at`, counts and jobs
  sorted by score descending. Never synthesise a missing field.
- `build_agents_view()` — assemble `agents`, `agent_scan`, `agent_scan_files`,
  `agent_events`, and an `agent_scan_error` for a malformed/absent scan.
- `build_context()` adds `**build_agents_view()`.

The loader has no writes and no network. It tolerates missing directories,
unreadable files, bad JSONL lines and a bad scan file by returning an empty or
error value.

### Template

New `templates/pages/agents.html`:

- Page wrapper `id="page-agents"`, labelled by `tab-agents`.
- Header: “Agents — Forge job-hunting team”.
- Roster cards: name, mode, description, memory summary, last events.
- Scan card: generated timestamp, counts, source report, full JSON/Markdown
  links, and a table of all scored jobs. Table scrolls horizontally on phone.
- Run card: `data-run-grid data-skills="scout-scan"`, so `app.js` renders the
  existing button, status, model picker and output dialog.
- Empty states for “no scan yet”, “scan unreadable”, and “no memory recorded”.

Add `("agents", "Agents")` to the nav after Interviews, and the include in
`index.html`.

### Runner

- Add `scout-scan` to `SKILL_RUNNERS`:
  - `kind: "opencode-agent"`, `agent: "scout"`, `options: True`,
    `providers: ["opencode"]`.
  - Prompt tells Scout to read its memory, run a free search-and-rank pass with
    the configured sources, write `scan-<date>.json` and `.md` under its
    `outputs/`, update its memory, read no full job descriptions, and report
    counts plus top matches.
  - `read_only: False`; the agent's own edit permission limits writes to its
    directory.
- `_resolve_run()` gains the kind: resolve the OpenCode executable with the
  existing `_resolve_opencode_exe()`, then build
  `[exe, "run", "--standalone", "--agent", agent, "-m", model_id, prompt]`.
  No `--auto`, no shell. Missing executable returns the existing `kind:
  "error"` result.
- Model: the card uses the same model/effort picker as the other option cards,
  limited to OpenCode's free catalogue. `_skill_catalog_payload()` carries the
  existing `_load_opencode_models()` list plus a new `providers: ["opencode"]`
  field; `app.js` hides the Claude/Codex/OpenRouter choices for a card with
  `providers` and selects the first allowed model by default. “Free” therefore
  means a free OpenCode model and no paid promotion step. The picker offers only
  free OpenCode models, and `/api/skills/run` rejects a non-OpenCode provider;
  it does not independently re-validate that a hand-crafted `opencode:<id>` is
  free.
- Add `scout-scan` to the Run tab's “Other workspace tools” grid as well.

### Verification

- `tests/test_agents.py`: roster parse (known four, unknown file, missing
  frontmatter), memory parse (missing file, malformed JSONL), scan parse
  (sorted, missing/invalid file, missing fields), and `build_context()` keys.
- `tests/test_agents_runner.py`: `scout-scan` is in the catalogue with
  `providers: ["opencode"]`; `_resolve_run` builds `--agent scout -m <model>`
  with no shell and no `--auto`; a non-OpenCode model is rejected; missing
  executable yields the error spec; the run endpoint still rejects a second
  in-flight scan and a missing CSRF header.
- `tests/test_design_contracts.py`: keep the new tab's wrapper and table
  inside the existing contrast/layout rules.
- Manual: `/` and `/#agents` return 200; screenshot at 390px and 1280px; no
  horizontal page overflow; scan table scrolls inside its card.
- `dashboard-app/CLAUDE.md`: add the new module, template, tab, runner kind and
  data source.

## Risks and open items

- Headless OpenCode may deny a tool the scan needs. The run will fail visibly;
  this design does not add a bypass flag. If that happens, the fix is an
  explicit agent permission rule, not `--auto`.
- A scan can take close to the 30-minute deadline. The existing run record
  already reports timeout, failure and output path.
- The scan's freshness is whatever its `generated_at` says; the page must show
  that timestamp rather than “today”.
- The tab shows jobs that are not in `interviews/job-applications.yml`; it does
  not imply they were applied to.

## Builder calls (settled)

- New module rather than growing `app.py` further.
- All jobs in one table, not a top-N plus a second view; the table is the
  source, the report links are the escape hatch.
- The scan card gets a model picker, but only over OpenCode's free models;
  other cards keep their current provider choices.
- No Reader deep-link work; full outputs open through `/api/file`.
