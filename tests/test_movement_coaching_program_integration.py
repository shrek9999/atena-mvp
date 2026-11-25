"""Programme integration for structured six-pattern movement decisions."""
from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision, get_method_english, get_pattern_english
from training.catalogue import get_exercise, load_catalogue
from training.program import PATTERN_LABELS, ProgramValidationError, _estimated_minutes, generate_program


BASE = {
    "goal": "hypertrophy",
    "experience": "intermediate",
    "equipment": [
        "barbell", "rack", "dumbbell", "bench", "pull_up_bar",
        "kettlebell", "cable", "resistance_band", "box",
        "household_support", "wall", "anchor_point",
    ],
    "sessions_per_week": 2,
    "session_minutes": 60,
}


def _pattern_exercises(plan, pattern):
    return [
        item
        for session in plan["sessions"]
        for item in session["exercises"]
        if item["pattern"] == pattern
    ]


def test_learn_decision_selects_reaching_squat_and_adds_learning_task():
    decision = build_movement_decision(
        "squat", "LEARN",
        selected_learning_method="reaching_counterbalance",
        decision_reason="Najprej utrdi osnovno koordinacijo in ravnotežje.",
    )
    plan = generate_program(BASE, movement_decisions={"squat": decision})
    assert _pattern_exercises(plan, "squat") == []
    tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
        if task["movement_pattern"] == "squat"
    ]
    assert tasks
    assert all(task["method_id"] == "reaching_counterbalance" for task in tasks)
    assert all(task["exercise_id"] is None for task in tasks)
    assert all(task["demo_url"] == "https://youtu.be/f6LSIpaDdSA" for task in tasks)
    assert all(task["tempo"] == "3-1-1" for task in tasks)
    assert all(task["pattern_label_en"] == "Squat" for task in tasks)
    assert all("controlled squat" in task["task_en"].lower() for task in tasks)
    assert all(task["method_en"] == "Counterbalance squat" for task in tasks)
    assert all("counterbalance" in task["description_en"].lower() for task in tasks)


def test_separate_movement_learning_tasks_do_not_inflate_workout_warmup_or_duration():
    decision = build_movement_decision(
        "squat", "LEARN",
        selected_learning_method="supported_squat_assistance",
        decision_reason="Najprej utrdi počep z oporo.",
    )
    plan = generate_program(BASE, movement_decisions={"squat": decision})
    for session in plan["sessions"]:
        tasks = [
            task for task in session["learning_tasks"]
            if task["movement_pattern"] == "squat"
        ]
        assert tasks
        assert session["warm_up_minutes"] == 7
        assert session["warm_up_range"] == "5–10 min"
        assert session["learning_tasks_estimated_minutes"] == 2
        assert session["estimated_minutes"] == _estimated_minutes(
            session["exercises"], session["warm_up_minutes"]
        )
        assert session["estimated_minutes"] <= session["available_minutes"]


def test_one_ready_pattern_is_not_mislabelled_as_a_full_body_session():
    methods = {
        "squat": "reaching_counterbalance",
        "hinge": "wall_hip_hinge",
        "horizontal_pull": "scapular_coordination",
        "vertical_push": "unloaded_overhead_reach",
        "lunge": "supported_split_squat",
    }
    decisions = {
        pattern: build_movement_decision(
            pattern, "LEARN",
            selected_learning_method=method,
            user_report={"status": "comfortable"},
            decision_reason="The pattern needs repeatable control before loaded training.",
        )
        for pattern, method in methods.items()
    }
    push = build_movement_decision(
        "horizontal_push", "READY",
        user_report={"status": "movement_controlled", "movement_control": {
            "confirmed_by_user": True, "repeatable": True,
            "criteria": {
                "tempo": True, "shoulder_elbow_wrist_control": True,
                "trunk_control": True, "stable_support": True, "tolerated_rom": True,
            },
        }},
        decision_reason="Horizontal push control is repeatable.",
    )
    push["training_phase"] = "capacity_development"
    decisions["horizontal_push"] = push

    plan = generate_program(BASE, movement_decisions=decisions)

    assert len(plan["sessions"]) == 2
    for session in plan["sessions"]:
        assert session["session_focus"] == "targeted"
        assert session["covered_patterns"] == ["horizontal_push"]
        assert "celotno telo" not in session["title"]
        assert session["warm_up_minutes"] == 7
        assert session["learning_tasks_estimated_minutes"] == 10
        assert session["estimated_minutes"] == _estimated_minutes(
            session["exercises"], session["warm_up_minutes"]
        )
        assert all(item["pattern"] == "horizontal_push" for item in session["exercises"])
        assert all(item["exercise_id"] == "push_up" for item in session["exercises"])


