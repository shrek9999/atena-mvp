"""Integration tests for self-reported movement adaptation in programme generation."""
import pytest

from training.program import ProgramValidationError, generate_program


BASE = {
    "goal": "hypertrophy",
    "experience": "intermediate",
    "equipment": [
        "barbell", "rack", "dumbbell", "bench", "pull_up_bar",
        "kettlebell", "cable", "resistance_band", "box",
        "household_support", "wall", "anchor_point",
    ],
    "sessions_per_week": 2,
    "session_minutes": 60,
}


def _exercises(plan, pattern):
    return [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] == pattern
    ]


def test_needs_support_selects_a_verified_simpler_squat_variant_and_reduces_dose():
    plan = generate_program(BASE, movement_assessment={"squat": "needs_support"})
    squats = _exercises(plan, "squat")
    assert squats
    assert all(exercise["exercise_id"] in {"reaching_squat", "air_squat"} for exercise in squats)
    assert all(exercise["prescription"]["sets"] <= 2 for exercise in squats)
    assert all(exercise["prescription"]["rir"] >= 3 for exercise in squats)
    assert all(exercise["prescription"]["adjustment_note"] for exercise in squats)
    assert plan["movement_adaptation"]["automatic_progression"] == "movement_assessment_does_not_trigger_progression"
    assert plan["movement_adaptation"]["is_diagnosis"] is False


def test_needs_support_hinge_uses_bodyweight_learning_variant_not_loaded_rdl():
    plan = generate_program(BASE, movement_assessment={"hinge": "needs_support"})
    hinges = _exercises(plan, "hinge")
    assert hinges
    assert all(exercise["exercise_id"] == "bodyweight_hip_hinge" for exercise in hinges)
    assert all(exercise["prescription"]["sets"] <= 2 for exercise in hinges)


def test_easy_feedback_does_not_progress_a_pattern_marked_needs_support():
    plan = generate_program(
        BASE,
        feedback={"difficulty": "easy", "discomfort": "no"},
        movement_assessment={"squat": "needs_support"},
    )
    squats = _exercises(plan, "squat")
    assert squats
    assert all(exercise["prescription"]["sets"] <= 2 for exercise in squats)
    assert all("lažja različica" in exercise["prescription"]["adjustment_note"] for exercise in squats)
    assert all("prelahek" not in exercise["prescription"]["adjustment_note"] for exercise in squats)


def test_uncertain_keeps_the_original_selection_and_explains_no_guessing():
    baseline = generate_program(BASE)
    uncertain = generate_program(BASE, movement_assessment={"squat": "uncertain"})
    assert [x["exercise_id"] for x in _exercises(uncertain, "squat")] == [
        x["exercise_id"] for x in _exercises(baseline, "squat")
    ]
    assert all("nisi prepričan" in x["prescription"]["adjustment_note"] for x in _exercises(uncertain, "squat"))


def test_symptom_report_omits_only_the_affected_pattern_and_never_auto_substitutes():
    plan = generate_program(BASE, movement_assessment={"squat": "symptoms_reported"})
    assert not _exercises(plan, "squat")
    events = plan["movement_adaptation"]["events"]
    assert any(event["pattern"] == "squat" and event["action"] == "omitted_pending_symptom_review" for event in events)
    assert "squat" in plan["weekly_summary"]["unfilled_patterns"]


def test_comfortable_self_report_does_not_change_exercise_selection():
    baseline = generate_program(BASE)
    assessed = generate_program(BASE, movement_assessment={"squat": "comfortable"})
    assert [
        x["exercise_id"] for session in assessed["sessions"] for x in session["exercises"]
    ] == [
        x["exercise_id"] for session in baseline["sessions"] for x in session["exercises"]
    ]


@pytest.mark.parametrize("assessment", [
    {"jump": "comfortable"},
    {"squat": "pass"},
    [],
    "comfortable",
])
def test_invalid_movement_assessment_is_rejected(assessment):
    with pytest.raises(ProgramValidationError):
        generate_program(BASE, movement_assessment=assessment)


def test_needs_support_lunge_is_omitted_until_a_verified_supported_variant_exists():
    plan = generate_program(BASE, movement_assessment={"lunge": "needs_support"})
    assert not _exercises(plan, "lunge")
    assert any(
        event["pattern"] == "lunge"
        and event["action"] == "omitted_no_verified_supported_variant"
        for event in plan["movement_adaptation"]["events"]
    )


def test_needs_support_vertical_push_is_not_relabelled_as_an_unassisted_press():
    profile = {**BASE, "equipment": [item for item in BASE["equipment"] if item != "resistance_band"]}
    plan = generate_program(profile, movement_assessment={"overhead": "needs_support"})
    assert not _exercises(plan, "vertical_push")
    assert any(
        event["pattern"] == "vertical_push"
        and event["action"] == "omitted_no_verified_supported_variant"
        for event in plan["movement_adaptation"]["events"]
    )


def test_needs_support_horizontal_push_does_not_fall_back_to_the_same_standard_push_up():
    profile = {**BASE, "equipment": ["bodyweight"]}
    plan = generate_program(profile, movement_assessment={"push": "needs_support"})
    assert not _exercises(plan, "horizontal_push")
    assert any(
        event["pattern"] == "horizontal_push"
        and event["action"] == "omitted_no_verified_supported_variant"
        for event in plan["movement_adaptation"]["events"]
    )


def test_needs_support_horizontal_pull_does_not_fall_back_to_unmodified_one_arm_row():
    profile = {**BASE, "equipment": ["dumbbell"]}
    plan = generate_program(profile, movement_assessment={"pull": "needs_support"})
    assert not _exercises(plan, "horizontal_pull")
    assert any(
        event["pattern"] == "horizontal_pull"
        and event["action"] == "omitted_no_verified_supported_variant"
        for event in plan["movement_adaptation"]["events"]
    )
