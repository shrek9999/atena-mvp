"""Independent final quality-gate tests for generated ATENA programmes."""
from copy import deepcopy
from itertools import product

import pytest

from training.program import generate_program
from training.quality_gate import validate_generated_program


GOALS = ["strength_hypertrophy", "functional", "mobility", "endurance", "fat_loss"]
LEVELS = ["beginner", "intermediate", "advanced"]
EQUIPMENT = {
    "bodyweight": ["bodyweight"],
    "free_weights": ["bodyweight", "dumbbell", "kettlebell"],
    "bands": ["bodyweight", "resistance_band"],
    "gym": [
        "bodyweight", "barbell", "dumbbell", "bench", "pull_up_bar",
        "cable", "kettlebell", "box", "resistance_band",
    ],
}


@pytest.mark.parametrize(
    "goal,experience,equipment,sessions,duration",
    list(product(GOALS, LEVELS, EQUIPMENT.values(), [2, 3, 4], [30, 45, 60])),
)
def test_generated_program_passes_independent_quality_gate(
    goal, experience, equipment, sessions, duration
):
    profile = {
        "goal": goal,
        "experience": experience,
        "equipment": equipment,
        "sessions_per_week": sessions,
        "session_minutes": duration,
        "include_accessories": False,
    }
    program = generate_program(profile)
    assert validate_generated_program(program, profile) == []


def _valid_program():
    profile = {
        "goal": "strength_hypertrophy",
        "experience": "beginner",
        "equipment": ["bodyweight", "dumbbell"],
        "sessions_per_week": 2,
        "session_minutes": 45,
        "include_accessories": False,
    }
    return profile, generate_program(profile)


def test_quality_gate_rejects_unavailable_equipment():
    profile, program = _valid_program()
    broken = deepcopy(program)
    broken["sessions"][0]["exercises"][0]["equipment"] = ["barbell"]
    assert any("nedostopno opremo" in issue for issue in validate_generated_program(broken, profile))


def test_quality_gate_rejects_unknown_exercise():
    profile, program = _valid_program()
    broken = deepcopy(program)
    broken["sessions"][0]["exercises"][0]["exercise_id"] = "made_up_exercise"
    assert any("preverjenem katalogu" in issue for issue in validate_generated_program(broken, profile))


def test_quality_gate_rejects_missing_tempo_and_progression_logic():
    profile, program = _valid_program()
    broken = deepcopy(program)
    exercise = broken["sessions"][0]["exercises"][0]
    exercise["prescription"]["tempo"] = ""
    exercise["coaching_logic"] = {}
    issues = validate_generated_program(broken, profile)
    assert any("tempo" in issue for issue in issues)
    assert any("regresije in progresije" in issue for issue in issues)


def test_quality_gate_rejects_overlong_session():
    profile, program = _valid_program()
    broken = deepcopy(program)
    broken["sessions"][0]["estimated_minutes"] = profile["session_minutes"] + 1
    assert any("presega razpoložljivi čas" in issue for issue in validate_generated_program(broken, profile))


@pytest.mark.parametrize("sessions", [2, 3, 4])
def test_power_sessions_have_enough_exercises_without_arbitrary_ceiling(sessions):
    profile = {"goal": "power", "experience": "intermediate", "equipment": ["bodyweight", "barbell", "dumbbell", "bench", "pull_up_bar", "cable", "kettlebell", "box", "resistance_band"], "sessions_per_week": sessions, "session_minutes": 60, "include_accessories": False}
    program = generate_program(profile)
    assert validate_generated_program(program, profile) == []
    assert all(len(session["exercises"]) >= 3 for session in program["sessions"])
    patterns = {exercise["pattern"] for session in program["sessions"] for exercise in session["exercises"]}
    assert patterns.intersection({"jump", "hinge_power"})
