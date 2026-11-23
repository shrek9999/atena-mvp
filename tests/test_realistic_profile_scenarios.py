"""Fifteen realistic onboarding profiles exercised against the deterministic planner."""
import pytest

from training.catalogue import get_exercise
from training.program import generate_program


PROFILES = [
    ("beginner_home_hypertrophy", {"goal": "hypertrophy", "experience": "beginner", "sessions_per_week": 2, "session_minutes": 45, "equipment": ["dumbbell", "bench", "resistance_band", "anchor_point"]}),
    ("intermediate_gym_hypertrophy", {"goal": "hypertrophy", "experience": "intermediate", "sessions_per_week": 2, "session_minutes": 60, "equipment": ["barbell", "rack", "dumbbell", "bench", "pull_up_bar", "cable"]}),
    ("advanced_full_gym_hypertrophy", {"goal": "hypertrophy", "experience": "advanced", "sessions_per_week": 3, "session_minutes": 75, "equipment": ["barbell", "rack", "dumbbell", "bench", "pull_up_bar", "cable", "kettlebell"], "include_accessories": True}),
    ("beginner_home_strength", {"goal": "strength", "experience": "beginner", "sessions_per_week": 2, "session_minutes": 60, "equipment": ["dumbbell", "bench", "resistance_band", "anchor_point"]}),
    ("intermediate_barbell_strength", {"goal": "strength", "experience": "intermediate", "sessions_per_week": 2, "session_minutes": 75, "equipment": ["barbell", "rack", "bench", "dumbbell", "pull_up_bar"]}),
    ("advanced_strength_four_days", {"goal": "strength", "experience": "advanced", "sessions_per_week": 4, "session_minutes": 75, "equipment": ["barbell", "rack", "bench", "dumbbell", "pull_up_bar", "kettlebell"], "include_accessories": True}),
    ("beginner_general_fitness", {"goal": "general_fitness", "experience": "beginner", "sessions_per_week": 2, "session_minutes": 45, "equipment": ["bodyweight", "dumbbell", "resistance_band", "anchor_point", "chair"]}),
    ("intermediate_functional", {"goal": "functional", "experience": "intermediate", "sessions_per_week": 2, "session_minutes": 60, "equipment": ["kettlebell", "dumbbell", "box", "resistance_band", "anchor_point", "pull_up_bar"]}),
    ("advanced_functional", {"goal": "functional", "experience": "advanced", "sessions_per_week": 3, "session_minutes": 75, "equipment": ["barbell", "rack", "kettlebell", "box", "pull_up_bar", "resistance_band", "anchor_point"]}),
    ("beginner_power", {"goal": "power", "experience": "beginner", "sessions_per_week": 2, "session_minutes": 60, "equipment": ["bodyweight", "box", "kettlebell", "dumbbell"]}),
    ("intermediate_power", {"goal": "power", "experience": "intermediate", "sessions_per_week": 2, "session_minutes": 60, "equipment": ["barbell", "rack", "box", "kettlebell", "dumbbell"]}),
    ("beginner_endurance", {"goal": "endurance", "experience": "beginner", "sessions_per_week": 2, "session_minutes": 45, "equipment": ["bicycle", "jump_rope", "bodyweight", "step"]}),
    ("intermediate_endurance", {"goal": "endurance", "experience": "intermediate", "sessions_per_week": 3, "session_minutes": 60, "equipment": ["rowing_machine", "air_bike", "ski_erg", "sled", "bodyweight"]}),
    ("beginner_mobility", {"goal": "mobility", "experience": "beginner", "sessions_per_week": 2, "session_minutes": 30, "equipment": ["bodyweight", "chair", "wall", "stick", "resistance_band"]}),
    ("advanced_mobility", {"goal": "mobility", "experience": "advanced", "sessions_per_week": 2, "session_minutes": 45, "equipment": ["bodyweight", "stick", "wall", "box", "resistance_band", "kettlebell"]}),
]


@pytest.mark.parametrize("scenario,profile", PROFILES, ids=[item[0] for item in PROFILES])
def test_realistic_onboarding_profile_generates_safe_catalogue_backed_plan(scenario, profile):
    plan = generate_program(profile)
    assert len(plan["sessions"]) == profile["sessions_per_week"], scenario
    assert plan["goal"] == profile["goal"]
    assert plan["experience"] == profile["experience"]
    for session in plan["sessions"]:
        assert session["estimated_minutes"] <= profile["session_minutes"], scenario
        assert session["exercise_count"] == len(session["exercises"])
        assert session["exercise_count"] >= 3
        for exercise in session["exercises"]:
            source = get_exercise(exercise["exercise_id"])
            assert source is not None, (scenario, exercise["exercise_id"])
            assert set(source["equipment"]).issubset(set(profile["equipment"]) | {"bodyweight"})
            assert set(exercise["equipment"]).issubset(set(profile["equipment"]) | {"bodyweight"})
            assert exercise["prescription"]["tempo"]
            assert exercise["prescription"]["tempo_description"]
            assert exercise["range_of_motion"]
            if profile["experience"] == "beginner" and profile["goal"] in {"hypertrophy", "strength", "general_fitness", "functional"}:
                if exercise["pattern"] not in {"trunk_stability", "anti_rotation"}:
                    assert exercise["prescription"]["rir"] >= 3
                    assert exercise["prescription"]["reps"] in {"8–10", "8–12", "10–15", "12–15"}
            if source["single_joint"] and profile["goal"] == "hypertrophy":
                assert profile["experience"] == "advanced"
                assert profile.get("include_accessories") is True


def test_loaded_hypertrophy_profile_exposes_straight_back_hinge_label():
    profile = {
        "goal": "hypertrophy",
        "experience": "intermediate",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": ["barbell", "rack", "dumbbell", "bench", "pull_up_bar"],
    }
    plan = generate_program(profile)
    hinges = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] == "hinge"
    ]
    assert hinges
    assert all(exercise["pattern_label"] == "predklon z nevtralno hrbtenico" for exercise in hinges)
