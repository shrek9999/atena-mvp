# ATENA MVP v0.1

Minimal public-service prototype.

## Endpoints

GET /health
POST /decision

## Run locally

pip install -r requirements.txt
python app.py

The service listens on port 8080.

## Example request

{
  "goal": {"primary": "strength"},
  "person": {"age": 45},
  "constraints": {"sessions_per_week": 5},
  "state": {"program": "strength/hypertrophy"},
  "response": {
    "performance": "declining",
    "rpe": 8.5,
    "recovery": "declining",
    "symptoms": "none"
  },
  "question": "Should the program be changed?"
}
