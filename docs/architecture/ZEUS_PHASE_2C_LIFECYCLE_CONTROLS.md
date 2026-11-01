# ZEUS prototype — lifecycle controls (Phase 2C)

## Implemented in the isolated prototype

- `enqueue()` creates a queued task without dispatching a specialist.
- `run(task_id)` performs one dispatch. A task can be dispatched only once.
- `cancel(task_id)` cancels queued or assigned tasks. It returns `false` for
  running, terminal, missing, or expired tasks.
- A running synchronous adapter call is **not interruptible**. The coordinator
  never reports a running task as cancelled merely because cancellation was
  requested.
- Terminal records receive `completed_at` and `expires_at`. Expired terminal
  records are purged lazily on ledger access or enqueue; capacity is reclaimed.
- Default terminal-record retention is 30 days, configurable for tests.
- Task records include a single-dispatch `attempt_count`, start/completion
  timestamps, and sanitized error codes.
- A lock protects ledger state while the specialist executes outside the lock.
- The approval gate is evaluated before adapter dispatch.

## Deliberately not implemented

- No durable queue, persistence, multi-process coordination, or recovery after
  process restart. The ledger is in memory only.
- No asynchronous worker or hard cancellation of an in-flight request.
- No automatic retries. Retrying a specialist call without a durable idempotency
  contract could duplicate side effects. A future retry policy must classify
  errors and require idempotency before retrying.
- No generic coordinator-enforced execution timeout. Network adapters must
  enforce their own transport timeout; Python cannot safely interrupt an
  arbitrary synchronous callable.
- No background expiry scheduler. Expiry is lazy and happens on the next ledger
  operation.

## Safety and cost

This change is code and tests on the feature branch only. It adds no dependencies,
databases, external APIs, paid services, credentials, or production changes.
