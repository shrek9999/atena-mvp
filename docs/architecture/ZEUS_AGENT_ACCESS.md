# ZEUS · ATENA · HERMES — Access and operating guide

## Unified entry point

- Dashboard: https://zeus-coordinator.onrender.com/dashboard (with or without trailing slash)
- Liveness: https://zeus-coordinator.onrender.com/health (public; confirms the process responds)
- Readiness: https://zeus-coordinator.onrender.com/ready (authenticated; confirms the durable ledger can be read)
- API base: https://zeus-coordinator.onrender.com
- Persistent ledger: Cloudflare D1, accessed only by the ZEUS Worker.

ZEUS is the coordinator and the single entry point. It routes fitness and
human-performance work to ATENA, and market/investment research work to
HERMES. HERMES v0.1 is a read-only public-source evidence collector; it does
not trade, forecast, or produce investment recommendations.

## First-time dashboard access

1. Open the dashboard URL.
2. In Render, open the `zeus-coordinator` service and its Environment section.
3. Copy the value of `ZEUS_API_TOKEN` and paste it into the dashboard.
4. Connect. The token is kept in this browser tab's `sessionStorage`; it is
   not written to D1 or sent to a third-party service.
5. Choose ATENA or HERMES, enter the task objective and JSON payload, and
   create the task. Approval-gated tasks require an explicit approval before
   execution.

The dashboard is served by the existing ZEUS Render service. It uses no
external JavaScript libraries, new paid service, or separate hosting account.
It is marked `noindex` and sends no task data until a valid bearer token is
provided.

## Routing

| Task domain | Specialist | Purpose |
|---|---|---|
| `fitness` | ATENA | Training and fitness decisions |
| `human_performance` | ATENA | Human-performance decisions |
| `markets` | HERMES | Market and macro evidence collection |
| `investment_research` | HERMES | Read-only investment research evidence |

ZEUS remains responsible for task lifecycle, approval, and durable metadata.
A specialist is not selected by client-supplied text; the coordinator maps
the supported domain to the specialist.

## API surface

All `/v1/*` routes require `Authorization: Bearer <ZEUS_API_TOKEN>`. The `/ready` route also requires the same bearer token; `/health` remains public for basic liveness checks.

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/agents` | List configured specialists and supported domains |
| POST | `/v1/tasks` | Create a task |
| GET | `/v1/tasks` | List durable task metadata |
| GET | `/v1/tasks/{task_id}` | Read task metadata |
| GET | `/v1/tasks/{task_id}/events` | Read append-only lifecycle events |
| POST | `/v1/tasks/{task_id}/approve` | Record explicit approval |
| POST | `/v1/tasks/{task_id}/run` | Execute a queued task |
| POST | `/v1/tasks/{task_id}/cancel` | Cancel a queued or assigned task |

The `run` response includes the specialist result for the authenticated
caller. The result exists only in coordinator memory for that request and is
not persisted in D1. Durable task and event endpoints expose metadata only.

## Data and security boundaries

- D1 stores task ID, domain, specialist, status, timestamps, attempt count,
  safe error/recovery codes, and append-only lifecycle events.
- D1 does not store task objectives, payloads, personal data, source excerpts,
  or specialist results.
- The API token and Worker ledger token are separate secrets.
- The dashboard never embeds the API token in HTML or JavaScript.
- HERMES performs bounded HTTPS GET requests only to its explicit public
  source allowlist and validates redirects.
- ATENA handles fitness and human-performance decisions; it is not a medical
  diagnostic service.
- Approval-gated tasks cannot run until the explicit approval endpoint is
  called.

## Production verification — 2026-11-01

- Cloudflare Worker version 6 deployed with the D1 trigger-aware transition
  fix.
- Synthetic ZEUS lifecycle passed: `queued → assigned → running → completed`.
- Live ZEUS → ATENA MCP synthetic decision completed.
- Live ZEUS → HERMES public-source retrieval completed.
- Both live tasks had one attempt and four durable lifecycle events.
- All synthetic smoke tasks and their event rows were removed after
  verification.
- Smoke flags were disabled (`false`); no permanent test records remain.

## Known operating constraint

The dashboard requires the owner to retrieve `ZEUS_API_TOKEN` from Render
once and paste it into the browser. The token is intentionally not exposed
through a public endpoint or included in repository files.
