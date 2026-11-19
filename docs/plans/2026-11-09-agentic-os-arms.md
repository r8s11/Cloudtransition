# Agentic OS and ARMS plan (2026-11-09)

Sources: `ARMS-Agentic-OS-Guide.pdf` (v1: three levels per part plus the command centre) and `arms-agentic-os-v2-guide.pdf` (v2: twelve new levels). `agentic-os/` is the mission-control runtime (missions, approvals, supervised local agent runs). Most ARMS levels were already adapted at workspace level on 2026-10-28 (`docs/plans/2026-10-28-second-brain-arms.md`, `tools/arms/README.md`). This plan covers what fits inside `agentic-os/` itself, and maps every level to where it lives.

## Built in agentic-os on 2026-11-09

Authoritative behaviour: `agentic-os/README.md`, section "Usage and launch options".

| Feature | ARMS level | What it is | Boundary kept |
| --- | --- | --- | --- |
| Skill buttons | v1 Skills 3, v2 Skills 1 (self-triggered) | `GET /api/projects/:id/skills` lists `.claude/skills` of a registered repository. The launch form shows one button per skill; a button sets the prompt to `/name`. | Explicit execution: the button does not start a run; **Start run** does. |
| Model and effort pickers | v2 Skills 2 (model routing, manual half) | `POST /api/runs` takes `model` / `effort` from the adapter's own list (`claude`: haiku, sonnet, opus; low, medium, high). | HTTP still cannot pass an executable or a free-form flag: values outside the list are a 400. |
| Run cost view | v2 Routines 2 (know what each job costs) | The `claude` adapter now runs with `--output-format json`; tokens and cost land on the run (migration `003_run_usage.sql`). `GET /api/usage?days=7` and the **Usage · last 7 days** panel rank prompts by cost. | No scheduler and no automatic cap. Other adapters show as unmetered. |
| Artifacts panel | v1 command centre principle 4 | `GET /api/artifacts` and `/api/artifacts/file`; panel lists `agentic-os/artifacts/`, newest first. | Read-only, contained to the folder, HTML/SVG sandboxed to an opaque origin. |

Proof: `npx tsc -b` clean; `npx vitest run --typecheck` 128 tests pass (121 before). New endpoints smoke-tested on a throwaway database; dashboard loaded in a browser with no script errors.

Not verified: a live `claude --output-format json` run (it would spend usage). The parser reads `type: "result"`, `result`, `usage.*_tokens` and `total_cost_usd`; an unrecognised report degrades to raw stdout with empty usage. First real run: confirm the Usage panel shows a cost.

## Open, in order of value

1. **Verify the Claude report on one real run.** One cheap run (`/…` skill on `haiku`). If the field names differ, fix `claudeUsage` in `packages/runtime/src/adapters.ts`.
2. **Per-run budget.** The CLI has `--max-budget-usd`. Offer a fixed list (for example 0.25, 1, 5) the same way model and effort are offered. This is the honest version of "capped routines" without a scheduler.
3. **Artifacts written by runs.** Nothing tells an agent to save into `agentic-os/artifacts/`. Either a line in each skill ("save reports to …") or an environment variable the adapter sets. Decide when the first skill produces a report.
4. **Jev model router.** `packages/model-router` is an empty stub. Automatic routing needs `OPENROUTER_API_KEY`, sends prompts to a third party, and costs money per call: needs explicit approval. Workspace rule: read the `typesafe-ai` skill first. Until then the picker is the router.
5. **Scheduler / routines.** `routines/` is empty by design: the safety posture says "no scheduler". Workspace routines already run through `tools/arms/routines.py` and launchd. Bringing them into agentic-os changes that posture and is a decision for the owner, not a default.
6. **Lint.** `npm run lint` fails before any file is checked: ESLint 10 finds no `eslint.config.*`. Pre-existing; not touched.

## The twelve v2 levels: what changed today

The level-by-level status, with its boundaries and unmet prerequisites, is the table "All twelve levels" in `tools/arms/README.md`. It was not re-verified today. Only these rows moved:

| Level | Before | Now |
| --- | --- | --- |
| Skills 1, self-triggered | Zero-model refresh-report button only; the model button runner (`button-runner/`) is broken (see `tools/arms/README.md`). | Any skill of a registered repository runs headlessly from the agentic-os launch form. |
| Skills 2, routing | Code paths need no model; no automatic routing. | Manual choice of model and effort per run. Automatic Jev routing still off (open item 4). |
| Routines 2, cost limits | Usage unknown when unrecorded. | Runs started through agentic-os record reported tokens and cost; the Usage panel ranks prompts. No cap yet (open item 2). Runs started elsewhere (launchd jobs, terminal) stay unrecorded. |
| Memory 3, self-evolving | Note and calibrate skills park and apply feedback. | Plus `brain.py remember --supersedes`: a corrected memory demotes the one it replaces. |

v1 guide levels that are still not started: Routines 2 and 3 (an always-on second machine with Syncthing, or the agent in the cloud). Both need hardware or a hosting choice from the owner.

## Rerun

```bash
cd agentic-os
npx tsc -b && npx vitest run --typecheck
npx tsx apps/api/src/server.ts      # http://localhost:8787, Agent runs tab
```
