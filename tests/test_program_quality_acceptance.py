"""Programme quality acceptance matrix for ATENA's deterministic planner.

These tests validate structural coaching rules, not real-world effectiveness,
movement quality or live conversational usability.
"""
from training.catalogue import get_exercise
from training.program import generate_program
from training.movement_coaching import build_movement_decision, get_exercise_options


PERSONAS = {
    "beginner": {
        "goal": "strength", "experience": "beginner", "sessions_per_week": 2,
        "session_minutes": 30, "equipment": ["bodyweight", "chair", "dumbbell"],
    },
    "occasional": {
        "goal": "strength_hypertrophy", "experience": "beginner", "sessions_per_week": 2,
        "session_minutes": 30, "equipment": ["bodyweight", "dumbbell", "chair"],
    },
    "regular_functional": {
        "goal": "functional", "experience": "intermediate", "sessions_per_week": 3,
        "session_minutes": 45,
        "equipment": ["bodyweight", "dumbbell", "kettlebell", "resistance_band",
                      "anchor_point", "pull_up_bar", "chair", "household_support"],
    },
    "mobility_limited": {
        "goal": "functional", "experience": "beginner", "sessions_per_week": 2,
        "session_minutes": 45,
        "equipment": ["bodyweight", "chair", "wall", "household_support",
                      "dumbbell", "resistance_band", "anchor_point"],
    },
    "muscle_mass": {
        "goal": "hypertrophy", "experience": "advanced", "sessions_per_week": 3,
        "session_minutes": 75,
        "equipment": ["bodyweight", "barbell", "rack", "dumbbell", "bench",
                      "pull_up_bar", "kettlebell", "cable"],
        "include_accessories": True,
    },
    "conditioning": {
        "goal": "endurance", "experience": "beginner", "sessions_per_week": 3,
        "session_minutes": 45, "equipment": ["bodyweight", "bicycle", "jump_rope", "step"],
    },
    "home_no_equipment": {
        "goal": "functional", "experience": "beginner", "sessions_per_week": 2,
        "session_minutes": 30, "equipment": ["bodyweight"],
    },
}


def _all_exercises(plan):
    return [exercise for session in plan["sessions"] for exercise in session["exercises"]]


def _by_id(plan):
    return {
        exercise["exercise_id"]: exercise
        for exercise in _all_exercises(plan)
    }


def test_all_seven_personas_receive_complete_and_equipment_compatible_programmes():
    for persona, profile in PERSONAS.items():
        plan = generate_program(profile)
        assert plan["goal"] == profile["goal"], persona
        assert plan["experience"] == profile["experience"], persona
        assert len(plan["sessions"]) == profile["sessions_per_week"], persona
        assert plan["sessions"], persona

        for session in plan["sessions"]:
            assert session["exercises"], (persona, session)
            assert session["estimated_minutes"] <= profile["session_minutes"], (persona, session)

        for exercise in _all_exercises(plan):
            catalogue_entry = get_exercise(exercise["exercise_id"])
            assert catalogue_entry is not None, (persona, exercise)
            assert set(exercise["equipment"]).issubset(
                set(profile["equipment"]) | {"bodyweight"}
            ), (persona, exercise)
            assert set(catalogue_entry["equipment"]).issubset(
                set(profile["equipment"]) | {"bodyweight"}
            ), (persona, exercise)


def test_every_programmed_exercise_has_coaching_and_range_of_motion_guidance():
    for persona, profile in PERSONAS.items():
        plan = generate_program(profile)
        for exercise in _all_exercises(plan):
            prescription = exercise["prescription"]
            assert isinstance(prescription["sets"], int) and prescription["sets"] >= 1, (persona, exercise)
            assert isinstance(prescription["rest_seconds"], int) and prescription["rest_seconds"] >= 0
            assert prescription.get("tempo"), (persona, exercise)
            assert prescription.get("tempo_description"), (persona, exercise)
            assert isinstance(prescription.get("tempo_seconds_per_rep"), (int, float))
            assert exercise.get("range_of_motion", "").strip(), (persona, exercise)
            assert exercise.get("cues"), (persona, exercise)
            assert exercise.get("warnings") is not None, (persona, exercise)


def test_strength_and_hypertrophy_resistance_work_keeps_a_reasonable_effort_reserve():
    for persona in ("beginner", "occasional", "muscle_mass"):
        plan = generate_program(PERSONAS[persona])
        resistance = [
            item for item in _all_exercises(plan)
            if item["exercise_category"] in {"compound", "accessory"}
        ]
        assert resistance, persona
        for exercise in resistance:
            prescription = exercise["prescription"]
            assert 1 <= prescription["sets"] <= 5, (persona, exercise)
            assert prescription.get("rir") is not None, (persona, exercise)
            assert 1 <= prescription["rir"] <= 5, (persona, exercise)


def test_unilateral_exercises_are_explicitly_prescribed_per_side():
    for persona, profile in PERSONAS.items():
        plan = generate_program(profile)
        for exercise in _all_exercises(plan):
            catalogue_entry = get_exercise(exercise["exercise_id"])
            if catalogue_entry.get("unilateral") or catalogue_entry.get("reps_per_side"):
                assert exercise["prescription"]["rep_unit"] == "per_side", (persona, exercise)


