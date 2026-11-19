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
