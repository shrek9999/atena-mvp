"""Realistic equipment and duration stress matrix for ATENA's 15 visible profiles."""

from itertools import product

import pytest

from training.program import generate_program


VISIBLE_GOALS = [
    "strength_hypertrophy",
    "functional",
    "mobility",
    "endurance",
    "fat_loss",
]
EXPERIENCE_LEVELS = ["beginner", "intermediate", "advanced"]
SESSIONS_PER_WEEK = [2, 3, 4]

# These are the four equipment choices exposed by the current onboarding UI.
EQUIPMENT_PROFILES = {
    "bodyweight": ["bodyweight"],
    "free_weights": ["bodyweight", "dumbbell", "kettlebell"],
    "bands": ["bodyweight", "resistance_band"],
    "gym": [
        "bodyweight", "barbell", "dumbbell", "bench", "pull_up_bar",
        "cable", "kettlebell", "box", "resistance_band",
    ],
}


@pytest.mark.parametrize(
    "goal,experience,equipment_name,equipment,sessions,duration",
    [
        (goal, experience, equipment_name, equipment, duration)
        for goal, experience, (equipment_name, equipment), sessions, duration in product(
            VISIBLE_GOALS,
            EXPERIENCE_LEVELS,
            EQUIPMENT_PROFILES.items(),
            SESSIONS_PER_WEEK,
            [30, 45, 60],
        )
    ],
)
def test_visible_profiles_work_with_realistic_equipment_and_time_choices(
    goal, experience, equipment_name, equipment, sessions, duration
):
    profile = {
        "goal": goal,
        "experience": experience,
        "sessions_per_week": sessions,
        "session_minutes": duration,
        "equipment": equipment,
        "include_accessories": False,
    }

    plan = generate_program(profile)

    assert plan["goal"] == goal, (goal, experience, equipment_name, duration)
    assert plan["experience"] == experience
    assert len(plan["sessions"]) == sessions

    available = set(equipment) | {"bodyweight"}
    for session in plan["sessions"]:
        context = (goal, experience, equipment_name, sessions, duration, session["session"])
        assert 3 <= len(session["exercises"]) <= 6, context
        assert session["available_minutes"] == duration, context
        assert session["estimated_minutes"] <= duration, context
        for exercise in session["exercises"]:
            assert set(exercise["equipment"]).issubset(available), (
                context, exercise["exercise_id"], exercise["equipment"]
            )
            assert exercise["prescription"]["tempo"]
            assert exercise["range_of_motion"]

    exercises = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
    ]
    if goal == "functional":
        assert all(exercise["pattern"] != "jump" for exercise in exercises)
        assert all(exercise["exercise_id"] != "lateral_shuffle" for exercise in exercises)
    if goal == "strength_hypertrophy" and experience != "advanced":
        assert all(exercise["joint_type"] == "multi_joint" for exercise in exercises)
        assert all(exercise["pattern"] not in {"trunk_stability", "anti_rotation"} for exercise in exercises)
