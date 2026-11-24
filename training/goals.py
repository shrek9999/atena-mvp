"""Canonical three-goal framework for ATENA Digital Coach.

The public onboarding exposes exactly three primary goals. Legacy identifiers
remain accepted for backward compatibility and are interpreted as canonical goals.
"""
from __future__ import annotations

CANONICAL_GOALS = {
    "strength_hypertrophy": {
        "id": "strength_hypertrophy",
        "label": "Moč + mišična masa",
        "description": "Pri manj izkušenih sta moč in mišična masa povezana cilja, zato ju razvijamo skupaj z obremenjenimi večsklepnimi vajami. Napredni lahko izberejo ločen poudarek na moči ali hipertrofiji.",
        "pillars": ["strength", "hypertrophy"],
        "advanced_specialization": ["strength", "hypertrophy"],
    },
    "functional": {
        "id": "functional",
        "label": "Funkcionalnost",
        "description": "Razvoj uporabne moči z obremenjenimi večsklepnimi vajami skozi veliko obvladano amplitudo; mobilnost razvijamo predvsem z močjo skozi ROM, vzdržljivost pa z intervali, krožno vadbo ali MetCon.",
        "pillars": ["strength", "mobility", "cardiorespiratory_conditioning", "functional_fitness"],
        "advanced_specialization": [],
    },
    "fat_loss": {
        "id": "fat_loss",
        "label": "Fat loss – zmanjšanje maščobne mase",
        "description": "Kombinacija obremenjene vadbe za ohranitev mišične mase, kondicijske vadbe in prehrane z zmernim energijskim primanjkljajem ter zadostnimi beljakovinami.",
        "pillars": ["strength", "hypertrophy", "muscular_endurance", "cardiorespiratory_conditioning", "weight_management", "nutrition"],
        "advanced_specialization": [],
        "nutrition_guidance": [
            "Ustvari zmeren in vzdržen energijski primanjkljaj; izogibaj se agresivnim dietam.",
            "Beljakovine naj bodo visoko na seznamu prioritet; okvirno 1,6–2,2 g/kg ciljne oziroma prilagojene telesne mase na dan, če ni zdravstvenih omejitev.",
            "Ohrani redno vadbo z zunanjimi bremeni za ohranjanje mišične mase in zmogljivosti.",
            "Kondicijo dodaj z intervali, MetCon vadbo ali daljšo hojo navkreber; obseg prilagajaj regeneraciji.",
            "Spremljaj večtedenski trend telesne mase in obseg pasu ter prehrano prilagajaj vzdržno."
        ],
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
