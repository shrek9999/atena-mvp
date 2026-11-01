# ZEUS persistence — free-tier feasibility and implementation decision

**Decision date:** 2026-11-01  
**Status:** design decision only; no database, Worker, token, binding, or deployment created.

## 1. Verified Cloudflare Free constraints

Cloudflare's current D1 documentation states that Workers Free includes:
- 5 million rows read per day;
- 100,000 rows written per day;
- 5 GB total D1 storage per account;
- 10 D1 databases per account;
- 500 MB maximum size per database;
- 7-day D1 Time Travel retention;
- 50 D1 queries per Worker invocation.

The D1 pricing model is scale-to-zero: no compute charge while idle. There are no D1 data-transfer/egress charges. On Workers Free, exceeding daily read/write quotas causes D1 queries to fail until the quota resets; exceeding storage prevents further inserts/schema changes until data is cleaned up. This is not an instruction to upgrade.

Sources:
- https://developers.cloudflare.com/d1/platform/pricing/
- https://developers.cloudflare.com/d1/platform/limits/
- https://developers.cloudflare.com/d1/reference/faq/

## 2. Account inventory checked read-only

The connected Cloudflare account currently lists one D1 database, named `atena-coach-pilot`. The account therefore appears to have room under the documented Free-plan maximum of ten databases. This is an inventory observation only; it does not authorize creating another database.

The existing coaching database must remain separate from ZEUS task state. ZEUS must not reuse it.

## 3. Recommended architecture

Use a dedicated D1 database for ZEUS, accessed through a small Cloudflare Worker proxy with a D1 binding.

Why a Worker proxy:
- Cloudflare's own D1 guidance recommends a Worker API for application access from outside Workers; the administrative D1 REST API is better suited to administration and is subject to the global Cloudflare API rate limit.
- The proxy can expose a narrow task/event API rather than arbitrary SQL.
- ZEUS Python on Render can call the proxy over HTTPS using a dedicated bearer secret.
- The D1 binding stays inside Cloudflare; the D1 administrative API token does not need to be stored in Render.

Reference:
- https://developers.cloudflare.com/d1/tutorials/build-an-api-to-access-d1/

## 4. Proposed resource boundaries

- Dedicated database: `zeus-task-ledger` (proposed name only).
- Worker: `zeus-ledger-api` (proposed name only).
- D1 binding: `ZEUS_DB`.
- Authentication: dedicated random bearer secret stored as a Worker secret and Render environment variable; never committed to Git.
- Worker routes: `POST /v1/tasks`, `GET /v1/tasks/{id}`, `GET /v1/tasks`, `POST /v1/tasks/{id}/events`.
- No arbitrary SQL endpoint, no public unauthenticated access, no browser-origin CORS access by default.
- Parameterized SQL only; strict request schemas and per-request size limits.
- Append-only event history, bounded task metadata and result retention.
- Retain minimal task metadata for 30 days by default; purge transient payloads promptly. No personal health/coaching payloads in ZEUS ledger.
- Database access limited to the ZEUS Worker; the ATENA coaching application has no binding.

## 5. Safety and free-tier controls

- Keep the account on Workers Free. Do not upgrade to Workers Paid.
- Set application-side limits well below free quotas; proposed daily cap: 10,000 writes and 500,000 rows read, with fail-closed behavior if limits are approached.
- No scheduled polling or high-frequency background jobs.
- Track D1 row reads/writes and storage in Cloudflare dashboard.
- Treat quota exhaustion as a temporary service-unavailable state; never trigger an automatic paid upgrade.
- No credentials or secret values in repository, logs, or task records.

## 6. Implementation sequence

1. Add the Worker proxy source, D1 schema and local tests to the isolated GitHub feature branch.
2. Add a Python client/repository adapter with injected transport and mocked tests.
3. Keep the current in-memory ledger as default; persistence remains opt-in until a D1 database and secret are explicitly provisioned.
4. Request approval before creating the separate D1 database, deploying the Worker, creating a bearer secret, or setting Render environment variables.
5. After approval, provision and test a non-production database; only then consider production use.

## 7. Not done

No D1 database has been created, no Worker deployed, no credentials generated, no Render environment variables changed, and no production configuration modified.


## 8. Isolated prototype code now prepared

The feature branch now contains:
- `cloudflare/zeus-ledger-worker/src/index.js`: narrow authenticated Worker API; no arbitrary SQL route.
- `cloudflare/zeus-ledger-worker/schema.sql`: minimal task metadata table and append-only lifecycle event triggers.
- `cloudflare/zeus-ledger-worker/wrangler.example.toml`: configuration template with an explicit unprovisioned database ID placeholder.
- `cloudflare/zeus-ledger-worker/test/worker.test.mjs`: local Node tests for authentication, metadata minimization, domain/specialist matching, status transitions and event history.
- `zeus/ledger_worker_client.py`: opt-in Python HTTPS client using a secret supplied only through environment variables. It sends task IDs, domain/specialist and lifecycle transitions only; it does not send objectives, prompts, payloads, personal coaching data or results.

This client is not yet connected to the in-memory Coordinator. That integration needs a deliberate persistence/error-recovery contract so a temporary Worker outage cannot leave the in-memory and persistent states inconsistent. The existing coordinator therefore remains the default and no persistence is active.

The Worker tests run against a mocked D1 binding; they do not prove a live D1 database exists or that a Worker has been deployed.
