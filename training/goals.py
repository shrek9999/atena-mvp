"""Canonical three-goal framework for ATENA Digital Coach.

The public onboarding exposes exactly three primary goals. Legacy identifiers
remain accepted for backward compatibility and are interpreted as canonical goals.
"""
from __future__ import annotations

CANONICAL_GOALS = {
    "strength_hypertrophy": {
        "id": "strength_hypertrophy",
        "label": "Moč + mišična masa",
        "description": "Pri začetnikih in manj izkušenih je moč + mišična masa skupen cilj: osnovni večsklepni gibi, postopna progresija in dovolj kakovostnega volumna. Pri naprednih se lahko cilj specializira v moč ali hipertrofijo.",
        "pillars": ["strength", "hypertrophy"],
        "advanced_specialization": ["strength", "hypertrophy"],
    },
    "functional": {
        "id": "functional",
        "label": "Funkcionalnost",
        "description": "Celostna zmogljivost: obremenjena večsklepna vadba, razvoj moči skozi čim večjo obvladano amplitudo (mobilnost predvsem skozi full-ROM vaje z bremenom) ter kondicija z MetConom ali intervali. Mobilnostni drili, ravnotežje in koordinacija so kratka ciljna priprava, ne glavni del treninga.",
        "pillars": ["strength", "mobility", "cardiorespiratory_conditioning", "functional_fitness"],
        "advanced_specialization": [],
    },
    "fat_loss": {
        "id": "fat_loss",
        "label": "Fat loss – zmanjšanje maščobne mase",
        "description": "Uravnavanje telesne teže temelji na treh stebrih: vadba z obremenitvijo za ohranjanje mišične mase, kondicijska/vzdržljivostna vadba in vzdržen energijski primanjkljaj z zadostnim vnosom beljakovin.",
        "pillars": ["strength", "hypertrophy", "muscular_endurance", "cardiorespiratory_conditioning", "weight_management", "nutrition"],
        "advanced_specialization": [],
        "nutrition_guidance": [
            "Ustvari zmeren in vzdržen energijski primanjkljaj; brez energijskega primanjkljaja dolgoročno zmanjšanje maščobne mase ni pričakovano. Izogibaj se agresivnim dietam.",
            "Zagotovi dovolj beljakovin za ohranjanje mišične mase; kot splošno izhodišče za zdrave odrasle, ki vadijo, uporabi približno 1,6–2,2 g/kg telesne mase na dan, nato prilagodi posamezniku.",
            "Vadbo z obremenitvijo ohrani kot obvezno osnovo programa; kondicijo dodaj z MetConom, intervali ali daljšo aerobno aktivnostjo, npr. hitro hojo v klanec.",
            "Večino prehrane naj sestavljajo hranilno bogata, pretežno minimalno predelana živila, zelenjava, sadje in viri vlaknin.",
            "Spremljaj večtedenski trend telesne mase in obseg pasu, ne posameznih dnevnih nihanj; prehrano prilagajaj počutju, spanju, regeneraciji in vzdržnosti."
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
