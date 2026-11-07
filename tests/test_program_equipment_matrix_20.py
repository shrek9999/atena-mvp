"""Twenty practical programme-generation profiles across goals and equipment access."""

from itertools import product

import pytest

from training.catalogue import get_exercise, load_catalogue
from training.program import generate_program


GOALS = [
    "strength_hypertrophy",
    "functional",
    "mobility",
    "endurance",
    "fat_loss",
]

EQUIPMENT_PROFILES = {
    "bodyweight_only": [],
    "dumbbell_home": ["dumbbell", "bench", "chair"],
    "band_home": ["resistance_band", "anchor_point", "chair"],
    "full_gym": None,
}


def _full_equipment():
    available = {"bodyweight"}
    for exercise in load_catalogue():
        available.update(exercise["equipment"])
        available.update(exercise.get("equipment_any", []))
    return sorted(available)


@pytest.mark.parametrize(
    "goal,equipment_name",
    list(product(GOALS, EQUIPMENT_PROFILES)),
)
def test_twenty_goal_and_equipment_profiles_generate_safe_catalogue_programmes(
    goal, equipment_name
):
    equipment = EQUIPMENT_PROFILES[equipment_name]
    if equipment is None:
        equipment = _full_equipment()

    profile = {
        "goal": goal,
        "experience": "beginner" if equipment_name in {"bodyweight_only", "band_home"} else "intermediate",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": equipment,
        "include_accessories": False,
    }
    plan = generate_program(profile)
    available = set(equipment) | {"bodyweight"}

    assert plan["goal"] == goal
    assert len(plan["sessions"]) == 2
    for session in plan["sessions"]:
        assert 3 <= len(session["exercises"]) <= 7
        assert session["estimated_minutes"] <= profile["session_minutes"]
        for exercise in session["exercises"]:
            source = get_exercise(exercise["exercise_id"])
            assert source is not None
            assert set(source["equipment"]).issubset(available)
            assert set(source.get("equipment_any", [])).intersection(available) or not source.get("equipment_any")
            assert exercise["prescription"]["sets"] >= 1
            assert exercise["prescription"]["tempo"]
            assert exercise["cues"]
            assert exercise["coaching_logic"]["regress_when"]
            assert exercise["coaching_logic"]["progress_when"]
