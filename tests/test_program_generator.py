import pytest

from training.program import ProgramValidationError, generate_program, validate_profile


BASE = {
    "goal": "hypertrophy",
    "experience": "intermediate",
    "equipment": ["barbell", "rack", "dumbbell", "bench", "pull_up_bar", "kettlebell", "cable", "resistance_band", "box"],
    "sessions_per_week": 2,
    "session_minutes": 60,
}


def test_generates_two_day_hypertrophy_program_from_catalogue_only():
    plan = generate_program(BASE)
    assert plan["program_version"] == "2.0.0"
    assert len(plan["sessions"]) == 2
    assert all(len(session["exercises"]) >= 3 for session in plan["sessions"])
    assert all(ex["joint_type"] == "multi_joint" for session in plan["sessions"] for ex in session["exercises"])
    assert all(session["estimated_minutes"] <= 60 for session in plan["sessions"])


def test_hypertrophy_excludes_single_joint_accessories_by_default():
    plan = generate_program(BASE)
    assert not any(ex["joint_type"] == "single_joint" for s in plan["sessions"] for ex in s["exercises"])


def test_advanced_user_can_opt_into_single_joint_accessories():
    profile = {**BASE, "experience": "advanced", "include_accessories": True}
    plan = generate_program(profile)
    assert plan["methodology"]["single_joint_accessories"] is True


def test_beginner_receives_lower_effort_and_volume():
    profile = {**BASE, "experience": "beginner", "equipment": ["dumbbell", "bench"]}
    plan = generate_program(profile)
    assert all(ex["prescription"]["rir"] >= 3 for s in plan["sessions"] for ex in s["exercises"])


def test_strength_program_uses_lower_rep_ranges_and_longer_rests():
    profile = {**BASE, "goal": "strength"}
    plan = generate_program(profile)
    assert all(int(ex["prescription"]["reps"].split("–")[0]) <= 6 for s in plan["sessions"] for ex in s["exercises"])
    assert all(ex["prescription"]["rest_seconds"] >= 150 for s in plan["sessions"] for ex in s["exercises"] if ex["pattern"] in {"squat", "hinge", "horizontal_push", "horizontal_pull"})


def test_equipment_filter_respected_for_every_exercise():
    profile = {**BASE, "equipment": ["dumbbell", "bench"]}
    plan = generate_program(profile)
    for session in plan["sessions"]:
        for exercise in session["exercises"]:
            assert set(exercise["equipment"]).issubset({"dumbbell", "bench", "bodyweight"})


def test_excluded_exercises_are_never_selected():
    profile = {**BASE, "excluded_exercise_ids": ["squat_goblet", "romanian_deadlift"]}
    plan = generate_program(profile)
    ids = {ex["exercise_id"] for s in plan["sessions"] for ex in s["exercises"]}
    assert "squat_goblet" not in ids
    assert "romanian_deadlift" not in ids


def test_excluded_pattern_is_respected():
    profile = {**BASE, "excluded_patterns": ["lunge"]}
    plan = generate_program(profile)
    assert all(ex["pattern"] != "lunge" for s in plan["sessions"] for ex in s["exercises"])


def test_duration_is_bounded_and_reported():
    plan = generate_program({**BASE, "session_minutes": 45})
    assert all(s["estimated_minutes"] <= 45 for s in plan["sessions"])


def test_invalid_goal_or_session_count_is_rejected():
    with pytest.raises(ProgramValidationError):
        generate_program({**BASE, "goal": "lose_pain"})
    with pytest.raises(ProgramValidationError):
        generate_program({**BASE, "sessions_per_week": 5})


def test_single_joint_accessories_are_restricted_to_advanced_level():
    with pytest.raises(ProgramValidationError, match="naprednim"):
        validate_profile({**BASE, "include_accessories": True})


def test_program_does_not_invent_exercises():
    from training.catalogue import load_catalogue
    known = {item["id"] for item in load_catalogue()}
    plan = generate_program(BASE)
    assert all(ex["exercise_id"] in known for s in plan["sessions"] for ex in s["exercises"])



def test_advanced_accessory_option_adds_single_joint_exercise():
    profile = {**BASE, "experience": "advanced", "include_accessories": True}
    plan = generate_program(profile)
    assert any(ex["joint_type"] == "single_joint" for s in plan["sessions"] for ex in s["exercises"])


def test_functional_goal_uses_supported_general_fitness_catalogue_pool():
    plan = generate_program({**BASE, "goal": "functional"})
    assert len(plan["sessions"]) == 2
    assert all(len(s["exercises"]) >= 3 for s in plan["sessions"])


def test_power_goal_uses_catalogue_power_exercises():
    plan = generate_program({**BASE, "goal": "power"})
    patterns = {ex["pattern"] for s in plan["sessions"] for ex in s["exercises"]}
    assert "jump" in patterns
    assert "hinge_power" in patterns


def test_three_and_four_day_splits_are_supported():
    for sessions in (3, 4):
        plan = generate_program({**BASE, "sessions_per_week": sessions})
        assert len(plan["sessions"]) == sessions
