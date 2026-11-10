"""Five-persona product validation: beginner, regular, mobility-limited,
muscle-mass focused and conditioning-focused users.

These are deterministic planner acceptance tests, not evidence of real-human
usability or live LLM conversation quality.
"""
from training.catalogue import get_exercise
from training.program import generate_program


PERSONAS = {
    "beginner": {
        "goal": "strength",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 30,
        "equipment": ["bodyweight", "chair", "dumbbell"],
    },
    "regular_functional": {
        "goal": "functional",
        "experience": "intermediate",
        "sessions_per_week": 3,
        "session_minutes": 45,
        "equipment": ["bodyweight", "dumbbell", "kettlebell", "resistance_band",
                      "anchor_point", "pull_up_bar", "chair", "household_support"],
    },
    "mobility_limited": {
        "goal": "functional",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 45,
        "equipment": ["bodyweight", "chair", "wall", "household_support",
                      "dumbbell", "resistance_band", "anchor_point"],
    },
    "muscle_mass": {
        "goal": "hypertrophy",
        "experience": "advanced",
        "sessions_per_week": 3,
        "session_minutes": 75,
        "equipment": ["bodyweight", "barbell", "rack", "dumbbell", "bench",
                      "pull_up_bar", "kettlebell", "cable"],
        "include_accessories": True,
    },
    "conditioning": {
        "goal": "endurance",
        "experience": "beginner",
        "sessions_per_week": 3,
        "session_minutes": 45,
        "equipment": ["bodyweight", "bicycle", "jump_rope", "step"],
    },
}


def _all_exercises(plan):
    return [exercise for session in plan["sessions"] for exercise in session["exercises"]]


def _patterns(plan):
    return {exercise["pattern"] for exercise in _all_exercises(plan)}


def test_five_persona_programmes_respect_schedule_time_catalogue_and_equipment():
    for persona, profile in PERSONAS.items():
        plan = generate_program(profile)
        assert len(plan["sessions"]) == profile["sessions_per_week"], persona
        assert plan["goal"] == profile["goal"], persona
        assert plan["experience"] == profile["experience"], persona
        for session in plan["sessions"]:
            assert 3 <= len(session["exercises"]) <= 6, (persona, session)
            assert session["estimated_minutes"] <= profile["session_minutes"], persona
            for exercise in session["exercises"]:
                catalogue_entry = get_exercise(exercise["exercise_id"])
                assert catalogue_entry is not None, (persona, exercise["exercise_id"])
                assert set(catalogue_entry["equipment"]).issubset(
                    set(profile["equipment"]) | {"bodyweight"}
                ), (persona, exercise["exercise_id"])


def test_beginner_gets_a_manageable_skill_and_effort_envelope():
    plan = generate_program(PERSONAS["beginner"])
    for exercise in _all_exercises(plan):
        if exercise["pattern"] not in {"trunk_stability", "anti_rotation"}:
            assert exercise["prescription"]["sets"] <= 3
            assert exercise["prescription"]["rir"] >= 3
            assert exercise["prescription"]["reps"] in {"8–10", "8–12", "10–15", "12–15"}


def test_regular_functional_user_gets_weekly_pattern_variety_without_session_bloat():
    plan = generate_program(PERSONAS["regular_functional"])
    patterns = _patterns(plan)
    assert {"squat", "hinge", "horizontal_push", "horizontal_pull"}.issubset(patterns)
    assert len(plan["sessions"]) == 3
    assert all(len(session["exercises"]) <= 6 for session in plan["sessions"])


def test_mobility_limited_user_gets_supported_variants_and_no_automatic_progression():
    plan = generate_program(
        PERSONAS["mobility_limited"],
        movement_assessment={
            "squat": "needs_support",
            "hinge": "needs_support",
            "lunge": "needs_support",
        },
    )
    exercises = _all_exercises(plan)
    by_pattern = {
        pattern: [exercise for exercise in exercises if exercise["pattern"] == pattern]
        for pattern in ("squat", "hinge", "lunge")
    }
    assert by_pattern["squat"]
    assert all(item["exercise_id"] in {"chair_sit_to_stand", "reaching_squat", "air_squat"}
               for item in by_pattern["squat"])
    assert by_pattern["hinge"]
    assert all(item["exercise_id"] == "wall_hip_hinge" for item in by_pattern["hinge"])
    assert by_pattern["lunge"]
    assert all(item["exercise_id"] == "supported_split_squat" for item in by_pattern["lunge"])
    assert plan["movement_adaptation"]["automatic_progression"] == (
        "movement_assessment_does_not_trigger_progression"
    )


def test_muscle_mass_user_gets_compound_foundation_and_only_opted_in_accessories():
    plan = generate_program(PERSONAS["muscle_mass"])
    exercises = _all_exercises(plan)
    assert {"squat", "hinge", "horizontal_push", "horizontal_pull"}.issubset(_patterns(plan))
    assert any(item["joint_type"] == "multi_joint" for item in exercises)
    assert any(item["joint_type"] == "single_joint" for item in exercises)
    assert all(item["prescription"].get("tempo") for item in exercises)


def test_conditioning_user_gets_conditioning_and_locomotion_not_random_metcon_only():
    plan = generate_program(PERSONAS["conditioning"])
    patterns = _patterns(plan)
    assert "conditioning" in patterns
    assert "locomotion" in patterns
    assert len(plan["sessions"]) == 3
    assert all(session["estimated_minutes"] <= 45 for session in plan["sessions"])
