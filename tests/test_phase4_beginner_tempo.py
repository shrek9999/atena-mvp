"""Phase 4 regression: beginner combined strength/hypertrophy tempo."""

from training.program import generate_program


def test_beginner_combined_strength_hypertrophy_uses_agreed_2_1_1_0_tempo():
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
    assert all(exercise["prescription"]["tempo"] == "2–1–1–0" for exercise in exercises)
    assert all(exercise["prescription"]["tempo_seconds_per_rep"] == 4 for exercise in exercises)
