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
            user_report={"status": "not_assessed"},
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


def test_program_route_requires_explicit_user_report_for_each_pattern(client):
    from training.movement_coaching import PATTERN_DEFINITIONS

    decisions = {
        pattern: {"movement_pattern": pattern, "decision": "READY"}
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
    assert response.status_code == 400
    assert set(response.get_json()["invalid_report_patterns"]) == set(PATTERN_DEFINITIONS)


def test_program_route_rejects_ready_decision_when_user_report_is_unassessed(client):
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    decisions = {
        pattern: build_movement_decision(pattern, "LEARN", user_report={"status": "comfortable"})
        for pattern in PATTERN_DEFINITIONS
    }
    decisions["squat"]["user_report"] = {"status": "not_assessed"}
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
    assert response.status_code == 400
    assert response.get_json()["invalid_report_patterns"] == ["squat"]


def test_program_route_rejects_comfortable_self_report_as_ready(client):
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    decisions = {
        pattern: build_movement_decision(
            pattern, "LEARN", user_report={"status": "comfortable"}
        )
        for pattern in PATTERN_DEFINITIONS
    }
    decisions["squat"] = build_movement_decision(
        "squat", "READY", user_report={"status": "comfortable"}
    )
    decisions["squat"]["training_phase"] = "capacity_development"
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
    assert response.status_code == 400
    assert response.get_json()["invalid_report_patterns"] == ["squat"]


def test_program_route_accepts_ready_only_with_repeatable_control_checklist(monkeypatch, client):
    import coach_routes
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    def fake_generate_program(profile, feedback=None, movement_assessment=None, movement_decisions=None, camera_coordination_observed=False):
        return {
            "goal": "functional",
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
            pattern, "LEARN", user_report={"status": "comfortable"}
        )
        for pattern in PATTERN_DEFINITIONS
    }
    decisions["squat"] = build_movement_decision(
        "squat", "READY", user_report={
            "status": "movement_controlled",
            "movement_control": {
                "confirmed_by_user": True, "repeatable": True,
                "criteria": {
                    "tempo": True, "balance": True, "knee_hip_foot_control": True,
                    "lumbopelvic_control": True, "tolerated_rom": True,
                },
            },
        }
    )
    decisions["squat"]["training_phase"] = "capacity_development"
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
    assert response.status_code == 200


def test_program_route_passes_structured_six_pattern_decisions(monkeypatch, client):
    import coach_routes
    from training.movement_coaching import build_movement_decision

    called = {}

    def fake_generate_program(profile, feedback=None, movement_assessment=None, movement_decisions=None, camera_coordination_observed=False):
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
            pattern, "LEARN",
            user_report={"status": "comfortable"},
            decision_reason="Samoocena je udobna; najprej preveri motorični nadzor.",
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
    assert called["movement_decisions"]["squat"]["decision"] == "LEARN"
    assert body["movement_assessment_applied"] is True
    assert body["movement_decisions_stored"] is False
    assert body["movement_adaptation"]["source"] == "structured_six_pattern_decisions"


def test_program_route_rejects_squat_capacity_phase_without_lumbopelvic_control(client):
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    decisions = {
        pattern: build_movement_decision(pattern, "LEARN", user_report={"status": "comfortable"})
        for pattern in PATTERN_DEFINITIONS
    }
    decisions["squat"] = build_movement_decision(
        "squat", "READY", user_report={
            "status": "movement_controlled",
            "movement_control": {
                "confirmed_by_user": True,
                "repeatable": True,
                "criteria": {
                    "tempo": True,
                    "balance": True,
                    "knee_hip_foot_control": True,
                    "lumbopelvic_control": False,
                    "tolerated_rom": True,
                },
            },
        },
    )
    decisions["squat"]["training_phase"] = "capacity_development"
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json={
            "movement_assessment_consent": True,
            "profile": {
                "goal": "hypertrophy",
                "experience": "beginner",
                "equipment": ["bodyweight"],
                "sessions_per_week": 2,
                "session_minutes": 45,
            },
            "movement_decisions": decisions,
        },
    )
    assert response.status_code == 400
    assert response.get_json()["invalid_report_patterns"] == ["squat"]


