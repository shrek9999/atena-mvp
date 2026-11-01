PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS zeus_tasks (
  task_id TEXT PRIMARY KEY NOT NULL,
  domain TEXT NOT NULL CHECK (domain IN ('fitness', 'human_performance', 'markets', 'investment_research')),
  specialist TEXT NOT NULL CHECK (specialist IN ('ATENA', 'HERMES')),
  status TEXT NOT NULL CHECK (status IN ('queued', 'assigned', 'running', 'completed', 'failed', 'blocked', 'cancelled')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  expires_at TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  error_code TEXT CHECK (error_code IS NULL OR error_code IN (
    'approval_required', 'specialist_unavailable', 'specialist_execution_failed', 'cancelled_by_request'
  )),
  CHECK (
    (domain IN ('fitness', 'human_performance') AND specialist = 'ATENA')
    OR
    (domain IN ('markets', 'investment_research') AND specialist = 'HERMES')
  )
);

CREATE INDEX IF NOT EXISTS idx_zeus_tasks_created ON zeus_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_zeus_tasks_status ON zeus_tasks(status, updated_at);

CREATE TABLE IF NOT EXISTS zeus_task_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL REFERENCES zeus_tasks(task_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK (event_type IN ('created', 'status_changed')),
  from_status TEXT,
  to_status TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_zeus_events_task ON zeus_task_events(task_id, event_id);

CREATE TRIGGER IF NOT EXISTS trg_zeus_task_created
AFTER INSERT ON zeus_tasks
BEGIN
  INSERT INTO zeus_task_events(task_id, event_type, from_status, to_status, occurred_at)
  VALUES (NEW.task_id, 'created', NULL, NEW.status, NEW.created_at);
END;

CREATE TRIGGER IF NOT EXISTS trg_zeus_task_status_changed
AFTER UPDATE OF status ON zeus_tasks
WHEN OLD.status <> NEW.status
BEGIN
  INSERT INTO zeus_task_events(task_id, event_type, from_status, to_status, occurred_at)
  VALUES (NEW.task_id, 'status_changed', OLD.status, NEW.status, NEW.updated_at);
END;
