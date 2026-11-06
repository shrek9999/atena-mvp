"""Broad scenario checks for catalogue-backed programme quality.

These tests intentionally use only the deterministic local generator; no API key,
network request, paid model, or production endpoint is involved.
"""
from itertools import product

import pytest

from training.catalogue import get_exercise, load_catalogue
from training.program import ProgramSafetyBlock, generate_program


def _complete_equipment_set():
    equipment = {"bodyweight"}
    for exercise in load_catalogue():
        equipment.update(exercise["equipment"])
        equipment.update(exercise.get("equipment_any", []))
    return sorted(equipment)


@pytest.mark.parametrize(
    "goal,experience",
    list(product(
        ["hypertrophy", "strength", "general_fitness", "functional", "power", "endurance", "mobility"],
        ["beginner", "intermediate", "advanced"],
    )),
)
def test_program_quality_across_goal_and_experience_matrix(goal, experience):
    profile = {
        "goal": goal,
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 90,
        "equipment": _complete_equipment_set(),
    }
    if experience == "advanced":
        profile["include_accessories"] = True

    plan = generate_program(profile)
    assert len(plan["sessions"]) == 2
    assert plan["program_version"]
    assert plan["methodology"]["exercise_source"] == "verified_catalogue_only"

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
            assert (
                exercise["range_of_motion"] is None
                or isinstance(exercise["range_of_motion"], str)
            )
            if source["single_joint"] and goal == "hypertrophy":
                assert experience == "advanced"
                assert profile.get("include_accessories") is True
            if experience == "beginner" and goal in {"hypertrophy", "strength", "general_fitness", "functional"}:
                if exercise["pattern"] in {"carry", "conditioning"}:
                    assert "rir" not in exercise["prescription"]
                    if exercise["pattern"] == "carry":
                        assert exercise["prescription"]["distance_based"] is True
                        assert exercise["prescription"]["reps"].endswith("m")
                    else:
                        assert exercise["time_based"] is True
                        assert exercise["prescription"]["work_seconds"] > 0
                elif exercise["pattern"] not in {"trunk_stability", "anti_rotation", "balance", "coordination"}:
                    assert exercise["prescription"]["rir"] >= 3
                    if exercise["pattern"] in {"jump", "hinge_power"}:
                        assert exercise["prescription"]["reps"] == "3–5"
                    else:
                        assert exercise["prescription"]["reps"] in {"8–10", "8–12", "10–15", "12–15"}


@pytest.mark.parametrize("session_minutes", [30, 45, 60, 90])
def test_hypertrophy_program_respects_flexible_session_time_envelope(session_minutes):
    profile = {
        "goal": "hypertrophy",
        "experience": "intermediate",
        "sessions_per_week": 2,
        "session_minutes": session_minutes,
        "equipment": _complete_equipment_set(),
    }
    plan = generate_program(profile)
    assert len(plan["sessions"]) == 2
    for session in plan["sessions"]:
        assert session["estimated_minutes"] <= session_minutes
        assert len(session["exercises"]) >= 3
        if session_minutes < 60:
            assert session["volume_adjustments"] or session["estimated_minutes"] <= session_minutes


def test_trunk_stability_is_only_added_after_specific_control_feedback():
    profile = {
        "goal": "hypertrophy",
        "experience": "intermediate",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": _complete_equipment_set(),
    }
    baseline = generate_program(profile)
    targeted = generate_program(profile, feedback={"movement_control": "bracing"})
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
    assert not baseline_patterns.intersection({"trunk_stability", "anti_rotation"})
    assert "trunk_stability" in targeted_patterns
    assert targeted["sessions"][0]["exercises"][0]["pattern"] == "trunk_stability"


def test_discomfort_feedback_blocks_automatic_programme_adaptation():
    profile = {
        "goal": "hypertrophy",
        "experience": "intermediate",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": _complete_equipment_set(),
    }
    with pytest.raises(ProgramSafetyBlock):
        generate_program(profile, feedback={"discomfort": "yes", "difficulty": "hard"})
