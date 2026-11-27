from flask import Flask

from coach_routes import coach_bp


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "phase18-scope-secret")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_VERSION", "phase18-scope-v1")
    monkeypatch.setenv("ATENA_ALLOW_SQLITE_STORAGE", "true")
    monkeypatch.setenv("ATENA_DATABASE_URL", f"sqlite:///{tmp_path / 'phase18-scope.sqlite3'}")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    client = app.test_client()
    created = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "phase18-scope-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "phase18-scope-v1",
            "health_data_consent": False,
            "profile": {
                "goal": "functional",
                "experience": "beginner",
                "equipment": ["bodyweight", "resistance_band"],
                "sessions_per_week": 2,
                "session_minutes": 45,
            },
        },
    )
    assert created.status_code == 201
    payload = created.get_json()
    return client, payload["profile"]["profile_id"], payload["profile_access_token"]


def test_session_specific_difficulty_source_is_persisted_and_returned_as_targeted_review(
    monkeypatch, tmp_path
):
    client, profile_id, token = _client(monkeypatch, tmp_path)
    saved = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-08",
            "duration_minutes": 30,
            "difficulty": "hard",
            "recovery": "good",
            "completed": False,
            "completion_reason": "high_difficulty",
            "difficulty_scope": "exercise",
            "affected_exercise_id": "push_up",
            "exercises": [],
        },
    )
    assert saved.status_code == 201
    assert saved.get_json()["session"]["session"]["affected_exercise_id"] == "push_up"

    adaptation = client.get(
        f"/coach/profile/{profile_id}/adaptation",
        headers={"X-Profile-Token": token},
    )
    assert adaptation.status_code == 200
    decision = adaptation.get_json()["adaptive_decision"]
    assert decision["decision"] == "review_affected_exercise"
    assert decision["scope"] == "affected_exercise"
    assert decision["affected_exercise_id"] == "push_up"


def test_exercise_scope_requires_a_valid_catalogue_exercise(monkeypatch, tmp_path):
    client, profile_id, token = _client(monkeypatch, tmp_path)
    response = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-08",
            "duration_minutes": 30,
            "difficulty": "hard",
            "recovery": "good",
            "completed": False,
            "completion_reason": "high_difficulty",
            "difficulty_scope": "exercise",
            "affected_exercise_id": "not-a-real-exercise",
            "exercises": [],
        },
    )
    assert response.status_code == 400
