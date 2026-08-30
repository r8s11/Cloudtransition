# Agentic OS V1 — Mission Foundation + Persistence & Policy

A TypeScript workspace implementing the core language of an agentic operating system:
missions, plans, persistence (SQLite), policy evaluation, and approvals.

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

- **Local only.** No external network calls. Persistence is a local SQLite file.
- **Single-agent.** No multi-agent behavior, no scheduling, no provider SDKs.
- **No AI/provider logic.** No model routing, no LLM calls, no fake provider behavior.
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

Migrations live in `src/migrations/` (inline `001_initial.sql`); the `migrations`
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
- Multi-agent orchestration, WebSocket agents, dashboard, cloud deployment

## Project structure

```
apps/       # API and CLI entry points
packages/   # Shared libraries (core, storage, policy, config, ...)
config/     # agentic-os.yaml configuration
skills/     # Skill definitions (example only)
memory/     # Memory partitions (personal, projects, work, knowledge)
routines/   # Routine definitions (unused in Phase 2)
artifacts/  # Generated artifacts
tests/      # Integration tests
```

## License

Internal — not distributed.
