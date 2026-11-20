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

const MIGRATION_002 = `
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL CHECK(length(trim(name)) > 0),
  path TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  adapter_id TEXT NOT NULL, prompt TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('starting','running','interrupting','terminating','completed','failed','interrupted','terminated','lost')),
  created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT, error TEXT,
  pid INTEGER CHECK(pid IS NULL OR pid > 0), owner_id TEXT NOT NULL,
  mission_id TEXT REFERENCES missions(id), plan_version INTEGER,
  task_id TEXT, exit_code INTEGER, signal TEXT,
  FOREIGN KEY (mission_id, plan_version) REFERENCES plans(mission_id, version),
  CHECK (plan_version IS NULL OR (mission_id IS NOT NULL AND plan_version > 0)),
  CHECK (task_id IS NULL OR (mission_id IS NOT NULL AND plan_version IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS run_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('state','stdout','stderr')),
  data TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_owner (
  slot INTEGER PRIMARY KEY CHECK(slot=1), owner_id TEXT NOT NULL,
  pid INTEGER NOT NULL CHECK(pid > 0), started TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_project ON agent_runs(project_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status, created_at, id);
CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id,id);
`;
const MIGRATION_003 = `
ALTER TABLE agent_runs ADD COLUMN model TEXT;
ALTER TABLE agent_runs ADD COLUMN effort TEXT;
ALTER TABLE agent_runs ADD COLUMN input_tokens INTEGER CHECK(input_tokens IS NULL OR input_tokens >= 0);
ALTER TABLE agent_runs ADD COLUMN output_tokens INTEGER CHECK(output_tokens IS NULL OR output_tokens >= 0);
ALTER TABLE agent_runs ADD COLUMN cost_usd REAL CHECK(cost_usd IS NULL OR cost_usd >= 0);
`;
const MIGRATION_004 = `
CREATE TABLE IF NOT EXISTS hub_sessions (
  mission_id TEXT PRIMARY KEY REFERENCES missions(id) ON DELETE CASCADE,
  budget INTEGER NOT NULL CHECK(budget > 0),
  max_depth INTEGER NOT NULL CHECK(max_depth > 0),
  models_json TEXT NOT NULL DEFAULT '{}',
  criteria_refs_json TEXT NOT NULL DEFAULT '[]',
  recommendation TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hub_tasks (
  mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  task_id TEXT NOT NULL,
  owner TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','in_progress','completed','blocked','interrupted')),
  lease_key TEXT,
  run_id TEXT,
  blocked_reason TEXT,
  guard_snapshot TEXT,
  git_head TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (mission_id, task_id)
);
CREATE TABLE IF NOT EXISTS hub_messages (
  id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  task_id TEXT,
  in_reply_to TEXT,
  from_agent TEXT NOT NULL,
  to_agent TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('assignment','result','note')),
  objective TEXT NOT NULL DEFAULT '',
  done_when TEXT NOT NULL DEFAULT '',
  input_refs TEXT NOT NULL DEFAULT '[]',
  output_refs TEXT NOT NULL DEFAULT '[]',
  result TEXT NOT NULL DEFAULT '',
  evidence TEXT NOT NULL DEFAULT '[]',
  decisions TEXT NOT NULL DEFAULT '[]',
  blockers TEXT NOT NULL DEFAULT '[]',
  approval_needed INTEGER NOT NULL DEFAULT 0,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hub_subscriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('run_completion','new_message')),
  created_at TEXT NOT NULL,
  UNIQUE (mission_id, kind)
);
CREATE TABLE IF NOT EXISTS hub_waiting (
  id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('approval','budget','blocker')),
  title TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL DEFAULT '',
  approval_id TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS hub_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  detail TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hub_messages_mission ON hub_messages(mission_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_hub_waiting_mission ON hub_waiting(mission_id, resolved_at);
CREATE INDEX IF NOT EXISTS idx_hub_tasks_status ON hub_tasks(mission_id, status);
`;
const MIGRATIONS: Migration[] = [
  { name: "001_initial.sql", sql: MIGRATION_001, hash: hashSql(MIGRATION_001) },
  { name: "002_agent_runtime.sql", sql: MIGRATION_002, hash: hashSql(MIGRATION_002) },
  { name: "003_run_usage.sql", sql: MIGRATION_003, hash: hashSql(MIGRATION_003) },
  { name: "004_hub.sql", sql: MIGRATION_004, hash: hashSql(MIGRATION_004) },
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
