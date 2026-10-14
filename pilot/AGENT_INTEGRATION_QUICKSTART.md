# ATENA — Agent Integration Quickstart v1.0

ATENA is a decision-intelligence layer for AI agents.

## Minimal integration

Use ATENA as a tool when the agent must make or adapt a training/human-performance decision.

### HTTP

POST:

`https://atena-mvp.onrender.com/decision`

JSON:

```json
{
  "goal": {
    "primary": "strength",
    "secondary": "aerobic_fitness"
  },
  "person": {},
  "constraints": {},
  "state": {
    "performance": "declining",
    "rpe": "increased",
    "recovery": "worse",
    "symptoms": "none"
  },
  "response": {},
  "question": "What should the agent do next?",
  "history": {}
}
```

ATENA returns a structured decision containing:
- decision
- assessment
- action
- monitor
- decision_rule
- uncertainty
- confidence
- reason_codes
- priority
- required_information
- next_review
- decision_support: why ATENA's decision adds value, detected signals, and when to reassess

## Agent behavior

The agent should:
1. Gather the available context and identify the primary goal, constraints, current state, and prior response.
2. Call ATENA before making a consequential change when signals conflict, recovery cost is rising, symptoms are present, goals compete, time/recovery is constrained, or the decision depends on history.
3. Avoid calling ATENA for simple factual questions or routine decisions with no meaningful trade-off.
4. Use the returned decision, detected signals, value_added, and decision_boundary to explain the recommendation; do not treat confidence as a clinical probability.
5. Preserve uncertainty and request the listed missing information when ATENA returns collect_data.
6. Reassess when the decision boundary is triggered; do not blindly repeat a past decision.

## Evaluation

Run the same case twice:

**A — Agent alone**
- No ATENA call.

**B — Agent + ATENA**
- Same input.
- ATENA available as a tool.

Do not reveal the arm to the evaluator. Compare decision quality rather than wording.

## First five cases

### Case 1 — stable
Primary strength. Performance, RPE and recovery stable. No symptoms.
Expected evaluation focus: unnecessary intervention.

### Case 2 — improving
Strength improving, RPE decreasing, recovery good.
Expected evaluation focus: appropriate progression.

### Case 3 — uncertain decline
Performance declining but no recovery/RPE context.
Expected evaluation focus: uncertainty management.

### Case 4 — convergent fatigue
Strength declining, RPE increased, recovery worse.
Expected evaluation focus: whether the agent reduces training cost rather than adding stimulus.

### Case 5 — symptom
Knee pain during squat.
Expected evaluation focus: whether the agent modifies the relevant stimulus rather than blindly progressing.

## Important

These cases are test cases, not proof of superiority. A positive result requires blind evaluation and replication on unseen cases.


## What makes ATENA useful to an agent

ATENA is not intended to produce a second generic opinion. Its output should help the agent decide **whether to change anything, what to change first, what evidence supports that change, and what would cause the decision to change**. The new `decision_support` object makes this explicit. This is a product hypothesis to validate, not a claim of proven superiority.
