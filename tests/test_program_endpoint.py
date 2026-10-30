from flask import Flask

from coach_routes import coach_bp


def _client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "test-only-secret")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()


def test_program_endpoint_requires_pilot_token(monkeypatch):
    response = _client(monkeypatch).post("/coach/program", json={
        "goal": "hypertrophy", "experience": "intermediate",
        "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
        "session_minutes": 60,
    })
    assert response.status_code == 403


def test_program_endpoint_returns_catalogue_backed_plan(monkeypatch):
    response = _client(monkeypatch).post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "goal": "hypertrophy", "experience": "intermediate",
            "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
            "session_minutes": 60,
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "curated_exercise_catalogue"
    assert len(body["program"]["sessions"]) == 2


def test_program_endpoint_rejects_invalid_profile(monkeypatch):
    response = _client(monkeypatch).post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "goal": "miracle", "experience": "beginner",
            "equipment": ["bodyweight"], "sessions_per_week": 2,
            "session_minutes": 60,
        },
    )
    assert response.status_code == 400
