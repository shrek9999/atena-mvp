# ZEUS phase 3 — coordinator integration and runtime

**Date:** 2026-11-01  
**Status:** coordinator integration implemented and verified; dedicated Render Free service deployed in restricted pre-configuration mode. Secure runtime secrets remain to be installed manually.

## 1. Durable ledger integration

The coordinator now accepts an optional `LedgerWorkerClient`. When configured:

1. A task is created in D1 before it is accepted into the local in-memory ledger.
2. Every lifecycle transition is sent to the Worker using compare-and-set semantics before the local state is changed.
3. If the Worker rejects a write or is unreachable, the coordinator raises `LedgerPersistenceUnavailable`; it does not silently fall back to in-memory-only operation.
4. The last confirmed local status is retained. If a specialist has returned but the terminal write fails, the local task remains `running`, retains its in-process result and surfaces a retryable persistence error. It is not falsely reported as completed.
5. The durable ledger stores task ID, domain, specialist and lifecycle metadata only. It never receives objectives, prompts, acceptance criteria, request payloads, specialist results, personal health/coaching information or investment/portfolio data.

The default coordinator remains in-memory when no ledger is injected, preserving offline tests and local development. The hosted ZEUS runtime is configured to require the durable ledger.

## 2. Approval and HTTP API

A separate authenticated Flask WSGI service is implemented in `zeus_service.py`.

- `GET /health` — public liveness probe only.
- `POST /v1/tasks` — create a queued task.
- `GET /v1/tasks` and `GET /v1/tasks/{id}` — read lifecycle metadata.
- `POST /v1/tasks/{id}/approve` — explicit approval for a queued task that requires it.
- `POST /v1/tasks/{id}/run` — execute one queued task.
- `POST /v1/tasks/{id}/cancel` — cancel only before execution.

All task endpoints require a separate ZEUS bearer token. The API rejects caller-supplied `approved=true`; approval must be a separate authenticated action. Public task responses intentionally omit objectives, payloads and specialist results.

The API returns HTTP 503 when durable creation or a lifecycle write cannot be confirmed. No silent persistence fallback is allowed.

## 3. Separate Render runtime

`render.yaml` now defines a separate `zeus-coordinator` web service:
- Render Free plan, Frankfurt region;
- dedicated WSGI entry point `zeus_service:app`;
- health check `/health`;
- auto-deploy disabled in the blueprint;
- separate `ZEUS_API_TOKEN`, `ZEUS_LEDGER_TOKEN` and `ZEUS_LEDGER_URL` variables;
- ATENA MCP endpoint used only as a specialist dependency.

ATENA services and their environment variables are not modified by this configuration. The ZEUS service must not reuse the ATENA runtime.

## 4. Current deployment

- Render service: `zeus-coordinator`
- URL: https://zeus-coordinator.onrender.com
- Service ID: `srv-dbje8m67bikc73f6sjjg`
- Region/plan: Frankfurt / Free
- Runtime: Python 3.12.15; Gunicorn; one worker with four threads.
- Auto-deploy is disabled. Code changes require an explicit deployment.
- `ZEUS_LEDGER_URL` and `ATENA_MCP_URL` are configured. Secret values are intentionally not transferred through chat or committed.
- Public root and `/health` both return the ZEUS liveness response. Task API calls return HTTP 503 until both secret variables are configured; no task execution is possible in this state.
- The service is a separate Render resource; no ATENA service, environment variable, or deployment was changed.

## 5. Verification scope and remaining boundary

New tests cover durable create and transition mirroring, failure behavior at create/assignment/completion/cancellation, authenticated API access, metadata minimization, explicit approval and execution/cancellation routes.

The deployed Cloudflare Worker has already passed an external unauthenticated-access check (HTTP 401) and its live D1 schema has been inspected. The Render ZEUS service is now deployed and its liveness endpoints have been checked externally. The authenticated end-to-end Worker operation still needs a matching secret configured in both Cloudflare and Render.

The runtime must not be described as production-ready until:
1. automated tests pass on the final branch head (159 Python tests; 8 Node tests; live ATENA MCP compatibility PASS);
2. a dedicated Render ZEUS service is created on the Free plan (completed);
3. a fresh Worker secret is set directly in Cloudflare and the matching value is set only in the ZEUS Render service (manual secure configuration still required);
4. a separate `ZEUS_API_TOKEN` is set in Render (manual secure configuration still required);
5. the live authenticated create → assign → run → complete lifecycle is verified;
6. an unauthenticated API request is verified to return HTTP 401 after configuration.

No changes are made to ATENA's service configuration, database or deployment. The feature PR remains separate from `main`; no merge or production rollout is performed.
