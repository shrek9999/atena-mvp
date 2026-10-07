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

## Agent behavior

The agent should:
1. Gather the available context.
2. Decide whether decision support is useful.
3. Call ATENA with the structured context.
4. Use ATENA's decision as decision support, not as an unquestionable instruction.
5. Produce the final user-facing response.
6. Preserve uncertainty when ATENA requests more information.

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
