`second_brain/` — Phase 1 Structured Memory Engine
====================================================

A hybrid Second Brain foundation: structured memory in code and PostgreSQL,
with long-form knowledge in Markdown/files deferred to later phases.

## What's here (Phase 1)

- **types/** — domain enums and dataclass models (Area, Entity, EntityAlias,
  Memory, MemorySource, MemoryEvidence, MemoryCandidate)
- **repositories/** — in-memory persistence (dict-backed) for all entities
- **services/** — validation, normalization, and delegation layer
- **seeding/** — idempotent default-area seeder (7 top-level areas)
- **db/migrations/** — 7 PostgreSQL migration files (review-only, not applied)
- **tests/** — 107 tests across 5 test files

## Package structure

```
packages/memory/python/
├── second_brain/          # Python package
│   ├── __init__.py
│   ├── types/             # enums + dataclass models
│   ├── repositories/      # in-memory persistence
│   ├── services/          # validation + business logic
│   ├── seeding/           # default area seeder
│   └── db/migrations/     # PostgreSQL DDL (review-only)
├── tests/                 # pytest suite
├── README.md              # this file
└── pyproject.toml         # package metadata
```

## Running tests

```bash
cd packages/memory/python
python3 -m pytest tests/ -v
```

## Claim type semantics

`claim_type` is now `MemoryClaimType | None` (was empty-string `""`).

- `None` — claim type not specified
- `MemoryClaimType.FACT` / `.INFERENCE` / `.OPINION` / `.DECISION` / `.HYPOTHESIS` — valid claim

Empty strings are no longer accepted.

## Migrations

The 7 SQL migration files in `second_brain/db/migrations/` are **review-only**.
They were generated for manual review and have **not** been applied to any
production database.

## Phase 1 scope

- PostgreSQL schema (migrations only, not wired)
- In-memory repositories for tests
- No pgvector, no embeddings, no autonomous memory creation
- No memory approval workflow
- No connectors, no UI
