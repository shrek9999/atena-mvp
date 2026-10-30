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


def test_pattern_filter_supports_lunge_variants():
    records = get_exercises(goal="hypertrophy", patterns={"lunge"})
    ids = {item["id"] for item in records}
    assert {"split_squat", "reverse_lunge", "forward_lunge", "rear_foot_elevated_split_squat", "atg_split_squat"} <= ids


def test_lookup_returns_none_for_unknown_id():
    assert get_exercise("not_a_real_exercise") is None


def test_catalogue_is_json_not_python_executable_content():
    raw = json.loads(Path("training/exercises.json").read_text(encoding="utf-8"))
    assert isinstance(raw, list)
