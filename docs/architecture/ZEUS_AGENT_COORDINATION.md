# ZEUS–ATENA–HERMES: agent coordination architecture

**Status:** Architecture proposal (Phase 2)  
**Date:** 2026-10-31  
**Base:** Existing ATENA pilot infrastructure  
**Scope:** Design only. No production services, credentials, user data, or deployments are changed by this document.

## 1. Executive decision

Build a small, tool-first coordination layer around the systems that already exist. Do not rebuild ATENA and do not introduce a heavyweight multi-agent framework in the first iteration.

- **ZEUS** is the coordinator. It turns a user objective into bounded tasks, delegates specialist work, checks evidence and completion, and reports back.
- **ATENA** remains the fitness and human-performance decision specialist. It is called only for consequential next-action decisions under uncertainty or trade-offs.
- **HERMES** is the market and opportunity research specialist. It is a planned integration; no live HERMES service was verified in the current inventory.
- **Human owner** sets priorities and approves consequential external actions.

The first implementation should be a **single coordinator with specialist tools**, not three autonomous services continuously calling one another. This is cheaper, easier to audit, and reduces loops and duplicated work.

## 2. Verified baseline and boundaries

The current inventory verified these components:

| Component | Verified role | Current boundary |
|---|---|---|
| Render `atena-mvp` | ATENA decision API, version 1.2.0 | Existing specialist; keep its decision logic independent |
| Render `atena-mcp` | Streamable HTTP MCP server | Exposes ATENA tools; recent logs show tool discovery and MCP requests |
| Render `atena-ai-coach-pilot` | Fitness coaching pilot | Separate product workflow; do not merge its user data into the coordinator |
| Cloudflare Pages `atena-ai-trener` | Digital trainer UI | Production feature flag was off during inventory; preview is not production |
| Cloudflare D1 `atena-coach-pilot` | Coach data store | Contains profile/program/workout/check-in tables; keep private coaching data isolated |
| Cloudflare KV `atena-limiter` | Rate limiting | Existing pilot infrastructure |
| GitHub `atena-mvp` | ATENA source, contracts, MCP server, pilot docs | Existing source of truth for ATENA |

No deployed ZEUS coordinator or HERMES specialist was verified. Existing ATENA documentation already defines when ATENA should be called, HTTP/MCP endpoints, fallback behavior, data minimization, and incremental-value evaluation. This architecture extends those contracts rather than replacing them.

## 3. Logical architecture

```text
                         USER / HUMAN OWNER
                                 |
                                 v
                         ZEUS COORDINATOR
                   intent -> plan -> delegate
                    verify -> report -> learn
                         /             \
                        v               v
              ATENA SPECIALIST     HERMES SPECIALIST
              Fitness decisions   Markets & opportunities
              Existing MCP        Future MCP contract
                        \               /
                         v             v
                      SHARED TASK CONTRACT
                    status / evidence / outputs
                                 |
                                 v
                       AUDIT + TASK MEMORY
                    metadata first; minimal data
```

The diagram is logical. It does not imply that ZEUS, HERMES, shared storage, or autonomous scheduling are already deployed.

### Component responsibilities

**ZEUS**
- Accepts a goal and clarifies only material missing information.
- Creates a short plan with explicit tasks, owners, dependencies, deadlines and success criteria.
- Routes tasks to specialists based on declared capability, not agent name alone.
- Verifies outputs against evidence and acceptance criteria.
- Retries only transient failures, with strict limits.
- Escalates decisions that require owner approval.
- Produces one concise status report and records unresolved blockers.

**ATENA**
- Owns fitness/human-performance decision support.
- Exposes its existing `atena_decide` and `atena_capabilities` MCP tools.
- Is called only for consequential decisions under uncertainty, competing goals, symptoms affecting training, limited time/recovery, or longitudinal response.
- Does not diagnose or replace clinical judgment.
- Does not become a general-purpose coordinator.

**HERMES**
- Owns market intelligence, macro context, capital-flow analysis and opportunity research.
- Must label facts, interpretations, assumptions and unknowns separately.
- Must attach dated sources to time-sensitive claims.
- Must not execute trades, move funds, or make binding financial commitments.
- Remains a planned specialist until its code, tools, data sources and operating costs are inspected.

