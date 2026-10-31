import json
from pathlib import Path

import pytest

from training.catalogue import (
    CatalogueValidationError,
    get_exercise,
    get_exercises,
    load_catalogue,
    validate_catalogue,
)


def test_catalogue_loads_and_has_unique_ids():
    records = load_catalogue()
    assert len(records) >= 20
    assert len({item["id"] for item in records}) == len(records)


def test_every_exercise_has_required_coaching_and_progression_metadata():
    for item in load_catalogue():
        assert item["cues"], item["id"]
        assert item["common_errors"], item["id"]
        assert item["regressions"], item["id"]
        assert item["progressions"], item["id"]
        assert item["warnings"], item["id"]


def test_duplicate_ids_are_rejected():
    item = load_catalogue()[0]
    with pytest.raises(CatalogueValidationError, match="Podvojen ID"):
        validate_catalogue([item, item])


def test_missing_fields_are_rejected():
    with pytest.raises(CatalogueValidationError, match="nima polj"):
        validate_catalogue([{"id": "incomplete"}])


def test_hypertrophy_defaults_to_multi_joint_exercises():
    records = get_exercises(goal="hypertrophy")
    assert records
    assert all(not item["single_joint"] for item in records)


def test_single_joint_accessories_are_opt_in():
    default = get_exercises(goal="hypertrophy")
    expanded = get_exercises(goal="hypertrophy", include_accessories=True)
    assert any(item["single_joint"] for item in expanded)
    assert not any(item["single_joint"] for item in default)


def test_equipment_filter_does_not_return_unavailable_gear():
    records = get_exercises(goal="hypertrophy", equipment={"dumbbell", "bench"})
    assert records
    assert all(set(item["equipment"]).issubset({"dumbbell", "bench", "bodyweight"}) for item in records)
    assert all(not item["equipment_any"] or set(item["equipment_any"]) & {"dumbbell", "bench", "bodyweight"} for item in records)


def test_pattern_filter_supports_lunge_variants():
    records = get_exercises(goal="hypertrophy", patterns={"lunge"})
    ids = {item["id"] for item in records}
    assert {"split_squat", "reverse_lunge", "forward_lunge", "rear_foot_elevated_split_squat", "atg_split_squat"} <= ids


def test_lookup_returns_none_for_unknown_id():
    assert get_exercise("not_a_real_exercise") is None


def test_catalogue_is_json_not_python_executable_content():
    raw = json.loads(Path("training/exercises.json").read_text(encoding="utf-8"))
    assert isinstance(raw, list)



def test_any_equipment_options_accept_either_dumbbell_or_kettlebell():
    dumbbell = {item["id"] for item in get_exercises(equipment={"dumbbell"})}
    kettlebell = {item["id"] for item in get_exercises(equipment={"kettlebell"})}
    assert "squat_goblet" in dumbbell
    assert "squat_goblet" in kettlebell


def test_required_equipment_still_requires_all_items():
    records = {item["id"] for item in get_exercises(equipment={"barbell"})}
    assert "back_squat" not in records
    records_with_rack = {item["id"] for item in get_exercises(equipment={"barbell", "rack"})}
    assert "back_squat" in records_with_rack



def test_equipment_any_must_be_a_list():
    item = load_catalogue()[0]
    item["equipment_any"] = "dumbbell"
    with pytest.raises(CatalogueValidationError, match="equipment_any"):
        validate_catalogue([item])


def test_unilateral_metadata_must_be_boolean():
    item = load_catalogue()[0]
    item["unilateral"] = "yes"
    with pytest.raises(CatalogueValidationError, match="unilateral"):
        validate_catalogue([item])



def test_every_catalogue_entry_has_scaling_and_role_metadata():
    for item in load_catalogue():
        assert item["loading_potential"] in {"low", "moderate", "high"}, item["id"]
        assert item["training_role"] in {"main", "accessory", "mobility", "conditioning", "stability", "power"}, item["id"]
        assert isinstance(item.get("time_based", False), bool), item["id"]


def test_bodyweight_hip_hinge_is_marked_as_a_low_load_skill_drill():
    item = get_exercise("bodyweight_hip_hinge")
    assert item["loading_potential"] == "low"


def test_household_supports_enable_safe_home_variants_in_catalogue():
    available = {"bodyweight", "chair", "towel", "wall", "household_support", "household_load"}
    ids = {item["id"] for item in get_exercises(equipment=available, include_accessories=True)}
    assert {"single_leg_box_squat", "inverted_row_table", "slider_leg_curl", "elevated_heel_hip_lift", "farmer_carry_bodyweight"} <= ids
    assert "kettlebell_one_arm_row" not in ids


def test_endurance_and_mobility_pools_are_distinct_and_present():
    endurance = {item["id"] for item in get_exercises(goal="endurance")}
    mobility = {item["id"] for item in get_exercises(goal="mobility")}
    assert {"running_easy", "brisk_walking", "burpee", "jump_rope", "box_jump_intervals"} <= endurance
    assert {"hip_90_90_switch", "ankle_knee_to_wall", "deep_squat_hold", "cossack_squat", "calf_raise_full_rom", "tibialis_raise", "couch_stretch", "supine_hamstring_stretch", "doorway_pec_stretch"} <= mobility



def test_cardiorespiratory_targets_are_not_mislabelled_as_muscles():
    cardio_ids = {"running_easy", "brisk_walking", "cycling", "burpee", "sled_push", "rower_intervals"}
    for item in load_catalogue():
        if item["id"] in cardio_ids:
            assert "cardiorespiratory" in item["target_systems"]
            assert "cardiorespiratory_system" not in item["primary_muscles"]



def test_mobility_holds_and_active_repetitions_have_different_dose_types():
    assert get_exercise("deep_squat_hold")["time_based"] is True
    assert get_exercise("couch_stretch")["time_based"] is True
    assert get_exercise("hip_90_90_switch")["time_based"] is False
    assert get_exercise("cossack_squat")["time_based"] is False
