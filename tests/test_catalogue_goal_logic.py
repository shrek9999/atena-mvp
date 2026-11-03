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


def test_beginner_strength_and_hypertrophy_share_practical_dose():
    squat = {"pattern": "squat", "unilateral": False}
    strength = _prescription("strength", "beginner", "squat", squat)
    hypertrophy = _prescription("hypertrophy", "beginner", "squat", squat)
    combined = _prescription("strength_hypertrophy", "beginner", "squat", squat)
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
