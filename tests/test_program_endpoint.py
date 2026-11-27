from flask import Flask

from coach_routes import (
    coach_bp, LEARNING_CONTROL_CRITERIA, DEFAULT_LEARNING_METHODS,
    _build_guided_learning_tasks,
)


def _client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "test-only-secret")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()




def _six_pattern_decisions():
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    methods = {
        "squat": "air_squat_counterweight",
        "hinge": "dowel_four_point",
        "horizontal_push": "incline_push_up",
        "horizontal_pull": "scapular_coordination",
        "vertical_push": "light_overhead_press",
        "lunge": "supported_split_squat",
    }
    return {
        pattern: {
            **build_movement_decision(
                pattern, "LEARN",
                selected_learning_method=methods[pattern],
                user_report={"status": "comfortable"},
                decision_reason="The guided learning task is complete; this does not certify technique mastery.",
            ),
            "training_phase": "movement_learning",
        }
        for pattern in PATTERN_DEFINITIONS
    }


def _complete_learning_progress():
    return {"version": "guided-six-pattern-learning-v1", "patterns": {
        pattern: {"criteria": {key: True for key in criteria}}
        for pattern, criteria in LEARNING_CONTROL_CRITERIA.items()
    }}



def _completed_six_pattern_decisions():
    decisions = _six_pattern_decisions()
    for record in decisions.values():
        record["user_report"]["status"] = "learning_completed_by_user"
    return decisions
def test_program_endpoint_requires_all_six_guided_learning_checklists_when_payload_is_supplied(monkeypatch):
    client = _client(monkeypatch)
    learning = {"patterns": {
        pattern: {"criteria": {key: True for key in criteria}}
        for pattern, criteria in LEARNING_CONTROL_CRITERIA.items()
    }}
    learning["patterns"]["hinge"]["criteria"]["spine_control"] = False
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "learning_progress": learning,
            "movement_decisions": _six_pattern_decisions(),
            "goal": "hypertrophy", "experience": "intermediate",
            "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
            "session_minutes": 60,
        },
    )
    assert response.status_code == 409
    assert response.get_json()["learning_required"] is True
    assert response.get_json()["missing_patterns"] == ["hinge"]


def test_program_endpoint_accepts_six_completed_guided_learning_checklists(monkeypatch):
    client = _client(monkeypatch)
    learning = {"patterns": {
        pattern: {"criteria": {key: True for key in criteria}}
        for pattern, criteria in LEARNING_CONTROL_CRITERIA.items()
    }}
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "learning_progress": learning,
            "movement_decisions": _six_pattern_decisions(),
            "goal": "hypertrophy", "experience": "intermediate",
            "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
            "session_minutes": 60,
        },
    )
    assert response.status_code == 200, response.get_json()

def test_program_endpoint_requires_learning_progress_before_generating_a_programme(monkeypatch):
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
    assert response.status_code == 409
    assert response.get_json()["learning_required"] is True


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
            "learning_progress": _complete_learning_progress(),
            "movement_decisions": _six_pattern_decisions(),
            "goal": "hypertrophy", "experience": "intermediate",
            "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
            "session_minutes": 60,
        },
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["source"] == "curated_exercise_catalogue"
    assert len(body["program"]["sessions"]) == 2


def test_program_endpoint_rejects_invalid_profile(monkeypatch):
    response = _client(monkeypatch).post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "learning_progress": _complete_learning_progress(),
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
            "learning_progress": _complete_learning_progress(),
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
            "learning_progress": _complete_learning_progress(),
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
        movement_decisions=_completed_six_pattern_decisions(),
    )
    assert program["sessions"][0]["exercises"][0]["prescription"]["sets"] == baseline["sessions"][0]["exercises"][0]["prescription"]["sets"]


def test_program_endpoint_blocks_automatic_adaptation_when_discomfort_reported(monkeypatch):
    client = _client(monkeypatch)
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "learning_progress": _complete_learning_progress(),
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
        "learning_progress": _complete_learning_progress(),
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
        "movement_assessment_consent": True,
        "learning_progress": _complete_learning_progress(),
        "movement_decisions": _six_pattern_decisions(),
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
        "learning_progress": _complete_learning_progress(),
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
        "learning_progress": _complete_learning_progress(),
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
        "learning_progress": _complete_learning_progress(),
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
        "learning_progress": _complete_learning_progress(),
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


