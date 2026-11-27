# ATENA Phase 5 — adaptive programme decisions

## Objective

Combine the existing session, exercise-progression, longitudinal and conditioning
signals into one explainable next-step decision with the narrowest justified scope.

## Decision contract

Every decision returns:
- a stable decision code and scope;
- reason codes and a plain-language explanation;
- the intended objective;
- measurable success signals that explain how the next comparable training will validate the decision;
- whether progression is allowed;
- an explicit statement that no programme mutation happened;
- a clarifying question when the available evidence cannot distinguish causes.

## Key rules

1. An incomplete session is not automatically treated as an excessive training dose.
   The engine distinguishes time constraints, high difficulty, poor recovery,
   external interruption and unknown causes when the structured reason is supplied.
2. Poor recovery, symptoms and structured movement-control concerns take precedence over positive progression signals.
3. Multi-week decline prompts review of the affected exercise, not automatic
   reduction of the whole programme.
4. Positive progression remains exercise-specific; one successful exercise does
   not increase the weekly programme volume.
5. A previous adjustment marked worse/no-change is not repeated. An untried
   adjustment is not silently replaced by another proposal.
6. Missing or mixed evidence results in a hold/clarifying question, not a guess.

## Integration status

The decision layer is wired into the authenticated progress, adaptation and
next-program API responses on the isolated phase-5 branch. The session API
accepts structured completion reasons and adaptation outcomes. Feedback is
bound to the deterministic ID of the latest decision ATENA issued.

The companion website integration is prepared in PR #53 of
shrek9999/tiny-figolla-016703. It adds structured workout logging, a first-party
proxy and a decision panel. The stateless POST /coach/adaptive-decision endpoint
accepts a bounded history snapshot (up to 50 sessions), validates its structure,
verifies feedback IDs against the preceding history and does not persist the
snapshot on Render.

The end-to-end path is not active until both draft PRs are reviewed and merged,
the backend is deployed to the closed Render pilot, and the Cloudflare Pages
preview is tested against that deployment.

## Safety and cost

No model calls, new dependencies, database migrations, secrets, paid services,
or production deployment are required by this module.
