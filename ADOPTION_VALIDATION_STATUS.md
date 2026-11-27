# ATENA — Adoption & Validation Status

**Status date:** 2026-10-20  
**Purpose:** Single operational snapshot for the ATENA agent-first decision-support project.  
**Scope:** ATENA as a specialist called by other AI agents; the website AI-coach pilot is a separate workstream.

## Executive status

ATENA has a public GitHub repository, HTTP API, remote MCP endpoint and active Official MCP Registry identity `io.github.shrek9999/atena` version `1.2.0`. A latest inspected GitHub Actions run for PR #16 passed the repository's offline structural/regression test workflow. Historical live-verification documentation reports a successful HTTP/MCP parity verification on 2026-10-18, but that result is not a fresh check.

On 2026-10-20, an external page-fetch check received HTTP 503 for `https://atena-mvp.onrender.com/health`, `/capabilities` and `/`; it received HTTP 406 for a simple GET to `https://atena-mcp.onrender.com/mcp`. A GET request to the MCP endpoint alone is not a valid Streamable HTTP protocol test. Render service metadata lists the HTTP API and MCP services as `live`, but neither has a configured Render health-check path. Render logs show gunicorn started for the API at 2026-10-20 12:42 UTC and show MCP transport/tool-list activity around that time. Current Render metric queries returned empty data. Therefore current end-to-end production health is **unconfirmed**, not marked as failed or passed.

## Confirmed facts

- Main branch HEAD observed: `334c5bb8dbcf593a9fb7060cf5ee47c38de43696` (`Test API request size limit in live verification`).
- Default branch: `main`; repository is public.
- Official MCP Registry lists `io.github.shrek9999/atena`, version `1.2.0`, status active, with remote URL `https://atena-mcp.onrender.com/mcp`.
- Render has three Free web services in the selected workspace:
  - `atena-mvp`, branch `main`, URL `https://atena-mvp.onrender.com`, service ID `srv-db1nbu97lnhs73do0ts0`.
  - `atena-mcp`, branch `main`, URL `https://atena-mcp.onrender.com`, service ID `srv-db2vqvu0tbcc7387ukt0`.
  - `atena-ai-coach-pilot`, branch `pilot/website-ai-coach`; this is a separate website coach pilot.
- Render service metadata showed no `healthCheckPath` set for either ATENA production service and the allow-list as `0.0.0.0/0`.
- Latest inspected run for PR #16: [GitHub Actions run #39416211308](https://github.com/shrek9999/atena-mvp/actions/runs/39416211308), conclusion `success`. It validates registry metadata JSON and offline test suites; it did not call a model or production/staging API.
- PRs #11–#16 remain open draft PRs as last inspected, in two distinct dependency chains:
  - Website coach pilot: #11 -> #12/#13 -> #14 -> #15 -> #16 (nested base branches need deliberate review before any merge).
  - Core ATENA validation/discovery improvements already merged in main historically; do not conflate the open website-coach PR stack with core product readiness.
- Existing protocol `pilot/AGENT_PILOT_v1.md` says to compare the same agent/model alone versus agent+ATENA on the same cases and blind the evaluator where possible.
- Current pilot results template has only a CSV header; no completed A/B results were found in the inspected main-branch files.
- Documentation explicitly says technical tests are not proof of incremental decision value or independent clinical validation.

## Open uncertainties / blockers

1. Fresh HTTP API health and decision endpoint response have not been confirmed at this check.
2. Fresh MCP initialize -> tools/list -> tools/call -> HTTP/MCP decision parity have not been successfully run within this audit session; HTTP GET of /mcp is not sufficient.
3. No current completed agent-alone versus agent+ATENA A/B results were found. No independent third-party integration or repeat usage was evidenced by files inspected.
4. Render Free service access is public; rate limits, tenant identity, abuse protection, MCP origin/host validation, retention/deletion and uptime monitoring must be reviewed before broader or paid traffic.
5. The core API is not currently guarded by a configured Render health-check path; configure it after confirming hosting controls and endpoint behavior.
6. The website AI-coach project remains separate and its stacked open PRs must not be casually merged as part of core MCP launch work.

## Priority order

### P0 — Fresh production verification
- Re-run the existing manual GitHub Actions workflow **ATENA Live Verification** from the Actions UI/workflow dispatch; it uses no paid LLM API.
- Confirm the latest actual HTTP status, health payload, capabilities, request-size rejection (413), all 20 unseen cases, MCP initialization/tool listing/call, and HTTP/MCP parity.
- Save run URL, UTC timestamp, commit SHA, pass/fail counts and failures. Do not confuse an offline PR test with production verification.

### P1 — Operational controls
- Inspect Render logs/metrics after the live verification.
- Configure the HTTP API health-check path as `/health` only after confirming it's safe and applicable.
- Assess the MCP service health-check strategy; `GET /mcp` is not a useful health check for Streamable HTTP.
- Review public access, abuse/rate controls and request payload minimization. Avoid changing production configuration without explicit approval.

### P2 — Prove added decision value (next product gate)
- Use existing `pilot/cases_v1.json`, `pilot/run_agent_pilot.py` and/or the manually gated Gemini pilot only after checking cost/billing safeguards.
- The OpenAI pilot script requires `OPENAI_API_KEY` and uses an external paid API unless the provider account has credit/free allocation. Do not run it without explicit cost authorization.
- The Gemini workflow requires an explicit `I_CONFIRM_FREE_TIER` gate and the operator must manually reconfirm the project is on Free Tier with no billing account attached. Do not execute blindly.
- Start with manual A/B evaluation if no free model budget exists. Score blind with the rubric and record wins/ties/losses, safety failures, decision quality, tool-call rate, latency and cost. Do not claim success from synthetic fixtures.

### P3 — External integrations
- Once P0 passes, offer the one-page Quickstart to a small set of relevant independent developers/projects.
- Record each integration stage separately: interested, connected, first successful call, repeated calls, and value feedback.
- Avoid payment/metering work until repeat usage and incremental value are evidenced.

## Safety and interpretation

ATENA is decision support for fitness/human performance, not a diagnosis or emergency medical system. Technical reliability, semantic response quality, independent clinical review and commercial demand are separate gates.

## Source files to keep aligned
- `README.md`
- `AGENT_DISCOVERY_AND_VALUE.md`
- `LAUNCHGUIDE.md`
- `BUSINESS_MODEL.md`
- `openapi.json`
- `agent_contract.json`
- `server.json`
- `pilot/AGENT_INTEGRATION_QUICKSTART.md`
- `pilot/AGENT_PILOT_v1.md`
- `pilot/EVALUATION_RUBRIC_v1.md`
- `pilot/RESULTS_TEMPLATE.csv`
