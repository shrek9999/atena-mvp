import pytest
from flask import Flask

from coach_routes import coach_bp
from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision
from coach_routes import LEARNING_CONTROL_CRITERIA


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "test-only-token")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()


def _learning_progress(complete=True):
    return {
        "patterns": {
            pattern: {"criteria": {key: complete for key in criteria}}
            for pattern, criteria in LEARNING_CONTROL_CRITERIA.items()
        }
    }


def _decisions(status="selected_for_learning"):
    methods = {
        "squat": "reaching_counterbalance",
        "hinge": "wall_hip_hinge",
        "horizontal_push": "incline_push_up",
        "horizontal_pull": "scapular_coordination",
        "vertical_push": "unloaded_overhead_reach",
        "lunge": "supported_split_squat",
    }
    return {
        pattern: build_movement_decision(
            pattern, "LEARN",
            selected_learning_method=methods[pattern],
            user_report={"status": status},
            decision_reason="Guided learning task completed; technique mastery is not certified.",
        )
        for pattern in PATTERN_DEFINITIONS
    }


def _program_payload():
    return {
        "movement_assessment_consent": True,
        "learning_progress": _learning_progress(),
        "movement_decisions": _decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight", "dumbbell", "bench", "household_support", "wall"],
            "sessions_per_week": 2, "session_minutes": 45,
        },
    }


def test_legacy_standalone_movement_assessment_is_retired(client):
    response = client.post(
        "/coach/movement-assessment",
        headers={"X-Pilot-Token": "test-only-token"},
        json={"assessment": {"squat": "comfortable"}},
    )
    assert response.status_code == 410
    assert response.get_json()["guided_learning_required"] is True


def test_legacy_profile_movement_assessment_is_retired(client):
    response = client.put(
        "/coach/profile/test-profile/movement-assessment",
        headers={"X-Profile-Token": "unused"},
        json={"movement_assessment_consent": True, "movement_patterns": {}},
    )
    assert response.status_code == 410
    assert response.get_json()["guided_learning_required"] is True


def test_program_route_requires_all_six_guided_learning_tasks(client, monkeypatch):
    import coach_routes

    def should_not_run(*args, **kwargs):
        raise AssertionError("Programme generation must not run before all six learning tasks.")

    monkeypatch.setattr(coach_routes, "generate_program", should_not_run)
    payload = _program_payload()
    payload.pop("learning_progress")
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json=payload,
    )
    assert response.status_code == 409
    body = response.get_json()
    assert body["learning_required"] is True
    assert set(body["missing_patterns"]) == set(PATTERN_DEFINITIONS)


def test_program_route_blocks_incomplete_learning_checklists(client, monkeypatch):
    import coach_routes

    def should_not_run(*args, **kwargs):
        raise AssertionError("Programme generation must wait for all six completed checklists.")

    monkeypatch.setattr(coach_routes, "generate_program", should_not_run)
    payload = _program_payload()
    payload["learning_progress"] = _learning_progress(complete=False)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json=payload,
    )
    assert response.status_code == 409
    assert response.get_json()["learning_required"] is True


def test_program_route_never_promotes_user_checklist_to_ready(client, monkeypatch):
    import coach_routes

    def should_not_run(*args, **kwargs):
        raise AssertionError("A user checklist cannot certify movement readiness.")

    monkeypatch.setattr(coach_routes, "generate_program", should_not_run)
    payload = _program_payload()
    payload["movement_decisions"]["squat"] = build_movement_decision(
        "squat", "READY", user_report={"status": "comfortable"}
    )
    payload["movement_decisions"]["squat"]["training_phase"] = "capacity_development"
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json=payload,
    )
    assert response.status_code == 400
    assert response.get_json()["invalid_report_patterns"] == ["squat"]


def test_program_route_passes_learning_completion_as_non_ready_starter_state(client, monkeypatch):
    import coach_routes

    captured = {}

    def fake_generate_program(profile, feedback=None, movement_assessment=None, movement_decisions=None, camera_coordination_observed=False):
        captured["decisions"] = movement_decisions
        return {
            "goal": "functional",
            "sessions": [{"session": 1, "exercises": [], "learning_tasks": []}],
            "movement_adaptation": {
                "source": "guided_six_pattern_learning",
                "is_diagnosis": False,
                "events": [],
                "summary": None,
            },
        }

    monkeypatch.setattr(coach_routes, "generate_program", fake_generate_program)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json=_program_payload(),
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["guided_learning_applied"] is True
    assert body["movement_assessment_applied"] is False
    assert all(item["decision"] == "LEARN" for item in captured["decisions"].values())
    assert all(item["user_report"]["status"] == "learning_completed_by_user" for item in captured["decisions"].values())


def test_program_route_rejects_old_movement_controlled_status(client, monkeypatch):
    import coach_routes

    def should_not_run(*args, **kwargs):
        raise AssertionError("Legacy movement-control self-report must not reach programme generation.")

    monkeypatch.setattr(coach_routes, "generate_program", should_not_run)
    payload = _program_payload()
    payload["movement_decisions"]["squat"]["user_report"] = {"status": "movement_controlled"}
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json=payload,
    )
    assert response.status_code == 400
    assert response.get_json()["invalid_report_patterns"] == ["squat"]


def test_program_route_requires_separate_plan_use_consent(client):
    payload = _program_payload()
    payload.pop("movement_assessment_consent")
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-token"},
        json=payload,
    )
    assert response.status_code == 403
    assert response.get_json()["consent_required"] is True
