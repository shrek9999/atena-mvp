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
            pattern, "LEARN",
            user_report={"status": "comfortable"},
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
            "movement_assessment_consent": True,
            "movement_decisions": _six_pattern_decisions(),
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
    from training.program import generate_program
    baseline = generate_program(
        {
            "goal": "hypertrophy", "experience": "intermediate",
            "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
            "session_minutes": 60,
        },
        movement_decisions=_six_pattern_decisions(),
    )
    assert program["sessions"][0]["exercises"][0]["prescription"]["sets"] == baseline["sessions"][0]["exercises"][0]["prescription"]["sets"]


def test_program_endpoint_blocks_automatic_adaptation_when_discomfort_reported(monkeypatch):
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


def test_clear_coordination_proxy_adds_only_a_low_demand_warmup_drill(monkeypatch):
    client = _client(monkeypatch)
    coordination = {
        "status": "observed",
        "quality": "adequate",
        "valid_frames": 12,
        "total_frames": 16,
        "observations": {
            "cross_body_alternation_observed": True,
            "left_to_right_contact_frames": 4,
            "right_to_left_contact_frames": 4,
            "alternating_transitions_proxy": 3,
        },
        "limitations": "Grobi 2D približek izmeničnega dotika nasprotne roke in kolena.",
        "source": "browser_pose_landmarker",
        "analysis_version": "six-pattern-proxy-v1",
    }
    payload = {
        "movement_assessment_consent": True,
        "movement_decisions": _six_pattern_decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight", "resistance_band"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {"coordination": coordination},
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v1",
            "dowel_three_contact_user_confirmed": False,
            "push_up_support_height": "floor",
            "video_stored": False,
            "video_uploaded": False,
        },
    }
    response = client.post(
        "/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["camera_observations"]["coordination"] == coordination
    assert body["camera_observations_stored"] is False
    assert body["camera_coordination_add_on_applied"] is True
    assert body["camera_observations_used_for_programme_decisions"] is True
    assert body["camera_observations_used_for_readiness_or_main_exercise_selection"] is False
    for session in body["program"]["sessions"]:
        block = session["camera_coordination_block"]
        assert block["is_readiness_assessment"] is False
        assert block["exercises"][0]["exercise_id"] == "controlled_lateral_step"
        assert block["exercises"][0]["sets"] == 1
        assert block["exercises"][0]["work_seconds"] == 10


def test_program_endpoint_rejects_contradictory_coordination_proxy_status(monkeypatch):
    payload = {
        "movement_assessment_consent": True,
        "movement_decisions": _six_pattern_decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight", "resistance_band"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {
            "coordination": {
                "status": "uncertain", "quality": "adequate",
                "valid_frames": 12, "total_frames": 16,
                "observations": {
                    "cross_body_alternation_observed": True,
                    "left_to_right_contact_frames": 4,
                    "right_to_left_contact_frames": 4,
                    "alternating_transitions_proxy": 3,
                },
                "limitations": "Grobi 2D približek.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v1",
            }
        },
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v1",
            "dowel_three_contact_user_confirmed": False,
            "push_up_support_height": "floor",
            "video_stored": False,
            "video_uploaded": False,
        },
    }
    response = _client(monkeypatch).post(
        "/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload
    )
    assert response.status_code == 400


