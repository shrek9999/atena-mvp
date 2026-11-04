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

def _matrix_plan(goal, experience):
    return generate_program({
        "goal": goal,
        "experience": experience,
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": _complete_equipment_set(),
        "include_accessories": False,
    })


def _first_exercise(plan, pattern):
    return next(
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] == pattern
    )


@pytest.mark.parametrize("goal", ["fat_loss"])
def test_conditioning_work_volume_scales_with_experience(goal):
    total_conditioning_sets = []
    for experience in EXPERIENCE_LEVELS:
        plan = _matrix_plan(goal, experience)
        total_conditioning_sets.append(sum(
            exercise["prescription"]["sets"]
            for session in plan["sessions"]
            for exercise in session["exercises"]
            if exercise["pattern"] == "conditioning"
        ))

    assert total_conditioning_sets == [4, 6, 8]


def test_strength_hypertrophy_main_lift_dose_scales_across_all_three_levels():
    prescriptions = [
        _first_exercise(_matrix_plan("strength_hypertrophy", level), "squat")["prescription"]
        for level in EXPERIENCE_LEVELS
    ]

    assert [item["reps"] for item in prescriptions] == ["8–12", "8–12", "5–8"]
    assert [item["rir"] for item in prescriptions] == [3, 3, 2]
    assert [item["sets"] for item in prescriptions] == [3, 3, 3]
    assert [item["tempo"] for item in prescriptions] == ["3–1–1–0", "2–0–X–0", "2–0–X–0"]


def test_functional_main_lift_prescription_distinguishes_intermediate_and_advanced():
    prescriptions = [
        _first_exercise(_matrix_plan("functional", level), "squat")["prescription"]
        for level in EXPERIENCE_LEVELS
    ]

    assert [item["reps"] for item in prescriptions] == ["8–12", "8–12", "6–10"]
    assert [item["rir"] for item in prescriptions] == [3, 3, 2]
    assert [item["tempo"] for item in prescriptions] == ["3–1–1–0", "2–0–1–0", "2–0–1–0"]


def test_mobility_work_volume_scales_for_advanced_profiles():
    prescriptions = [
        _first_exercise(_matrix_plan("mobility", level), "mobility")["prescription"]
        for level in EXPERIENCE_LEVELS
    ]

    assert [item["sets"] for item in prescriptions] == [2, 2, 3]

def test_endurance_interval_duration_scales_with_experience():
    aerobic_interval_seconds = []
    for experience in EXPERIENCE_LEVELS:
        plan = _matrix_plan("endurance", experience)
        interval = next(
            exercise
            for session in plan["sessions"]
            for exercise in session["exercises"]
            if exercise["pattern"] == "conditioning" and exercise.get("endurance_type") == "aerobic"
        )
        aerobic_interval_seconds.append(interval["prescription"]["work_seconds"])

    assert aerobic_interval_seconds == [120, 150, 180]
