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
