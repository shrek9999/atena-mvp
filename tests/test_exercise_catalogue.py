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



def test_push_up_has_a_catalogue_backed_height_progression_and_dumbbell_row_needs_no_bench():
    push_up = get_exercise("push_up")
    assert {"push_up_incline", "wall_push_up"} <= set(push_up["regressions"])
    assert "push_up_decline" in push_up["progressions"]
    assert "push_up_incline" in {item["id"] for item in get_exercises(equipment={"bodyweight", "household_support"})}
    assert "push_up_decline" in {item["id"] for item in get_exercises(equipment={"bodyweight", "household_support"})}
    assert "one_arm_row" in {item["id"] for item in get_exercises(goal="hypertrophy", equipment={"dumbbell"})}



def test_joint_regions_and_cardiorespiratory_systems_are_not_mislabelled_as_muscles():
    non_muscle_tags = {
        "ankle_mobility", "hip_mobility", "shoulder_mobility", "thoracic_mobility",
        "shoulders", "upper_back", "grip", "cardiorespiratory_system",
    }
    for item in load_catalogue():
        assert not (set(item["primary_muscles"]) | set(item["secondary_muscles"])) & non_muscle_tags, item["id"]
    assert get_exercise("ankle_knee_to_wall")["target_regions"] == ["ankle"]
    assert get_exercise("hip_90_90_switch")["target_regions"] == ["hip"]


def test_added_strength_side_and_atg_variants_are_available():
    records = {item["id"] for item in load_catalogue()}
    assert {
        "dead_hang", "hip_90_90_ir_isometric", "crab_reach",
        "elevated_pigeon_hinge", "straight_leg_hip_hinge", "wall_butterfly",
        "patrick_step", "reverse_nordic_curl", "sled_backward_drag",
        "front_rack_carry", "overhead_carry",
    } <= records


def test_every_exercise_has_valid_taxonomy_and_stability_metadata():
    valid_patterns = {
        "squat", "lunge", "hinge", "hip_extension", "push", "pull", "carry", "trunk_control",
        "locomotion", "conditioning", "mobility", "balance", "coordination", "accessory",
    }
    valid_stability_roles = {"primary", "supporting", "incidental", "none"}
    valid_stability_focus = {"trunk_control", "trunk_bracing", "balance", "coordination", "joint_control"}
    for item in load_catalogue():
        assert item["movement_pattern"] in valid_patterns, item["id"]
        assert item["training_purposes"], item["id"]
        assert item["stability_role"] in valid_stability_roles, item["id"]
        assert set(item["stability_focus"]) <= valid_stability_focus, item["id"]
        assert (item["stability_role"] == "none") == (not item["stability_focus"]), item["id"]


def test_reaching_squat_is_an_accessible_squat_with_supporting_stability_role():
    item = get_exercise("reaching_squat")
    assert item["movement_pattern"] == "squat"
    assert item["stability_role"] == "supporting"
    assert {"trunk_bracing", "balance", "coordination"} <= set(item["stability_focus"])
    assert {"stability", "trunk_bracing", "balance", "coordination", "skill"} <= set(item["training_purposes"])
    assert "hypertrophy" not in item["training_purposes"]
    assert "weight_plate" in item["equipment_any"]
    assert any("5 kg" in cue for cue in item["cues"])


def test_unloaded_hinge_uses_neutral_back_forward_bend_user_facing_name():
    item = get_exercise("bodyweight_hip_hinge")
    assert item["name"] == "Predklon z ravnim hrbtom (lastna teža)"
    assert any("nevtralnega položaja hrbtenice" in cue for cue in item["cues"])



def test_knee_flexion_accessories_are_not_misclassified_as_hip_hinge_patterns():
    assert get_exercise("slider_leg_curl")["movement_pattern"] == "accessory"
    assert get_exercise("nordic_hamstring_curl")["movement_pattern"] == "accessory"


def test_static_stretches_do_not_claim_balance_or_stability_training():
    for exercise_id in ("couch_stretch", "supine_hamstring_stretch", "doorway_pec_stretch", "calf_wall_stretch"):
        item = get_exercise(exercise_id)
        assert item["training_purposes"] == ["mobility"]
        assert item["stability_role"] == "none"
        assert item["stability_focus"] == []


def test_low_load_trunk_control_drills_are_not_tagged_as_hypertrophy_exercises():
    for exercise_id in ("pallof_press", "dead_bug", "seated_leg_lift"):
        assert "hypertrophy" not in get_exercise(exercise_id)["training_purposes"]



def test_hip_extension_variants_are_distinct_from_the_predklon_pattern():
    for exercise_id in ("hip_thrust", "glute_bridge", "long_lever_glute_bridge", "elevated_heel_hip_lift"):
        assert get_exercise(exercise_id)["movement_pattern"] == "hip_extension"
    assert get_exercise("bodyweight_hip_hinge")["movement_pattern"] == "hinge"



def test_programme_hinge_label_uses_neutral_back_predklon_wording():
    from training.program import PATTERN_LABELS

    assert PATTERN_LABELS["hinge"] == "predklon z nevtralno hrbtenico"



def test_single_leg_balance_reach_uses_balance_and_joint_control_stability_focus():
    item = get_exercise("single_leg_balance_reach")
    assert item["stability_role"] == "primary"
    assert set(item["stability_focus"]) == {"balance", "joint_control"}



def test_purpose_filter_returns_only_exercises_with_requested_training_purpose():
    records = get_exercises(purposes={"cardiorespiratory_conditioning"})
    assert records
    assert all("cardiorespiratory_conditioning" in item["training_purposes"] for item in records)


def test_primary_and_supporting_stability_roles_are_tagged_as_stability_purpose():
    for item in load_catalogue():
        if item["stability_role"] in {"primary", "supporting"}:
            assert "stability" in item["training_purposes"], item["id"]
        else:
            assert "stability" not in item["training_purposes"], item["id"]


def test_reaching_squat_is_not_eligible_as_a_hypertrophy_stimulus_by_purpose():
    mobility = {item["id"] for item in get_exercises(goal="mobility", purposes={"mobility"})}
    hypertrophy = {item["id"] for item in get_exercises(goal="hypertrophy", purposes={"hypertrophy"})}
    assert "reaching_squat" in mobility
    assert "reaching_squat" not in hypertrophy


def test_everyday_movement_regressions_are_catalogued_with_required_supports():
    chair = get_exercise("chair_sit_to_stand")
    wall_hinge = get_exercise("wall_hip_hinge")
    assert chair["pattern"] == "squat"
    assert chair["level"] == "beginner"
    assert "chair" in chair["equipment_any"] or "household_support" in chair["equipment_any"]
    assert wall_hinge["pattern"] == "hinge"
    assert wall_hinge["level"] == "beginner"
    assert "wall" in wall_hinge["equipment_any"]
