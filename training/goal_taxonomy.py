"""Canonical ATENA goal taxonomy and backwards-compatible legacy mapping.

This module is intentionally pure: it does not mutate profiles, rewrite stored
records, or change programme generation until an explicit integration step.
"""
from __future__ import annotations

CANONICAL_GOALS = {
    "strength_muscle",
    "functional_fitness",
    "body_weight_management",
}

LEGACY_GOAL_MAP = {
    "strength": ("strength_muscle", "strength", "balanced"),
    "hypertrophy": ("strength_muscle", "hypertrophy", "balanced"),
    "strength_hypertrophy": ("strength_muscle", "balanced", "balanced"),
    "fat_loss": ("body_weight_management", "balanced", "balanced"),
    "general_fitness": ("functional_fitness", "balanced", "general"),
    "functional": ("functional_fitness", "balanced", "general"),
    "power": ("functional_fitness", "balanced", "power"),
    "endurance": ("functional_fitness", "balanced", "endurance"),
    "mobility": ("functional_fitness", "balanced", "mobility"),
}

VALID_STRENGTH_EMPHASIS = {"balanced", "strength", "hypertrophy"}
VALID_FUNCTIONAL_FOCUS = {"general", "power", "endurance", "mobility"}


class GoalTaxonomyError(ValueError):
    """Raised when a goal cannot be mapped without inventing user intent."""


def canonicalize_goal(goal: object, *, experience: object = None,
                      training_emphasis: object = None,
                      functional_focus: object = None) -> dict:
    """Return a canonical goal plus an explicit legacy generator mapping.

    Legacy values are preserved as the internal generator target so this
    adapter can be introduced before any programme-generation behaviour changes.
    Specialised strength/hypertrophy emphasis is honoured only for advanced
    users. Functional qualities remain focus dimensions within functional
    fitness, not standalone primary goals.
    """
    if not isinstance(goal, str) or not goal.strip():
        raise GoalTaxonomyError("Cilj vadbe ni določen.")

    if experience is not None and experience not in {"beginner", "intermediate", "advanced"}:
        raise GoalTaxonomyError("Raven izkušenj ni veljavna.")

    raw_goal = goal.strip().lower()
    if raw_goal in LEGACY_GOAL_MAP:
        canonical_goal, legacy_emphasis, legacy_focus = LEGACY_GOAL_MAP[raw_goal]
        source = "legacy"
        legacy_goal = raw_goal
    elif raw_goal in CANONICAL_GOALS:
        canonical_goal = raw_goal
        source = "canonical"
        if raw_goal == "strength_muscle":
            if training_emphasis is not None and training_emphasis not in VALID_STRENGTH_EMPHASIS:
                raise GoalTaxonomyError("Poudarek vadbe za moč in mišično maso ni veljaven.")
            legacy_emphasis = training_emphasis or "balanced"
            legacy_focus = "balanced"
            if experience != "advanced":
                legacy_emphasis = "balanced"
            legacy_goal = {
                "balanced": "strength_hypertrophy",
                "strength": "strength",
                "hypertrophy": "hypertrophy",
            }[legacy_emphasis]
        elif raw_goal == "functional_fitness":
            if functional_focus is not None and functional_focus not in VALID_FUNCTIONAL_FOCUS:
                raise GoalTaxonomyError("Poudarek funkcionalne vadbe ni veljaven.")
            legacy_focus = functional_focus or "general"
            legacy_emphasis = "balanced"
            legacy_goal = {
                "general": "functional",
                "power": "power",
                "endurance": "endurance",
                "mobility": "mobility",
            }[legacy_focus]
        else:
            legacy_emphasis = "balanced"
            legacy_focus = "balanced"
            legacy_goal = "fat_loss"
    else:
        raise GoalTaxonomyError("Izbrani cilj vadbe ni podprt.")

    # A legacy strength/hypertrophy selection is retained as its original
    # generator intent; the combined goal is the user-facing canonical goal.
    if raw_goal in {"strength", "hypertrophy", "strength_hypertrophy"}:
        if experience != "advanced":
            legacy_emphasis = "balanced"
            legacy_goal = "strength_hypertrophy"

    return {
        "canonical_goal": canonical_goal,
        "legacy_generator_goal": legacy_goal,
        "strength_emphasis": legacy_emphasis,
        "functional_focus": legacy_focus,
        "source_goal": raw_goal,
        "source_schema": source,
        "requires_clarification": False,
    }
