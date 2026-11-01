# ZEUS phase 6 — readiness and operational safety

Date: 2026-11-01

## Scope

Add an authenticated readiness probe that distinguishes process liveness from
actual availability of the durable task ledger.

## Implementation

- `GET /health` remains public and reports process liveness only.
- `GET /ready` requires `Authorization: Bearer <ZEUS_API_TOKEN>`.
- Readiness performs a bounded metadata-list read through the coordinator.
  In production this checks the Cloudflare D1 ledger through the existing
  authenticated Worker client.
- Success returns HTTP 200 with a minimal `ledger: ok` status.
- Failure returns HTTP 503 with `ledger: unavailable`; exception details and
  task metadata are not exposed.
- Added tests for unauthenticated access, success, and ledger outage behavior.

## Production verification — 2026-11-01

- Render deployment `dep-dbjj5brbc2fs73cvneu0` for application commit
  `38304ca29295e6d00a23abdb3629cc87d1048d4c` is confirmed live.
- A later documentation-only commit was deployed as
  `dep-dbjj9vtg1s2s73ftkdn0`; it is live. Its application tree is identical to
  the previously verified code tree.
- Public `GET /health` returned HTTP 200.
- Public `GET /dashboard` returned HTTP 200.
- Unauthenticated `GET /ready` returned HTTP 401, confirming protection.
- The authenticated production `/ready` success path was not invoked in this
  pass. The production token was deliberately not retrieved or exposed.
  The success, failure, and authentication paths are covered by unit tests.
- D1 was queried read-only: both expected tables exist and the task/event
  counts are zero after synthetic smoke cleanup.

## CI verification

The merge-base conflict with `architecture/zeus-agent-coordination` was
resolved by a non-force merge commit. The resulting PR head is
`3376995745340a51c10d3d97d1b505f8026d48b6`; the tree is unchanged from the
live application deployment.

For this exact PR head, GitHub Actions completed successfully:

- `ZEUS validation` run #63: Python tests passed (182); Worker syntax and
  Worker tests passed (12).
- `ATENA Decision Engine Tests` run #367: Python tests passed (182);
  Worker syntax/tests passed; live ATENA MCP compatibility check passed;
  HERMES public-source smoke passed with one source retrieved successfully.
- HERMES probe result: Federal Reserve source succeeded; the FRED and BLS
  sources were rejected or unavailable in that run. A passing smoke means at
  least one allowlisted source worked, not that every source is healthy.

PR #33 is now mergeable, has no base-branch commits missing, and remains a
draft. It has not been merged.

## Remaining production confirmation

The only unverified phase-6 runtime path is an authenticated production
`GET /ready` response with the real ZEUS token. Do not paste the token into
chat or commit it to GitHub. It can be checked locally with:

```bash
curl -i https://zeus-coordinator.onrender.com/ready \
  -H "Authorization: Bearer <ZEUS_API_TOKEN>"
```

Expected success: HTTP 200 and `ledger: ok`. An unauthenticated request
should return HTTP 401.

## Cost and data handling

No new service, paid plan, database table, or secret was introduced. The
readiness check reads at most one task metadata row and does not return it.
No Cloudflare D1 data or secrets were changed in phase 6.
