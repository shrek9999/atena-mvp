# ATENA–ZEUS–HERMES project status audit

Audit date: 2026-11-01
Scope: deployed services, repository state, specialist contracts, training
programme engine, data persistence, safety, validation, and pilot readiness.

## Executive status

The project has a working technical foundation and several deployed
components, but it is not yet a public, fully autonomous, revenue-ready
product. The most complete parts are ZEUS's metadata coordinator and the
deterministic ATENA training-programme generator. The largest immediate
blocker for the coach product is the failed Supabase/PostgreSQL connectivity
check. HERMES is currently an evidence collector, not an autonomous market
analyst.

## Deployed services

All four Render web services were observed on the Free plan at audit time.

| Service | Branch | Observed state | Live health configuration |
| --- | --- | --- | --- |
| `atena-mvp` | `main` | Not suspended; `/health` and `/capabilities` returned HTTP 200 on retry | No Render health-check path configured |
| `atena-mcp` | `main` | Not suspended; authenticated MCP POST traffic is present in logs and live compatibility CI passes | No Render health-check path configured |
| `atena-ai-coach-pilot` | `pilot/website-ai-coach` | Not suspended; `/health` returned HTTP 200 | `/health` |
| `zeus-coordinator` | `feature/zeus-coordinator-skeleton` | Live; `/health` and `/dashboard` returned HTTP 200 | No Render health-check path configured |

The first unauthenticated GET to the main ATENA health URL returned HTTP 503;
subsequent checks returned HTTP 200. Treat this as a transient/cold-start
observation, not evidence of a persistent outage. A plain GET to the
streamable MCP `/mcp` endpoint is not a valid MCP protocol test; the live
POST-based compatibility check passed.

## ZEUS — coordinator and durable task ledger

**Implemented and deployed**

- Authenticated task API and a small browser dashboard.
- Specialist routing to ATENA for fitness/human-performance domains and HERMES
  for markets/investment-research domains.
- Durable Cloudflare D1 task metadata and lifecycle events.
- State-transition checks, restart recovery markers, bounded metadata reads,
  and fail-closed behavior when the ledger cannot be reached.
- Specialist output is returned to the authenticated caller for that run and
  is not persisted to D1.
- Dashboard token entry is session-scoped in the browser; no token is embedded
  in the page.

**Verified**

- Cloudflare Worker version 6 is active with its existing D1 binding and
  ledger-token binding preserved.
- Production lifecycle and live synthetic ATENA/HERMES routing smoke tests
  passed in the preceding production verification.
- D1 contains the expected task and event tables; both currently contain zero
  rows after synthetic test cleanup.
- Phase-6 readiness route is implemented and protected. Unauthenticated
  production access returns HTTP 401. The authenticated production 200 path
  has not yet been called without exposing the token.
- PR-head CI run #63 passed: 182 Python tests and 12 Worker tests.

**Not yet a full autonomous orchestration platform**

The current execution path is an authenticated, caller-triggered coordinator
flow. It is not yet a durable background worker fleet or a self-scheduling
agent system. D1 deliberately stores lifecycle metadata only, so task payloads
and results do not survive process restarts. The `expires_at` field is set
for terminal tasks, but the Worker currently has no scheduled cleanup
handler/cron trigger; retention cleanup should be implemented before the
ledger accumulates production history.

## ATENA — decision engine and MCP

**Implemented and verified**

- HTTP service and capability discovery endpoint.
- MCP server with a live decision tool compatibility check.
- Live ATENA MCP compatibility smoke passed on the current ZEUS PR head.
- The current CI suite passed 182 Python tests.

**Product evidence still missing**

- No completed blinded, held-out Agent-vs-Agent+ATENA evaluation proving
  incremental decision quality.
- No independent external integrator has completed a supervised integration.
- No recorded customer interviews, repeat-use evidence, or willingness-to-pay
  evidence. These remain separate from technical test success.

## ATENA AI Coach — training product

### Public website prototype

The public website route `https://gregajenko.si/ai-trener` is marked as a
development prototype and `noindex,nofollow`; it explicitly says it is not
open to public use. It describes a catalogue-based programme flow and says
that this programme step does not call an AI model or store profile data.

### Backend pilot

The separate Render pilot service exposes authenticated chat, deterministic
programme generation, profile, session, progress, export, consent, and
adaptation endpoints.

- The curated exercise catalogue contains 109 entries: 99 multi-joint and 10
  single-joint exercises.
- Seven training goals and three experience levels are represented.
- Programme generation supports 2, 3, or 4 sessions per week and an estimated
  25–120 minute session envelope.
- Hypertrophy defaults favour compound movement patterns; single-joint
  accessories are optional for advanced users.
