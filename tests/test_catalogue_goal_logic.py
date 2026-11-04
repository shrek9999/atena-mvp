"""Quality checks for goal-specific exercise catalogue and programming policy."""
import json
from pathlib import Path

from training.catalogue import get_exercises, load_catalogue
from training.program import _prescription, _session_patterns


def test_catalogue_has_movement_and_loading_taxonomy():
    exercises = load_catalogue()
    assert len(exercises) >= 110
    for item in exercises:
        assert item.get("movement_family")
        assert item.get("loading_mode") in {"bodyweight_or_fixed_environment", "external_load", "mixed"}
        assert isinstance(item.get("mobility_strength"), bool)
        assert isinstance(item.get("functional_components"), list)


def test_sissy_squat_and_l_sit_are_advanced_catalogue_options():
    by_id = {item["id"]: item for item in load_catalogue()}
    assert by_id["sissy_squat"]["level"] == "advanced"
    assert by_id["sissy_squat"]["single_joint"] is True
    assert by_id["l_sit"]["level"] == "advanced"
    assert by_id["l_sit"]["time_based"] is True


def test_mobility_catalogue_includes_strength_through_range():
    by_id = {item["id"]: item for item in load_catalogue()}
    assert "mobility" in by_id["romanian_deadlift"]["goals"]
    assert by_id["atg_split_squat"]["mobility_strength"] is True
    assert by_id["loaded_deep_squat"]["mobility_strength"] is True


def test_functional_week_covers_balance_coordination_power_and_conditioning():
    week = [_session_patterns(i, 2, "functional") for i in range(2)]
    patterns = {pattern for session in week for pattern in session}
    assert {"balance", "coordination", "jump", "conditioning", "squat", "hinge"} <= patterns


def test_fat_loss_sessions_combine_strength_and_conditioning():
    week = [_session_patterns(i, 2, "fat_loss") for i in range(2)]
    assert all("squat" in session and "hinge" in session and "conditioning" in session for session in week)


def test_less_experienced_strength_and_hypertrophy_share_practical_dose():
    squat = {"pattern": "squat", "unilateral": False}
    for level in ("beginner", "intermediate"):
        strength = _prescription("strength", level, "squat", squat)
        hypertrophy = _prescription("hypertrophy", level, "squat", squat)
        combined = _prescription("strength_hypertrophy", level, "squat", squat)
        assert (strength["sets"], strength["reps"], strength["rir"]) == (hypertrophy["sets"], hypertrophy["reps"], hypertrophy["rir"])
        assert (strength["sets"], strength["reps"], strength["rir"]) == (combined["sets"], combined["reps"], combined["rir"])


def test_advanced_strength_and_hypertrophy_are_differentiated():
    squat = {"pattern": "squat", "unilateral": False}
    strength = _prescription("strength", "advanced", "squat", squat)
    hypertrophy = _prescription("hypertrophy", "advanced", "squat", squat)
    assert strength["reps"] != hypertrophy["reps"]
    assert strength["rest_seconds"] > hypertrophy["rest_seconds"]


def test_equipment_gated_calisthenics_never_assume_bars_or_nordic_anchor():
    bodyweight = {item["id"] for item in get_exercises(goal="strength", equipment=["bodyweight"], include_accessories=True)}
    pullup_bar = {item["id"] for item in get_exercises(goal="strength", equipment=["bodyweight", "pull_up_bar"], include_accessories=True)}
    dip_bars = {item["id"] for item in get_exercises(goal="strength", equipment=["bodyweight", "dip_bars"], include_accessories=True)}
    nordic_anchor = {item["id"] for item in get_exercises(goal="strength", equipment=["bodyweight", "secure_ankle_anchor"], include_accessories=True)}
    assert "pull_up" not in bodyweight and "pull_up" in pullup_bar
    assert "parallel_bar_dip" not in bodyweight and "parallel_bar_dip" in dip_bars
    assert "nordic_hamstring_curl" not in bodyweight and "nordic_hamstring_curl" in nordic_anchor


