# ATENA Phase 5 — adaptive programme decisions

## Objective

Combine the existing session, exercise-progression, longitudinal and conditioning
signals into one explainable next-step decision with the narrowest justified scope.

## Decision contract

Every decision returns:
- a stable decision code and scope;
- reason codes and a plain-language explanation;
- the intended objective;
- whether progression is allowed;
- an explicit statement that no programme mutation happened;
- a clarifying question when the available evidence cannot distinguish causes.

## Key rules

1. An incomplete session is not automatically treated as an excessive training dose.
   The engine distinguishes time constraints, high difficulty, poor recovery,
   external interruption and unknown causes when the structured reason is supplied.
2. Poor recovery and symptoms take precedence over positive progression signals.
3. Multi-week decline prompts review of the affected exercise, not automatic
   reduction of the whole programme.
4. Positive progression remains exercise-specific; one successful exercise does
   not increase the weekly programme volume.
5. A previous adjustment marked worse/no-change is not repeated. An untried
   adjustment is not silently replaced by another proposal.
6. Missing or mixed evidence results in a hold/clarifying question, not a guess.

## Integration boundary

This phase introduces the pure decision layer and its regression tests. The
session API and website must next expose structured completion reasons and
adaptation outcomes, then call this layer from the authenticated adaptation
and next-program routes. Until that integration is complete, this module is
not yet the active production decision path.

## Safety and cost

No model calls, new dependencies, database migrations, secrets, paid services,
or production deployment are required by this module.
