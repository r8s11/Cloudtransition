import { createHash } from "node:crypto";
import { Database } from "./database.js";

/** A single migration loaded from disk. */
export interface Migration {
  name: string;
  sql: string;
  hash: string;
}

/**
 * Initial schema migration (mirrors src/migrations/001_initial.sql for review).
 *
 * Kept inline so the storage package has a single, code-loadable source of
 * truth and does not depend on `import.meta`/filesystem resolution under the
 * CommonJS build used by this workspace.
 */
const MIGRATION_001 = `
CREATE TABLE IF NOT EXISTS migrations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  hash TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS missions (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  acceptance_criteria TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  plan_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (mission_id, version)
);

CREATE TABLE IF NOT EXISTS mission_transitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  from_status TEXT NOT NULL,
  to_status TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_requests (
  id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  run_id TEXT,
  capability TEXT NOT NULL,
  action TEXT NOT NULL,
  reason TEXT NOT NULL,
  risk TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_plans_mission_id ON plans(mission_id);
CREATE INDEX IF NOT EXISTS idx_transitions_mission_id ON mission_transitions(mission_id);
CREATE INDEX IF NOT EXISTS idx_approvals_mission_id ON approval_requests(mission_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approval_requests(status);
`;

/** Migrations in deterministic order (filename sort). */
const MIGRATIONS: Migration[] = [
  { name: "001_initial.sql", sql: MIGRATION_001, hash: hashSql(MIGRATION_001) },
];

function hashSql(sql: string): string {
  return createHash("sha256").update(sql).digest("hex");
}

/**
 * Apply any migrations that have not yet been recorded, in deterministic order.
 *
 * Guarantees:
 *  - Migrations run in filename order.
 *  - A migration that is already recorded is never re-run.
 *  - Each applied migration is recorded in the `migrations` table with its hash.
 *  - If a recorded migration's hash differs on reopen, the open fails fast.
 *  - Migrations run inside a transaction so a failure leaves the DB clean.
 */
export function applyMigrations(database: Database): void {
  database.exec(`
    CREATE TABLE IF NOT EXISTS migrations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      hash TEXT NOT NULL,
      applied_at TEXT NOT NULL
    );
  `);

  const applied = database
    .prepare("SELECT name, hash FROM migrations")
    .all() as Array<{ name: string; hash: string }>;
  const appliedByName = new Map(applied.map((m) => [m.name, m.hash]));

  database.transaction(() => {
    for (const migration of MIGRATIONS) {
      const existingHash = appliedByName.get(migration.name);
      if (existingHash === undefined) {
        database.exec(migration.sql);
        database
          .prepare(
            "INSERT INTO migrations (name, hash, applied_at) VALUES (?, ?, ?)",
          )
          .run(migration.name, migration.hash, new Date().toISOString());
      } else if (existingHash !== migration.hash) {
        throw new Error(
          `Migration '${migration.name}' has changed since it was applied. ` +
            `Refusing to re-run. Stored hash differs from current SQL.`,
        );
      }
      // Already applied with matching hash -> skip silently (reopen is safe).
    }
  });
}

export { MIGRATIONS };
