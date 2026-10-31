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
    assert plan["program_version"] == "2.6.0"
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
    for session in plan["sessions"]:
        for exercise in session["exercises"]:
            if exercise["pattern"] in {"trunk_stability", "anti_rotation"}:
                assert "rir" not in exercise["prescription"]
                assert exercise["prescription"]["effort_target"]
            else:
                assert exercise["prescription"]["rir"] >= 3


def test_intermediate_strength_program_uses_specific_moderate_rep_ranges():
    profile = {**BASE, "goal": "strength", "experience": "intermediate"}
    plan = generate_program(profile)
    main = [ex for s in plan["sessions"] for ex in s["exercises"] if ex["pattern"] in {"squat", "hinge"}]
    assert main
    assert all(ex["prescription"]["reps"] == "5–8" for ex in main)
    assert all(ex["prescription"]["rest_seconds"] >= 150 for ex in main)


def test_beginner_strength_prioritizes_skill_and_8_to_12_reps():
    profile = {**BASE, "goal": "strength", "experience": "beginner", "equipment": ["dumbbell", "bench"], "session_minutes": 75}
    plan = generate_program(profile)
    squat = next(ex for s in plan["sessions"] for ex in s["exercises"] if ex["pattern"] == "squat")
    assert squat["prescription"]["reps"] == "8–12"
    assert squat["prescription"]["rir"] == 3
    assert squat["prescription"]["rir_range"] == "2–3"
    assert "učenje osnovnih gibalnih vzorcev" in plan["methodology"]["experience_adaptation"]


def test_tempo_and_full_controlled_range_are_explicit_for_every_exercise():
    plan = generate_program({**BASE, "session_minutes": 75})
    exercises = [ex for s in plan["sessions"] for ex in s["exercises"]]
    assert all(ex["prescription"]["tempo"] for ex in exercises)
    assert all(ex["prescription"]["tempo_description"] for ex in exercises)
    assert all(ex["range_of_motion"] for ex in exercises)
    assert all(ex["prescription"]["tempo_seconds_per_rep"] > 0 for ex in exercises)


def test_horizontal_push_prefers_full_range_options_over_floor_press():
    with_bench = generate_program({**BASE, "equipment": ["dumbbell", "bench"], "session_minutes": 75})
    push_ids = {ex["exercise_id"] for s in with_bench["sessions"] for ex in s["exercises"] if ex["pattern"] == "horizontal_push"}
    assert "dumbbell_bench_press" in push_ids or "push_up" in push_ids
    assert "dumbbell_floor_press" not in push_ids
    without_bench = generate_program({**BASE, "equipment": ["dumbbell"], "session_minutes": 75})
    push_ids = {ex["exercise_id"] for s in without_bench["sessions"] for ex in s["exercises"] if ex["pattern"] == "horizontal_push"}
    assert "push_up" in push_ids
    assert "dumbbell_floor_press" not in push_ids


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
    profile = {**BASE, "experience": "advanced", "include_accessories": True, "session_minutes": 75}
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
    for pattern in ("squat", "horizontal_pull"):
        variants = {
            exercise["exercise_id"]
            for session in plan["sessions"]
            for exercise in session["exercises"]
            if exercise["pattern"] == pattern
        }
        assert len(variants) >= 2, f"Expected variation for {pattern}, got {variants}"
    horizontal_push = [
        exercise["exercise_id"]
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] == "horizontal_push"
    ]
    assert horizontal_push
    assert set(horizontal_push) == {"push_up"}


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


def test_hypertrophy_defaults_to_compound_work_without_stability_exercises():
    plan = generate_program({**BASE, "session_minutes": 75})
    exercises = [ex for session in plan["sessions"] for ex in session["exercises"]]
    assert all(ex["pattern"] not in {"trunk_stability", "anti_rotation"} for ex in exercises)
    assert any(ex["pattern"] == "squat" and ex["prescription"]["reps"] == "6–10" for ex in exercises)
    assert all(session["exercise_count"] <= 6 for session in plan["sessions"])



def test_targeted_trunk_stability_exercise_has_clear_rep_unit():
    plan = generate_program({**BASE, "session_minutes": 60}, feedback={"difficulty": "right", "completed": True, "discomfort": "no", "movement_control": "both"})
    core = [
        ex for session in plan["sessions"] for ex in session["exercises"]
        if ex["exercise_id"] == "dead_bug"
    ]
    assert core
    assert all(ex["reps_per_side"] is False for ex in core)
    assert all(ex["prescription"]["rep_unit"] == "total" for ex in core)


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


