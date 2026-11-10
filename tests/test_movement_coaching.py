"""Tests for the six-pattern coaching registry and assessment record contract."""
import pytest

from training.movement_coaching import (
    MovementCoachingError,
    build_movement_decision,
    get_exercise_options,
    get_pattern_coaching,
    validate_pattern_registry,
)


def test_all_six_patterns_and_catalogue_links_are_valid():
    result = validate_pattern_registry()
    assert result["valid"] is True
    assert result["patterns"] == 6
    assert result["exercise_links_checked"] >= 30


def test_squat_reaching_squat_is_a_learning_method_not_a_mandatory_first_step():
    squat = get_pattern_coaching("squat")
    method = next(item for item in squat["learning_methods"] if item["id"] == "reaching_counterbalance")
    assert method["exercise_id"] == "reaching_squat"
    assert "protiutež" in method["description"]
    options = {item["id"] for item in squat["exercise_options"]}
    assert {"reaching_squat", "squat_goblet", "back_squat", "front_squat"} <= options


def test_squat_options_are_filtered_by_experience_and_available_equipment():
    beginner = get_exercise_options("squat", equipment=["bodyweight"], experience="beginner")
    assert beginner
    assert all(item["level"] == "beginner" for item in beginner)
    assert "back_squat" not in {item["id"] for item in beginner}

    advanced = get_exercise_options(
        "squat", equipment=["barbell", "rack", "dumbbell", "kettlebell"],
        experience="advanced", goal="strength",
    )
    ids = {item["id"] for item in advanced}
    assert {"squat_goblet", "back_squat", "front_squat"} <= ids


def test_hinge_learning_method_preserves_three_contacts_and_fourth_lumbar_control():
    hinge = get_pattern_coaching("hinge")
    method = next(item for item in hinge["learning_methods"] if item["id"] == "dowel_four_point")
    assert method["exercise_id"] is None
    assert all(term in method["description"] for term in ("trtico", "torakalnim", "zadnjim delom glave"))
    assert "četrta kontrolna točka" in method["description"].lower()
    assert "ledveni krivini" in method["description"].lower()
    assert "ne sme spreminjati" in method["description"].lower()


def test_supported_lunge_method_links_to_real_catalogue_exercise():
    lunge = get_pattern_coaching("lunge")
    method = next(item for item in lunge["learning_methods"] if item["id"] == "supported_split_squat")
    assert method["exercise"]["id"] == "supported_split_squat"
    assert "opora" in method["description"].lower()


def test_bent_over_row_is_separate_from_hinge_but_requires_trunk_position():
    row = get_pattern_coaching("horizontal_pull")
    assert row["task_id"] == "bent_over_row"
    assert "predklon" in row["task"]
    assert "dumbbell_bent_over_row" in {item["id"] for item in row["exercise_options"]}


def test_equipment_filter_does_not_offer_barbell_row_without_barbell():
    options = get_exercise_options(
        "horizontal_pull", equipment=["resistance_band"], experience="beginner"
    )
    ids = {item["id"] for item in options}
    assert "band_row" in ids
    assert "barbell_bent_over_row" not in ids


def test_decision_record_keeps_observations_and_user_report_separate():
    record = build_movement_decision(
        "hinge",
        "LEARN",
        observations={"spine_position": "not_observed"},
        equipment=["bodyweight"],
        implement_variant="broomstick",
        load=0,
        load_unit="kg",
        camera_views=["side"],
        capture_quality="adequate",
        confidence="medium",
        user_report={"pain": "no", "region": None},
        selected_learning_method="dowel_four_point",
        decision_reason="Najprej utrdi ohranjanje nevtralne ledvene krivine.",
    )
    assert record["assessment_version"] == "six-pattern-coaching-v1"
    assert record["observations"] == {"spine_position": "not_observed"}
    assert record["user_report"]["pain"] == "no"
    assert record["decision"] == "LEARN"
    assert record["is_diagnosis"] is False


@pytest.mark.parametrize("pattern,decision", [
    ("unknown", "READY"),
    ("squat", "PASS"),
    ("lunge", "REGRESS"),
])
def test_invalid_pattern_or_decision_is_rejected(pattern, decision):
    if pattern == "lunge":
        with pytest.raises(MovementCoachingError):
            build_movement_decision(pattern, decision, selected_exercise_id="push_up")
    else:
        with pytest.raises(MovementCoachingError):
            build_movement_decision(pattern, decision)


def test_exercise_selection_rejects_exercise_from_another_pattern():
    with pytest.raises(MovementCoachingError):
        build_movement_decision("squat", "READY", selected_exercise_id="push_up")



def test_horizontal_push_options_exclude_wall_push_up():
    coaching = get_pattern_coaching("horizontal_push")
    method_ids = {item["id"] for item in coaching["learning_methods"]}
    option_ids = {item["id"] for item in coaching["exercise_options"]}
    assert "wall_push_up" not in method_ids
    assert "wall_push_up" not in option_ids
    assert "incline_push_up" in method_ids
    assert "push_up_incline" in option_ids
