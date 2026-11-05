"""Regression tests for ATENA's general-population coaching standard."""

from training.catalogue import get_exercise, load_catalogue
from coach_routes import SYSTEM_PROMPT


def test_superman_is_a_verified_bodyweight_mat_accessory_not_a_primary_strength_lift():
    exercise = get_exercise("superman")
    assert exercise is not None
    assert exercise["equipment"] == ["bodyweight"]
    assert exercise["level"] == "beginner"
    assert exercise["training_role"] == "accessory"
    assert exercise["loading_potential"] == "low"
    assert "general_fitness" in exercise["goals"]
    assert exercise["regressions"]
    assert exercise["progressions"]
    assert any("ledven" in cue.casefold() for cue in exercise["common_errors"])


def test_catalogue_keeps_superman_available_as_a_complementary_exercise():
    records = load_catalogue()
    exercise = next(item for item in records if item["id"] == "superman")
    assert exercise["movement_pattern"] == "trunk_control"
    assert exercise["stability_role"] == "supporting"


def test_coach_prompt_prioritizes_simple_effective_bodyweight_exercises():
    prompt = SYSTEM_PROMPT.casefold()
    assert "a controlled bodyweight squat" in prompt
    assert "3 × 8 bodyweight squats" in prompt
    assert "do not replace them with advanced variations merely to make the plan look sophisticated" in prompt


def test_coach_prompt_requires_explicit_equipment_and_rejects_unsafe_table_rows():
    prompt = SYSTEM_PROMPT.casefold()
    assert "never assume a table" in prompt
    assert "do not prescribe table rows" in prompt
    assert "missing pulling option is a real limitation" in prompt


def test_coach_prompt_has_observable_regression_and_progression_criteria():
    prompt = SYSTEM_PROMPT.casefold()
    assert "across at least two exposures" in prompt
    assert "regression triggers" in prompt
    assert "progression triggers" in prompt
    assert "change one variable at a time" in prompt


def test_coach_prompt_keeps_mat_based_trunk_work_as_complementary_not_a_replacement_for_pulling():
    prompt = SYSTEM_PROMPT.casefold()
    assert "mat-based exercises" in prompt
    assert "do not pretend a prone back exercise fully replaces loaded pulling" in prompt


def test_coach_prompt_requires_concise_non_repetitive_exercise_cues():
    prompt = SYSTEM_PROMPT.casefold()
    assert "2–4 concise, non-repetitive coaching cues" in prompt
    assert "avoid repeating generic amplitude and safety paragraphs" in prompt
