# ZEUS Phase 5 — Production lifecycle smoke test

## Purpose

Validate the authenticated ZEUS HTTP contract and its durable D1 lifecycle path
without exposing either production token or invoking a real specialist.

## Activation

The smoke test is opt-in. Set `ZEUS_STARTUP_SMOKE=1` on the Render
`zeus-coordinator` service and trigger a manual deploy. The next initialized
runtime performs one synthetic lifecycle through Flask's authenticated API
test client, backed by the configured live `LedgerWorkerClient` and D1 Worker.

## Checks

- Unauthenticated task-list request is rejected with HTTP 401.
- A synthetic fitness task is created.
- The task is dispatched to a deterministic stub ATENA adapter.
- Durable task metadata can be read back and contains no objective or payload.
- Append-only D1 events confirm the ordered lifecycle:
  `queued → assigned → running → completed`.

Approval endpoint semantics remain covered by the automated API contract tests; the production smoke keeps its execution path independent of volatile approval state.

The fixed task ID `zeus-internal-smoke-v1` prevents duplicate smoke records.
A previously completed task is treated as an already-passed smoke test. An
incomplete record fails closed rather than being replayed.

## Safety boundaries

- No production user request, health data, portfolio data, or private payload
  is used or persisted.
- No real ATENA or HERMES call is made.
- No task is automatically replayed after a runtime restart.
- The test does not expose an unauthenticated public trigger or return secrets.
- After a successful run, unset `ZEUS_STARTUP_SMOKE` and redeploy to return
  the service to normal operation.

## What this proves

This validates the authenticated HTTP routes, approval gate, coordinator
dispatch boundary, durable task transitions, metadata readback, and event
history in one live runtime. It does not prove a full real-specialist
customer workflow, because the specialist is intentionally stubbed.
