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
        ("UNASSESSABLE", "supported_squat", valid_report()),
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
