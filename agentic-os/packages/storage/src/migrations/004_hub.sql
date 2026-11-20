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
