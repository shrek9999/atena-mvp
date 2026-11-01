from flask import Flask

import coach_routes
from coach_routes import coach_bp


def test_adaptation_endpoint_is_authenticated_and_non_automatic(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    client = app.test_client()

    def get_profile(profile_id, token):
        if token != "profile-token":
            from coach_store import ProfileNotFound
            raise ProfileNotFound()
        return {"profile_id": profile_id, "profile": {"goal": "strength"}}

    monkeypatch.setattr(coach_routes, "store_get_profile", get_profile)
    monkeypatch.setattr(coach_routes, "store_list_sessions", lambda profile_id, token, limit=50: [
        {"session_date": "2026-11-01", "session": {
            "completed": True, "difficulty": "hard", "exercises": [],
        }},
        {"session_date": "2026-10-29", "session": {
            "completed": True, "difficulty": "hard", "exercises": [],
        }},
    ])

    denied = client.get("/coach/profile/example/adaptation")
    assert denied.status_code == 404
    response = client.get(
        "/coach/profile/example/adaptation",
        headers={"X-Profile-Token": "profile-token"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["adaptation"]["decision"] == "review_volume_reduction"
    assert payload["automatic_program_changes"] is False
