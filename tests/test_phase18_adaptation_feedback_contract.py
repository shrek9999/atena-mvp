from flask import Flask

from coach_routes import coach_bp


def _profile_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "phase18-pilot-secret")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_VERSION", "phase18-test-v1")
    monkeypatch.setenv("ATENA_ALLOW_SQLITE_STORAGE", "true")
    monkeypatch.setenv("ATENA_DATABASE_URL", f"sqlite:///{tmp_path / 'phase18.sqlite3'}")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    client = app.test_client()
    created = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "phase18-pilot-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "phase18-test-v1",
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


def _log_session(client, profile_id, token, day, adaptation_response=None):
    payload = {
        "session_date": day,
        "duration_minutes": 30,
        "difficulty": "moderate",
        "recovery": "good",
        "completed": True,
        "exercises": [],
    }
    if adaptation_response is not None:
        payload["adaptation_response"] = adaptation_response
    return client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json=payload,
    )


def test_adaptation_feedback_contract_is_returned_and_persisted_with_next_session(
    monkeypatch, tmp_path
):
    client, profile_id, token = _profile_client(monkeypatch, tmp_path)
    first = _log_session(client, profile_id, token, "2026-11-07")
    assert first.status_code == 201

    guidance = client.get(
        f"/coach/profile/{profile_id}/adaptation",
        headers={"X-Profile-Token": token},
    )
    assert guidance.status_code == 200
    decision = guidance.get_json()["adaptive_decision"]
    assert decision["feedback_contract"]["field"] == "adaptation_response"
    assert decision["adaptation_id"]

    response = {"adaptation_id": decision["adaptation_id"], "outcome": "helped"}
    second = _log_session(
        client, profile_id, token, "2026-11-08", adaptation_response=response
    )
    assert second.status_code == 201
    assert second.get_json()["session"]["session"]["adaptation_response"] == response

    history = client.get(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
    )
    assert history.status_code == 200
    assert history.get_json()["sessions"][0]["session"]["adaptation_response"] == response


def test_adaptation_feedback_rejects_stale_or_fabricated_decision_id(
    monkeypatch, tmp_path
):
    client, profile_id, token = _profile_client(monkeypatch, tmp_path)
    first = _log_session(client, profile_id, token, "2026-11-07")
    assert first.status_code == 201

    response = _log_session(
        client,
        profile_id,
        token,
        "2026-11-08",
        adaptation_response={"adaptation_id": "not-the-current-id", "outcome": "helped"},
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "adaptation_id_mismatch"