def test_beginner_strength_and_hypertrophy_share_dose_across_main_patterns():
    exercise_patterns = [
        "squat", "hinge", "lunge", "horizontal_push", "horizontal_pull",
        "vertical_push", "vertical_pull",
    ]
    for pattern in exercise_patterns:
        exercise = {"pattern": pattern, "unilateral": pattern == "lunge"}
        strength = _prescription("strength", "beginner", pattern, exercise)
        hypertrophy = _prescription("hypertrophy", "beginner", pattern, exercise)
        assert (strength["sets"], strength["reps"], strength["rir"]) == (
            hypertrophy["sets"], hypertrophy["reps"], hypertrophy["rir"]
        ), pattern


def test_functional_sessions_are_compact_and_distribute_all_capacities():
    week = [_session_patterns(i, 2, "functional") for i in range(2)]
    assert all(len(session) <= 6 for session in week)
    patterns = {pattern for session in week for pattern in session}
    assert {"squat", "hinge", "horizontal_push", "horizontal_pull",
            "balance", "coordination", "jump", "conditioning"} <= patterns


def test_dips_are_classified_as_vertical_push_not_horizontal_push():
    dips = next(item for item in load_catalogue() if item["id"] == "parallel_bar_dip")
    assert dips["pattern"] == "vertical_push"


def test_generated_functional_program_fits_a_normal_session():
    from training.program import generate_program
    result = generate_program({
        "goal": "functional", "experience": "intermediate",
        "sessions_per_week": 2, "session_minutes": 60,
        "equipment": ["barbell", "rack", "plates", "dumbbell", "kettlebell",
                      "bench", "cable", "pull_up_bar"],
    })
    assert len(result["sessions"]) == 2
    assert all(session["estimated_minutes"] <= 60 for session in result["sessions"])
    patterns = {item["pattern"] for session in result["sessions"] for item in session["exercises"]}
    assert {"balance", "coordination", "jump", "conditioning"} <= patterns


def test_generated_fat_loss_program_keeps_strength_and_conditioning_together():
    from training.program import generate_program
    result = generate_program({
        "goal": "fat_loss", "experience": "intermediate",
        "sessions_per_week": 2, "session_minutes": 60,
        "equipment": ["barbell", "rack", "plates", "dumbbell", "kettlebell",
                      "bench", "cable", "pull_up_bar"],
    })
    for session in result["sessions"]:
        patterns = {item["pattern"] for item in session["exercises"]}
        assert "squat" in patterns and "hinge" in patterns and "conditioning" in patterns


def test_generated_mobility_program_contains_strength_through_range():
    from training.program import generate_program
    result = generate_program({
        "goal": "mobility", "experience": "intermediate",
        "sessions_per_week": 2, "session_minutes": 60,
        "equipment": ["dumbbell", "kettlebell"],
    })
    items = [item for session in result["sessions"] for item in session["exercises"]]
    assert any(item["exercise_id"] in {"romanian_deadlift", "loaded_deep_squat", "atg_split_squat"}
               for item in items)


def test_bodyweight_only_progressions_do_not_suggest_unavailable_loaded_variants():
    from training.program import generate_program
    result = generate_program({
        "goal": "strength", "experience": "beginner",
        "sessions_per_week": 2, "session_minutes": 60,
        "equipment": ["bodyweight"],
    })
    unavailable_terms = (
        "ročk", "kettlebell", "mrtvi dvig z dvignjenega položaja", "mrtvi dvig s premorom", "dodatno obremenitvijo",
        "uteži", "bremenom", "drogom", "škripcu", "elastik",
    )
    for session in result["sessions"]:
        for item in session["exercises"]:
            for reference in item["progressions"] + item["regressions"] + item["alternatives"]:
                assert not any(term in reference.casefold() for term in unavailable_terms), (
                    item["exercise_id"], reference
                )


def test_full_gym_strength_plan_keeps_loaded_main_lifts_and_bodyweight_upper_body():
    from training.program import generate_program
    result = generate_program({
        "goal": "strength_hypertrophy", "experience": "advanced",
        "sessions_per_week": 2, "session_minutes": 90,
        "equipment": ["barbell", "rack", "plates", "dumbbell", "kettlebell",
                      "bench", "cable", "pull_up_bar"],
    })
    ids = {item["exercise_id"] for session in result["sessions"] for item in session["exercises"]}
    assert "push_up" in ids
    assert ids.intersection({"pull_up", "chin_up", "foot_assisted_pull_up"})
    assert ids.intersection({"back_squat", "front_squat", "squat_goblet", "dumbbell_squat_front_rack"})
    assert ids.intersection({"deadlift", "romanian_deadlift"})


