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
    assert plan["program_version"] == "2.3.0"
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
    assert all(int(ex["prescription"]["reps"].split("–")[0]) <= 6 for s in plan["sessions"] for ex in s["exercises"] if ex["pattern"] in {"squat", "hinge", "horizontal_push", "horizontal_pull"})
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


def test_two_day_hypertrophy_program_covers_horizontal_pull_when_band_available():
    profile = {**BASE, "equipment": ["dumbbell", "resistance_band"]}
    plan = generate_program(profile)
    for session in plan["sessions"]:
        patterns = {exercise["pattern"] for exercise in session["exercises"]}
        assert "horizontal_pull" in patterns
    assert any(exercise["exercise_id"] == "band_row" for session in plan["sessions"] for exercise in session["exercises"])


def test_two_day_program_rotates_available_exercise_variants():
    profile = {**BASE, "equipment": ["dumbbell", "resistance_band"]}
    plan = generate_program(profile)
    for pattern in ("squat", "horizontal_push", "horizontal_pull"):
        variants = {
            exercise["exercise_id"]
            for session in plan["sessions"]
            for exercise in session["exercises"]
            if exercise["pattern"] == pattern
        }
        assert len(variants) >= 2, f"Expected variation for {pattern}, got {variants}"


def test_weekly_summary_reports_actual_pattern_exposure():
    plan = generate_program({**BASE, "equipment": ["dumbbell", "resistance_band"]})
    summary = plan["weekly_summary"]
    assert summary["pattern_session_frequency"]["horizontal_pull"] == 2
    assert summary["pattern_work_sets"]["horizontal_pull"] == 6


def test_catalogue_ids_in_regressions_and_alternatives_are_localized():
    plan = generate_program({**BASE, "equipment": ["dumbbell", "resistance_band"]})
    alternatives = [
        value
        for session in plan["sessions"]
        for exercise in session["exercises"]
        for value in exercise["alternatives"] + exercise["regressions"]
    ]
    assert "hip_thrust" not in alternatives
    assert "reverse_lunge" not in alternatives
    assert "Potisk bokov" not in alternatives


def test_glute_bridge_is_not_classified_as_a_hinge():
    from training.catalogue import get_exercise
    assert get_exercise("glute_bridge")["pattern"] == "hip_extension"


def test_unilateral_lunge_reps_are_explicitly_per_side():
    plan = generate_program({**BASE, "session_minutes": 75})
    lunges = [ex for s in plan["sessions"] for ex in s["exercises"] if ex["pattern"] == "lunge"]
    assert lunges
    assert all(ex["reps_per_side"] is True for ex in lunges)
    assert all(ex["prescription"]["rep_unit"] == "per_side" for ex in lunges)


def test_hypertrophy_core_patterns_are_available_in_the_catalogue():
    from training.catalogue import get_exercises
    ids = {ex["id"] for ex in get_exercises(goal="hypertrophy", equipment={"resistance_band"})}
    assert "dead_bug" in ids
    assert "pallof_press" in ids


def test_vertical_pull_band_option_requires_a_safe_anchor_point():
    from training.catalogue import get_exercises
    without_anchor = {ex["id"] for ex in get_exercises(goal="hypertrophy", equipment={"resistance_band"})}
    with_anchor = {ex["id"] for ex in get_exercises(goal="hypertrophy", equipment={"resistance_band", "anchor_point"})}
    assert "band_lat_pulldown" not in without_anchor
    assert "band_lat_pulldown" in with_anchor


def test_exercise_prescriptions_are_not_uniform_for_hypertrophy():
    plan = generate_program({**BASE, "session_minutes": 75})
    prescriptions = {
        (ex["pattern"], ex["prescription"]["reps"], ex["prescription"]["rest_seconds"])
        for s in plan["sessions"] for ex in s["exercises"]
    }
    assert any(pattern == "trunk_stability" and reps == "10–15" and rest == 60 for pattern, reps, rest in prescriptions)
    assert any(pattern == "squat" and reps == "6–10" and rest >= 120 for pattern, reps, rest in prescriptions)



