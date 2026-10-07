# ATENA — Agent Pilot v1.0

## Purpose

Validate whether an AI agent produces better decisions with ATENA than the same agent without ATENA.

**Unit of analysis:** AI-agent decision, not human user behavior.

**Primary comparison**
- Arm A: Agent alone
- Arm B: Agent + ATENA

ATENA is called as a decision-control tool between agent reasoning and the final action.

## Protocol

1. Give the same case to the same agent in both arms.
2. Arm A: agent answers without ATENA.
3. Arm B: agent receives the same case and may call `POST /decision`.
4. Store the final decision from both arms.
5. Score both outputs blind where possible.
6. Do not tune ATENA to individual cases during the pilot.
7. Keep development cases separate from unseen cases.

## Primary metrics

- Decision quality: 0–2
- Unnecessary intervention rate
- Uncertainty error rate
- Goal-priority error rate
- Longitudinal consistency error rate
- Harmful recommendation rate

## Success criterion

ATENA is promising only if Agent + ATENA shows a reproducible improvement over Agent alone on at least one meaningful decision-quality dimension, without introducing a comparable new error.

This pilot is not clinical validation and does not establish that ATENA universally outperforms LLMs.

## Agent tool contract

Endpoint:
`POST https://atena-mvp.onrender.com/decision`

Input:
`goal, person, constraints, state, response, question, history`

Output:
`assessment, decision, action, monitor, decision_rules, uncertainty, confidence, reason_codes, priority, required_information, next_review, schema_version`

## Evaluation

Use blinded labels A/B rather than revealing which arm used ATENA to the evaluator.

Record:
- case_id
- arm
- final_decision
- action
- score
- error_tags
- evaluator_note

## Next gate

Run the first 20 cases through both arms. Do not change production logic until the results show a repeated failure pattern.
