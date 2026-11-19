# Agentic OS — Mission Foundation and Agent Runtime

A TypeScript workspace implementing the core language of an agentic operating system:
missions, plans, persistence (SQLite), policy evaluation, approvals, and local coding-agent supervision.

## Setup

```bash
npm install
npm run test
npm run build
npm run check
```

Requires Node.js >= 22.17.0 (uses the built-in `node:sqlite` module). This workspace
uses npm workspaces (no pnpm).

## Safety posture

- **Local control plane.** Persistence is SQLite; the API binds to `127.0.0.1`.
  Supervised coding agents may contact their configured external providers.
- **Explicit execution.** Users start and control runs; there is no scheduler or
  autonomous multi-agent orchestration.
- **Agent-neutral.** Provider SDKs are not embedded; adapters launch installed CLIs.
- **Core is infrastructure-agnostic.** `packages/core` has no dependency on storage,
  policy, CLI, API, connectors, runtime, or models. Domain rules live only there.

## Phase 1 — Mission Foundation

Core domain model with Zod schemas, mission lifecycle transitions, and plan validation.

- `packages/core` — missions, plans, Zod schemas, transition matrix, plan validation.

## Phase 2 — Persistence + Policy Foundation

A mission can be created, persisted, retrieved, transitioned safely, audited, and
subjected to explicit policy checks.

### packages/storage

Local SQLite persistence via the built-in `node:sqlite` module (no ORM).

- `Database` — opens/applies migrations, tracks applied migrations by name + hash.
- `SqliteMissionRepository` — create / getById / update / list missions.
- `SqlitePlanRepository` — save (validated via Core `parsePlan`) / getLatest plans.
- `SqliteTransitionRepository` — records every persisted status change (audit).
- `SqliteApprovalRepository` — create / get / list / resolve approval requests.

Migrations live in `src/migrations/` (mirrored inline in `migrations.ts`); the `migrations`
table records each applied migration so reopening never re-runs it. Plans are stored
as validated JSON; missions store `acceptance_criteria` as JSON.

### packages/policy

Small, centralized policy engine.

- `evaluatePolicy(config, request)` → `"allow" | "deny" | "require_approval"`.
- Resolution order: exact `capability.action` rule → `capability.*` wildcard → default.
- Default decision for unknown capabilities: **`require_approval`** (safe fallback).

### packages/config

Dependency-free configuration loader. Reads `config/agentic-os.yaml` (a small YAML
subset) and validates it against a Zod schema. Holds `database.provider/path` and the
`policy` rules.

### apps/cli

`agent-os` CLI (real functionality in Phase 2). Uses Core + storage + config; never
re-implements transition logic or SQL.

```bash
node apps/cli/src/cli.ts mission create \
  --title "Improve event search" \
  --objective "Add searchable event filtering" \
  --acceptance "Users can search events by title" \
  --acceptance "Results paginate"

node apps/cli/src/cli.ts mission list
node apps/cli/src/cli.ts mission show <id>
node apps/cli/src/cli.ts mission transition <id> running --reason "Plan accepted"
```

Illegal transitions call Core validation and do **not** modify the database.

### apps/api

Mission Control HTTP server + dashboard (read/write).

```bash
# seed a mission via the CLI, then open the dashboard
npx tsx apps/api/src/server.ts
# → http://localhost:8787  (PORT env var overrides)
```

Always on (macOS): `launchd/com.cloudtransition.mission-control.plist` keeps
this server running while the drive is mounted; install, restart and remove
commands are in its header. Start the server from `agentic-os/`, never from
`apps/api/`: the database path in `config/agentic-os.yaml` is relative to the
working directory, and `apps/api/.agentic-os/os.db` is a different, empty file.

Endpoints under `/api/`: `GET/POST /api/missions`, `GET /api/missions/:id`,
`GET /api/missions/:id/plan`, `GET /api/missions/:id/history`,
`POST /api/missions/:id/transition`, `GET/POST /api/approvals`,
`POST /api/approvals/:id/resolve`, `GET /api/transitions`.
All writes go through the same Core validation as the CLI. The dashboard has two
workspaces:

- **Missions:** status lanes, open/all/terminal-status filters, approvals queue
  (approve/reject), mission inspection (criteria, latest plan, history, legal
  transitions), and an inline new-mission form.
