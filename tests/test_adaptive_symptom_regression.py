"""Regression tests for symptom-aware movement assessment."""
import pytest

from training.movement_coaching import (
    MovementCoachingError,
    validate_symptom_regression_report,
)
from training.catalogue import get_exercise


def valid_report():
    return {
        "status": "symptoms_reported",
        "regression_test": {
            "status": "tolerated",
            "variation_id": "supported_squat",
            "pain_during": 1,
            "worsened": False,
        },
    }


def test_local_symptom_can_pass_only_the_tested_regression():
    validate_symptom_regression_report(valid_report(), "REGRESS", "supported_squat")


@pytest.mark.parametrize(
    "decision,exercise_id,report",
    [
        ("READY", "supported_squat", valid_report()),
        ("LEARN", "supported_squat", valid_report()),
        ("REGRESS", "air_squat", valid_report()),
        ("REGRESS", "supported_squat", {
            "status": "symptoms_reported",
            "regression_test": {
                "status": "tolerated", "variation_id": "supported_squat",
                "pain_during": 3, "worsened": False,
            },
        }),
        ("REGRESS", "supported_squat", {
            "status": "symptoms_reported",
            "regression_test": {
                "status": "tolerated", "variation_id": "supported_squat",
                "pain_during": 1, "worsened": True,
            },
        }),
    ],
)
def test_symptom_report_rejects_untested_or_intolerable_variations(decision, exercise_id, report):
    with pytest.raises(MovementCoachingError):
        validate_symptom_regression_report(report, decision, exercise_id)


def test_supported_squat_is_a_verified_catalogue_exercise():
    exercise = get_exercise("supported_squat")
    assert exercise is not None
    assert exercise["pattern"] == "squat"
    assert set(exercise["equipment_any"]) == {"household_support", "suspension_trainer"}


def test_symptom_report_can_remain_unassessable_without_a_tolerated_regression():
    validate_symptom_regression_report({"status": "symptoms_reported"}, "UNASSESSABLE", None)

from training.movement_coaching import PATTERN_DEFINITIONS, build_movement_decision
from training.program import generate_program


BASE_PROFILE = {
    "goal": "hypertrophy",
    "experience": "intermediate",
    "equipment": [
        "bodyweight", "barbell", "rack", "dumbbell", "bench",
        "pull_up_bar", "kettlebell", "cable", "resistance_band",
        "household_support", "wall", "anchor_point",
    ],
    "sessions_per_week": 2,
    "session_minutes": 60,
}


def structured_assessment(needs_support_pattern):
    decisions = {}
    for pattern in PATTERN_DEFINITIONS:
        needs_support = pattern == needs_support_pattern
        decisions[pattern] = build_movement_decision(
            pattern,
            "LEARN" if needs_support else "READY",
            user_report={"status": "needs_support" if needs_support else "comfortable"},
            decision_reason="synthetic acceptance test",
        )
    return decisions


def test_structured_needs_support_uses_verified_equipment_compatible_variant():
    plan = generate_program(
        BASE_PROFILE,
        movement_decisions=structured_assessment("squat"),
    )
    squats = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] == "squat"
    ]
    assert squats
    assert {exercise["exercise_id"] for exercise in squats} == {"supported_squat"}


def test_structured_needs_support_without_approved_equipment_omits_only_that_pattern():
    profile = {**BASE_PROFILE, "equipment": ["bodyweight", "dumbbell"]}
    plan = generate_program(
        profile,
        movement_decisions=structured_assessment("horizontal_pull"),
    )
    exercises = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
    ]
    assert not any(exercise["pattern"] == "horizontal_pull" for exercise in exercises)
    assert any(
        event["pattern"] == "horizontal_pull"
        and event["action"] == "omitted_unassessable_pending_reassessment"
        for event in plan["movement_adaptation"]["events"]
    )