def test_dowel_hinge_learning_task_uses_a_catalogue_supported_low_skill_variant():
    decision = build_movement_decision(
        "hinge", "LEARN",
        equipment=["wall", "bodyweight"],
        implement_variant="broomstick",
        selected_learning_method="dowel_four_point",
        decision_reason="Utrdi tri stične točke in četrto kontrolo ledvene krivine.",
    )
    plan = generate_program(BASE, movement_decisions={"hinge": decision})
    assert _pattern_exercises(plan, "hinge") == []
    tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
        if task["movement_pattern"] == "hinge"
    ]
    assert tasks
    assert all(task["method_id"] == "dowel_four_point" for task in tasks)
    assert all(task["exercise_id"] is None for task in tasks)


def test_regress_decision_uses_verified_supported_split_squat():
    decision = build_movement_decision(
        "lunge", "REGRESS",
        equipment=["household_support", "bodyweight"],
        selected_learning_method="supported_split_squat",
        selected_exercise_id="supported_split_squat",
        decision_reason="Začasno uporabi oporo za ravnotežje.",
    )
    plan = generate_program(BASE, movement_decisions={"lunge": decision})
    assert _pattern_exercises(plan, "lunge") == []
    tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
        if task["movement_pattern"] == "lunge"
    ]
    assert tasks
    assert all(task["method_id"] == "supported_split_squat" for task in tasks)
    assert all(task["exercise_id"] is None for task in tasks)


def test_ready_decision_starts_conservatively_without_automatic_progression():
    baseline = generate_program(BASE)
    ready = build_movement_decision(
        "squat", "READY",
        user_report={"status": "movement_controlled", "movement_control": {
            "confirmed_by_user": True, "repeatable": True,
            "criteria": {
                "tempo": True, "balance": True, "knee_hip_foot_control": True,
                "lumbopelvic_control": True, "tolerated_rom": True,
            },
        }},
        decision_reason="Po učenju je počep ponovljivo nadzorovan.",
    )
    ready["training_phase"] = "capacity_development"
    assessed = generate_program(BASE, movement_decisions={"squat": ready})
    selected = _pattern_exercises(assessed, "squat")
    assert selected
    assert all(item.get("loading_potential") != "high" for item in selected)
    assert [item["exercise_id"] for item in selected] != [
        item["exercise_id"] for item in _pattern_exercises(baseline, "squat")
    ]
    assert assessed["movement_adaptation"]["automatic_progression"] == "movement_assessment_does_not_trigger_progression"
    assert any(
        event["action"] == "ready_for_light_loaded_start"
        for event in assessed["movement_adaptation"]["events"]
    )


def test_horizontal_pull_and_overhead_learning_stay_unloaded_until_control_is_verified():
    pull = build_movement_decision(
        "horizontal_pull", "LEARN",
        selected_learning_method="scapular_coordination",
        user_report={"status": "comfortable"},
        decision_reason="Najprej vadi gibanje lopatic brez bremena.",
    )
    overhead = build_movement_decision(
        "vertical_push", "LEARN",
        selected_learning_method="unloaded_overhead_reach",
        user_report={"status": "comfortable"},
        decision_reason="Najprej vadi pot rok nad glavo brez bremena.",
    )
    plan = generate_program(BASE, movement_decisions={
        "horizontal_pull": pull, "vertical_push": overhead,
    })
    assert _pattern_exercises(plan, "horizontal_pull") == []
    assert _pattern_exercises(plan, "vertical_push") == []
    tasks = [task for session in plan["sessions"] for task in session["learning_tasks"]]
    method_ids = {task["method_id"] for task in tasks}
    assert "scapular_coordination" in method_ids
    assert "unloaded_overhead_reach" in method_ids