def _movement_control_for(pattern, *, all_true=True, confirmed=True, repeatable=True):
    criteria = {
        "squat": {"tempo", "balance", "knee_hip_foot_control", "lumbopelvic_control", "tolerated_rom"},
        "hinge": {"tempo", "hip_hinge_coordination", "spine_control", "balance", "tolerated_rom"},
        "horizontal_push": {"tempo", "shoulder_elbow_wrist_control", "trunk_control", "stable_support", "tolerated_rom"},
        "horizontal_pull": {"tempo", "scapular_arm_control", "trunk_control", "stable_base", "tolerated_rom"},
        "vertical_push": {"tempo", "overhead_control", "trunk_control", "scapular_control", "tolerated_rom"},
        "lunge": {"tempo", "balance", "pelvis_hip_knee_foot_control", "hip_extension", "trunk_control", "tolerated_rom"},
    }[pattern]
    return {
        "confirmed_by_user": confirmed,
        "repeatable": repeatable,
        "criteria": {key: all_true for key in criteria},
    }


def test_saved_six_pattern_assessment_unlocks_only_explicitly_confirmed_pattern(monkeypatch, client):
    import coach_routes
    from training.movement_coaching import PATTERN_DEFINITIONS

    captured = {}
    monkeypatch.setattr(coach_routes, "_profile_token", lambda: "profile-token")
    monkeypatch.setattr(
        coach_routes, "store_get_profile",
        lambda profile_id, token: {"health_data_consent": True},
    )

    def save_assessment(profile_id, token, record):
        captured["record"] = record
        return {"updated_at": "2026-11-14T17:00:00Z"}

    monkeypatch.setattr(coach_routes, "store_save_movement_assessment", save_assessment)
    patterns = {
        pattern: {"status": "uncertain"}
        for pattern in PATTERN_DEFINITIONS
    }
    patterns["squat"] = {
        "status": "comfortable",
        "movement_control": _movement_control_for("squat"),
    }

    response = client.put(
        "/coach/profile/test-profile/movement-assessment",
        headers={"X-Profile-Token": "profile-token"},
        json={"movement_assessment_consent": True, "movement_patterns": patterns},
    )

    assert response.status_code == 200
    decisions = response.get_json()["movement_decisions"]
    assert decisions["squat"]["decision"] == "READY"
    assert decisions["squat"]["user_report"]["status"] == "movement_controlled"
    assert decisions["squat"]["training_phase"] == "capacity_development"
    assert decisions["hinge"]["decision"] == "UNASSESSABLE"
    assert captured["record"]["decisions"]["squat"]["user_report"]["movement_control"]["repeatable"] is True


def test_saved_six_pattern_assessment_keeps_incomplete_control_in_learning(monkeypatch, client):
    import coach_routes
    from training.movement_coaching import PATTERN_DEFINITIONS

    monkeypatch.setattr(coach_routes, "_profile_token", lambda: "profile-token")
    monkeypatch.setattr(
        coach_routes, "store_get_profile",
        lambda profile_id, token: {"health_data_consent": True},
    )
    monkeypatch.setattr(
        coach_routes, "store_save_movement_assessment",
        lambda profile_id, token, record: {"updated_at": "2026-11-14T17:00:00Z"},
    )
    patterns = {
        pattern: {"status": "uncertain"}
        for pattern in PATTERN_DEFINITIONS
    }
    patterns["squat"] = {
        "status": "comfortable",
        "movement_control": _movement_control_for("squat", all_true=False),
    }

    response = client.put(
        "/coach/profile/test-profile/movement-assessment",
        headers={"X-Profile-Token": "profile-token"},
        json={"movement_assessment_consent": True, "movement_patterns": patterns},
    )

    assert response.status_code == 200
    squat = response.get_json()["movement_decisions"]["squat"]
    assert squat["decision"] == "LEARN"
    assert squat["user_report"]["status"] == "comfortable"
    assert "training_phase" not in squat


def test_saved_six_pattern_assessment_rejects_malformed_control_criteria(monkeypatch, client):
    import coach_routes
    from training.movement_coaching import PATTERN_DEFINITIONS

    monkeypatch.setattr(coach_routes, "_profile_token", lambda: "profile-token")
    monkeypatch.setattr(
        coach_routes, "store_get_profile",
        lambda profile_id, token: {"health_data_consent": True},
    )
    patterns = {
        pattern: {"status": "uncertain"}
        for pattern in PATTERN_DEFINITIONS
    }
    patterns["squat"] = {
        "status": "comfortable",
        "movement_control": {
            "confirmed_by_user": True,
            "repeatable": True,
            "criteria": {"tempo": True},
        },
    }

    response = client.put(
        "/coach/profile/test-profile/movement-assessment",
        headers={"X-Profile-Token": "profile-token"},
        json={"movement_assessment_consent": True, "movement_patterns": patterns},
    )

    assert response.status_code == 400
