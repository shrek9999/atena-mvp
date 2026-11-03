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
    def logged_session(day):
        return {
            "session_date": day,
            "session": {
                "completed": True,
                "difficulty": "moderate",
                "recovery": "good",
                "exercises": [{
                    "exercise_id": "barbell_squat",
                    "sets_completed": 3,
                    "reps_completed": 10,
                    "load_kg": 60.0,
                    "rir": 3,
                    "planned_sets": 3,
                    "target_reps_min": 8,
                    "target_reps_max": 12,
                    "execution_quality": "controlled",
                    "set_results": [
                        {"reps": 10, "load_kg": 60.0, "rir": 3},
                        {"reps": 10, "load_kg": 60.0, "rir": 3},
                        {"reps": 10, "load_kg": 60.0, "rir": 3},
                    ],
                }],
            },
        }

    monkeypatch.setattr(coach_routes, "store_list_sessions", lambda profile_id, token, limit=50: [
        logged_session(day) for day in (
            "2026-10-01", "2026-10-08", "2026-10-15", "2026-10-22", "2026-10-29"
        )
    ])
    denied = client.get("/coach/profile/example/progress")
    assert denied.status_code == 404
    response = client.get(
        "/coach/profile/example/progress",
        headers={"X-Profile-Token": "profile-secret"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["progress"]["completed_sessions"] == 5
    assert payload["progress"]["exercise_trends"][0]["status"] == "stable"
    assert payload["longitudinal_progression"]["method"] == "last_five_comparable_exposures"
    assert payload["longitudinal_progression"]["automatic_program_changes"] is False
    assert payload["longitudinal_progression"]["exercise_trends"][0]["status"] == "plateau_candidate"
    assert payload["longitudinal_progression"]["exercise_trends"][0]["review"] == "coach_review_required"
    assert payload["training_cycle"]["cycle_week"] == 3
    assert payload["training_cycle"]["phase"] == "progression_review"
    assert payload["training_cycle"]["automatic_program_changes"] is False
    assert payload["automatic_load_changes"] is False