def test_unassessable_omits_pattern_until_assessment_is_available():
    unassessable = build_movement_decision(
        "squat", "UNASSESSABLE",
        capture_quality="insufficient",
        limitations=["Stopala niso bila vidna v celotnem posnetku."],
        decision_reason="Ni dovolj dokazov za sklep.",
    )
    assessed = generate_program(BASE, movement_decisions={"squat": unassessable})
    assert not _pattern_exercises(assessed, "squat")
    assert any(
        event["action"] == "omitted_unassessable_pending_reassessment"
        for event in assessed["movement_adaptation"]["events"]
    )


def test_new_decision_contract_rejects_conflicting_legacy_assessment():
    decision = build_movement_decision("squat", "READY")
    try:
        generate_program(
            BASE,
            movement_assessment={"squat": "comfortable"},
            movement_decisions={"squat": decision},
        )
    except ValueError as exc:
        assert "ne kombiniraj" in str(exc)
    else:
        raise AssertionError("Conflicting assessment sources should be rejected.")


def test_structured_symptom_report_omits_only_affected_pattern_pending_review():
    decision = build_movement_decision(
        "squat", "UNASSESSABLE",
        user_report={"status": "symptoms_reported", "region": "knee"},
        decision_reason="Uporabnik je navedel nelagodje; potrebna je dodatna razjasnitev.",
    )
    plan = generate_program(BASE, movement_decisions={"squat": decision})
    assert not _pattern_exercises(plan, "squat")
    assert _pattern_exercises(plan, "hinge")
    event = next(event for event in plan["movement_adaptation"]["events"] if event["pattern"] == "squat")
    assert event["action"] == "omitted_pending_symptom_review"



def test_horizontal_push_never_selects_wall_push_up_even_when_wall_is_available():
    decision = build_movement_decision(
        "horizontal_push", "LEARN",
        equipment=["wall", "household_support", "bodyweight"],
        selected_learning_method="incline_push_up",
        selected_exercise_id="push_up_incline",
        decision_reason="Uporabi stabilno povišano oporo, brez sklece ob steni.",
    )
    plan = generate_program(BASE, movement_decisions={"horizontal_push": decision})
    assert _pattern_exercises(plan, "horizontal_push") == []
    tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
        if task["movement_pattern"] == "horizontal_push"
    ]
    assert tasks
    assert all(task["method_id"] == "incline_push_up" for task in tasks)
    assert all(task["exercise_id"] is None for task in tasks)


def test_hinge_user_facing_label_uses_neutral_spine_not_flat_back_language():
    assert PATTERN_LABELS["hinge"] == "predklon z nevtralno hrbtenico"


def test_loaded_bent_over_row_learning_requires_hinge_ready():
    row = build_movement_decision(
        "horizontal_pull", "LEARN",
        equipment=["dumbbell"],
        selected_learning_method="light_one_arm_hinge_row",
        selected_exercise_id="one_arm_row",
        decision_reason="Najprej utrdi koordinacijo lopatice in komolca z lahkim bremenom.",
    )
    try:
        generate_program(BASE, movement_decisions={"horizontal_pull": row})
    except ProgramValidationError as exc:
        assert "predklon" in str(exc).lower()
        assert "ready" in str(exc).lower()
    else:
        raise AssertionError("Loaded bent-over row must require a READY hinge assessment.")


