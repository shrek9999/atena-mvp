# ZEUS phase 6 — readiness and operational safety

Date: 2026-11-01

## Scope

Add an authenticated readiness probe that distinguishes process liveness from
actual availability of the durable task ledger.

## Changes

- `GET /health` remains public and reports process liveness only.
- `GET /ready` requires `Authorization: Bearer <ZEUS_API_TOKEN>`.
- Readiness performs a bounded metadata-list read through the coordinator.
  In production this checks the Cloudflare D1 ledger through the existing
  authenticated Worker client.
- A successful check returns HTTP 200 with a minimal `ledger: ok` status.
- A failed check returns HTTP 503 with `ledger: unavailable`; exception
  details and task metadata are not exposed.
- Added tests for authentication, success, and ledger outage behavior.

## Production and deployment boundary

This phase is committed to `feature/zeus-coordinator-skeleton` only.
The Render service has automatic deploy disabled, and no production deploy or
Cloudflare Worker change was triggered. The existing production deployment
therefore remains unchanged until CI and review are complete.

## Verification still required

- Confirm GitHub Actions runs the new Python tests on PR #33.
- After CI passes and PR merge conflicts are resolved, deploy the readiness
  endpoint and verify authenticated 200/503 behavior against the live ledger.

## Cost and data handling

No new service, paid plan, database table, secret, or persistent user data was
introduced. The readiness check reads at most one task metadata row and does
not return it to the caller.