- Warm-up time is estimated flexibly; trunk-stability work is not added by
  default to hypertrophy plans and is introduced only when feedback identifies
  a control issue.
- Hard, incomplete, or poorly recovered sessions conservatively reduce
  compound exercise sets. Pain/new discomfort blocks automatic adaptation.
- Profile storage uses opt-in gates and separate health-data consent. Profile
  access tokens are hashed; export and deletion routes exist.

### Verified and blocked

- The latest staging quality workflow #47 passed with 177 Python tests.
- The latest staging endpoint verification workflow #31 failed only at the
  Supabase/PostgreSQL connectivity check, which returned the safe category
  `database_connection_failed`.
- In that same run, deterministic hypertrophy programme generation returned
  HTTP 200; the straight-back hinge terminology check passed; the beginner
  endurance time-envelope check passed; the safety-first chat check returned
  HTTP 200; the profile-storage-disabled check and CORS preflight passed.
- Therefore programme generation and the pilot chat path have working
  evidence, but persistent profile/session/progress storage is not verified
  and must remain disabled until database connectivity and privacy gates are
  confirmed.
- One live Gemini chat smoke call succeeded in CI. Provider free-allocation
  and billing status were not established by that test; do not run repeated
  model tests until the allocation/billing state is confirmed.

**End-to-end product gap**

The backend endpoints exist, but the complete user journey—safety-first
intake, structured profile, generated plan, saved sessions, progress summary,
and feedback-based next-step decision—has not yet been proven as one
continuous production flow with working persistent storage.

## HERMES — public-source research

HERMES v0.1 is a bounded, read-only public-source evidence collector.

- Accepts only explicitly supplied HTTPS URLs on a strict public-source
  allowlist; at most five URLs and bounded document size/time.
- Validates redirects and rejects credentials, non-HTTPS URLs, and unlisted
  hosts.
- Returns excerpts, source metadata, retrieval timestamps, failures, and
  limitations.
- Does not calculate capital flows, valuation, price confirmation,
  probabilities, forecasts, or buy/sell recommendations. It does not trade
  or mutate portfolios.
- The latest live smoke passed because one Federal Reserve source was
  retrieved. FRED and BLS sources failed in that run. The collector therefore
  has limited source coverage and must not be described as a finished
  investment analyst.

## Repository and CI state

- PR #33, `feature/zeus-coordinator-skeleton` → `architecture/zeus-agent-coordination`,
  is open, draft, and mergeable. The branch is 177 commits ahead and zero
  commits behind after a non-force merge commit. It has not been merged.
- For the merged-base PR head, GitHub Actions run #63 (ZEUS validation) and
  run #367 (ATENA Decision Engine Tests) both passed.
- Run #367 passed 182 Python tests, 12 Worker tests, the live ATENA MCP
  compatibility check, and the HERMES public-source smoke.
- PR #11 for the AI Coach pilot remains a separate draft. The pilot service is
  deployed from its own branch and is not the same deployment as the main
  ATENA decision-engine service.
- Render automatic deployment is disabled for ZEUS. Its live application tree
  is identical to the tree verified by the latest PR-head CI; subsequent
  branch commits in this audit are documentation-only.

## Operational and security gaps

1. Fix and verify the Supabase/PostgreSQL connection before enabling profile
   storage. Keep storage disabled until privacy notice approval and explicit
   health-data consent are in place.
2. Add Render health-check paths for the main ATENA service, MCP service, and
   ZEUS service; the live service configuration currently has none.
3. Implement scheduled deletion of expired ZEUS task metadata/events, or
   explicitly document a different retention policy.
4. Complete an authenticated production `GET /ready` success check without
   disclosing the token.
5. Verify the end-to-end coach flow with synthetic data and a real database
   only after connectivity succeeds.
6. Confirm Gemini free-tier/billing state before further live chat calls.
7. Complete the blinded incremental-value test and one independent external
   integration before making adoption or product-value claims.
8. Add monitoring/rate-limit and operational security checks before opening
   the services to broader traffic.

## Recommended order of work

1. Resolve Supabase connectivity and confirm storage readiness; do not enable
   health-data storage before privacy approval.
2. Complete the ZEUS authenticated readiness probe.
3. Add live Render health checks and D1 retention cleanup.
4. Run one end-to-end synthetic coach journey through intake, programme,
   session logging, progress, export/deletion, and adaptation.
5. Freeze the product contract and run the blinded ATENA value evaluation.
6. Invite one independent integrator and conduct customer discovery.
7. Only then decide whether to open the coach pilot publicly or introduce
   pricing.

## Cost boundary

No paid Render plan, new paid service, or additional database was enabled in
this audit. All observed Render services were on Free plans. Live model
provider billing/allocation remains unverified and is a release gate.
