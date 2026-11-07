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



def test_program_endpoint_accepts_nested_profile_and_reduces_hard_feedback(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "profile": {
                "goal": "hypertrophy", "experience": "intermediate",
                "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
                "session_minutes": 60,
            },
            "feedback": {"difficulty": "hard", "completed": True, "discomfort": "no"},
        },
    )
    assert response.status_code == 200
    program = response.get_json()["program"]
    assert program["feedback_applied"]["difficulty"] == "hard"
    assert program["methodology"]["last_session_adjustment"] == "reduce_sets_increase_reserve"
    first = program["sessions"][0]["exercises"][0]["prescription"]
    assert first["sets"] == 2
    assert first["rir"] == 4


def test_program_endpoint_holds_after_easy_feedback_instead_of_auto_progressing(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "profile": {
                "goal": "hypertrophy", "experience": "intermediate",
                "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
                "session_minutes": 60,
            },
            "feedback": {"difficulty": "easy", "completed": True, "discomfort": "no"},
        },
    )
    assert response.status_code == 200
    program = response.get_json()["program"]
    assert program["methodology"]["last_session_adjustment"] == "hold_and_progress_by_rule"
    assert program["sessions"][0]["exercises"][0]["prescription"]["sets"] == 3


def test_program_endpoint_blocks_automatic_adaptation_when_discomfort_reported(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "profile": {
                "goal": "hypertrophy", "experience": "intermediate",
                "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
                "session_minutes": 60,
            },
            "feedback": {"difficulty": "hard", "completed": False, "discomfort": "yes"},
        },
    )
    assert response.status_code == 409
    assert response.get_json()["blocked"] is True


def test_program_endpoint_uses_supplied_prior_feedback_history_for_progression(monkeypatch):
    client = _client(monkeypatch)
    profile = {
        "goal": "hypertrophy", "experience": "intermediate",
        "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
        "session_minutes": 60,
    }
    before = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={"profile": profile},
    )
    feedback = {"difficulty": "easy", "completed": True, "discomfort": "no", "recovery": "normal"}
    after = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "profile": profile,
            "feedback": feedback,
            "feedback_history": [feedback],
        },
    )
    assert before.status_code == after.status_code == 200
    before_reps = before.get_json()["program"]["sessions"][0]["exercises"][0]["prescription"]["reps"]
    after_reps = after.get_json()["program"]["sessions"][0]["exercises"][0]["prescription"]["reps"]
    assert before_reps != after_reps