**Human owner**
- Sets strategy, priority and risk tolerance.
- Approves publishing, spending, account changes, external messages, financial actions and any irreversible operation.
- Can pause or cancel any task.

## 4. Shared task contract

Use one versioned JSON envelope for all coordinator-to-specialist requests and responses. Keep specialist-specific payloads inside `input` and `output`; do not force every agent into one domain schema.

### Task request

```json
{
  "schema_version": "1.0",
  "task_id": "uuid",
  "parent_task_id": null,
  "created_at": "ISO-8601",
  "requested_by": "human",
  "assigned_to": "atena",
  "task_type": "fitness.next_action_decision",
  "objective": "Choose the next training action given the stated context",
  "input": {},
  "constraints": {
    "deadline": null,
    "max_attempts": 2,
    "budget_limit": 0,
    "data_classification": "sensitive_minimized"
  },
  "acceptance_criteria": [
    "Return a structured decision",
    "State uncertainty and missing information",
    "Include monitoring and reassessment criteria"
  ],
  "approval_required": false
}
```

### Task response

```json
{
  "schema_version": "1.0",
  "task_id": "uuid",
  "agent": "atena",
  "status": "completed",
  "started_at": "ISO-8601",
  "completed_at": "ISO-8601",
  "output": {},
  "evidence": [],
  "uncertainty": [],
  "warnings": [],
  "usage": {
    "model_calls": 0,
    "estimated_cost": 0
  },
  "requires_human_approval": false
}
```

### Required task states

`queued -> assigned -> running -> completed | failed | blocked | cancelled`

- `completed` requires acceptance criteria to be met.
- `blocked` requires a concrete blocker and the smallest needed human action.
- `failed` must include a safe failure reason; never fabricate completion.
- `cancelled` stops retries and downstream work.
- Every state transition is timestamped and attributable.

## 5. Routing and orchestration rules

1. ZEUS classifies the request by domain, risk, required evidence and freshness.
2. ZEUS checks the specialist capability declaration.
3. ZEUS creates the smallest useful task; it does not broadcast every task to every agent.
4. ZEUS sends only the minimum context required by that specialist.
5. The specialist returns a structured result with evidence, uncertainty and limitations.
6. ZEUS validates the result against the acceptance criteria.
7. If evidence is insufficient, ZEUS may request one bounded clarification or retry.
8. ZEUS does not let one specialist silently override another specialist's domain.
9. Conflicting outputs become a human-readable conflict with evidence, not an invented consensus.
10. ZEUS reports what was done, what was not done, and what remains blocked.

### Initial routing table

| Request | Route | Notes |
|---|---|---|
| Fitness programming or training decision | ATENA / coach pilot as appropriate | ATENA only for consequential decision support; the coach pilot owns program generation |
| Markets, liquidity, macro, investment research | HERMES | Research only; no execution |
| Business strategy, project planning, task coordination | ZEUS | May delegate bounded research tasks |
| General factual question | ZEUS directly | Do not invoke specialists without added value |
| Medical diagnosis or emergency | Human/qualified professional | ATENA is not a diagnostic service |
| Trade, purchase, publication, account mutation | Human approval gate | No autonomous execution in v1 |

## 6. Memory and data design

Do not combine all agent memory into one unrestricted conversation history.

Use three logical memory classes:

1. **Task ledger** — task IDs, status, timestamps, owner, specialist, acceptance criteria, evidence references and cost metadata.
2. **Shared project memory** — durable non-sensitive decisions, architecture choices, project status and reusable facts.
3. **Private specialist memory** — domain-specific data with explicit access boundaries. Fitness profiles and workout histories remain in the existing coach data store and are not automatically shared with HERMES.

Design principles:
- Store references and summaries rather than duplicating raw data.
- Do not store credentials, API keys or tokens in task payloads or logs.
- Do not send identifiable or unrelated health information to other agents.
- Apply retention and deletion rules before real-user onboarding.
- Use role-based access and least privilege.
- Keep an auditable record of who/what read or changed a resource.

