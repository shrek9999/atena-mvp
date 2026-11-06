import pytest

from training.goal_taxonomy import (
    CANONICAL_GOALS,
    GoalTaxonomyError,
    canonicalize_goal,
)


@pytest.mark.parametrize(
    "legacy,canonical,focus",
    [
        ("strength", "strength_muscle", "balanced"),
        ("hypertrophy", "strength_muscle", "balanced"),
        ("strength_hypertrophy", "strength_muscle", "balanced"),
        ("fat_loss", "body_weight_management", "balanced"),
        ("general_fitness", "functional_fitness", "general"),
        ("functional", "functional_fitness", "general"),
        ("power", "functional_fitness", "power"),
        ("endurance", "functional_fitness", "endurance"),
        ("mobility", "functional_fitness", "mobility"),
    ],
)
def test_legacy_goals_map_to_three_canonical_goals(legacy, canonical, focus):
    result = canonicalize_goal(legacy, experience="intermediate")
    assert result["canonical_goal"] == canonical
    assert result["functional_focus"] == focus
    assert result["source_goal"] == legacy
    assert result["source_schema"] == "legacy"
    assert result["legacy_generator_goal"] in {
        "strength_hypertrophy", "fat_loss", "functional",
        "power", "endurance", "mobility",
    }


def test_canonical_strength_muscle_uses_combined_generator_goal_by_default():
    result = canonicalize_goal("strength_muscle", experience="beginner")
    assert result["canonical_goal"] == "strength_muscle"
    assert result["legacy_generator_goal"] == "strength_hypertrophy"
    assert result["strength_emphasis"] == "balanced"


@pytest.mark.parametrize("emphasis,expected", [
    ("strength", "strength"),
    ("hypertrophy", "hypertrophy"),
])
def test_only_advanced_users_can_receive_specialised_strength_emphasis(emphasis, expected):
    advanced = canonicalize_goal(
        "strength_muscle", experience="advanced", training_emphasis=emphasis
    )
    non_advanced = canonicalize_goal(
        "strength_muscle", experience="intermediate", training_emphasis=emphasis
    )
    assert advanced["legacy_generator_goal"] == expected
    assert advanced["strength_emphasis"] == emphasis
    assert non_advanced["legacy_generator_goal"] == "strength_hypertrophy"
    assert non_advanced["strength_emphasis"] == "balanced"


@pytest.mark.parametrize("focus,expected", [
    ("general", "functional"),
    ("power", "power"),
    ("endurance", "endurance"),
    ("mobility", "mobility"),
])
def test_functional_qualities_are_focus_dimensions_not_primary_goals(focus, expected):
    result = canonicalize_goal(
        "functional_fitness", experience="beginner", functional_focus=focus
    )
    assert result["canonical_goal"] == "functional_fitness"
    assert result["legacy_generator_goal"] == expected
    assert result["functional_focus"] == focus


def test_canonical_body_weight_management_maps_to_existing_fat_loss_generator():
    result = canonicalize_goal("body_weight_management", experience="intermediate")
    assert result["canonical_goal"] == "body_weight_management"
    assert result["legacy_generator_goal"] == "fat_loss"


@pytest.mark.parametrize("goal", [None, "", "cardio_only", "unknown"])
def test_unknown_goal_fails_closed(goal):
    with pytest.raises(GoalTaxonomyError):
        canonicalize_goal(goal)


def test_invalid_strength_emphasis_is_rejected():
    with pytest.raises(GoalTaxonomyError):
        canonicalize_goal(
            "strength_muscle", experience="advanced", training_emphasis="maximal"
        )


def test_invalid_functional_focus_is_rejected():
    with pytest.raises(GoalTaxonomyError):
        canonicalize_goal(
            "functional_fitness", experience="intermediate", functional_focus="crossfit"
        )


def test_invalid_experience_is_rejected():
    with pytest.raises(GoalTaxonomyError):
        canonicalize_goal("strength_muscle", experience="elite")
