"""Regression tests for ATENA's public three-goal framework."""
import pytest

from training.goals import CANONICAL_GOALS, normalize_goal, public_goal_options


def test_public_onboarding_exposes_exactly_three_primary_goals():
    options = public_goal_options()
    assert [item["id"] for item in options] == [
        "strength_hypertrophy", "functional", "fat_loss"
    ]
    assert len(CANONICAL_GOALS) == 3


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("strength", "strength_hypertrophy"),
        ("hypertrophy", "strength_hypertrophy"),
        ("general_fitness", "functional"),
        ("power", "functional"),
        ("endurance", "functional"),
        ("mobility", "functional"),
        ("weight_management", "fat_loss"),
    ],
)
def test_legacy_goal_ids_normalize_without_breaking_existing_profiles(legacy, canonical):
    assert normalize_goal(legacy) == canonical


@pytest.mark.parametrize("goal", ["strength_hypertrophy", "functional", "fat_loss"])
def test_canonical_goal_ids_are_stable(goal):
    assert normalize_goal(goal) == goal


def test_unknown_goal_is_rejected():
    with pytest.raises(ValueError):
        normalize_goal("marathon")