def test_program_endpoint_accepts_skipped_coordination_as_uncertain_context(monkeypatch):
    payload = {
        "movement_assessment_consent": True,
        "movement_decisions": _six_pattern_decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {
            "coordination": {
                "status": "uncertain", "quality": "insufficient",
                "valid_frames": 0, "total_frames": 0,
                "observations": {
                    "cross_body_alternation_observed": False,
                    "left_to_right_contact_frames": 0,
                    "right_to_left_contact_frames": 0,
                    "alternating_transitions_proxy": 0,
                },
                "limitations": "Koordinacijski preizkus je bil preskočen ali ni bilo dovolj vidnih sličic.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v1",
            }
        },
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v1",
            "dowel_three_contact_user_confirmed": False,
            "push_up_support_height": "floor",
            "video_stored": False,
            "video_uploaded": False,
        },
    }
    response = _client(monkeypatch).post(
        "/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["camera_observations"]["coordination"]["status"] == "uncertain"
    assert body["camera_coordination_add_on_applied"] is False
    assert body["camera_observations_used_for_programme_decisions"] is False
    assert all("camera_coordination_block" not in session for session in body["program"]["sessions"])



def test_insufficient_quality_coordination_proxy_does_not_add_warmup_drill(monkeypatch):
    payload = {
        "movement_assessment_consent": True,
        "movement_decisions": _six_pattern_decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {
            "coordination": {
                "status": "observed", "quality": "insufficient",
                "valid_frames": 12, "total_frames": 16,
                "observations": {
                    "cross_body_alternation_observed": True,
                    "left_to_right_contact_frames": 4,
                    "right_to_left_contact_frames": 4,
                    "alternating_transitions_proxy": 3,
                },
                "limitations": "Kakovost slike ni zadostna za uporabo pri izbiri dodatne vaje.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v1",
            }
        },
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v1",
            "dowel_three_contact_user_confirmed": False,
            "push_up_support_height": "floor",
            "video_stored": False,
            "video_uploaded": False,
        },
    }
    response = _client(monkeypatch).post(
        "/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["camera_coordination_add_on_applied"] is False
    assert body["camera_observations_used_for_programme_decisions"] is False
    assert all("camera_coordination_block" not in session for session in body["program"]["sessions"])


def test_program_endpoint_accepts_six_pattern_camera_proxy_v2_protocol_v3(monkeypatch):
    client = _client(monkeypatch)
    payload = {
        "movement_assessment_consent": True,
        "movement_decisions": _six_pattern_decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {
            "squat": {
                "status": "observed", "quality": "adequate",
                "valid_frames": 18, "total_frames": 24,
                "observations": {
                    "knee_flexion_proxy_deg": 92,
                    "hip_angle_proxy_deg": 118,
                    "trunk_tilt_proxy_deg": 24,
                    "left_knee_tracking_proxy": -0.08,
                    "right_knee_tracking_proxy": 0.06,
                    "side_to_side_difference_proxy": 0.14,
                    "knee_angle_asymmetry_proxy_deg": 7,
                    "hip_vertical_excursion_proxy": 0.22,
                    "pelvic_control": "not_assessable_from_2d_pose",
                    "heel_contact_check": "user_confirmation_required",
                },
                "limitations": "Grobi 2D približek; ne potrjuje kakovosti ali pripravljenosti.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v2",
            },
            "hinge": {
                "status": "uncertain", "quality": "insufficient",
                "valid_frames": 2, "total_frames": 24,
                "observations": {},
                "limitations": "Premalo zanesljivih sličic.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v2",
            },
        },
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v3",
            "views": 8,
            "repetitions": 2,
            "tempo": "3-1-1",
            "lunge_repetitions_total": 2,
            "lunge_one_per_side": True,
            "dowel_three_contact_user_confirmed": True,
            "push_up_support_height": "floor",
            "video_stored": False,
            "video_uploaded": False,
        },
    }
    response = client.post("/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body["camera_observations"]["squat"]["analysis_version"] == "six-pattern-proxy-v2"
    assert body["camera_observations"]["hinge"]["status"] == "uncertain"
    assert body["camera_observations_stored"] is False
    assert body["camera_observations_used_for_programme_decisions"] is False
    assert body["camera_protocol"]["version"] == "six-pattern-camera-flow-v3"


def test_camera_v3_protocol_rejects_wrong_view_count(monkeypatch):
    payload = {
        "movement_assessment_consent": True,
        "movement_decisions": _six_pattern_decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {
            "squat": {
                "status": "uncertain", "quality": "insufficient",
                "valid_frames": 0, "total_frames": 0,
                "observations": {}, "limitations": "Premalo sličic.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v2",
            }
        },
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v3",
            "views": 6,
            "repetitions": 2,
            "tempo": "3-1-1",
            "lunge_repetitions_total": 2,
            "lunge_one_per_side": True,
            "dowel_three_contact_user_confirmed": False,
            "push_up_support_height": "floor",
            "video_stored": False,
            "video_uploaded": False,
        },
    }
    response = _client(monkeypatch).post(
        "/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload
    )
    assert response.status_code == 400