def test_loaded_bent_over_row_is_allowed_after_hinge_is_marked_ready():
    hinge = build_movement_decision(
        "hinge", "READY",
        user_report={"status": "movement_controlled", "movement_control": {
            "confirmed_by_user": True, "repeatable": True,
            "criteria": {
                "tempo": True, "balance": True, "hip_hinge_coordination": True,
                "spine_control": True, "tolerated_rom": True,
            },
        }},
        decision_reason="Predklon je po učenju ponovljivo obvladan.",
    )
    hinge["training_phase"] = "capacity_development"
    row = build_movement_decision(
        "horizontal_pull", "READY",
        equipment=["dumbbell"],
        user_report={"status": "movement_controlled", "movement_control": {
            "confirmed_by_user": True, "repeatable": True,
            "criteria": {
                "tempo": True, "scapular_arm_control": True, "trunk_control": True,
                "stable_base": True, "tolerated_rom": True,
            },
        }},
        decision_reason="Horizontalni poteg je po učenju ponovljivo obvladan.",
    )
    row["training_phase"] = "capacity_development"
    plan = generate_program(BASE, movement_decisions={"hinge": hinge, "horizontal_pull": row})
    assert _pattern_exercises(plan, "horizontal_pull")


def test_band_row_learning_does_not_require_bent_over_hinge_readiness():
    row = build_movement_decision(
        "horizontal_pull", "LEARN",
        user_report={"status": "needs_support"},
        selected_learning_method="scapular_coordination",
        decision_reason="Najprej vadi gibanje lopatic brez dodatnega bremena.",
    )
    plan = generate_program(BASE, movement_decisions={"horizontal_pull": row})
    assert _pattern_exercises(plan, "horizontal_pull") == []
    tasks = [task for session in plan["sessions"] for task in session["learning_tasks"]]
    assert any(task["method_id"] == "scapular_coordination" for task in tasks)


def test_saved_needs_support_self_report_without_method_resolves_to_safe_wall_hinge():
    profile = {
        **BASE,
        "experience": "beginner",
        "equipment": ["wall", "household_support"],
    }
    decision = build_movement_decision(
        "hinge", "LEARN",
        user_report={"status": "needs_support"},
        decision_reason="Uporabnik potrebuje lažjo učno različico predklona.",
    )
    plan = generate_program(profile, movement_decisions={"hinge": decision})
    assert _pattern_exercises(plan, "hinge") == []
    tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
        if task["movement_pattern"] == "hinge"
    ]
    assert tasks
    assert all(task["method_id"] == "wall_hip_hinge" for task in tasks)
    assert all(task["exercise_id"] is None for task in tasks)
    assert all(task["method"] == "Predklon ob steni" for task in tasks)
    assert all("pomik bokov nazaj" in task["description"] for task in tasks)


def test_needs_support_without_compatible_equipment_omits_only_that_pattern():
    profile = {
        **BASE,
        "experience": "beginner",
        "equipment": ["wall", "household_support"],
    }
    row = build_movement_decision(
        "horizontal_pull", "LEARN",
        user_report={"status": "needs_support"},
        decision_reason="Uporabnik potrebuje lažjo različico horizontalnega potega.",
    )
    vertical_push = build_movement_decision(
        "vertical_push", "LEARN",
        user_report={"status": "needs_support"},
        decision_reason="Uporabnik potrebuje lažjo različico vertikalnega potiska.",
    )
    plan = generate_program(
        profile,
        movement_decisions={"horizontal_pull": row, "vertical_push": vertical_push},
    )
    assert not _pattern_exercises(plan, "horizontal_pull")
    assert not _pattern_exercises(plan, "vertical_push")
    tasks = [task for session in plan["sessions"] for task in session["learning_tasks"]]
    assert {task["method_id"] for task in tasks} >= {
        "scapular_coordination", "unloaded_overhead_reach"
    }
    assert all(task["exercise_id"] is None for task in tasks)
    assert not any(
        event["action"] == "omitted_no_equipment_compatible_learning_variant"
        and event["pattern"] in {"horizontal_pull", "vertical_push"}
        for event in plan["movement_adaptation"]["events"]
    )


