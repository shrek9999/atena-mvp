"""Acceptance tests for the supported squat catalogue option."""

from training.catalogue import get_exercise
from training.movement_assessment import SUPPORTED_VARIANTS
from training.movement_coaching import get_exercise_options


def test_supported_squat_requires_confirmed_stable_support():
    without_support = get_exercise_options(
        "squat", equipment=["bodyweight"], experience="beginner", goal="functional"
    )
    with_support = get_exercise_options(
        "squat", equipment=["bodyweight", "household_support"],
        experience="beginner", goal="functional",
    )

    assert "supported_squat" not in {item["id"] for item in without_support}
    assert "supported_squat" in {item["id"] for item in with_support}


def test_supported_squat_is_registered_only_as_a_squat_variant():
    exercise = get_exercise("supported_squat")
    assert exercise is not None
    assert exercise["pattern"] == "squat"
    assert "supported_squat" in SUPPORTED_VARIANTS["squat"]
    assert all(
        "supported_squat" not in variants
        for pattern, variants in SUPPORTED_VARIANTS.items()
        if pattern != "squat"
    )


def test_supported_squat_has_explicit_stability_and_stop_cues():
    exercise = get_exercise("supported_squat")
    text = " ".join(exercise["cues"] + exercise["warnings"]).casefold()
    assert "stabilne opore" in text
    assert "bolečina" in text
    assert exercise["loading_potential"] == "low"
    assert set(exercise["equipment_any"]) == {"household_support", "suspension_trainer"}
