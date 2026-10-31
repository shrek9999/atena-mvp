# ZEUS Phase 2B — coordinator skeleton

## Scope

This is an isolated, offline prototype. It does not modify the Flask application,
Render services, Cloudflare resources, production routes, or user data.

## Included

- Deterministic routing: fitness/human performance → ATENA; markets/investment research → HERMES.
- A bounded in-memory task ledger with explicit lifecycle states.
- Specialist adapters injected by the caller; no model or network dependency.
- A hard approval gate for tasks marked as requiring approval.
- Sanitized failure records; raw exception text and task payloads are not copied to the ledger.
- No recursive delegation.

## Current limitations

- ATENA and HERMES adapters are not connected in this skeleton. The ATENA adapter
  will be connected through the existing remote MCP interface in the next integration
  step. HERMES remains unavailable until its source/deployment is located or a
  specialist implementation is explicitly selected.
- The ledger is process-local and ephemeral. It is suitable only for tests and
  a single-process prototype, not multi-user or production operation.
- There is no autonomous language-model planner. Routing is deterministic by design.

## Local tests

Run:

```bash
python -m pip install pytest
pytest -q tests/test_zeus_coordinator.py
```

No paid API calls or external service requests are made by these tests.