def test_camera_v3_protocol_rejects_wrong_view_count(monkeypatch):
    payload = {
        "movement_assessment_consent": True,
        "learning_progress": _complete_learning_progress(),
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


def test_program_endpoint_rejects_self_reported_readiness_even_with_all_pattern_criteria(monkeypatch):
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
            "learning_progress": _complete_learning_progress(),
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
    assert response.status_code == 400

def test_learn_decision_creates_learning_task_not_a_loaded_work_set(monkeypatch):
    from training.program import generate_program
    from training.movement_coaching import build_movement_decision

    decisions = _six_pattern_decisions()
    decisions["squat"] = {
        **build_movement_decision(
            "squat",
            "LEARN",
            selected_learning_method="air_squat_counterweight",
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

    safe_squat_starters = {"supported_squat", "chair_sit_to_stand", "air_squat"}
    for session in program["sessions"]:
        squat_exercises = [item for item in session["exercises"] if item["pattern"] == "squat"]
        assert all(item["exercise_id"] in safe_squat_starters for item in squat_exercises)
        squat_tasks = [
            task for task in session["learning_tasks"]
            if task["movement_pattern"] == "squat"
        ]
        assert len(squat_tasks) == 1
        assert squat_tasks[0]["method_id"] == "air_squat_counterweight"
        assert squat_tasks[0]["exercise_id"] in safe_squat_starters
        assert squat_tasks[0]["decision"] == "LEARN"

def test_unavailable_pull_and_overhead_press_are_omitted_without_inventing_equipment():
    from training.program import generate_program
    from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision

    methods = {
        "squat": "air_squat_counterweight",
        "hinge": "dowel_four_point",
        "horizontal_push": "incline_push_up",
        "horizontal_pull": "scapular_coordination",
        "vertical_push": "light_overhead_press",
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
            "goal": "strength_hypertrophy",
            "experience": "beginner",
            "equipment": ["bodyweight", "household_support", "chair", "wall"],
            "sessions_per_week": 2,
            "session_minutes": 30,
        },
        movement_decisions=decisions,
    )

    assert len(program["sessions"]) == 2
    for session in program["sessions"]:
        assert len(session["learning_tasks"]) <= 4
        assert all(task["movement_pattern"] in {
            exercise["pattern"] for exercise in session["exercises"]
        } for task in session["learning_tasks"])
        assert all(
            exercise["pattern"] not in {"horizontal_pull", "vertical_push"}
            for exercise in session["exercises"]
        )
    assert {"horizontal_pull", "vertical_push"}.issubset(
        set(program["weekly_summary"]["unfilled_patterns"])
    )
    omission_events = {
        event["pattern"]: event["action"]
        for event in program["movement_adaptation"]["events"]
        if event["action"] == "omitted_no_equipment_compatible_learning_variant"
    }
    assert omission_events["horizontal_pull"] == "omitted_no_equipment_compatible_learning_variant"
    assert omission_events["vertical_push"] == "omitted_no_equipment_compatible_learning_variant"




def test_program_endpoint_allows_one_temporarily_excluded_pattern(monkeypatch):
    client = _client(monkeypatch)
    learning = _complete_learning_progress()
    learning["patterns"]["hinge"] = {
        "status": "excluded",
        "exclusion_reason": "pain",
    }
    decisions = _six_pattern_decisions()
    from training.movement_coaching import build_movement_decision
    decisions["hinge"] = {
        **build_movement_decision(
            "hinge", "UNASSESSABLE",
            user_report={"status": "symptoms_reported"},
            decision_reason="The user temporarily excluded this pattern because of symptoms.",
        ),
        "training_phase": "excluded",
    }
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "learning_progress": learning,
            "movement_decisions": decisions,
            "profile": {
                "goal": "hypertrophy", "experience": "intermediate",
                "equipment": ["dumbbell", "bench"], "sessions_per_week": 2,
                "session_minutes": 60,
            },
        },
    )
    assert response.status_code == 200, response.get_json()
    program = response.get_json()["program"]
    assert all(
        exercise.get("pattern") != "hinge"
        for session in program["sessions"]
        for exercise in session["exercises"]
    )
    assert program["movement_adaptation"]["structured_decisions"]["hinge"]["decision"] == "UNASSESSABLE"


def test_program_endpoint_allows_a_pain_excluded_pattern_after_a_safe_regression(monkeypatch):
    client = _client(monkeypatch)
    learning = _complete_learning_progress()
    learning["patterns"]["squat"] = {"status": "excluded", "exclusion_reason": "pain"}
    decisions = _six_pattern_decisions()
    from training.movement_coaching import build_movement_decision
    decisions["squat"] = build_movement_decision(
        "squat", "REGRESS",
        selected_exercise_id="supported_squat",
        user_report={
            "status": "symptoms_reported",
            "regression_test": {
                "status": "tolerated",
                "variation_id": "supported_squat",
                "pain_during": 2,
                "worsened": False,
                "tempo": "slow_controlled",
                "load_adjustment": "reduced",
                "range_adjustment": "within_tolerance",
                "symptom_context": {
                    "familiarity": "familiar_stable",
                    "movement_quality_changed": False,
                    "next_day_response": "same_or_better",
                },
                "acute_warning_signs": [],
                "support_method": "stable_support",
            },
        },
    )
    decisions["squat"]["training_phase"] = "movement_learning"
    response = client.post(
        "/coach/program",
        headers={"X-Pilot-Token": "test-only-secret"},
        json={
            "movement_assessment_consent": True,
            "learning_progress": learning,
            "movement_decisions": decisions,
            "profile": {
                "goal": "hypertrophy", "experience": "intermediate",
                "equipment": ["dumbbell", "bench", "household_support"], "sessions_per_week": 2,
                "session_minutes": 60,
            },
        },
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["program"]["movement_adaptation"]["structured_decisions"]["squat"]["decision"] == "REGRESS"



def test_initial_guided_learning_payload_uses_bodyweight_squat_and_exposes_coaching_protocol():
    assert DEFAULT_LEARNING_METHODS["squat"] == "bodyweight_squat"
    tasks = _build_guided_learning_tasks(["squat"])
    assert len(tasks) == 1
    squat = tasks[0]
    assert squat["method_id"] == "bodyweight_squat"
    assert squat["method"] == "Počep z lastno težo"
    assert "predročenju" in squat["description"]
    assert squat["learning_protocol"]["repetitions"] == 5
    assert squat["learning_protocol"]["tempo"] == "3–1–1"
    assert len(squat["learning_protocol"]["criteria"]) == 6
    assert "Status učenja" not in squat