def test_l_sit_progressions_and_regressions_resolve_to_real_catalogue_exercises():
    by_id = {item["id"]: item for item in load_catalogue()}
    l_sit = by_id["l_sit"]
    assert all(reference in by_id for reference in l_sit["regressions"] + l_sit["alternatives"])
    assert by_id["seated_leg_lift"]["level"] == "beginner"
    assert by_id["tuck_sit"]["level"] == "intermediate"
    assert by_id["hollow_body_hold"]["level"] == "intermediate"


def test_timed_trunk_skills_receive_seconds_not_repetition_counts():
    from training.program import _prescription
    for exercise_id in ("l_sit", "tuck_sit", "hollow_body_hold"):
        exercise = next(item for item in load_catalogue() if item["id"] == exercise_id)
        prescription = _prescription("functional", "advanced", exercise["pattern"], exercise)
        assert prescription["work_seconds"] > 0
        assert prescription["time_label"] == "zadržanja"
        assert "s" in prescription["reps"]
        assert "rir" not in prescription


def test_seated_leg_lift_is_prescribed_as_dynamic_unilateral_repetitions():
    from training.program import _prescription
    exercise = next(item for item in load_catalogue() if item["id"] == "seated_leg_lift")
    prescription = _prescription("functional", "beginner", exercise["pattern"], exercise)
    assert prescription["rep_unit"] == "per_side"
    assert "work_seconds" not in prescription
    assert "s" not in prescription["reps"]



def test_cossack_squat_uses_canonical_english_display_name():
    exercise = next(item for item in load_catalogue() if item["id"] == "cossack_squat")
    assert exercise["name"] == "Cossack squat"
    assert exercise["name_en"] == "Cossack squat"
    assert "kozaški" not in exercise["name"].casefold()


def test_beginner_combined_strength_hypertrophy_uses_foundational_tempo():
    from training.program import _prescription

    patterns = [
        "squat", "lunge", "hinge", "hip_extension",
        "horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull",
    ]
    for pattern in patterns:
        exercise = {"id": f"test_{pattern}", "pattern": pattern, "unilateral": pattern == "lunge"}
        prescription = _prescription("strength_hypertrophy", "beginner", pattern, exercise)
        assert prescription["tempo"] == "3–1–1–0", pattern
        assert prescription["tempo_seconds_per_rep"] == 5, pattern



def test_cossack_squat_progression_uses_canonical_name_without_literal_translation():
    exercise = next(item for item in load_catalogue() if item["id"] == "cossack_squat")
    references = exercise["regressions"] + exercise["progressions"] + exercise["alternatives"]
    assert all("kozaški" not in reference.casefold() for reference in references)
    assert "Cossack squat z ročko" in exercise["progressions"]


def test_beginner_bodyweight_hypertrophy_uses_challenging_posterior_chain_option():
    from training.program import generate_program

    result = generate_program({
        "goal": "strength_hypertrophy",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": ["bodyweight"],
    })
    exercises = [item for session in result["sessions"] for item in session["exercises"]]
    ids = {item["exercise_id"] for item in exercises}
    assert "long_lever_glute_bridge" in ids
    assert "supported_single_leg_rdl" not in ids
    assert "bodyweight_hip_hinge" not in ids
    bridge = next(item for item in exercises if item["exercise_id"] == "long_lever_glute_bridge")
    assert bridge["loading_potential"] == "moderate"
    assert bridge["prescription"]["rir_range"] == "2–3"


def test_bodyweight_only_program_discloses_horizontal_pull_equipment_limit():
    from training.program import generate_program

    result = generate_program({
        "goal": "strength_hypertrophy",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": ["bodyweight"],
    })
    assert "horizontal_pull" in result["weekly_summary"]["unfilled_patterns"]
    assert any("horizontalnega potega" in note for note in result["limitations"])



def test_beginner_combined_goal_methodology_summary_matches_exercise_tempo():
    from training.program import generate_program

    result = generate_program({
        "goal": "strength_hypertrophy",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": ["bodyweight", "dumbbell", "bench"],
    })
    assert "3–1–1–0" in result["methodology"]["tempo"]
    assert "3–1–2–0" not in result["methodology"]["tempo"]
    assert result["program_version"] == "2.8.0"
