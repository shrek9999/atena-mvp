from flask import Flask

import coach_routes
from coach_routes import coach_bp


def test_progress_endpoint_returns_authenticated_non_prescriptive_summary(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    client = app.test_client()
    def get_profile(profile_id, token):
        if token != "profile-secret":
            from coach_store import ProfileNotFound
            raise ProfileNotFound()
        return {"profile_id": profile_id, "profile": {"goal": "strength"}}

    monkeypatch.setattr(coach_routes, "store_get_profile", get_profile)
    monkeypatch.setattr(coach_routes, "store_list_sessions", lambda profile_id, token, limit=50: [
        {"session_date": "2026-10-30", "session": {
            "completed": True, "difficulty": "moderate",
            "exercises": [{"exercise_id": "barbell_squat", "sets_completed": 3,
                           "reps_completed": 8, "load_kg": 60.0}],
        }},
        {"session_date": "2026-11-01", "session": {
            "completed": True, "difficulty": "moderate",
            "exercises": [{"exercise_id": "barbell_squat", "sets_completed": 3,
                           "reps_completed": 8, "load_kg": 62.5}],
        }},
    ])
    denied = client.get("/coach/profile/example/progress")
    assert denied.status_code == 404
    response = client.get(
        "/coach/profile/example/progress",
        headers={"X-Profile-Token": "profile-secret"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["progress"]["completed_sessions"] == 2
    assert payload["progress"]["exercise_trends"][0]["status"] == "load_increased"
    assert payload["longitudinal_progression"]["method"] == "last_five_comparable_exposures"
    assert payload["longitudinal_progression"]["automatic_program_changes"] is False
    assert payload["automatic_load_changes"] is False
