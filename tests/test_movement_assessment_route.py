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
