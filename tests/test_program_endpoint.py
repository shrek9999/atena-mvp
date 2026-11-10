from flask import Flask

from coach_routes import coach_bp


def _client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "test-only-secret")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()




def _six_pattern_decisions():
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision
    return {
        pattern: build_movement_decision(
            pattern, "READY",
            decision_reason="Osnovno gibanje je po samooceni udobno in nadzorovano.",
        )
        for pattern in PATTERN_DEFINITIONS
    }


def test_program_endpoint_requires_pilot_token(monkeypatch):
    response = _client(monkeypatch).post("/coach/program", json={
        "goal": "hypertrophy", "experience": "intermediate",
        "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
        "session_minutes": 60,
    })
    assert response.status_code == 403


def test_program_endpoint_returns_catalogue_backed_plan(monkeypatch):
    response = _client(monkeypatch).post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "movement_decisions": _six_pattern_decisions(),
            "goal": "hypertrophy", "experience": "intermediate",
            "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
            "session_minutes": 60,
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "curated_exercise_catalogue"
    assert len(body["program"]["sessions"]) == 2


def test_program_endpoint_rejects_invalid_profile(monkeypatch):
    response = _client(monkeypatch).post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "movement_decisions": _six_pattern_decisions(),
            "goal": "miracle", "experience": "beginner",
            "equipment": ["bodyweight"], "sessions_per_week": 2,
            "session_minutes": 60,
        },
    )
    assert response.status_code == 400



def test_program_endpoint_accepts_nested_profile_and_reduces_hard_feedback(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "movement_decisions": _six_pattern_decisions(),
            "profile": {
                "goal": "hypertrophy", "experience": "intermediate",
                "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
                "session_minutes": 60,
            },
            "feedback": {"difficulty": "hard", "completed": True, "discomfort": "no"},
        },
    )
    assert response.status_code == 200
    program = response.get_json()["program"]
    assert program["feedback_applied"]["difficulty"] == "hard"
    assert program["methodology"]["last_session_adjustment"] == "reduce_sets_increase_reserve"
    first = program["sessions"][0]["exercises"][0]["prescription"]
    assert first["sets"] == 2
    assert first["rir"] == 4


def test_program_endpoint_holds_after_easy_feedback_instead_of_auto_progressing(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "profile": {
                "goal": "hypertrophy", "experience": "intermediate",
                "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
                "session_minutes": 60,
            },
            "feedback": {"difficulty": "easy", "completed": True, "discomfort": "no"},
        },
    )
    assert response.status_code == 200
    program = response.get_json()["program"]
    assert program["methodology"]["last_session_adjustment"] == "hold_and_progress_by_rule"
    assert program["sessions"][0]["exercises"][0]["prescription"]["sets"] == 3


def test_program_endpoint_blocks_automatic_adaptation_when_discomfort_reported(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "profile": {
                "goal": "hypertrophy", "experience": "intermediate",
                "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
                "session_minutes": 60,
            },
            "feedback": {"difficulty": "hard", "completed": False, "discomfort": "yes"},
        },
    )
    assert response.status_code == 409
    assert response.get_json()["blocked"] is True



def test_program_endpoint_returns_camera_observations_as_separate_non_decisional_context(monkeypatch):
    client = _client(monkeypatch)
    payload = {
        "movement_assessment_consent": True,
        "movement_decisions": _six_pattern_decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight", "resistance_band"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {
            "squat": {
                "status": "observed", "quality": "adequate",
                "valid_frames": 20, "total_frames": 24,
                "observations": {"knee_flexion_proxy_deg": 95, "heel_lift_visible": False},
                "limitations": "2D približek, ne klinična meritev.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v1",
            }
        },
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v1",
            "dowel_three_contact_user_confirmed": True,
            "push_up_support_height": "floor",
            "video_stored": False,
            "video_uploaded": False,
        },
    }
    response = client.post("/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body["camera_observations"]["squat"]["observations"]["knee_flexion_proxy_deg"] == 95
    assert body["camera_observations_stored"] is False
    assert body["camera_observations_used_for_programme_decisions"] is False
    assert body["camera_protocol"]["video_stored"] is False


def test_program_endpoint_rejects_camera_payload_claiming_video_storage(monkeypatch):
    payload = {
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {
            "hinge": {
                "status": "uncertain", "quality": "insufficient",
                "valid_frames": 0, "total_frames": 0,
                "observations": {}, "limitations": "Premalo sličic.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v1",
            }
        },
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v1",
            "dowel_three_contact_user_confirmed": False,
            "push_up_support_height": "floor",
            "video_stored": True,
            "video_uploaded": False,
        },
    }
    response = _client(monkeypatch).post(
        "/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload
    )
    assert response.status_code == 400