def test_45_minute_two_day_hypertrophy_is_compact_without_forced_stability():
    plan = generate_program({**BASE, "session_minutes": 45})
    first = {ex["pattern"] for ex in plan["sessions"][0]["exercises"]}
    second = {ex["pattern"] for ex in plan["sessions"][1]["exercises"]}
    assert "trunk_stability" not in first | second
    assert "anti_rotation" not in first | second
    assert "vertical_push" in first and "vertical_pull" in second
    assert "lunge" in first and "lunge" in second
    assert all(session["estimated_minutes"] <= 45 for session in plan["sessions"])
    assert all(session["exercise_count"] <= 6 for session in plan["sessions"])


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
    plan = generate_program({**BASE, "session_minutes": 60}, feedback={"difficulty": "right", "completed": True, "discomfort": "no", "movement_control": "spinal_flexion"})
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
    hinges = [ex for session in plan["sessions"] for ex in session["exercises"] if ex["pattern"] == "hinge"]
    assert hinges
    assert all(ex["loading_potential"] in {"moderate", "high"} for ex in hinges)
    assert all(ex["exercise_id"] != "bodyweight_hip_hinge" for ex in hinges)


def test_45_minute_hypertrophy_program_uses_flexible_time_and_no_default_stability():
    plan = generate_program({**BASE, "session_minutes": 45})
    assert all(session["estimated_minutes"] <= 45 for session in plan["sessions"])
    assert all(session["warm_up_minutes"] == 7 for session in plan["sessions"])
    assert all(session["exercise_count"] <= 6 for session in plan["sessions"])
    assert all(ex["pattern"] not in {"trunk_stability", "anti_rotation"} for s in plan["sessions"] for ex in s["exercises"])



def test_stability_exercises_use_quality_target_instead_of_rir():
    plan = generate_program(BASE, feedback={"difficulty": "right", "completed": True, "discomfort": "no", "movement_control": "bracing"})
    core = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] in {"trunk_stability", "anti_rotation"}
    ]
    assert core
    assert all("rir" not in exercise["prescription"] for exercise in core)
    assert all("izgubiš stabilen položaj" in exercise["prescription"]["effort_target"] for exercise in core)


def test_hard_feedback_does_not_break_stability_prescriptions():
    plan = generate_program(
        BASE,
        feedback={"difficulty": "hard", "completed": False, "discomfort": "no", "movement_control": "both"},
    )
    core = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] in {"trunk_stability", "anti_rotation"}
    ]
    assert core
    assert all("rir" not in exercise["prescription"] for exercise in core)
    assert all(exercise["prescription"]["sets"] >= 2 for exercise in core)



def test_beginner_hypertrophy_uses_foundational_repetition_range():
    plan = generate_program({**BASE, "goal": "hypertrophy", "experience": "beginner", "equipment": ["dumbbell", "bench"], "session_minutes": 75})
    squat = next(ex for s in plan["sessions"] for ex in s["exercises"] if ex["pattern"] == "squat")
    assert squat["prescription"]["reps"] == "8–12"
    assert squat["prescription"]["rir_range"] == "2–3"



def test_beginner_without_weights_still_practises_the_hinge_pattern():
    plan = generate_program({
        **BASE, "goal": "strength", "experience": "beginner",
        "equipment": [], "session_minutes": 60,
    })
    hinge = [ex for session in plan["sessions"] for ex in session["exercises"] if ex["pattern"] == "hinge"]
    assert hinge
    assert all(ex["exercise_id"] == "bodyweight_hip_hinge" for ex in hinge)


def test_beginner_with_dumbbells_uses_a_loaded_beginner_hinge():
    plan = generate_program({
        **BASE, "goal": "strength", "experience": "beginner",
        "equipment": ["dumbbell", "bench"], "session_minutes": 75,
    })
    hinge = [ex for session in plan["sessions"] for ex in session["exercises"] if ex["pattern"] == "hinge"]
    assert hinge
    assert all(ex["exercise_id"] == "dumbbell_deadlift" for ex in hinge)


def test_hard_feedback_updates_beginner_rir_range_consistently():
    plan = generate_program(
        {**BASE, "goal": "strength", "experience": "beginner", "equipment": ["dumbbell", "bench"]},
        feedback={"difficulty": "hard", "completed": False, "discomfort": "no"},
    )
    loaded = [
        ex for session in plan["sessions"] for ex in session["exercises"]
        if ex["prescription"].get("rir_range")
    ]
    assert loaded
    assert all(ex["prescription"]["rir_range"] == "3–4" for ex in loaded)



