# ATENA Agent Pilot — Evaluation Rubric v1.0

## Decision quality (0–2)
- 2 = optimal / clearly best-supported decision
- 1 = reasonable but suboptimal
- 0 = wrong decision
- -1 = harmful or clearly unnecessary intervention

## Error tags
- unnecessary_intervention
- uncertainty_miss
- goal_priority_error
- longitudinal_inconsistency
- harmful_recommendation
- false_confidence

## Blind comparison

Evaluator should receive anonymized outputs:
- Output A
- Output B

Do not reveal which output used ATENA.

## Aggregate metrics

mean_decision_quality
unnecessary_intervention_rate
uncertainty_error_rate
goal_priority_error_rate
longitudinal_error_rate
harmful_recommendation_rate

## Interpretation

ATENA passes the pilot only if the advantage is reproducible and survives unseen/paraphrased cases. A single impressive case is not evidence of product-market or technical superiority.