def test_kettlebell_only_ready_row_does_not_override_conservative_loading_gate():
    profile = {
        **BASE,
        "experience": "intermediate",
        "equipment": ["kettlebell", "bodyweight", "chair", "wall", "household_support"],
    }
    hinge = build_movement_decision(
        "hinge", "READY",
        user_report={"status": "movement_controlled", "movement_control": {
            "confirmed_by_user": True, "repeatable": True,
            "criteria": {
                "tempo": True, "balance": True, "hip_hinge_coordination": True,
                "spine_control": True, "tolerated_rom": True,
            },
        }},
        decision_reason="Predklon je po učenju ponovljivo obvladan.",
    )
    hinge["training_phase"] = "capacity_development"
    row = build_movement_decision(
        "horizontal_pull", "READY",
        equipment=["kettlebell"],
        selected_exercise_id="kettlebell_one_arm_row",
        user_report={"status": "movement_controlled", "movement_control": {
            "confirmed_by_user": True, "repeatable": True,
            "criteria": {
                "tempo": True, "scapular_arm_control": True, "trunk_control": True,
                "stable_base": True, "tolerated_rom": True,
            },
        }},
        decision_reason="Horizontalni poteg je po učenju ponovljivo obvladan.",
    )
    row["training_phase"] = "capacity_development"
    plan = generate_program(profile, movement_decisions={"hinge": hinge, "horizontal_pull": row})
    rows = _pattern_exercises(plan, "horizontal_pull")
    assert rows == []
    assert any(
        event["pattern"] == "horizontal_pull"
        and event["action"] == "omitted_no_conservative_starting_variant"
        for event in plan["movement_adaptation"]["events"]
    )

def test_six_learning_patterns_repeat_in_both_weekly_sessions():
    methods = {
        "squat": "reaching_counterbalance",
        "hinge": "wall_hip_hinge",
        "horizontal_push": "incline_push_up",
        "horizontal_pull": "scapular_coordination",
        "vertical_push": "unloaded_overhead_reach",
        "lunge": "supported_split_squat",
    }
    decisions = {
        pattern: build_movement_decision(
            pattern, "LEARN",
            selected_learning_method=method,
            user_report={"status": "comfortable"},
            decision_reason="The pattern needs repeatable control before loaded training.",
        )
        for pattern, method in methods.items()
    }

    plan = generate_program(BASE, movement_decisions=decisions)

    assert len(plan["sessions"]) == 2
    assert all(session["session_focus"] == "movement_learning" for session in plan["sessions"])
    expected_patterns = set(methods)
    session_patterns = [
        [task["movement_pattern"] for task in session["learning_tasks"]]
        for session in plan["sessions"]
    ]
    assert [len(patterns) for patterns in session_patterns] == [6, 6]
    assert all(set(patterns) == expected_patterns for patterns in session_patterns)
    all_learning_tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
    ]
    assert all(task["sets"] == 2 for task in all_learning_tasks)
    assert all("controlled reps" in task["reps"] for task in all_learning_tasks)
    assert all("kontrolirane" not in task["reps"] for task in all_learning_tasks)
    assert next(task for task in all_learning_tasks if task["movement_pattern"] == "lunge")["reps"].endswith("per side")
    assert next(task for task in all_learning_tasks if task["movement_pattern"] == "horizontal_pull")["reps"].startswith("6–8")
    assert all(
        exercise["pattern"] not in methods
        for session in plan["sessions"]
        for exercise in session["exercises"]
    )
    assert all(session["estimated_minutes"] >= session["warm_up_minutes"] for session in plan["sessions"])
    assert all(session["estimated_minutes"] <= session["available_minutes"] for session in plan["sessions"])
    assert not any(
        event["action"] == "learning_tasks_deferred_to_later_sessions"
        for event in plan["movement_adaptation"]["events"]
    )




def test_ready_pattern_keeps_the_same_main_exercise_across_weekly_sessions():
    squat = build_movement_decision(
        "squat", "READY",
        user_report={"status": "movement_controlled", "movement_control": {
            "confirmed_by_user": True, "repeatable": True,
            "criteria": {
                "tempo": True, "balance": True, "knee_hip_foot_control": True,
                "lumbopelvic_control": True, "tolerated_rom": True,
            },
        }},
        decision_reason="Počep je po učenju ponovljivo nadzorovan.",
    )
    squat["training_phase"] = "capacity_development"

    plan = generate_program(BASE, movement_decisions={"squat": squat})

    assert len(plan["sessions"]) == 2
    squat_ids_by_session = [
        [item["exercise_id"] for item in session["exercises"] if item["pattern"] == "squat"]
        for session in plan["sessions"]
    ]
    assert all(len(ids) == 1 for ids in squat_ids_by_session)
    assert squat_ids_by_session[0] == squat_ids_by_session[1]



