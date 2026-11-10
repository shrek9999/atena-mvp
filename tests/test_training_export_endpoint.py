from flask import Flask

import coach_routes
from coach_routes import coach_bp


def test_profile_export_requires_profile_token_and_disables_caching(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    client = app.test_client()

    def get_profile(profile_id, token):
        if token != "valid-token":
            from coach_store import ProfileNotFound
            raise ProfileNotFound()
        return {
            "profile_id": profile_id,
            "profile": {"goal": "strength"},
            "health_data_consent": False,
        }

    def get_sessions(profile_id, token, limit=50):
        assert limit == 5000
        return [{
            "session_id": "session-1",
            "session_date": "2026-11-01",
            "session": {"completed": True, "exercises": []},
        }]

    monkeypatch.setattr(coach_routes, "store_get_profile", get_profile)
    monkeypatch.setattr(coach_routes, "store_list_sessions", get_sessions)
    monkeypatch.setattr(coach_routes, "store_get_movement_assessment", lambda profile_id, token: None)
    monkeypatch.setattr(coach_routes, "store_list_program_versions", lambda profile_id, token, limit=10: [])

    denied = client.get("/coach/profile/example/export")
    assert denied.status_code == 404

    response = client.get(
        "/coach/profile/example/export",
        headers={"X-Profile-Token": "valid-token"},
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, private"
    assert "attachment" in response.headers["Content-Disposition"]
    payload = response.get_json()
    assert payload["export_version"] == "1.1"
    assert payload["movement_assessment"] is None
    assert payload["program_versions"] == []
    assert payload["profile"]["profile_id"] == "example"
    assert len(payload["sessions"]) == 1
