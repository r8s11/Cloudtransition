# Workspace map

Owner: Roosevelt Segura, an IT professional in a job-search transition who runs career, learning, code and operations alone from this one workspace.

Start with the relevant department below, follow its router to the source, and open only what the task needs. Existing folders stay in place. This is the canonical department map; `CLAUDE.md` points here.

| Department | Router | Work and destinations |
| --- | --- | --- |
| Operations | [OPERATIONS.md](OPERATIONS.md) | Tasks, weekly cadence, IT playbook, progress and reflections |
| Code | [CODE.md](CODE.md) | Applications, scripts, infrastructure and search tools |
| Career & money | [MONEY.md](MONEY.md) | Résumés, interviews, networking, freelance and finance |
| Learning | [LEARNING.md](LEARNING.md) | Study plans, degree track, books, certifications and skill inventory |
| Content & visuals | [CONTENT.md](CONTENT.md) | Artifacts, drafts, prompts, resources and image descriptions |
| Health | [HEALTH.md](HEALTH.md) | Health-related tasks; no dedicated collection yet |

## Memory and search

- [memory.md](memory.md) is the short memory index: one linked line per memory. Details live in [second-brain/memories/](second-brain/memories/), not in this map.
- For source-backed knowledge, run `python3 second-brain/brain.py query "question"`. It checks the catalogue before opening content; retrieval uses plain text and a deterministic keyword index, not embeddings or a vector database.
- Save durable memories with `remember` so the memory file and indexes stay synchronized. When a memory replaces an older one, add `--supersedes OLD-ID` instead of editing or deleting the old file. `query` rebuilds the index itself when the source it would answer from has changed; run `python3 second-brain/brain.py index` after adding or removing sources, then `python3 second-brain/brain.py check`. See [second-brain/README.md](second-brain/README.md).
- For code structure use the graph instructions below. If a department router cannot locate the source, use a scoped text search; do not start with a workspace-wide scan.

## Working rules

- Current state comes from [TASKS.md](TASKS.md), [DASHBOARD.md](DASHBOARD.md) and [routine.md](routine.md). Project-specific guidance stays with its project; read it before editing.
- Local review and passive reports: [tools/arms/](tools/arms/). HTML-first artifacts: [artifacts/](artifacts/). Feedback is parked, never silently applied.
- Never index or copy credentials, employer-private content or personal academic records into shared memory. Keep build-output/vendor assets out of the curated content index; record exclusions rather than claiming coverage.
- New images need adjacent Markdown containing the exact generation prompt, actual model, date and source references. Old images need a factual caption with its model/date; an unavailable original prompt is **unknown**, never invented. Follow [CONTENT.md](CONTENT.md).
- Do not send idle cache-keepalive pings.
- Any work that calls TypeSafe (Jev), writes its questions or state, or replaces an LLM prompt-and-parse step, keyword match or brittle heuristic with a typed question: read the `typesafe-ai` skill first (`~/.agents/skills/typesafe-ai/SKILL.md`). Live API tests need the user's permission and a budget, since they use `TYPESAFE_API_KEY` and send the data.
- When a referenced file or folder is created, moved, renamed, archived or removed, update its department router in the same change. New departments belong in this map.

## AI agents

Agent definitions and per-agent state. Read the definition before running or editing an agent; state lives under `workspace/agents/`.

- OpenCode definitions: [`.opencode/agents/`](.opencode/agents/) — Forge, Scout, Job Reader, CV Adapter, Gmail Reader, personal-growth-mentor, specialized-chief-of-staff, and the Impeccable subagents.
- Claude definitions: [`.claude/agents/`](.claude/agents/) — Gmail Reader, personal-growth-mentor, specialized-chief-of-staff, and the Impeccable subagents.
- Codex definitions: [`.codex/agents/`](.codex/agents/) — personal-growth-mentor, specialized-chief-of-staff.
- Job-hunting team state: [workspace/agents/](workspace/agents/) (`forge/`, `scout/`, `job-reader/`, `cv-adapter/` outputs and memory). See [workspace/agents/README.md](workspace/agents/README.md).
- Personal Growth Mentor state: [workspace/agents/personal-growth-mentor/](workspace/agents/personal-growth-mentor/), independent of the job-hunting pipeline.
- Dashboard copies and runners: [dashboard-app/.opencode/agents/](dashboard-app/.opencode/agents/), [dashboard-app/.claude/agents/](dashboard-app/.claude/agents/), [dashboard-app/.github/agents/](dashboard-app/.github/agents/).

OpenCode agent files:

