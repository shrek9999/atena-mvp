from flask import Flask

from coach_routes import coach_bp


def client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()


def session(day, *, completed=True, difficulty="moderate", recovery="normal",
            completion_reason=None, adaptation_response=None):
    value = {
        "completed": completed,
        "difficulty": difficulty,
        "recovery": recovery,
        "exercises": [],
    }
    if completion_reason is not None:
        value["completion_reason"] = completion_reason
    if adaptation_response is not None:
        value["adaptation_response"] = adaptation_response
    return {"session_date": day, "session": value}


def post(client, sessions, token="pilot-test-secret"):
    return client.post(
        "/coach/adaptive-decision",
        headers={"X-Pilot-Token": token},
        json={"sessions": sessions},
    )


def test_adaptive_decision_endpoint_requires_pilot_token(monkeypatch):
    response = post(client(monkeypatch), [], token="")
    assert response.status_code == 403


def test_adaptive_decision_endpoint_distinguishes_time_shortage(monkeypatch):
    response = post(client(monkeypatch), [
        session("2026-11-03", completed=False, difficulty="unknown",
                completion_reason="time_constraint")
    ])
    assert response.status_code == 200
    result = response.get_json()["adaptive_decision"]
    assert result["decision"] == "restructure_session"
    assert result["scope"] == "session_structure"
    assert result["automatic_program_changes"] is False
    assert result["adaptation_id"]


def test_adaptive_decision_endpoint_distinguishes_poor_recovery(monkeypatch):
    response = post(client(monkeypatch), [
        session("2026-11-03", completed=False, difficulty="hard",
                recovery="poor", completion_reason="poor_recovery")
    ])
    assert response.status_code == 200
    assert response.get_json()["adaptive_decision"]["decision"] == "recovery_review"


def test_adaptive_decision_endpoint_rejects_unstructured_or_health_fields(monkeypatch):
    response = post(client(monkeypatch), [{
        "session_date": "2026-11-03",
        "session": {"completed": True, "difficulty": "moderate",
                    "recovery": "normal", "exercises": [],
                    "free_text": "some note"}
    }])
    assert response.status_code == 400


def test_adaptive_decision_endpoint_accepts_valid_previous_outcome(monkeypatch):
    api = client(monkeypatch)
    previous = session("2026-11-02", completed=False, difficulty="unknown",
                       completion_reason="time_constraint")
    first = post(api, [previous]).get_json()["adaptive_decision"]
    latest = session(
        "2026-11-03",
        adaptation_response={"adaptation_id": first["adaptation_id"], "outcome": "worse"},
    )
    response = post(api, [latest, previous])
    assert response.status_code == 200
    decision = response.get_json()["adaptive_decision"]
    assert decision["decision"] == "reassess_previous_change"
    assert decision["previous_adaptation_id"] == first["adaptation_id"]


def test_adaptive_decision_endpoint_rejects_forged_previous_outcome_id(monkeypatch):
    api = client(monkeypatch)
    previous = session("2026-11-02")
    latest = session(
        "2026-11-03",
        adaptation_response={"adaptation_id": "forged-adaptation-id", "outcome": "worse"},
    )
    response = post(api, [latest, previous])
    assert response.status_code == 409
    assert response.get_json()["code"] == "adaptation_id_mismatch"


def test_adaptive_decision_endpoint_bounds_history_size(monkeypatch):
    sessions = [session(f"2026-10-{(i % 28) + 1:02d}") for i in range(51)]
    response = post(client(monkeypatch), sessions)
    assert response.status_code == 400
