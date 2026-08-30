# Agentic OS V1 — Mission Foundation

A TypeScript workspace implementing the core language of an agentic operating system:
missions, tasks, plans, tool calls, verification, approvals, and events.

## Setup

```bash
npm install
npm run test
npm run build
npm run check
```

Requires Node.js >= 22.17.0. pnpm is not used; this workspace uses npm workspaces.

## Safety posture

- **Local only.** No network calls, no filesystem access beyond project scaffolding, no secrets.
- **Single-agent.** No multi-agent behavior, no scheduling, no provider SDKs.
- **No persistence.** No SQLite, no migrations, no repositories, no storage layer.
- **No runtime execution.** No CLI commands, no API routes, no connector behavior.
- **No AI/provider logic.** No model routing, no policy evaluation, no real or fake provider behavior.

## V1 exclusions

Phase 1 intentionally does **not** include:

- SQLite, migrations, repositories
- Policy evaluation, connectors, provider behavior
- Runtime execution, CLI commands, API routes
- Routines, skills, memory loaders
- Network calls, filesystem operations beyond scaffolding
- Database ORM, command-execution, browser/UI
- Cloud configuration, scheduling, vector search
- Multi-agent behavior, dashboards

## Project structure

```
apps/       # API and CLI entry points (empty shells in V1)
packages/   # Shared libraries (core has the domain model)
config/     # Shared configuration
skills/     # Skill definitions (example only in V1)
memory/     # Memory partitions (personal, projects, work, knowledge)
routines/   # Routine definitions
artifacts/  # Generated artifacts
tests/      # Integration tests
```

## License

Internal — not distributed.