- **Agent runs:** repository registration, installed CLI detection, an explicit
  prompt-driven launch form with optional mission/plan/task references, active
  and historical run filters, pagination, captured stdout/stderr and lifecycle
  events, output-follow control, and confirmed interrupt/terminate actions.
  The launch form also offers **skill buttons** (one per skill in the chosen
  repository's `.claude/skills`; a button fills the prompt with `/name`, and
  nothing starts until **Start run**), and **Model** / **Effort** pickers when
  the chosen agent offers them. Below the run list: **Usage · last 7 days**
  (prompts ranked by reported cost, then tokens) and **Artifacts** (files in
  `artifacts/`, newest first, opening in a new tab).

Data refreshes every five seconds while the page is visible. Refresh preserves
drafts, selection, keyboard focus, and paused output scroll position. Workspace
changes progressively enhance with View Transitions; selection reveals the
inspector and brings it into view on narrow screens. Reduced-motion preferences
disable animation; browsers without View Transitions update immediately.

The dark Control Room design remains local and dependency-free. No demonstration
data is embedded. See `PRODUCT.md`, `DESIGN.md`, and the surface brief under
`apps/api/.impeccable/surfaces/` for the product and design contracts.

The server reads the dashboard HTML at startup. Restart the API process after
editing `apps/api/www/index.html`; a browser reload alone cannot replace a
running server's cached HTML.

## Mission Control Phase 1 — Agent Runtime

`packages/runtime` supervises local coding-agent processes. `packages/storage`
persists canonical Git repositories as projects, runs, and ordered events in the
existing database through additive migration `002_agent_runtime.sql`. The dashboard
exposes this runtime without introducing a competing mission/task model.

### Start and control a run