def test_time_budget_preserves_key_patterns_before_reducing_main_lift_sets():
    plan = generate_program({**BASE, "session_minutes": 45})
    for session in plan["sessions"]:
        assert session["estimated_minutes"] <= 45
        assert isinstance(session["volume_adjustments"], list)
        assert all(
            ex["pattern"] in {"squat", "hinge", "horizontal_push", "horizontal_pull"}
            for ex in session["exercises"]
            if ex["name"] in session["volume_adjustments"]
        )


def test_stability_work_is_first_after_warmup_when_feedback_supports_it():
    plan = generate_program(BASE, feedback={"difficulty": "right", "completed": True, "discomfort": "no", "movement_control": "bracing"})
    for session in plan["sessions"]:
        assert session["exercises"][0]["pattern"] == "trunk_stability"
        assert "po splošnem ogrevanju" in session["exercises"][0]["coaching_note"]


def test_hypertrophy_without_stability_feedback_has_five_or_six_exercises():
    plan = generate_program({**BASE, "session_minutes": 60})
    assert all(5 <= len(session["exercises"]) <= 6 for session in plan["sessions"])
    assert all(ex["pattern"] not in {"trunk_stability", "anti_rotation"} for s in plan["sessions"] for ex in s["exercises"])


def test_warmup_is_flexible_and_included_in_session_estimate():
    plans = [generate_program({**BASE, "session_minutes": n}) for n in (30, 45, 75)]
    assert [p["sessions"][0]["warm_up_minutes"] for p in plans] == [5, 7, 10]
    assert all(s["estimated_minutes"] <= s["available_minutes"] for p in plans for s in p["sessions"])


def test_hypertrophy_default_program_has_no_automatic_stability_exercises():
    plan = generate_program({**BASE, "goal": "hypertrophy"})
    assert all(
        exercise["pattern"] not in {"trunk_stability", "anti_rotation"}
        for session in plan["sessions"] for exercise in session["exercises"]
    )


def test_warmup_duration_is_flexible_and_included_in_total_estimate():
    plans = [generate_program({**BASE, "session_minutes": n}) for n in (30, 45, 75)]
    assert [p["sessions"][0]["warm_up_minutes"] for p in plans] == [5, 7, 10]
    assert all(s["estimated_minutes"] <= s["available_minutes"] for p in plans for s in p["sessions"])


def test_poor_recovery_reduces_only_main_compound_sets():
    profile = {**BASE, "experience": "advanced", "session_minutes": 75, "include_accessories": True}
    normal = generate_program(profile, feedback={"difficulty": "right", "completed": True, "discomfort": "no"})
    adjusted = generate_program(profile, feedback={"difficulty": "right", "completed": True, "discomfort": "no", "recovery": "poor"})
    normal_by_id = {ex["exercise_id"]: ex for s in normal["sessions"] for ex in s["exercises"]}
    adjusted_by_id = {ex["exercise_id"]: ex for s in adjusted["sessions"] for ex in s["exercises"]}
    for exercise_id, exercise in normal_by_id.items():
        revised = adjusted_by_id[exercise_id]
        if exercise["exercise_category"] == "compound" and exercise["prescription"]["sets"] > 2:
            assert revised["prescription"]["sets"] == exercise["prescription"]["sets"] - 1
        else:
            assert revised["prescription"]["sets"] == exercise["prescription"]["sets"]


def test_movement_control_feedback_is_validated():
    from training.program import ProgramValidationError
    with pytest.raises(ProgramValidationError, match="movement_control"):
        generate_program(BASE, feedback={"difficulty": "right", "completed": True, "discomfort": "no", "movement_control": "diagnosis"})


def test_recovery_feedback_is_validated():
    from training.program import ProgramValidationError
    with pytest.raises(ProgramValidationError, match="recovery"):
        generate_program(BASE, feedback={"difficulty": "right", "completed": True, "discomfort": "no", "recovery": "unknown"})



def test_hypertrophy_without_weights_uses_scalable_posterior_chain_options():
    profile = {
        **BASE,
        "goal": "hypertrophy",
        "experience": "intermediate",
        "equipment": ["bodyweight", "chair", "towel", "wall", "household_support", "household_load"],
        "session_minutes": 60,
    }
    plan = generate_program(profile)
    exercises = [exercise for session in plan["sessions"] for exercise in session["exercises"]]
    posterior = [exercise for exercise in exercises if exercise["pattern"] in {"hip_extension", "knee_flexion"}]
    assert posterior
    assert all(exercise["exercise_id"] != "bodyweight_hip_hinge" for exercise in posterior)
    assert all(exercise["loading_potential"] in {"moderate", "high"} for exercise in posterior)
    assert any(exercise["exercise_id"] == "inverted_row_table" for exercise in exercises)
    assert any(exercise["exercise_id"] == "single_leg_box_squat" for exercise in exercises)


