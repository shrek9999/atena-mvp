"""Regression coverage for all nine ATENA programme goals and three levels."""
from itertools import product

import pytest

from training.catalogue import get_exercise, load_catalogue
from training.program import generate_program


GOALS = [
    "strength",
    "hypertrophy",
    "strength_hypertrophy",
    "fat_loss",
    "general_fitness",
    "functional",
    "power",
    "endurance",
    "mobility",
]
LEVELS = ["beginner", "intermediate", "advanced"]


def _all_equipment():
    values = {"bodyweight"}
    for exercise in load_catalogue():
        values.update(exercise["equipment"])
        values.update(exercise.get("equipment_any", []))
    return sorted(values)


@pytest.mark.parametrize("goal,experience", list(product(GOALS, LEVELS)))
def test_all_nine_goals_generate_catalogue_backed_plans(goal, experience):
    profile = {
        "goal": goal,
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": _all_equipment(),
        "include_accessories": experience == "advanced" and goal == "strength_hypertrophy",
    }
    plan = generate_program(profile)

    assert plan["goal"] == goal
    assert plan["experience"] == experience
    assert len(plan["sessions"]) == 2
    for session in plan["sessions"]:
        assert session["estimated_minutes"] <= 60
        assert session["exercise_count"] == len(session["exercises"])
        assert session["exercise_count"] >= 3
        for exercise in session["exercises"]:
            source = get_exercise(exercise["exercise_id"])
            assert source is not None
            assert set(source["equipment"]).issubset(set(profile["equipment"]) | {"bodyweight"})
            assert exercise["prescription"]["tempo"]
            assert exercise["prescription"]["tempo_description"]
            assert exercise["range_of_motion"]
            assert exercise["training_purposes"]


@pytest.mark.parametrize("experience", LEVELS)
def test_endurance_is_not_a_strength_program(experience):
    equipment = _all_equipment()
    strength = generate_program({
        "goal": "strength", "experience": experience,
        "sessions_per_week": 2, "session_minutes": 60, "equipment": equipment,
    })
    endurance = generate_program({
        "goal": "endurance", "experience": experience,
        "sessions_per_week": 2, "session_minutes": 60, "equipment": equipment,
    })
    strength_patterns = {
        item["pattern"] for session in strength["sessions"] for item in session["exercises"]
    }
    endurance_patterns = {
        item["pattern"] for session in endurance["sessions"] for item in session["exercises"]
    }
    assert {"locomotion", "conditioning"}.issubset(endurance_patterns)
    assert "locomotion" not in strength_patterns
    assert "conditioning" not in strength_patterns


@pytest.mark.parametrize("experience", LEVELS)
def test_functional_goal_has_its_own_capacity_signature_without_unassessed_jumps(experience):
    plan = generate_program({
        "goal": "functional", "experience": experience,
        "sessions_per_week": 2, "session_minutes": 60, "equipment": _all_equipment(),
    })
    exercises = [item for session in plan["sessions"] for item in session["exercises"]]
    patterns = {item["pattern"] for item in exercises}
    assert {"squat", "hinge", "horizontal_push", "horizontal_pull", "conditioning"}.issubset(patterns)
    assert {"lunge", "locomotion"}.issubset(patterns)
    assert "jump" not in patterns
    assert "lateral_shuffle" not in {item["exercise_id"] for item in exercises}


@pytest.mark.parametrize("experience", LEVELS)
def test_power_goal_exposes_power_purpose_and_explosive_patterns(experience):
    plan = generate_program({
        "goal": "power", "experience": experience,
        "sessions_per_week": 2, "session_minutes": 60, "equipment": _all_equipment(),
    })
    exercises = [item for session in plan["sessions"] for item in session["exercises"]]
    assert any("power" in item["training_purposes"] for item in exercises)
    assert any(item["pattern"] in {"jump", "hinge_power"} for item in exercises)


@pytest.mark.parametrize("experience", LEVELS)
def test_mobility_goal_includes_active_mobility_and_foundational_strength(experience):
    plan = generate_program({
        "goal": "mobility", "experience": experience,
        "sessions_per_week": 2, "session_minutes": 60, "equipment": _all_equipment(),
    })
    patterns = {
        item["pattern"] for session in plan["sessions"] for item in session["exercises"]
    }
    assert "mobility" in patterns
    assert "mobility_stretch" in patterns
    assert "squat" in patterns


@pytest.mark.parametrize("experience", LEVELS)
def test_fat_loss_goal_retains_resistance_training_and_conditioning(experience):
    plan = generate_program({
        "goal": "fat_loss", "experience": experience,
        "sessions_per_week": 2, "session_minutes": 60, "equipment": _all_equipment(),
    })
    patterns = {
        item["pattern"] for session in plan["sessions"] for item in session["exercises"]
    }
    assert {"squat", "hinge", "conditioning"}.issubset(patterns)