def test_selected_for_learning_creates_learning_task_without_loaded_exercise():
    decision = build_movement_decision(
        "squat", "LEARN",
        selected_learning_method="reaching_counterbalance",
        user_report={"status": "selected_for_learning", "intent": "learn_this_pattern"},
        decision_reason="The user selected the squat pattern to learn.",
    )
    plan = generate_program(BASE, movement_decisions={"squat": decision})
    assert _pattern_exercises(plan, "squat") == []
    tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
        if task["movement_pattern"] == "squat"
    ]
    assert tasks
    assert all(task["method_id"] == "reaching_counterbalance" for task in tasks)
    assert all(task["exercise_id"] is None for task in tasks)



def test_saved_profile_hinge_selection_uses_supported_wall_learning_method():
    decision = build_movement_decision(
        "hinge", "LEARN",
        user_report={"status": "selected_for_learning", "intent": "learn_this_pattern"},
        decision_reason="The user selected the hinge pattern to learn.",
    )
    plan = generate_program(BASE, movement_decisions={"hinge": decision})
    assert _pattern_exercises(plan, "hinge") == []
    tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
        if task["movement_pattern"] == "hinge"
    ]
    assert tasks
    assert all(task["method_id"] == "wall_hip_hinge" for task in tasks)
    assert all(task["exercise_id"] is None for task in tasks)



def test_all_selected_for_learning_patterns_get_safe_learning_methods_without_loaded_work():
    methods = {
        "squat": "reaching_counterbalance",
        "hinge": "wall_hip_hinge",
        "horizontal_push": "incline_push_up",
        "horizontal_pull": "scapular_coordination",
        "vertical_push": "unloaded_overhead_reach",
        "lunge": "supported_split_squat",
    }
    decisions = {
        pattern: build_movement_decision(
            pattern, "LEARN",
            user_report={"status": "selected_for_learning", "intent": "learn_this_pattern"},
            decision_reason="The user selected this pattern for guided learning.",
        )
        for pattern in methods
    }
    profile = {
        **BASE,
        "goal": "functional",
        "experience": "beginner",
        "equipment": ["bodyweight", "household_support", "wall"],
        "session_minutes": 45,
    }
    plan = generate_program(profile, movement_decisions=decisions)
    exercises = [exercise for session in plan["sessions"] for exercise in session["exercises"]]
    tasks = [task for session in plan["sessions"] for task in session["learning_tasks"]]
    assert not any(exercise["pattern"] in methods for exercise in exercises)
    by_pattern = {task["movement_pattern"]: task["method_id"] for task in tasks}
    assert {pattern: by_pattern[pattern] for pattern in methods} == methods



def test_every_foundational_pattern_and_learning_method_has_reviewed_english_copy():
    assert set(PATTERN_DEFINITIONS) == {
        "squat", "hinge", "horizontal_push", "horizontal_pull",
        "vertical_push", "lunge",
    }
    for pattern, definition in PATTERN_DEFINITIONS.items():
        english_pattern = get_pattern_english(pattern)
        assert english_pattern
        assert english_pattern["label"]
        assert english_pattern["task"]
        for method in definition["learning_methods"]:
            english_method = get_method_english(method["id"])
            assert english_method, f"Missing English learning method: {method['id']}"
            assert english_method[0]
            assert english_method[1]