Requires macOS or Linux, Git, Node.js >= 22.17.0, and an installed/authenticated
`claude` or `codex` executable on the server's `PATH`. Agent availability means
the executable responds to `--version`, not that its provider credentials work.
The defaults launch
`claude --print --output-format json [--model M] [--effort E] -- <prompt>` or
`codex exec -- <prompt>` with closed stdin and separate stdout/stderr pipes.
Claude writes one JSON report when it exits; the runtime stores that report's
answer as the run's stdout and its token counts and cost on the run (see
[Usage and launch options](#usage-and-launch-options)).
Interactive terminal/PTY sessions are not supported in this phase.

From this workspace:

```bash
npx tsx apps/api/src/server.ts

curl http://127.0.0.1:8787/api/agents
curl -H 'Content-Type: application/json' \
  -d '{"path":"/absolute/path/to/repository","name":"My repository"}' \
  http://127.0.0.1:8787/api/projects

# Use the returned project ID:
curl -H 'Content-Type: application/json' \
  -d '{"projectId":"<project-id>","adapterId":"claude","prompt":"Review the repository and summarize its architecture."}' \
  http://127.0.0.1:8787/api/runs

# Use the returned internal run ID:
curl 'http://127.0.0.1:8787/api/runs?active=true'
curl 'http://127.0.0.1:8787/api/runs?active=false'
curl 'http://127.0.0.1:8787/api/runs/<run-id>/events?after=0&limit=100'
curl -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8787/api/runs/<run-id>/interrupt
curl -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8787/api/runs/<run-id>/terminate
```

| Endpoint | Purpose |
| --- | --- |
| `GET/POST /api/projects` | List/register repositories; subdirectories and symlinks resolve to the same Git root |
| `GET /api/projects/:id/skills` | List skills (`name`, `description`) in that repository's `.claude/skills` |
| `GET /api/agents` | Detect installed supported adapters, with the `models` and `efforts` each one offers |
| `GET /api/usage?days=7` | Runs of the last 1–90 days grouped by prompt and adapter, most expensive first |
| `GET /api/artifacts` | Files under `artifacts/` (path, size, modified time), newest first, at most 200 |
| `GET /api/artifacts/file?path=…` | One listed artifact; 404 for anything outside the folder |
| `GET/POST /api/runs` | List/start runs |
| `GET /api/runs/:id` | Read persisted metadata and lifecycle state |
| `GET /api/runs/:id/events` | Read ordered `state`, `stdout`, and `stderr` events |
| `POST /api/runs/:id/interrupt` | Send SIGINT to the live process group |
| `POST /api/runs/:id/terminate` | Send SIGTERM, escalating to SIGKILL after three seconds |

Run listing accepts `projectId`, `active=true|false`, `limit` (1–1000, default 100),
and `offset`. Omit `active` for both active and historical runs. Events use an
exclusive `after` event-ID cursor and the same limit bounds. Output is stored in
chunks, not necessarily lines; concatenate chunks by stream to reconstruct it.

Start accepts optional `missionId`, `planVersion`, and `taskId`. A task reference
requires its mission and an existing plan version and is validated against the
authoritative Core plan. Runs retain that version even when a new plan is saved.
Finishing a process never automatically advances its mission or task.

### Usage and launch options

`POST /api/runs` accepts optional `model` and `effort`. Each must be a value the
chosen adapter lists in `GET /api/agents` (`claude`: `haiku`, `sonnet`, `opus`
and `low`, `medium`, `high`; `codex`: none); anything else is rejected with 400
before a run is created. The value becomes one fixed flag argument, so HTTP
still cannot supply an executable or a free-form flag. Both are stored on the
run, `null` meaning the agent's own default.

A run carries `inputTokens`, `outputTokens` and `costUsd` when its adapter
reports usage, otherwise `null` ("unmetered" in the dashboard). Input tokens
include cache writes and cache reads. `costUsd` is the CLI's own
API-price figure; on a subscription it is an equivalent, not a charge. For
such an adapter stdout is held until the process exits (up to 8 MB, then stored
as it arrives): a well-formed report is replaced by its answer text; anything
else — an interrupted run, an error message — is stored unchanged with usage
left empty. Stderr is always stored as it arrives.

To run a skill, start a run whose prompt is `/skill-name` in a repository that
holds the skill. There is no scheduler and no caps: the usage view shows which
prompt costs most; lowering it means choosing a smaller model or effort.

Artifacts are any files saved under `agentic-os/artifacts/` (four folder levels
deep; dot files and symbolic links are skipped; 20 MB per file). HTML and SVG
are served with `Content-Security-Policy: sandbox allow-scripts`, which gives
the page an opaque origin: its scripts run, but the runtime API rejects its
requests. Unknown file types download instead of rendering.

### Lifecycle and recovery

- `starting` is persisted before spawn; `running` means the OS spawned the process,
  not that authentication or an agent task succeeded.
- Natural exit becomes `completed` (exit code 0) or `failed`. Spawn and stream
  errors are recorded. Terminal state is persisted only after captured pipes close.
- Interrupt and terminate requests first become `interrupting` / `terminating`;
  observed exit becomes `interrupted` / `terminated`. An ignored SIGINT leaves the
  run active; use terminate to escalate. Requests for terminal runs are idempotent.
- The API owns one supervisor lease per database. Graceful server shutdown
  terminates its live runs before closing SQLite. Child processes must remain in
  their process group for descendant cleanup; deliberately detached daemons are
  outside this supervision contract.
- After an abrupt supervisor exit, unfinished runs become `lost` on startup.
  Metadata and already-captured output remain available. Surviving processes
  are **not reattached or signalled using old PIDs**: PID reuse makes that unsafe.
  Inspect and clean up any survivors manually; their exit status is unknown.

### Safety and extension boundary

The runtime API is for trusted local users. It rejects non-loopback Host headers,
cross-origin access, and non-JSON mutations; it is not an authenticated multi-user
service and must not be exposed through a public proxy. Prompts and captured
output are plaintext in SQLite and may contain sensitive data. Protect the
database and its backups; automatic log retention is not implemented.

Agents inherit the server user's environment, credentials, filesystem permissions,
and their own CLI configuration. The adapters do not add permission/sandbox bypass
flags. Core policy/approval records do **not** sandbox agent tool execution.
Only register repositories and request actions you trust.

`AgentAdapter` separates detection, process creation, interruption, and termination
from supervision. `CommandAgentAdapter` can be configured by trusted host code;
HTTP cannot supply arbitrary executables or command-line flags. New adapters
must create a process-group leader, return its live `ChildProcess` immediately,
and expose piped stdout/stderr. An adapter may name the `models` and `efforts`
it offers and a `usage` parser for its exit report; `claudeUsage` is the only
provider-specific parsing. No tool-call normalization is claimed: events cover
process state and output only. The Claude report format was not exercised
against a live paid run when this was written; an unrecognised report degrades
to raw stdout with empty usage.

## Mission Control Hub — supervised shared sessions

`packages/hub` turns one Mission into a supervised shared session: a durable
mailbox of handoffs, a code-routed orchestrator, durable subscriptions to run
completion and new messages, and a Session tab in the dashboard. Design and
acceptance cases: [`docs/plans/mission-control-hub/`](../docs/plans/mission-control-hub/).

- **Mailbox.** Every handoff carries `mission_id`, `task_id`, `in_reply_to`,
  `from`, `to`, `type`, `objective`, `done_when`, `input_refs`, `output_refs`,
  `result`, `evidence`, `decisions`, `blockers`, `approval_needed`. Writes are
  loopback-only and idempotent by key. Routing follows the coordinator tree in
  `config/agentic-os.yaml` (`hub.agents`); specialist-to-specialist messages need
  an explicit `dependsOn` task relationship; broadcasts are refused. Message
  content is data: it cannot grant permissions or redirect work.
- **Orchestrator.** Leases one task at a time per Mission, enforces the model-call
  budget (`hub.budget`, default 10) and delegation depth (`hub.maxDepth`, default 3),
  and completes a Mission only after every acceptance criterion is checked against
  named evidence. A process exit alone never completes a task. Paid models create
  an approval and wait; free OpenCode models run by default.
- **Workers.** The `opencode` adapter launches one named agent from the registry.
  A worker finishes with one fenced ` ```handoff ` JSON block; the orchestrator
  validates evidence paths and guard snapshots (no writes to another agent's
  private memory or unowned outputs; a git commit during a run becomes a blocker).
- **Session tab.** Objective, phase and owner, completed handoffs with artifact
  links (`/api/hub/file`, restricted to registry output dirs), waiting-for-you
  items, run states, token/cost totals, Pause mission and Stop all runs. Routine
  inter-agent messages stay inside a collapsed audit view.
- **Tailnet.** Command Center's proxy stays read-only except `POST …/pause` and
  `POST /api/hub/stop-runs`; approvals and mailbox writes remain Mac-only.
- **Recovery.** After an abrupt supervisor exit, lost runs interrupt their tasks
  and pause the Mission; accepted handoffs stay completed. Nothing restarts itself.

Endpoints under `/api/hub/`: `missions/prepare-application`, `missions/:id/start`,
`missions`, `missions/:id/session`, `missions/:id/messages` (GET/POST),
`missions/:id/pause`, `missions/:id/resume`, `missions/:id/waiting/:wid/resolve`,
`stop-runs`, `agents`, `file`. Verification harnesses can point one server at a
temp database/workspace with `AGENTIC_OS_CONFIG`, `hub.opencodeExecutable`,
`hub.workspaceRoot` and `hub.trackerUrl`.

## packages/memory/python

Structured Second Brain engine (Phase 1, unchanged by Phase 2). Python package with
domain types, in-memory repositories, services, and PostgreSQL migration files.

```bash
cd packages/memory/python
python3 -m pytest tests/ -v
```

- In-memory dict-backed repositories (no database wiring yet)
- 7 PostgreSQL migration files in `second_brain/db/migrations/` — review-only, not applied
- `claim_type` is `MemoryClaimType | None` (not empty-string)
- No pgvector, no embeddings, no autonomous memory creation, no approval workflow

## memory/

Human-readable Markdown knowledge store partitions.

```
memory/
├── personal/    # personal notes and knowledge
├── projects/    # project-level documentation
├── work/        # work-related knowledge
└── knowledge/   # general knowledge base
```

## Phase 2 explicit exclusions (deferred to later phases)

- OpenAI / Anthropic / Gemini SDKs, model router behavior, LLM calls
- Autonomous runtime loops, connectors (GitHub/Gmail/Calendar/Supabase), browser control
- Skills loader, memory loader, routines, scheduler, vector DB, embeddings
- Autonomous multi-agent loops, WebSocket agents, cloud deployment (mission-scoped supervised orchestration ships in the Hub)

## Project structure

```
apps/       # API and CLI entry points
packages/   # Shared libraries (core, storage, policy, config, ...)
config/     # agentic-os.yaml configuration
skills/     # Skill definitions (example only)
memory/     # Memory partitions (personal, projects, work, knowledge)
routines/   # Routine definitions (unused in Phase 2)
artifacts/  # Agent-made files; listed in the dashboard's Artifacts panel
tests/      # Integration tests
```

## License

Internal — not distributed.
