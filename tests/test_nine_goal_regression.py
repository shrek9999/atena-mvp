"""Backward-compatibility tests for legacy ATENA goal identifiers."""
from itertools import product

import pytest

from training.catalogue import load_catalogue
from training.goals import normalize_goal
from training.program import generate_program


GOALS = {
    "strength": "strength_hypertrophy",
    "hypertrophy": "strength_hypertrophy",
    "strength_hypertrophy": "strength_hypertrophy",
    "general_fitness": "functional",
    "functional": "functional",
    "power": "functional",
    "endurance": "functional",
    "mobility": "functional",
    "fat_loss": "fat_loss",
    "weight_management": "fat_loss",
}
LEVELS = ["beginner", "intermediate", "advanced"]


def _all_equipment():
    values = {"bodyweight"}
    for exercise in load_catalogue():
        values.update(exercise["equipment"])
        values.update(exercise.get("equipment_any", []))
    return sorted(values)


@pytest.mark.parametrize(("legacy_goal", "canonical_goal"), GOALS.items())
def test_legacy_goal_ids_normalize_to_the_three_public_tracks(legacy_goal, canonical_goal):
    assert normalize_goal(legacy_goal) == canonical_goal


@pytest.mark.parametrize(("goal", "experience"), list(product(GOALS, LEVELS)))
def test_legacy_goal_ids_generate_catalogue_backed_canonical_programmes(goal, experience):
    plan = generate_program({
        "goal": goal,
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": _all_equipment(),
        "include_accessories": False,
    })
    assert plan["goal"] == GOALS[goal]
    assert plan["goal_framework"]["id"] == GOALS[goal]
    assert plan["experience"] == experience
    assert len(plan["sessions"]) == 2
    for session in plan["sessions"]:
        assert session["estimated_minutes"] <= 60
        assert session["exercise_count"] == len(session["exercises"])
        assert session["exercise_count"] >= 3
