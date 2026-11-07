import pytest
from flask import Flask

from coach_routes import coach_bp


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "test-only-token")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()


def test_movement_assessment_requires_pilot_token(client):
    response = client.post(
        "/coach/movement-assessment",
        json={"assessment": {"squat": "comfortable"}},
    )
    assert response.status_code == 403


def test_movement_assessment_returns_stateless_conservative_result(client):
    response = client.post(
        "/coach/movement-assessment",
        headers={"X-Pilot-Token": "test-only-token"},
        json={"assessment": {"squat": "comfortable", "hinge": "needs_support"}},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["stored"] is False
    assert body["source"] == "self_reported_movement_assessment"
    assert body["assessment"]["automatic_programme_change"] == "none"
    assert body["assessment"]["coaching_guidance"]["consider_supported_or_simpler_variation"] == ["hinge"]


def test_movement_assessment_rejects_invalid_payload(client):
    response = client.post(
        "/coach/movement-assessment",
        headers={"X-Pilot-Token": "test-only-token"},
        json={"assessment": {"jump": "comfortable"}},
    )
    assert response.status_code == 400


def test_movement_assessment_preflight_is_available(client):
    response = client.options("/coach/movement-assessment")
    assert response.status_code == 204


def test_program_route_returns_assessment_as_context_without_changing_program(monkeypatch, client):
    import coach_routes

    called = {}

    def fake_generate_program(profile, feedback=None, movement_assessment=None, feedback_history=None):
        called["profile"] = profile
        called["feedback"] = feedback
        called["movement_assessment"] = movement_assessment
        return {"goal": "functional", "sessions": [{"session": 1, "exercises": []}]}

    monkeypatch.setattr(coach_routes, "generate_program", fake_generate_program)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json={
            "profile": {"goal": "functional", "experience": "beginner"},
            "movement_assessment": {"squat": "needs_support", "hinge": "comfortable"},
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert called["profile"]["goal"] == "functional"
    assert called["movement_assessment"] == {"squat": "needs_support", "hinge": "comfortable"}
    assert body["program"]["goal"] == "functional"
    assert body["movement_assessment"]["is_diagnosis"] is False
    assert body["movement_assessment"]["automatic_programme_change"] == "none"
    assert body["movement_assessment"]["coaching_guidance"]["consider_supported_or_simpler_variation"] == ["squat"]
    assert body["movement_assessment_stored"] is False


def test_program_route_rejects_invalid_movement_assessment_without_generating(monkeypatch, client):
    import coach_routes

    def should_not_run(*args, **kwargs):
        raise AssertionError("Programme generator must not run for invalid assessment.")

    monkeypatch.setattr(coach_routes, "generate_program", should_not_run)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json={
            "profile": {"goal": "functional", "experience": "beginner"},
            "movement_assessment": {"jump": "comfortable"},
        },
    )
    assert response.status_code == 400
    assert "Neznane" in response.get_json()["error"]