def test_core_movement_exercises_have_complete_english_cues_and_safety_notes():
    core_ids = {
        "supported_squat", "chair_sit_to_stand", "reaching_squat", "air_squat",
        "squat_goblet", "wall_hip_hinge", "bodyweight_hip_hinge",
        "push_up_incline", "push_up", "band_row", "trx_row", "one_arm_row",
        "band_overhead_press", "overhead_press", "supported_split_squat",
        "split_squat", "reverse_lunge", "back_squat", "front_squat",
        "romanian_deadlift", "deadlift", "hip_thrust", "dumbbell_bench_press",
        "barbell_bench_press", "pull_up", "two_dumbbell_squat", "glute_bridge",
        "dumbbell_floor_press", "dumbbell_bent_over_row", "dumbbell_deadlift",
        "dumbbell_squat_side", "dumbbell_squat_front_rack",
        "kettlebell_one_arm_row", "chin_up", "foot_assisted_pull_up",
        "pike_push_up", "barbell_bent_over_row",
    }
    for exercise_id in core_ids:
        exercise = get_exercise(exercise_id)
        assert len(exercise["cues_en"]) == len(exercise["cues"])
        assert len(exercise["warnings_en"]) == len(exercise["warnings"])
        assert all(text.strip() for text in exercise["cues_en"] + exercise["warnings_en"])
    push_up = get_exercise("push_up")
    assert push_up["range_of_motion_en"]
    assert "shoulder-blade control" in push_up["range_of_motion_en"]


def test_functional_programme_exposes_english_full_range_guidance():
    functional = {**BASE, "goal": "functional", "experience": "beginner"}
    plan = generate_program(functional)
    exercises = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
    ]
    english_ranges = [exercise.get("range_of_motion_en") for exercise in exercises]
    assert any(
        isinstance(value, str) and "greatest range of motion" in value
        for value in english_ranges
    )

def test_additional_exercises_have_complete_english_coaching_arrays():
    translated_ids = {
        "forward_lunge", "rear_foot_elevated_split_squat", "atg_split_squat",
        "farmer_carry", "pallof_press", "dead_bug", "lateral_raise",
        "biceps_curl", "triceps_pressdown", "box_jump",
        "band_lat_pulldown", "supported_single_leg_rdl", "walking_lunge",
        "lateral_lunge", "step_up", "bench_dip", "parallel_bar_dip",
        "ring_row", "inverted_row_table", "barbell_overhead_press",
        "kettlebell_swing", "single_leg_rdl", "long_lever_glute_bridge",
        "elevated_heel_hip_lift", "slider_leg_curl", "nordic_hamstring_curl",
        "farmer_carry_bodyweight", "suitcase_carry", "running_easy",
        "brisk_walking", "cycling", "jump_rope", "burpee", "sled_push",
        "rower_intervals", "mountain_climber", "deep_squat_hold",
        "ankle_knee_to_wall", "cossack_squat", "pistol_squat",
        "hip_90_90_switch", "shinbox_getup", "thoracic_rotation_quadruped",
        "shoulder_car", "loaded_deep_squat", "calf_raise_full_rom",
        "tibialis_raise", "copenhagen_plank", "dead_bug_band",
        "single_leg_box_squat", "band_assisted_pull_up", "shoulder_pass_through_stick",
        "wall_slide", "ski_erg_intervals", "air_bike_intervals", "shuttle_run",
        "bear_crawl", "step_up_intervals", "band_assisted_parallel_bar_dip",
        "box_jump_intervals",
        "couch_stretch", "supine_hamstring_stretch", "doorway_pec_stretch",
        "calf_wall_stretch", "wall_push_up", "push_up_decline", "dead_hang",
        "hip_90_90_ir_isometric", "crab_reach", "elevated_pigeon_hinge",
        "straight_leg_hip_hinge", "wall_butterfly", "patrick_step",
        "reverse_nordic_curl", "sled_backward_drag", "front_rack_carry",
        "overhead_carry", "squat_jump", "standing_broad_jump", "heel_elevated_squat",
        "sissy_squat", "l_sit", "single_leg_balance_reach", "lateral_shuffle",
        "seated_leg_lift", "tuck_sit", "hollow_body_hold", "controlled_lateral_step",
        "superman", "kettlebell_lateral_deadlift", "plate_overhead_press",
    }
    assert len(translated_ids) == 91
    source_fields = {
        "cues_en": "cues",
        "warnings_en": "warnings",
        "common_errors_en": "common_errors",
        "regressions_en": "regressions",
        "progressions_en": "progressions",
        "alternatives_en": "alternatives",
    }
    for exercise_id in translated_ids:
        exercise = get_exercise(exercise_id)
        for english_field, source_field in source_fields.items():
            assert len(exercise[english_field]) == len(exercise[source_field])
            assert all(item.strip() for item in exercise[english_field])


