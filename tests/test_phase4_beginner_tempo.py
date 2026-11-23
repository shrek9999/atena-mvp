"""Regression: universal controlled learning tempo for strength exercises."""

from training.program import generate_program


def test_beginner_combined_strength_hypertrophy_uses_universal_controlled_tempo():
    profile = {
        "goal": "strength_hypertrophy",
        "experience": "beginner",
        "equipment": ["barbell", "rack", "dumbbell", "bench", "pull_up_bar"],
        "sessions_per_week": 2,
        "session_minutes": 75,
    }
    plan = generate_program(profile)
    exercises = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] in {"squat", "hinge"}
    ]

    assert exercises
    assert all(exercise["prescription"]["tempo"] == "3–1–2–0" for exercise in exercises)
    assert all(exercise["prescription"]["tempo_seconds_per_rep"] == 6 for exercise in exercises)
