"""Safety contract tests for symptom-triggered movement regression retests."""

import pytest

from training.movement_assessment import SYMPTOM_REGRESSION_VARIANTS
from training.movement_coaching import (
    MovementCoachingError,
    build_movement_decision,
    validate_symptom_regression_report,
)
from training.program import ProgramValidationError, generate_program


PROFILE = {
    "goal": "functional",
    "experience": "beginner",
    "equipment": ["bodyweight", "household_support"],
    "sessions_per_week": 2,
    "session_minutes": 45,
}


def _report(*, status="tolerated", variation="supported_squat", pain=1, worsened=False):
    return {
        "status": "symptoms_reported",
        "regression_test": {
            "status": status,
            "variation_id": variation,
            "pain_during": pain,
            "worsened": worsened,
        },
    }


def test_only_exact_tolerated_squat_regression_can_be_included():
    validate_symptom_regression_report(
        _report(), "REGRESS", "supported_squat",
        SYMPTOM_REGRESSION_VARIANTS["squat"],
    )


@pytest.mark.parametrize(
    "report,decision,exercise,allowed",
    [
        (_report(pain=3), "REGRESS", "supported_squat", SYMPTOM_REGRESSION_VARIANTS["squat"]),
        (_report(worsened=True), "REGRESS", "supported_squat", SYMPTOM_REGRESSION_VARIANTS["squat"]),
        (_report(variation="chair_sit_to_stand"), "REGRESS", "supported_squat", SYMPTOM_REGRESSION_VARIANTS["squat"]),
        ({"status": "symptoms_reported"}, "REGRESS", "supported_squat", SYMPTOM_REGRESSION_VARIANTS["squat"]),
        (_report(variation="unknown_exercise"), "REGRESS", "unknown_exercise", SYMPTOM_REGRESSION_VARIANTS["squat"]),
        (_report(variation="supported_squat"), "REGRESS", "supported_squat", SYMPTOM_REGRESSION_VARIANTS["lunge"]),
        (_report(pain=True), "REGRESS", "supported_squat", SYMPTOM_REGRESSION_VARIANTS["squat"]),
    ],
)
def test_invalid_or_mismatched_retest_is_rejected(report, decision, exercise, allowed):
    with pytest.raises(MovementCoachingError):
        validate_symptom_regression_report(report, decision, exercise, allowed)


def test_symptom_without_successful_retest_remains_unassessable():
    validate_symptom_regression_report(
        {"status": "symptoms_reported"}, "UNASSESSABLE", None,
        SYMPTOM_REGRESSION_VARIANTS["squat"],
    )


def test_failed_retest_is_recorded_but_cannot_select_an_exercise():
    validate_symptom_regression_report(
        _report(status="not_tolerated", pain=4), "UNASSESSABLE", None,
        SYMPTOM_REGRESSION_VARIANTS["squat"],
    )


def test_unassessable_symptom_cannot_smuggle_in_a_selected_exercise():
    with pytest.raises(MovementCoachingError):
        validate_symptom_regression_report(
            {"status": "symptoms_reported"}, "UNASSESSABLE", "supported_squat",
            SYMPTOM_REGRESSION_VARIANTS["squat"],
        )


def test_regression_decision_without_exact_selected_exercise_is_rejected_by_generator():
    decision = build_movement_decision(
        "squat", "REGRESS",
        user_report=_report(),
        decision_reason="Synthetic safety contract test",
    )
    with pytest.raises(ProgramValidationError):
        generate_program(PROFILE, movement_decisions={"squat": decision})


def test_generator_uses_only_the_exact_retested_regression():
    decision = build_movement_decision(
        "squat", "REGRESS",
        user_report=_report(),
        selected_exercise_id="supported_squat",
        decision_reason="Synthetic safety contract test",
    )
    plan = generate_program(PROFILE, movement_decisions={"squat": decision})
    squats = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] == "squat"
    ]
    assert squats
    assert {exercise["exercise_id"] for exercise in squats} == {"supported_squat"}
    assert all(exercise["prescription"]["sets"] <= 2 for exercise in squats)


def test_symptomatic_pattern_is_omitted_after_failed_retest():
    decision = build_movement_decision(
        "squat", "UNASSESSABLE",
        user_report=_report(status="not_tolerated", pain=4),
        decision_reason="Synthetic failed retest",
    )
    plan = generate_program(PROFILE, movement_decisions={"squat": decision})
    squats = [
        exercise
        for session in plan["sessions"]
        for exercise in session["exercises"]
        if exercise["pattern"] == "squat"
    ]
    assert not squats
