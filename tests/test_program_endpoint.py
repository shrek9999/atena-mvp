from flask import Flask

from coach_routes import coach_bp


def _client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "test-only-secret")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()




def _six_pattern_decisions():
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    criteria_by_pattern = {
        "squat": {"tempo", "balance", "knee_hip_foot_control", "lumbopelvic_control", "tolerated_rom"},
        "hinge": {"tempo", "hip_hinge_coordination", "spine_control", "balance", "tolerated_rom"},
        "horizontal_push": {"tempo", "shoulder_elbow_wrist_control", "trunk_control", "stable_support", "tolerated_rom"},
        "horizontal_pull": {"tempo", "scapular_arm_control", "trunk_control", "stable_base", "tolerated_rom"},
        "vertical_push": {"tempo", "overhead_control", "trunk_control", "scapular_control", "tolerated_rom"},
        "lunge": {"tempo", "balance", "pelvis_hip_knee_foot_control", "hip_extension", "trunk_control", "tolerated_rom"},
    }
    return {
        pattern: {
            **build_movement_decision(
                pattern,
                "READY",
                user_report={
                    "status": "movement_controlled",
                    "movement_control": {
                        "confirmed_by_user": True,
                        "repeatable": True,
                        "criteria": {key: True for key in criteria_by_pattern[pattern]},
                    },
                },
                decision_reason="Vsi kriteriji motoričnega nadzora so ponovljivi in potrjeni.",
            ),
            "training_phase": "capacity_development",
        }
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
            "lunge": {
                "status": "observed", "quality": "adequate",
                "valid_frames": 12, "total_frames": 12,
                "observations": {
                    "visible_side": "left",
                    "knee_flexion_proxy_deg": 105,
                    "hip_angle_proxy_deg": 132,
                    "trunk_tilt_proxy_deg": 18,
                    "hip_vertical_excursion_proxy": 0.12,
                    "repetitions_detected": 2,
                    "range_of_motion_proxy": "partial",
                },
                "limitations": "Bočni 2D približki ne potrjujejo obeh strani ali ravnotežja.",
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
    assert body["camera_observations"]["lunge"]["observations"]["visible_side"] == "left"
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


def test_camera_v4_protocol_accepts_nine_views_for_frontal_lunge(monkeypatch):
    payload = {
        "movement_assessment_consent": True,
        "movement_decisions": _six_pattern_decisions(),
        "profile": {
            "goal": "functional", "experience": "beginner",
            "equipment": ["bodyweight"], "sessions_per_week": 2,
            "session_minutes": 45,
        },
        "camera_observations": {
            "lunge": {
                "status": "observed", "quality": "adequate",
                "valid_frames": 24, "total_frames": 24,
                "observations": {
                    "hip_extension_excursion_proxy_deg": 28,
                    "frontal_pelvis_level_difference_proxy": 0.04,
                    "frontal_left_knee_tracking_proxy": 0.12,
                    "frontal_right_knee_tracking_proxy": 0.11,
                },
                "limitations": "Čelni in bočni 2D približki; medenico in stopalo preveri neposredno.",
                "source": "browser_pose_landmarker",
                "analysis_version": "six-pattern-proxy-v2",
            }
        },
        "camera_protocol": {
            "version": "six-pattern-camera-flow-v4",
            "views": 9,
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
    response = _client(monkeypatch).post(
        "/coach/program", headers={"X-Pilot-Token": "test-only-secret"}, json=payload
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["camera_protocol"]["version"] == "six-pattern-camera-flow-v4"
    assert body["camera_protocol"]["views"] == 9
    assert body["camera_observations"]["lunge"]["observations"]["hip_extension_excursion_proxy_deg"] == 28
    assert body["camera_observations_used_for_programme_decisions"] is False

def test_program_endpoint_accepts_current_vertical_push_and_lunge_mastery_criteria(monkeypatch):
    from training.movement_coaching import build_movement_decision

    decisions = _six_pattern_decisions()
    criteria_by_pattern = {
        "vertical_push": {
            "tempo": True,
            "overhead_control": True,
            "trunk_control": True,
            "scapular_control": True,
            "tolerated_rom": True,
        },
        "lunge": {
            "tempo": True,
            "balance": True,
            "pelvis_hip_knee_foot_control": True,
            "hip_extension": True,
            "trunk_control": True,
            "tolerated_rom": True,
        },
    }
    for pattern, criteria in criteria_by_pattern.items():
        record = build_movement_decision(
            pattern,
            "READY",
            user_report={
                "status": "movement_controlled",
                "movement_control": {
                    "confirmed_by_user": True,
                    "repeatable": True,
                    "criteria": criteria,
                },
            },
            decision_reason="Vsi kriteriji so bili neposredno preverjeni in ponovljivi.",
        )
        record["training_phase"] = "capacity_development"
        decisions[pattern] = record

    response = _client(monkeypatch).post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "movement_decisions": decisions,
            "profile": {
                "goal": "functional",
                "experience": "beginner",
                "equipment": ["bodyweight", "dumbbell", "kettlebell", "barbell", "bench", "rack", "resistance_band"],
                "sessions_per_week": 2,
                "session_minutes": 45,
            },
        },
    )
    assert response.status_code == 200, response.get_json()

def test_learn_decision_creates_learning_task_not_a_loaded_work_set(monkeypatch):
    from training.program import generate_program
    from training.movement_coaching import build_movement_decision

    decisions = _six_pattern_decisions()
    decisions["squat"] = {
        **build_movement_decision(
            "squat",
            "LEARN",
            selected_learning_method="reaching_counterbalance",
            user_report={"status": "comfortable"},
            decision_reason="Prijetna samoocena še ne potrdi motoričnega nadzora.",
        ),
        "training_phase": "movement_learning",
    }
    program = generate_program(
        {
            "goal": "strength_hypertrophy",
            "experience": "beginner",
            "equipment": ["bodyweight", "household_support", "chair", "wall", "dumbbell", "kettlebell"],
            "sessions_per_week": 2,
            "session_minutes": 45,
        },
        movement_decisions=decisions,
    )

    for session in program["sessions"]:
        assert all(item["pattern"] != "squat" for item in session["exercises"])
        squat_tasks = [
            task for task in session["learning_tasks"]
            if task["movement_pattern"] == "squat"
        ]
        assert len(squat_tasks) == 1
        assert squat_tasks[0]["method_id"] == "reaching_counterbalance"
        assert squat_tasks[0]["exercise_id"] is None
        assert squat_tasks[0]["decision"] == "LEARN"

def test_all_unmastered_patterns_can_form_a_learning_only_program(monkeypatch):
    from training.program import generate_program
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    methods = {
        "squat": "reaching_counterbalance",
        "hinge": "dowel_four_point",
        "horizontal_push": "incline_push_up",
        "horizontal_pull": "scapular_coordination",
        "vertical_push": "unloaded_overhead_reach",
        "lunge": "supported_split_squat",
    }
    decisions = {
        pattern: {
            **build_movement_decision(
                pattern,
                "LEARN",
                selected_learning_method=methods[pattern],
                user_report={"status": "comfortable"},
                decision_reason="Učenje motoričnega nadzora pred razvojem zmogljivosti.",
            ),
            "training_phase": "movement_learning",
        }
        for pattern in PATTERN_DEFINITIONS
    }
    program = generate_program(
        {
            "goal": "functional",
            "experience": "beginner",
            "equipment": ["bodyweight", "household_support", "chair", "wall"],
            "sessions_per_week": 2,
            "session_minutes": 30,
        },
        movement_decisions=decisions,
    )

    assert len(program["sessions"]) == 2
    seen_learning_patterns = set()
    for session in program["sessions"]:
        assert not any(
            exercise["pattern"] in PATTERN_DEFINITIONS
            for exercise in session["exercises"]
        )
        assert session["session_phase"] == "movement_learning"
        assert "učenje gibalnih vzorcev" in session["title"].lower()
        assert session["learning_tasks"]
        assert all(task["exercise_id"] is None for task in session["learning_tasks"])
        assert all(task["decision"] == "LEARN" for task in session["learning_tasks"])
        seen_learning_patterns.update(task["movement_pattern"] for task in session["learning_tasks"])
    assert seen_learning_patterns == set(PATTERN_DEFINITIONS)