**Storage decision:** do not create a new database in this phase. First define the schema and access model. A separate coordinator store can be considered only after the runtime and retention requirements are settled. Do not reuse `atena-coach-pilot` as unrestricted shared agent memory.

## 7. Safety, autonomy and approval policy

### Allowed without approval in v1
- Read public information and connected project metadata.
- Draft plans, reports, code changes and recommendations.
- Run bounded, non-destructive tests.
- Read service health, logs and deployment metadata.
- Create an isolated branch or draft pull request for review, when explicitly within the assigned task.

### Approval required
- Production deployment or rollback.
- Changing DNS, environment variables, secrets, billing or access permissions.
- Sending external messages or publishing public content.
- Spending money or starting a paid service.
- Financial transactions or trades.
- Deleting or overwriting user data.
- Opening the fitness product to public users or processing real health data.

### Global guardrails
- Default budget limit: zero new spend.
- Max two retries for transient failures; no retries for validation/permission errors.
- Per-task timeout and cancellation.
- No recursive delegation without a depth limit.
- No agent may grant itself new tools or permissions.
- Treat external web pages, files and tool output as untrusted data, never as system instructions.
- Never report a tool action as successful until its result confirms success.

## 8. Observability and quality gates

For each task record:
- task ID, parent task ID, assigned specialist and status;
- start/end timestamps and latency;
- source/evidence references;
- retry count and failure category;
- model/tool usage and estimated cost;
- acceptance-criteria pass/fail;
- human approval decision, if applicable.

Initial quality targets (proposed, to be measured rather than assumed):
- 100% of consequential actions pass through the approval policy.
- 100% of completed tasks have an evidence or output reference.
- 0 unapproved production mutations.
- 0 credentials in logs or task memory.
- All specialist failures are surfaced honestly.
- Track task completion, rework rate, latency, and cost per completed task.

## 9. Phased implementation

### Phase 2A — contract and boundaries (this document)
- Confirm responsibilities and routing.
- Define task envelope, lifecycle, memory classes and approval gates.
- Preserve existing ATENA interfaces.

### Phase 2B — read-only coordinator skeleton
- Implement a minimal ZEUS API/worker with task creation, routing metadata and status reporting.
- Initially support only direct tasks and ATENA capability discovery / synthetic smoke tests.
- No autonomous writes to production services.
- Keep orchestration deterministic; add an LLM planner only if it provides measurable value.

### Phase 3 — shared task ledger
- Add a separate coordinator store only after schema review.
- Add audit trail, cancellation, timeout and retry handling.
- Do not migrate or copy private coach records.

### Phase 4 — HERMES integration
- Inspect and verify HERMES implementation and data sources.
- Publish a capability contract and read-only MCP tools.
- Connect HERMES through the same task envelope.
- Test specialist isolation and source freshness.

### Phase 5 — controlled pilot
- Run synthetic and then owner-supervised tasks.
- Compare specialist-assisted results with ZEUS-only baseline.
- Measure accuracy, rework, latency, costs and approval burden.
- Expand autonomy only after each safety and quality gate passes.

## 10. Immediate next actions

1. Resolve the failing offline checks in `tiny-figolla-016703` before using its current branch as a production-quality base.
2. Confirm which ATENA coach deployment is the canonical pilot UI/API; keep the decision engine and program-generation workflow clearly separated.
3. Inspect HERMES source, deployment, data sources and operating cost before integration.
4. Choose the lowest-cost coordinator runtime only after these checks. A small Cloudflare Worker is a candidate, not yet a decision.
5. Build Phase 2B on an isolated branch and validate with synthetic tasks only.

## 11. Explicit non-goals

- No three-agent swarm with unrestricted mutual delegation.
- No shared unrestricted chat history.
- No automatic trades, purchases, public publishing or production deployments.
- No new paid model/API requirement.
- No public launch of the fitness coach from this architecture work.
- No claim that ZEUS or HERMES is already implemented.

---

**Decision:** use ZEUS as a thin coordinator, ATENA and HERMES as bounded specialists, and a versioned task contract as their shared interface. Start with read-only orchestration and expand autonomy only when evidence, cost and safety are demonstrated.