| Agent | Definition | State |
| --- | --- | --- |
| Forge | [`.opencode/agents/forge.md`](.opencode/agents/forge.md) | [`workspace/agents/forge/`](workspace/agents/forge/) |
| Scout | [`.opencode/agents/scout.md`](.opencode/agents/scout.md) | [`workspace/agents/scout/`](workspace/agents/scout/) |
| Job Reader | [`.opencode/agents/job-reader.md`](.opencode/agents/job-reader.md) | [`workspace/agents/job-reader/`](workspace/agents/job-reader/) |
| CV Adapter | [`.opencode/agents/cv-adapter.md`](.opencode/agents/cv-adapter.md) | [`workspace/agents/cv-adapter/`](workspace/agents/cv-adapter/) |
| Gmail Reader | [`.opencode/agents/gmail-reader.md`](.opencode/agents/gmail-reader.md) | — (read-only; answers from `kb.sqlite`) |
| personal-growth-mentor | [`.opencode/agents/personal-growth-mentor.md`](.opencode/agents/personal-growth-mentor.md) | [`workspace/agents/personal-growth-mentor/`](workspace/agents/personal-growth-mentor/) |
| specialized-chief-of-staff | [`.opencode/agents/specialized-chief-of-staff.md`](.opencode/agents/specialized-chief-of-staff.md) | — |
| impeccable-asset-producer | [`.opencode/agents/impeccable-asset-producer.md`](.opencode/agents/impeccable-asset-producer.md) | — |
| impeccable-documenter | [`.opencode/agents/impeccable-documenter.md`](.opencode/agents/impeccable-documenter.md) | — |
| impeccable-finish-reviewer | [`.opencode/agents/impeccable-finish-reviewer.md`](.opencode/agents/impeccable-finish-reviewer.md) | — |
| impeccable-manual-edit-applier | [`.opencode/agents/impeccable-manual-edit-applier.md`](.opencode/agents/impeccable-manual-edit-applier.md) | — |

## Compaction handoff

- Keep the active goal, scope, constraints, acceptance criteria and unfinished user requests.
- Keep decisions with reasons, rejected approaches, approvals and their limits; do not reopen settled choices without new evidence.
- Keep changed files and authoritative sources as paths and sections, not copied documents.
- Keep approved templates and prompts by saved path/version and required substitutions. Save unsaved exact text before compaction; do not reconstruct it from a paraphrase.
- Keep verification commands/results, known failures, blockers and ordered next actions. Distinguish observed facts from assumptions.
- Keep live jobs/tool handles and completed setup. Check that retained state is still live; do not repeat successful setup merely because the chat compacted.
- Drop duplicate logs, resolved troubleshooting and unrelated history. Load linked details only when needed; never copy secrets or private records into shared handoffs.

<!-- trail:start -->
## Trail — repo context graph

This repo is indexed in `.trail/cache/`: small linked markdown nodes that explain each
system and carry exact file:line spans, kept in sync with the code through git.

For ANY task here — understanding how something works, finding where code lives,
or scoping a change — get context from the graph before grepping or opening
source files. Re-ask freely (it's cheap) and reuse literal identifiers you
already have (symbol, error string, file name) as the query. New to this repo?
Run `trail map` first — a token-budgeted orientation (dir clusters, hubs,
hotspots), no LLM, no key.

- Run `trail ask "<your question>" --source` → ranked nodes with the relevant
  code spans inlined (each hit's ≤8-line crux by default; `--full` for whole
  definitions when the crux isn't enough). Match the tool to the task shape:
  for understanding or editing, the top node IS the answer — cite its
  `covers:` file:line spans and edit straight from `--source`. For
  exhaustive tasks ("every occurrence / every caller of this pattern"), ranked
  results are top-N, not complete — run `trail grep "<literal>"` instead
  (exhaustive over indexed files, grouped by enclosing symbol), falling back
  to raw `grep -rn` only for unindexed files.
- `trail skeleton <file>` → every definition's signature + span, ~10× cheaper
  than reading the file; use it to skim an API surface.
- `trail callers <symbol>` gives precomputed, exact edges — who calls this.
  Add `--direction out` for what it calls, or `--depth N` to walk
  transitively for the full blast radius. For structural questions, skip
  ranking and use this directly.
- Or browse: `.trail/cache/INDEX.md` lists every node; follow the links.
- Monorepos and folders of multiple repos rank fairly across sub-projects —
  hits carry `[scope/]` labels naming which one they're from. Narrow with
  `trail ask "<task>" --in <scope>/` once you know where you're working.

If a returned span is truncated ("+N more lines"), open the file at that exact
range before finalizing. Only open source files when a node genuinely lacks a
needed detail, and then at the exact file:line the node points to — never
re-read whole files.

After big code changes, refresh the graph with `trail build` (deterministic,
no API key, $0).
<!-- trail:end -->
