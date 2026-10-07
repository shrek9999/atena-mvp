# ATENA — Decision Intelligence for AI Fitness Agents

ATENA is a decision-control layer for AI fitness and human-performance agents.

Core principle: **ATENA does not optimize the program. ATENA optimizes the next decision.**

## API
- GET /health
- GET /capabilities
- POST /decision

Production URL: https://atena-mvp.onrender.com

## Decision loop
GOAL → CONTEXT → CONSTRAINTS → PRIORITY → STATE → STIMULUS → COST → HYPOTHESES → OPTIONS → DECISION → ACTION → MEASURE → INTERPRET → ADAPT

ATENA emphasizes:
- goal priority
- uncertainty-first decisions
- minimum intervention
- stimulus-cost reasoning
- response over prescription
- longitudinal consistency

## Run
pip install -r requirements.txt
gunicorn app:app

## Contract
See openapi.json and agent_contract.json.


## v1.0 hardening

The v1.0 decision engine includes:
- goal-priority reasoning
- uncertainty-first data collection
- minimum-intervention modification
- stimulus-cost and fatigue convergence checks
- longitudinal response handling
- explicit separation of absolute metrics from change/delta signals
- explicit handling of negative symptom statements
- standardized decision types: maintain, progress, reduce, modify, collect_data, refer

### Regression validation

A new 20-case unseen robustness suite is included in `tests/unseen_20_cases.json` with an executable pytest regression test in `tests/test_unseen_20.py`.

This suite is a development/engineering validation set, not independent clinical validation or proof that ATENA outperforms a general LLM.
## Real-world agent pilot

ATENA is intended to be used by AI agents as a decision-intelligence layer, not as a consumer application for human coaches. The first real-world validation compares the same agent **alone** vs **agent + ATENA** on identical decision cases. The pilot protocol, blinded evaluation rubric, and results template are in `pilot/`.
