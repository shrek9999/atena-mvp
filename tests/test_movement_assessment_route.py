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


def test_program_route_requires_all_six_pattern_decisions(monkeypatch, client):
    import coach_routes
    from training.movement_coaching import PATTERN_DEFINITIONS

    def should_not_run(*args, **kwargs):
        raise AssertionError("Programme generator must not run before all six patterns are assessed.")

    monkeypatch.setattr(coach_routes, "generate_program", should_not_run)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json={
            "movement_assessment_consent": True,
            "profile": {"goal": "functional", "experience": "beginner"},
        },
    )
    assert response.status_code == 409
    body = response.get_json()
    assert body["assessment_required"] is True
    assert set(body["missing_patterns"]) == set(PATTERN_DEFINITIONS)


def test_program_route_rejects_legacy_partial_assessment(monkeypatch, client):
    import coach_routes

    def should_not_run(*args, **kwargs):
        raise AssertionError("Legacy partial assessment must not reach programme generation.")

    monkeypatch.setattr(coach_routes, "generate_program", should_not_run)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json={
            "movement_assessment_consent": True,
            "profile": {"goal": "functional", "experience": "beginner"},
            "movement_assessment": {"squat": "needs_support", "hinge": "comfortable"},
        },
    )
    assert response.status_code == 409
    assert response.get_json()["assessment_required"] is True


def test_program_route_requires_explicit_movement_assessment_consent(client):
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    decisions = {
        pattern: build_movement_decision(pattern, "READY")
        for pattern in PATTERN_DEFINITIONS
    }
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json={
            "profile": {
                "goal": "functional", "experience": "beginner",
                "equipment": ["bodyweight"], "sessions_per_week": 2,
                "session_minutes": 45,
            },
            "movement_decisions": decisions,
        },
    )
    assert response.status_code == 403
    assert response.get_json()["consent_required"] is True


def test_program_route_blocks_when_all_six_patterns_are_unassessable(monkeypatch, client):
    import coach_routes
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    def should_not_run(*args, **kwargs):
        raise AssertionError("No programme may be generated without at least one assessable pattern.")

    monkeypatch.setattr(coach_routes, "generate_program", should_not_run)
    decisions = {
        pattern: build_movement_decision(
            pattern, "UNASSESSABLE",
            decision_reason="Naloga ni bila ocenjena.",
        )
        for pattern in PATTERN_DEFINITIONS
    }
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json={
            "movement_assessment_consent": True,
            "profile": {
                "goal": "functional", "experience": "beginner",
                "equipment": ["bodyweight"], "sessions_per_week": 2,
                "session_minutes": 45,
            },
            "movement_decisions": decisions,
        },
    )
    assert response.status_code == 409
    assert response.get_json()["assessment_required"] is True
    assert "vsaj en vzorec varno oceniti" in response.get_json()["message"]


def test_program_route_passes_structured_six_pattern_decisions(monkeypatch, client):
    import coach_routes
    from training.movement_coaching import build_movement_decision

    called = {}

    def fake_generate_program(profile, feedback=None, movement_assessment=None, movement_decisions=None):
        called["movement_decisions"] = movement_decisions
        return {
            "goal": "hypertrophy",
            "sessions": [{"session": 1, "exercises": [], "learning_tasks": []}],
            "movement_adaptation": {
                "source": "structured_six_pattern_decisions",
                "is_diagnosis": False,
                "events": [],
                "summary": None,
            },
        }

    monkeypatch.setattr(coach_routes, "generate_program", fake_generate_program)
    decisions = {
        pattern: build_movement_decision(
            pattern, "READY",
            decision_reason="Osnovno gibanje je po samooceni udobno in nadzorovano.",
        )
        for pattern in ("squat", "hinge", "horizontal_push", "horizontal_pull", "vertical_push", "lunge")
    }
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json={
            "movement_assessment_consent": True,
            "profile": {
                "goal": "hypertrophy", "experience": "beginner",
                "equipment": ["bodyweight", "dumbbell", "chair", "wall", "household_support"],
                "sessions_per_week": 2, "session_minutes": 45,
            },
            "movement_decisions": decisions,
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert set(called["movement_decisions"]) == set(decisions)
    assert called["movement_decisions"]["squat"]["decision"] == "READY"
    assert body["movement_assessment_applied"] is True
    assert body["movement_decisions_stored"] is False
    assert body["movement_adaptation"]["source"] == "structured_six_pattern_decisions"
