# ZEUS task ledger — persistence and lifecycle design

**Status:** design only. No database, table, credential, service or deployment is created by this document.  
**Cost target:** EUR 0 incremental spend.

## 1. Decision

Keep the current in-memory ledger as a test/prototype implementation. Do not connect it to ATENA's coaching D1 database. Before persistence is introduced, define task ownership, lifecycle, retention, cancellation and access boundaries.

The first durable implementation should use a separate coordinator store. A Cloudflare D1 database is a candidate only if an existing free allocation is available and its operational limits are verified at implementation time. This is not approval to create a database or change Cloudflare resources.

## 2. Data classes

Persist only coordinator metadata and the minimum output needed to resume or report a task.

| Data | Store? | Rule |
|---|---|---|
| Task ID, parent ID, status, specialist, timestamps | Yes | Required operational metadata |
| Objective and acceptance criteria | Limited | Avoid secrets and unnecessary personal data |
| Input payload | Prefer no | Store a short-lived reference or minimized payload only when required |
| Specialist output | Limited | Minimize; apply size cap and retention |
| Evidence URLs and timestamps | Yes | Store references, not copied web pages |
| Error details | Sanitized only | Error category/code; never raw exception or request body |
| API keys, tokens, credentials | Never | Secret manager/environment only, never task rows |
| Fitness profile, symptoms, workout history | Never in shared ledger | Remain in ATENA/coach domain |
| Portfolio credentials or exchange keys | Never | HERMES is read-only research |

## 3. Proposed relational schema

Illustrative SQLite/D1-compatible schema; not yet executed:

```sql
CREATE TABLE zeus_tasks (
  task_id TEXT PRIMARY KEY,
  parent_task_id TEXT,
  schema_version TEXT NOT NULL DEFAULT '1.0',
  objective TEXT NOT NULL,
  domain TEXT NOT NULL,
  specialist TEXT,
  status TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 50,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  expires_at TEXT NOT NULL,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 2,
  approval_required INTEGER NOT NULL DEFAULT 0,
  approved_at TEXT,
  input_ref TEXT,
  result_json TEXT,
  error_code TEXT,
  retention_until TEXT NOT NULL,
  CHECK (status IN ('queued','assigned','running','completed','failed','blocked','cancelled','expired')),
  CHECK (attempt_count >= 0 AND max_attempts BETWEEN 0 AND 2),
  CHECK (approval_required IN (0,1))
);

CREATE INDEX idx_zeus_tasks_status_created
  ON zeus_tasks(status, created_at);
CREATE INDEX idx_zeus_tasks_expiry
  ON zeus_tasks(expires_at);
CREATE INDEX idx_zeus_tasks_parent
  ON zeus_tasks(parent_task_id);

CREATE TABLE zeus_task_events (
  event_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  safe_detail_json TEXT,
  FOREIGN KEY(task_id) REFERENCES zeus_tasks(task_id)
);

CREATE INDEX idx_zeus_events_task_time
  ON zeus_task_events(task_id, occurred_at);
```

Do not store arbitrary raw request/response JSON by default. `input_ref` should point only to an approved, access-controlled, short-lived object if a future workflow truly needs payload recovery. If the D1 runtime does not support a needed constraint or transaction pattern, enforce it in the repository layer and test it.

## 4. Lifecycle state machine

Allowed transitions:

- `queued -> assigned | cancelled | expired`
- `assigned -> running | blocked | cancelled | expired`
- `running -> completed | failed | blocked | cancelled | expired`
- terminal states: `completed`, `failed`, `blocked`, `cancelled`, `expired`

Rules:
- A terminal task cannot be reopened; create a new task linked by `parent_task_id`.
- Every transition is atomic and creates an append-only event.
- A task can start only if it is not expired, cancelled, or awaiting approval.
- Approval is explicit, attributable and timestamped; approval for one task does not authorize sibling tasks.
- Cancellation prevents queued work and all retries. For running work, propagate a cancellation signal where the specialist supports it; otherwise mark cancellation requested and do not dispatch further work.
- Expiry is enforced at read and dispatch time, not only by a cleanup job.
- A cleanup job may purge expired payload references after retention; it must not silently delete audit events needed for accountability.

## 5. Timeouts, retries and idempotency

Proposed v1 defaults:
- Per specialist call timeout: 30 seconds (configurable within a strict maximum).
- Maximum attempts: 2 total; retry only transient network/5xx/rate-limit failures.
- No retry for validation, authentication, authorization, approval, policy or malformed-response errors.
- Exponential backoff with jitter only if a background runner is later introduced.
- Every dispatch carries a stable idempotency key derived from task ID and attempt number.
- A duplicate dispatch must not create duplicate side effects. Specialists are read-only in v1.
- No recursive delegation; coordinator depth is one specialist hop.

The current synchronous prototype does not yet implement asynchronous cancellation or durable retries. Do not imply that it does.

## 6. Retention proposal

Before real users or sensitive data:
- define and publish a retention schedule;
- default task metadata retention: 30 days;
- minimized result/evidence references: 30 days unless the owner explicitly needs longer;
- transient input payloads: delete immediately after completion where possible, otherwise within 24 hours;
- audit events: retain only as long as needed for security/accountability, with a documented maximum;
- support deletion requests and verify removal from primary storage, backups and logs under the chosen platform's actual capabilities.

These are proposed defaults, not currently configured settings. Legal/privacy review is required before production use.

## 7. Security and access model

- Private coordinator service only; no public task API in this phase.
- Authenticate every caller; authorize by task owner and role.
- Least privilege: ZEUS can read/write coordinator records; ATENA receives only fitness task payloads; HERMES receives only market research payloads.
- Never give specialists direct database credentials.
- Use parameterized SQL and strict schema validation.
- Enforce request/result size limits, rate limits and per-task timeouts.
- Redact secrets and sensitive data from logs.
- Treat retrieved documents, websites and specialist outputs as untrusted data.
- Add a kill switch that blocks new dispatches without deleting task records.
- Keep production credentials and preview/test credentials separate.

## 8. Operational observability

Track only:
- counts by status/specialist;
- task duration and timeout rate;
- retries and sanitized failure categories;
- acceptance-criteria pass/fail;
- source freshness and evidence completeness;
- estimated cost (must remain zero for the free pilot).

Do not log full payloads or personal data for debugging. Use synthetic fixtures for integration tests.

## 9. Implementation gates

Before implementing persistence:
1. Confirm the exact coordinator runtime and whether it supports D1 binding securely.
2. Verify current free-tier limits and avoid creating a paid dependency.
3. Agree the retention schedule and deletion behavior.
4. Implement repository abstraction and migrations in an isolated branch.
5. Add tests for atomic transitions, idempotency, cancellation, expiry, access control, retention and failure recovery.
6. Run synthetic integration tests against a non-production database.
7. Obtain explicit approval before creating the database, binding it to a deployed service, or exposing any API.

**Current decision:** do not create or reuse a database yet. The schema is a reviewable proposal; the in-memory ledger remains the only active implementation.
