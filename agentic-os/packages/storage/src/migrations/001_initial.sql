-- Migration 001: initial Agentic OS persistence schema
-- Applied once; tracked in the `migrations` table.

CREATE TABLE IF NOT EXISTS migrations (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  name    TEXT NOT NULL UNIQUE,
  hash    TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS missions (
  id                  TEXT PRIMARY KEY,
  title               TEXT NOT NULL,
  description         TEXT,
  status              TEXT NOT NULL,
  priority            TEXT NOT NULL,
  acceptance_criteria TEXT NOT NULL,  -- JSON array of strings
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL,
  started_at          TEXT,
  completed_at        TEXT
);

CREATE TABLE IF NOT EXISTS plans (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id  TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  version     INTEGER NOT NULL,
  plan_json   TEXT NOT NULL,           -- validated Plan object, stored as JSON
  created_at  TEXT NOT NULL,
  UNIQUE (mission_id, version)
);

CREATE TABLE IF NOT EXISTS mission_transitions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id  TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  from_status TEXT NOT NULL,
  to_status   TEXT NOT NULL,
  reason      TEXT,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_requests (
  id          TEXT PRIMARY KEY,
  mission_id  TEXT NOT NULL,
  run_id      TEXT,
  capability  TEXT NOT NULL,
  action      TEXT NOT NULL,
  reason      TEXT NOT NULL,
  risk        TEXT NOT NULL,
  status      TEXT NOT NULL,           -- pending | approved | rejected
  created_at  TEXT NOT NULL,
  resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_plans_mission_id ON plans(mission_id);
CREATE INDEX IF NOT EXISTS idx_transitions_mission_id ON mission_transitions(mission_id);
CREATE INDEX IF NOT EXISTS idx_approvals_mission_id ON approval_requests(mission_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approval_requests(status);