def test_programme_explains_progression_and_changes_only_a_small_dose_after_easy_feedback():
    profile = PERSONAS["regular_functional"]
    baseline = generate_program(profile)
    easier = generate_program(
        profile,
        feedback={"difficulty": "easy", "completed": True, "recovery": "normal"},
    )
    base_by_id = _by_id(baseline)
    easy_by_id = _by_id(easier)
    common_ids = set(base_by_id) & set(easy_by_id)
    assert common_ids
    assert any(
        easy_by_id[key]["prescription"] != base_by_id[key]["prescription"]
        for key in common_ids
    )
    for exercise in _all_exercises(baseline):
        logic = exercise["coaching_logic"]
        assert any("dveh izpostavitvah" in condition for condition in logic["progress_when"])
        assert len(logic["progression_order"]) >= 3
        assert "spreminjaj samo eno glavno spremenljivko naenkrat" in logic["progression_order"]


def test_hard_feedback_reduces_actual_next_training_dose():
    profile = PERSONAS["regular_functional"]
    baseline = generate_program(profile)
    easier_next = generate_program(
        profile,
        feedback={"difficulty": "hard", "completed": True, "recovery": "normal"},
    )
    base_by_id = _by_id(baseline)
    hard_by_id = _by_id(easier_next)
    common_ids = set(base_by_id) & set(hard_by_id)
    assert common_ids
    assert any(
        hard_by_id[key]["prescription"] != base_by_id[key]["prescription"]
        for key in common_ids
    )
    assert any(
        "adjustment_note" in hard_by_id[key]["prescription"]
        for key in common_ids
    )


def test_poor_recovery_reduces_compound_volume_without_rewriting_the_whole_programme():
    profile = PERSONAS["regular_functional"]
    baseline = generate_program(profile)
    reduced = generate_program(
        profile,
        feedback={"difficulty": "right", "completed": True, "recovery": "poor"},
    )
    base_by_id = _by_id(baseline)
    reduced_by_id = _by_id(reduced)
    common_ids = set(base_by_id) & set(reduced_by_id)
    assert common_ids
    assert any(
        reduced_by_id[key]["prescription"]["sets"] < base_by_id[key]["prescription"]["sets"]
        for key in common_ids
    )


def test_no_equipment_profile_does_not_invent_a_horizontal_pull_exercise():
    plan = generate_program(PERSONAS["home_no_equipment"])
    assert "horizontal_pull" in plan["weekly_summary"]["unfilled_patterns"]
    assert all(
        set(exercise["equipment"]).issubset({"bodyweight"})
        for exercise in _all_exercises(plan)
    )
    assert any("horizontalnega potega" in item for item in plan["limitations"])


def test_reported_discomfort_blocks_programme_adaptation():
    from training.program import ProgramSafetyBlock

    try:
        generate_program(
            PERSONAS["beginner"],
            feedback={"discomfort": "yes"},
        )
    except ProgramSafetyBlock:
        return
    raise AssertionError("Reported discomfort must block automatic programme adaptation")



def test_mobility_limited_persona_adapts_only_the_assessed_squat_pattern():
    profile = PERSONAS["mobility_limited"]
    baseline = generate_program(profile)

    squat_decision = build_movement_decision(
        "squat",
        "LEARN",
        user_report={"status": "needs_support"},
        selected_learning_method="target_squat",
        selected_exercise_id="chair_sit_to_stand",
        decision_reason="Acceptance test: limited squat capacity requires a supported learning variation.",
    )
    adapted = generate_program(profile, movement_decisions={"squat": squat_decision})

    def exercise_ids_by_pattern(plan):
        result = {}
        for exercise in _all_exercises(plan):
            result.setdefault(exercise["pattern"], set()).add(exercise["exercise_id"])
        return result

    baseline_patterns = exercise_ids_by_pattern(baseline)
    adapted_patterns = exercise_ids_by_pattern(adapted)

    assert "squat" not in adapted_patterns
    for pattern, exercise_ids in baseline_patterns.items():
        if pattern != "squat":
            assert adapted_patterns.get(pattern) == exercise_ids, pattern
    assert any(pattern != "squat" for pattern in adapted_patterns)

    events = adapted["movement_adaptation"]["events"]
    assert any(
        event["pattern"] == "squat"
        and event["action"] == "unloaded_learning_task_only"
        for event in events
    )
    assert any(
        task["movement_pattern"] == "squat"
        and task["method_id"] == "target_squat"
        and task["exercise_id"] is None
        for session in adapted["sessions"] for task in session["learning_tasks"]
    )



def test_chair_sit_to_stand_is_registered_as_a_squat_learning_option():
    profile = PERSONAS["mobility_limited"]
    options = get_exercise_options(
        "squat",
        equipment=profile["equipment"],
        experience=profile["experience"],
        goal=None,
    )
    assert "chair_sit_to_stand" in {exercise["id"] for exercise in options}
