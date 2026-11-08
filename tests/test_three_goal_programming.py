"""Integration coverage for ATENA's three public training goals."""
from itertools import product

import pytest

from training.catalogue import load_catalogue
from training.program import generate_program


GOALS = ["strength_hypertrophy", "functional", "fat_loss"]
LEVELS = ["beginner", "intermediate", "advanced"]


def all_equipment():
    values = {"bodyweight"}
    for exercise in load_catalogue():
        values.update(exercise["equipment"])
        values.update(exercise.get("equipment_any", []))
    return sorted(values)


@pytest.mark.parametrize(("goal", "experience"), list(product(GOALS, LEVELS)))
def test_three_canonical_goals_generate_distinct_valid_programs(goal, experience):
    plan = generate_program({
        "goal": goal,
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": all_equipment(),
        "include_accessories": False,
    })
    assert plan["goal"] == goal
    assert plan["goal_framework"]["id"] == goal
    assert len(plan["sessions"]) == 2
    for session in plan["sessions"]:
        assert session["estimated_minutes"] <= 60
        assert session["exercises"]


@pytest.mark.parametrize("experience", LEVELS)
def test_functional_goal_combines_strength_mobility_coordination_and_metcon(experience):
    plan = generate_program({
        "goal": "functional",
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": all_equipment(),
        "include_accessories": False,
    })
    exercises = [item for session in plan["sessions"] for item in session["exercises"]]
    patterns = {item["pattern"] for item in exercises}
    assert {"squat", "hinge", "mobility", "conditioning", "coordination", "carry"}.issubset(patterns)


@pytest.mark.parametrize("experience", LEVELS)
def test_fat_loss_goal_preserves_strength_and_adds_conditioning_and_nutrition_framework(experience):
    plan = generate_program({
        "goal": "fat_loss",
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": all_equipment(),
        "include_accessories": False,
    })
    patterns = {item["pattern"] for session in plan["sessions"] for item in session["exercises"]}
    assert {"squat", "hinge", "conditioning"}.issubset(patterns)
    assert "nutrition" in plan["goal_framework"]["pillars"]


def test_strength_and_mass_goal_only_allows_specialization_for_advanced_users():
    for level in ["beginner", "intermediate"]:
        plan = generate_program({
            "goal": "strength_hypertrophy",
            "experience": level,
            "training_emphasis": "strength",
            "sessions_per_week": 2,
            "session_minutes": 60,
            "equipment": all_equipment(),
            "include_accessories": False,
        })
        assert plan["training_emphasis"] == "balanced"

    advanced = generate_program({
        "goal": "strength_hypertrophy",
        "experience": "advanced",
        "training_emphasis": "strength",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": all_equipment(),
        "include_accessories": False,
    })
    assert advanced["training_emphasis"] == "strength"
