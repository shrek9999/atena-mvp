"""Canonical three-goal framework for ATENA Digital Coach.

The public onboarding exposes exactly three primary goals. Legacy identifiers
remain accepted at API boundaries and are normalized before profile storage.
"""
from __future__ import annotations

CANONICAL_GOALS = {
    "strength_hypertrophy": {
        "id": "strength_hypertrophy",
        "label": "Moč + mišična masa",
        "description": "Razvoj moči in mišične mase z osnovnimi večsklepnimi gibalnimi vzorci.",
        "pillars": ["strength", "hypertrophy"],
        "advanced_specialization": ["strength", "hypertrophy"],
    },
    "functional": {
        "id": "functional",
        "label": "Funkcionalnost",
        "description": "Celostna zmogljivost: moč, mobilnost skozi nadzorovano polno amplitudo, koordinacija, stabilnost in kondicija/MetCon.",
        "pillars": ["strength", "mobility", "coordination", "balance", "cardiorespiratory_conditioning", "functional_fitness"],
        "advanced_specialization": [],
    },
    "fat_loss": {
        "id": "fat_loss",
        "label": "Fat loss – zmanjšanje maščobne mase",
        "description": "Ohranjanje mišične mase z vadbo moči, razvoj vzdržljivosti in podpora vzdržni prehranski strategiji.",
        "pillars": ["strength", "hypertrophy", "muscular_endurance", "cardiorespiratory_conditioning", "weight_management", "nutrition"],
        "advanced_specialization": [],
    },
}

LEGACY_GOAL_ALIASES = {
    "strength": "strength_hypertrophy",
    "hypertrophy": "strength_hypertrophy",
    "general_fitness": "functional",
    "power": "functional",
    "endurance": "functional",
    "mobility": "functional",
    "weight_management": "fat_loss",
}

def normalize_goal(value: object) -> str:
    """Return one of the three canonical goal IDs; reject unknown values."""
    if not isinstance(value, str):
        raise ValueError("Cilj vadbe mora biti besedilna vrednost.")
    goal = value.strip().casefold()
    goal = LEGACY_GOAL_ALIASES.get(goal, goal)
    if goal not in CANONICAL_GOALS:
        raise ValueError("Izberi enega od treh glavnih ciljev ATENE.")
    return goal

def public_goal_options() -> list[dict]:
    """Return stable, user-facing onboarding options in display order."""
    return [
        {**goal, "advanced_specialization": list(goal["advanced_specialization"])}
        for goal in CANONICAL_GOALS.values()
    ]
