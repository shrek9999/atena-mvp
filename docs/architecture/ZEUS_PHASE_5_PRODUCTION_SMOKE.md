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


## Production defect found and fixed (2026-11-01)

The first live lifecycle attempt exposed a false HTTP 409 on the
`assigned → running` transition. The D1 status trigger writes both the task
row and an append-only event row, so the D1 change counter can be greater than
one. The Worker incorrectly required `meta.changes === 1`.

The Worker now treats any finite positive change count as a successful
conditional update and still rejects zero-change stale or missing-task
updates. The deployed Worker version is 6. A production smoke confirmed all
four transitions and the matching event history.

## Separate live-specialist smoke

The stub-based smoke above remains intentionally isolated from real agents.
A separate opt-in `ZEUS_LIVE_AGENT_SMOKE=1` (or
`ZEUS_STARTUP_SMOKE=2`) path exercises both real adapters through the
ZEUS coordinator using synthetic, non-personal inputs:

- ATENA: Streamable HTTP MCP initialize and `atena_decide` call.
- HERMES: read-only retrieval from the allowlisted official public sources.
- Both: authenticated ZEUS task creation, specialist execution, durable
  metadata readback, and the four-event lifecycle.

Specialist results are checked in process memory only. D1 stores no objective,
payload, source excerpts, or specialist result. The live smoke is non-blocking
for service startup if an external specialist is temporarily unavailable.

The 2026-11-01 production run completed both synthetic tasks with one attempt
each. The three synthetic smoke tasks and their event rows were deleted after
verification. Both smoke flags were disabled (`false`).
