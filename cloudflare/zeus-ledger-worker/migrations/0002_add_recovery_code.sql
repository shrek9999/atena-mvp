-- ZEUS ledger migration 0002
-- Adds a bounded, non-sensitive marker explaining why an active task was
-- blocked during process restart. Does not add or persist request payloads.
ALTER TABLE zeus_tasks
ADD COLUMN recovery_code TEXT
CHECK (recovery_code IS NULL OR recovery_code IN ('runtime_restarted'));