def test_entire_exercise_catalogue_has_complete_english_coaching_arrays():
    source_fields = {
        "cues_en": "cues",
        "warnings_en": "warnings",
        "common_errors_en": "common_errors",
        "regressions_en": "regressions",
        "progressions_en": "progressions",
        "alternatives_en": "alternatives",
    }
    exercises = load_catalogue()
    assert len(exercises) == 128
    for exercise in exercises:
        assert exercise["name_en"].strip()
        for english_field, source_field in source_fields.items():
            translated = exercise[english_field]
            source = exercise[source_field]
            assert isinstance(translated, list)
            assert len(translated) == len(source)
            assert all(isinstance(item, str) and item.strip() for item in translated)



def test_program_exposes_english_goal_framework_and_session_titles_without_replacing_slovenian():
    plan = generate_program(BASE)
    assert plan["goal_framework_en"]["label"] == "Strength + Muscle Mass"
    assert "compound exercises" in plan["goal_framework_en"]["description"]
    assert all(session["title"].startswith("Trening ") for session in plan["sessions"])
    assert all(session["title_en"].startswith("Session ") for session in plan["sessions"])
    assert all("Squat" in session["title_en"] or "Full Body" in session["title_en"] or "Targeted Work" in session["title_en"] or "Focused Training" in session["title_en"] for session in plan["sessions"])


def test_fat_loss_program_includes_complete_english_nutrition_guidance():
    plan = generate_program({**BASE, "goal": "fat_loss"})
    assert plan["goal_framework_en"]["label"] == "Fat Loss"
    assert len(plan["nutrition_guidance_en"]) == 5
    assert any("energy deficit" in item for item in plan["nutrition_guidance_en"])
    assert any("resistance training" in item for item in plan["nutrition_guidance_en"])


def test_functional_program_goal_framework_is_localized():
    plan = generate_program({**BASE, "goal": "functional"})
    assert plan["goal_framework_en"]["label"] == "Functional Fitness"
    assert "controlled range of motion" in plan["goal_framework_en"]["description"]


def test_dynamic_coaching_methodology_tempo_and_limitations_have_english_fields():
    plan = generate_program(BASE)
    methodology = plan["methodology_en"]
    assert "greatest range of motion" in methodology["range_of_motion"]
    assert "one principal variable at a time" in methodology["progression"]
    assert methodology["deload"]
    assert plan["limitations_en"]
    prescriptions = [
        exercise["prescription"]
        for session in plan["sessions"]
        for exercise in session["exercises"]
    ]
    assert any(item.get("tempo_description_en") for item in prescriptions)
    for event in (plan.get("movement_adaptation") or {}).get("events", []):
        if event.get("action") in {
            "mild_symptom_load_tempo_and_rom_adjustment",
            "simpler_catalogue_variant_selected",
            "stable_support_cue",
            "kept_selection_pending_user_clarification",
            "ready_for_light_loaded_start",
            "learning_tasks_deferred_to_later_sessions",
            "learning_or_regression_variant_selected",
        }:
            assert event.get("message_en")

def test_functional_preparation_blocks_expose_reviewed_english_fields():
    plan = generate_program({**BASE, "goal": "functional", "experience": "beginner"})
    blocks = [
        session.get("mobility_block")
        for session in plan["sessions"]
        if session.get("mobility_block")
    ]
    assert blocks
    for block in blocks:
        assert block["purpose_en"]
        assert block["amplitude_rule_en"]
        for exercise in block["exercises"]:
            assert exercise["name_en"]
            assert exercise["component_en"] in {"mobility", "balance", "coordination", "stability"}
            assert exercise["tempo_en"] == "slow and controlled"
            assert isinstance(exercise["cues_en"], list)
            assert isinstance(exercise["warnings_en"], list)

