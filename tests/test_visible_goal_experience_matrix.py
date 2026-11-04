"""Quality matrix for the five visible ATENA goals and three experience levels."""

from itertools import product

import pytest

from training.catalogue import get_exercise, load_catalogue
from training.program import generate_program


VISIBLE_GOALS = [
    "strength_hypertrophy",
    "functional",
    "mobility",
    "endurance",
    "fat_loss",
]
EXPERIENCE_LEVELS = ["beginner", "intermediate", "advanced"]


def _complete_equipment_set():
    equipment = {"bodyweight"}
    for exercise in load_catalogue():
        equipment.update(exercise["equipment"])
        equipment.update(exercise.get("equipment_any", []))
    return sorted(equipment)


@pytest.mark.parametrize(
    "goal,experience",
    list(product(VISIBLE_GOALS, EXPERIENCE_LEVELS)),
)
def test_all_fifteen_visible_goal_experience_profiles_generate_valid_distinct_plans(goal, experience):
    profile = {
        "goal": goal,
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": _complete_equipment_set(),
        "include_accessories": False,
    }
    plan = generate_program(profile)

    assert plan["goal"] == goal
    assert plan["experience"] == experience
    assert len(plan["sessions"]) == 2
    assert plan["methodology"]["exercise_source"] == "verified_catalogue_only"

    patterns = set()
    for session in plan["sessions"]:
        assert 3 <= len(session["exercises"])
        assert session["estimated_minutes"] <= profile["session_minutes"]
        for exercise in session["exercises"]:
            source = get_exercise(exercise["exercise_id"])
            assert source is not None, exercise["exercise_id"]
            assert set(source["equipment"]).issubset(set(profile["equipment"]) | {"bodyweight"})
            assert set(exercise["equipment"]).issubset(set(profile["equipment"]) | {"bodyweight"})
            assert exercise["prescription"]["tempo"]
            assert exercise["prescription"]["tempo_description"]
            assert exercise["range_of_motion"]
            patterns.add(exercise["pattern"])

    expected = {
        "strength_hypertrophy": {"squat", "hinge", "horizontal_push", "horizontal_pull"},
        "functional": {"balance", "coordination", "conditioning"},
        "mobility": {"mobility", "mobility_stretch", "squat"},
        "endurance": {"locomotion", "conditioning"},
        "fat_loss": {"squat", "hinge", "conditioning"},
    }[goal]
    if goal == "functional" and experience == "beginner":
        expected.add("carry")
    if goal == "functional" and experience != "beginner":
        expected.add("jump")
    assert expected.issubset(patterns), (goal, experience, patterns)


def test_five_visible_goals_have_distinct_program_pattern_signatures():
    equipment = _complete_equipment_set()
    signatures = {}
    for goal in VISIBLE_GOALS:
        plan = generate_program({
            "goal": goal,
            "experience": "intermediate",
            "sessions_per_week": 2,
            "session_minutes": 60,
            "equipment": equipment,
            "include_accessories": False,
        })
        signatures[goal] = frozenset(
            exercise["pattern"]
            for session in plan["sessions"]
            for exercise in session["exercises"]
        )
    assert len(set(signatures.values())) == len(VISIBLE_GOALS), signatures


def test_functional_beginner_avoids_unassessed_jumps_and_uses_beginner_coordination():
    plan = generate_program({
        "goal": "functional",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": _complete_equipment_set(),
        "include_accessories": False,
    })
    exercises = [exercise for session in plan["sessions"] for exercise in session["exercises"]]
    assert all(exercise["pattern"] != "jump" for exercise in exercises)
    coordination = [exercise for exercise in exercises if exercise["pattern"] == "coordination"]
    assert coordination
    assert all(exercise["exercise_id"] == "controlled_lateral_step" for exercise in coordination)
    assert all(get_exercise(exercise["exercise_id"])["level"] == "beginner" for exercise in coordination)


def test_functional_goal_adds_trunk_control_only_when_feedback_identifies_a_need():
    profile = {
        "goal": "functional",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": _complete_equipment_set(),
        "include_accessories": False,
    }
    baseline = generate_program(profile)
    targeted = generate_program(
        profile,
        feedback={
            "difficulty": "right",
            "completed": True,
            "discomfort": "no",
            "recovery": "normal",
            "movement_control": "bracing",
        },
    )
    baseline_patterns = {
        exercise["pattern"]
        for session in baseline["sessions"]
        for exercise in session["exercises"]
    }
    targeted_patterns = {
        exercise["pattern"]
        for session in targeted["sessions"]
        for exercise in session["exercises"]
    }
    assert "trunk_stability" not in baseline_patterns
    assert "trunk_stability" in targeted_patterns
    assert targeted["sessions"][0]["exercises"][0]["pattern"] == "trunk_stability"