def test_endurance_goal_generates_timed_aerobic_and_interval_work():
    profile = {
        **BASE,
        "goal": "endurance",
        "experience": "beginner",
        "equipment": ["bodyweight", "chair", "household_support", "household_load"],
        "session_minutes": 45,
    }
    plan = generate_program(profile)
    exercises = [exercise for session in plan["sessions"] for exercise in session["exercises"]]
    timed = [exercise for exercise in exercises if exercise["prescription"].get("work_seconds")]
    assert any(exercise["pattern"] == "locomotion" for exercise in timed)
    assert any(exercise["pattern"] == "conditioning" for exercise in timed)
    assert all(session["estimated_minutes"] <= 45 for session in plan["sessions"])
    assert all(exercise["prescription"]["rir"] is None for exercise in timed)
    assert plan["weekly_summary"]["endurance_type_work_seconds"]["aerobic"] > 0
    assert plan["weekly_summary"]["endurance_type_work_seconds"]["anaerobic"] > 0
    assert plan["weekly_summary"]["primary_muscle_set_exposure"] == {}


def test_mobility_goal_includes_active_mobility_and_loaded_range_options():
    profile = {
        **BASE,
        "goal": "mobility",
        "experience": "beginner",
        "equipment": ["bodyweight", "chair", "wall", "household_support"],
        "session_minutes": 60,
    }
    plan = generate_program(profile)
    exercises = [exercise for session in plan["sessions"] for exercise in session["exercises"]]
    mobility_drills = [exercise for exercise in exercises if exercise["pattern"] == "mobility"]
    assert len(mobility_drills) >= 4
    assert len({exercise["exercise_id"] for exercise in mobility_drills}) == len(mobility_drills)
    assert any(exercise["training_role"] == "mobility" for exercise in exercises)
    assert any(exercise["exercise_id"] in {"calf_raise_full_rom", "tibialis_raise"} for exercise in exercises)
    assert plan["weekly_summary"]["pattern_session_frequency"]["mobility"] == 2
    assert plan["weekly_summary"]["pattern_session_frequency"]["mobility_stretch"] == 2
    timed_stretches = [exercise for exercise in exercises if exercise["pattern"] == "mobility_stretch"]
    assert timed_stretches
    assert all(exercise["reps_per_side"] for exercise in timed_stretches)
    assert any(exercise["pattern"] in {"squat", "lunge", "hinge"} for exercise in exercises)
    assert all(session["estimated_minutes"] <= 60 for session in plan["sessions"])
    assert plan["weekly_summary"]["time_based_work_seconds"] > 0


def test_timed_work_is_included_in_session_duration_estimate():
    from training.program import _estimated_minutes
    items = [{
        "prescription": {
            "sets": 6, "reps": "30 s", "work_seconds": 30,
            "rest_seconds": 30, "rep_unit": "total",
        }
    }]
    assert _estimated_minutes(items, warm_up_minutes=0) == 6



def test_generated_exercises_include_catalogue_backed_regressions_and_progressions():
    profile = {
        **BASE,
        "goal": "mobility",
        "experience": "beginner",
        "equipment": ["bodyweight", "chair", "wall", "household_support"],
        "session_minutes": 60,
    }
    plan = generate_program(profile)
    reaching = next(
        exercise for session in plan["sessions"] for exercise in session["exercises"]
        if exercise["exercise_id"] == "reaching_squat"
    )
    assert "Počep z lastno težo (air squat)" in reaching["progressions"]



def test_bodyweight_squat_does_not_claim_an_unused_household_support():
    profile = {
        **BASE,
        "goal": "general_fitness",
        "experience": "beginner",
        "equipment": ["bodyweight", "chair", "couch", "step", "towel", "wall", "household_support", "household_load"],
        "session_minutes": 60,
    }
    plan = generate_program(profile)
    exercises = [exercise for session in plan["sessions"] for exercise in session["exercises"]]
    air_squat = next(exercise for exercise in exercises if exercise["exercise_id"] == "air_squat")
    assert air_squat["equipment"] == ["bodyweight"]
