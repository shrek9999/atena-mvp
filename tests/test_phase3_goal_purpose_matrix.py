"""Phase 3 regression matrix: generated exercise purposes must match the selected goal."""

import pytest

from training.program import generate_program


BASE = {
    "experience": "intermediate",
    "equipment": [
        "barbell", "rack", "dumbbell", "bench", "pull_up_bar",
        "kettlebell", "cable", "resistance_band", "box",
        "bodyweight", "weight_plate", "rowing_machine", "ski_erg",
        "air_bike", "sled", "jump_rope", "chair", "wall",
        "household_support", "household_load",
    ],
    "sessions_per_week": 2,
    "session_minutes": 60,
}

ALLOWED_PURPOSES = {
    "strength": {"strength"},
    "hypertrophy": {"hypertrophy"},
    "strength_hypertrophy": {"strength", "hypertrophy"},
    "fat_loss": {"strength", "hypertrophy", "general_fitness", "cardiorespiratory_conditioning"},
    "general_fitness": {
        "general_fitness", "functional_fitness", "strength",
        "cardiorespiratory_conditioning", "mobility", "balance", "coordination",
    },
    "functional": {
        "functional_fitness", "general_fitness", "strength",
        "cardiorespiratory_conditioning", "mobility", "balance",
        "coordination", "power",
    },
    "power": {"power", "strength"},
    "endurance": {"cardiorespiratory_conditioning", "muscular_endurance", "general_fitness"},
    "mobility": {"mobility", "strength", "general_fitness", "functional_fitness", "balance", "coordination"},
}


@pytest.mark.parametrize("goal,allowed", ALLOWED_PURPOSES.items())
@pytest.mark.parametrize("experience", ["beginner", "intermediate", "advanced"])
def test_generated_programme_uses_only_purposes_compatible_with_goal(goal, allowed, experience):
    plan = generate_program({**BASE, "goal": goal, "experience": experience})
    exercises = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
    ]

    assert exercises, f"No exercises generated for {goal}/{experience}"
    incompatible = [
        (exercise["exercise_id"], exercise["training_purposes"])
        for exercise in exercises
        if not (set(exercise["training_purposes"]) & allowed)
    ]
    assert not incompatible, f"Incompatible exercises for {goal}/{experience}: {incompatible}"
