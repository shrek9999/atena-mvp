"""Phase B coaching-decision regression tests.

These tests validate deterministic coaching decisions and the prompt contract.
They deliberately do not call Gemini or any paid/external API.
"""
import pytest

from training.catalogue import get_exercises, load_catalogue
from training.program import (
    ProgramSafetyBlock,
    ProgramValidationError,
    _prescription,
    generate_program,
    validate_profile,
)


def _equipment():
    available = {"bodyweight"}
    for item in load_catalogue():
        available.update(item["equipment"])
        available.update(item.get("equipment_any", []))
    return sorted(available)


def _profile(goal="hypertrophy", experience="beginner", minutes=60):
    return {
        "goal": goal,
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": minutes,
        "equipment": _equipment(),
        **({"include_accessories": True} if experience == "advanced" else {}),
    }


@pytest.mark.parametrize("goal", ["hypertrophy", "strength"])
def test_beginner_main_squat_uses_skill_focused_repetition_range_and_reserve(goal):
    candidates = get_exercises(
        goal=goal, equipment=_equipment(), patterns=["squat"], level="beginner"
    )
    assert candidates, f"No beginner squat candidate for {goal}"
    prescription = _prescription(goal, "beginner", "squat", candidates[0])
    assert prescription["sets"] >= 2
    assert prescription["reps"] in {"8–12", "8–10", "10–15", "12–15"}
    assert prescription["rir"] >= 3


def test_strength_and_hypertrophy_share_controlled_learning_tempo():
    exercise = next(
        item for item in load_catalogue()
        if item["pattern"] == "squat" and item["training_role"] == "main"
    )
    strength = _prescription("strength", "intermediate", "squat", exercise)
    hypertrophy = _prescription("hypertrophy", "intermediate", "squat", exercise)
    assert strength["tempo"] == "3–1–2–0"
    assert hypertrophy["tempo"] == "3–1–2–0"
    assert strength["tempo_description"] == hypertrophy["tempo_description"]


def test_single_joint_hypertrophy_accessories_are_catalogue_opt_in_and_advanced_only():
    default_selection = get_exercises(
        goal="hypertrophy", equipment=_equipment(), include_accessories=False
    )
    accessory_selection = get_exercises(
        goal="hypertrophy", equipment=_equipment(), include_accessories=True
    )
    assert all(not item["single_joint"] for item in default_selection)
    assert any(item["single_joint"] for item in accessory_selection)

    beginner_profile = _profile("hypertrophy", "beginner")
    beginner_profile["include_accessories"] = True
    with pytest.raises(ProgramValidationError):
        validate_profile(beginner_profile)


@pytest.mark.parametrize(
    "goal,expected_tempo",
    [
        ("strength", "3–1–2–0"),
        ("hypertrophy", "3–1–2–0"),
        ("fat_loss", "3–1–2–0"),
        ("functional", "3–1–2–0"),
    ],
)
def test_program_preserves_universal_controlled_tempo(goal, expected_tempo):
    plan = generate_program(_profile(goal, "intermediate"))
    resistance_patterns = {
        "squat", "hinge", "lunge", "horizontal_push", "horizontal_pull",
        "vertical_push", "vertical_pull", "hip_extension",
    }
    resistance_exercises = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] in resistance_patterns
    ]
    assert resistance_exercises
    assert all(item["prescription"]["tempo"] == expected_tempo for item in resistance_exercises)


def test_program_never_uses_equipment_outside_the_declared_profile():
    declared = {"bodyweight", "dumbbell"}
    profile = _profile("hypertrophy", "beginner")
    profile["equipment"] = sorted(declared)
    plan = generate_program(profile)
    for session in plan["sessions"]:
        for exercise in session["exercises"]:
            assert set(exercise["equipment"]).issubset(declared)


@pytest.mark.parametrize(
    "feedback",
    [
        {"discomfort": "yes"},
        {"discomfort": "yes", "difficulty": "hard", "recovery": "poor"},
    ],
)
def test_any_reported_discomfort_blocks_automatic_program_generation(feedback):
    with pytest.raises(ProgramSafetyBlock):
        generate_program(_profile(), feedback=feedback)


def test_catalogue_contains_no_duplicate_exercise_ids_and_has_expected_scale():
    catalogue = load_catalogue()
    ids = [item["id"] for item in catalogue]
    assert len(ids) == len(set(ids))
    assert len(catalogue) >= 100
    assert all(item["name"].strip() and item["pattern"].strip() for item in catalogue)
