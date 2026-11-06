"""Extended validation across goals, training ages, equipment and exclusions."""
from itertools import product

import pytest

from training.catalogue import get_exercise, load_catalogue
from training.program import generate_program


GOALS = ("strength_hypertrophy", "fat_loss")
LEVELS = ("beginner", "intermediate", "advanced")


@pytest.mark.parametrize("goal,experience", list(product(GOALS, LEVELS)))
def test_extended_goal_and_experience_profiles(goal, experience):
    frequency = 4 if goal == "strength_hypertrophy" else 3
    profile = {
        "goal": goal,
        "experience": experience,
        "sessions_per_week": frequency,
        "session_minutes": 75,
        "equipment": [
            "bodyweight", "barbell", "rack", "weight_plate", "dumbbell",
            "kettlebell", "bench", "cable", "pull_up_bar", "resistance_band",
        ],
    }
    if experience == "advanced":
        profile["include_accessories"] = goal == "strength_hypertrophy"
    if experience == "advanced" and goal == "strength_hypertrophy":
        profile["training_emphasis"] = "strength"

    plan = generate_program(profile)
    assert len(plan["sessions"]) == frequency
    for session in plan["sessions"]:
        assert session["estimated_minutes"] <= profile["session_minutes"]
        assert session["exercise_count"] == len(session["exercises"])
        assert session["exercise_count"] >= 3
        for item in session["exercises"]:
            source = get_exercise(item["exercise_id"])
            assert source is not None
            assert set(source["equipment"]).issubset(set(profile["equipment"]) | {"bodyweight"})
            assert set(item["equipment"]).issubset(set(profile["equipment"]) | {"bodyweight"})
            assert item["prescription"]["tempo"]
            assert item["range_of_motion"] is None or isinstance(item["range_of_motion"], str)
            if source["single_joint"]:
                assert experience == "advanced"
                assert goal == "strength_hypertrophy"
                assert profile.get("include_accessories") is True


@pytest.mark.parametrize(
    "goal,experience,equipment",
    [
        ("strength", "beginner", ["bodyweight"]),
        ("general_fitness", "beginner", ["bodyweight", "chair", "wall", "step"]),
        ("functional", "intermediate", ["bodyweight", "kettlebell", "box"]),
        ("hypertrophy", "intermediate", ["bodyweight", "dumbbell", "bench", "resistance_band"]),
        ("endurance", "beginner", ["bodyweight", "bicycle", "jump_rope", "step"]),
        ("mobility", "advanced", ["bodyweight", "stick", "wall", "resistance_band", "kettlebell"]),
    ],
)
def test_limited_equipment_profiles_never_assume_unavailable_equipment(goal, experience, equipment):
    profile = {
        "goal": goal,
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": equipment,
        "pistol_squat_capable": False,
    }
    plan = generate_program(profile)
    available = set(equipment) | {"bodyweight"}
    for session in plan["sessions"]:
        for item in session["exercises"]:
            source = get_exercise(item["exercise_id"])
            assert source is not None
            assert set(source["equipment"]).issubset(available)
            assert set(item["equipment"]).issubset(available)
            assert item["exercise_id"] != "pistol_squat"


def test_excluded_patterns_and_exercises_are_respected_for_movement_limitations():
    profile = {
        "goal": "power",
        "experience": "intermediate",
        "sessions_per_week": 2,
        "session_minutes": 75,
        "equipment": ["bodyweight", "barbell", "rack", "weight_plate", "dumbbell", "kettlebell", "box"],
        "excluded_patterns": ["jump"],
        "excluded_exercise_ids": ["deadlift"],
    }
    plan = generate_program(profile)
    exercises = [item for session in plan["sessions"] for item in session["exercises"]]
    assert exercises
    assert all(item["pattern"] != "jump" for item in exercises)
    assert all(item["exercise_id"] != "deadlift" for item in exercises)


def test_advanced_accessories_remain_opt_in_and_goal_specific():
    base = {
        "goal": "strength_hypertrophy",
        "experience": "advanced",
        "sessions_per_week": 2,
        "session_minutes": 90,
        "equipment": ["bodyweight", "barbell", "rack", "weight_plate", "dumbbell", "bench"],
        "include_accessories": False,
    }
    without = generate_program(base)
    with_accessories = generate_program({**base, "include_accessories": True})
    without_ids = {
        item["exercise_id"] for session in without["sessions"] for item in session["exercises"]
    }
    with_ids = {
        item["exercise_id"] for session in with_accessories["sessions"] for item in session["exercises"]
    }
    single_joint = {
        item["id"] for item in load_catalogue()
        if item.get("single_joint") and item.get("pattern") == "accessory"
    }
    assert not (without_ids & single_joint)
    assert with_ids.issuperset(without_ids)


def test_non_advanced_profiles_cannot_enable_single_joint_accessories():
    profile = {
        "goal": "hypertrophy",
        "experience": "intermediate",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": ["bodyweight", "dumbbell", "bench"],
        "include_accessories": True,
    }
    with pytest.raises(ValueError, match="naprednim"):
        generate_program(profile)