def test_core_stability_reps_are_explicitly_per_side():
    plan = generate_program({**BASE, "session_minutes": 60})
    core = [
        ex for session in plan["sessions"] for ex in session["exercises"]
        if ex["exercise_id"] in {"dead_bug", "pallof_press"}
    ]
    assert {ex["exercise_id"] for ex in core} == {"dead_bug", "pallof_press"}
    assert all(ex["reps_per_side"] is True for ex in core)
    assert all(ex["prescription"]["rep_unit"] == "per_side" for ex in core)


def test_unilateral_time_estimate_accounts_for_both_sides():
    from training.program import _estimated_minutes
    item = {"prescription": {"reps": "8–10", "sets": 3, "rest_seconds": 90, "rep_unit": "per_side"}}
    both = _estimated_minutes([item])
    item["prescription"]["rep_unit"] = "total"
    one_side = _estimated_minutes([item])
    assert both > one_side


def test_alternatives_are_distinct_and_equipment_compatible():
    profile = {**BASE, "equipment": ["dumbbell", "resistance_band"]}
    plan = generate_program(profile)
    for session in plan["sessions"]:
        for exercise in session["exercises"]:
            assert exercise["name"] not in exercise["alternatives"]
            assert all(isinstance(value, str) and value for value in exercise["alternatives"])


def test_45_minute_two_day_hypertrophy_keeps_core_and_vertical_patterns():
    plan = generate_program({**BASE, "session_minutes": 45})
    first = {ex["pattern"] for ex in plan["sessions"][0]["exercises"]}
    second = {ex["pattern"] for ex in plan["sessions"][1]["exercises"]}
    assert "trunk_stability" in first
    assert "vertical_push" in first
    assert "lunge" in first
    assert "anti_rotation" in second
    assert "vertical_pull" in second
    assert "lunge" in second
    assert all(session["estimated_minutes"] <= 45 for session in plan["sessions"])


def test_band_vertical_pull_is_selected_only_with_explicit_anchor_equipment():
    profile = {
        **BASE,
        "equipment": ["dumbbell", "bench", "resistance_band", "anchor_point"],
        "session_minutes": 60,
    }
    plan = generate_program(profile)
    vertical_pulls = [
        ex for session in plan["sessions"] for ex in session["exercises"]
        if ex["pattern"] == "vertical_pull"
    ]
    assert any(ex["exercise_id"] == "band_lat_pulldown" for ex in vertical_pulls)
    assert all("anchor_point" in ex["equipment"] for ex in vertical_pulls if ex["exercise_id"] == "band_lat_pulldown")


def test_hip_thrust_and_glute_bridge_are_classified_as_hip_extension():
    from training.catalogue import get_exercise
    assert get_exercise("glute_bridge")["pattern"] == "hip_extension"
    assert get_exercise("hip_thrust")["pattern"] == "hip_extension"


def test_core_stability_exercises_are_not_labelled_as_compound_lifts():
    plan = generate_program({**BASE, "session_minutes": 60})
    core = [
        ex for session in plan["sessions"] for ex in session["exercises"]
        if ex["pattern"] in {"trunk_stability", "anti_rotation"}
    ]
    assert core
    assert all(ex["exercise_category"] == "stability" for ex in core)


def test_alternatives_preserve_movement_pattern_and_do_not_duplicate_regressions():
    plan = generate_program({**BASE, "equipment": ["dumbbell", "resistance_band"], "session_minutes": 60})
    for session in plan["sessions"]:
        for ex in session["exercises"]:
            assert not set(ex["alternatives"]).intersection(ex["regressions"])
    bridge = next(ex for session in plan["sessions"] for ex in session["exercises"] if ex["exercise_id"] == "glute_bridge")
    assert "Romunski mrtvi dvig" not in bridge["alternatives"]


def test_45_minute_hypertrophy_program_keeps_a_three_minute_time_buffer():
    plan = generate_program({**BASE, "session_minutes": 45})
    assert all(session["estimated_minutes"] <= 42 for session in plan["sessions"])
    first = {ex["pattern"] for ex in plan["sessions"][0]["exercises"]}
    second = {ex["pattern"] for ex in plan["sessions"][1]["exercises"]}
    assert "trunk_stability" in first
    assert "anti_rotation" in second
