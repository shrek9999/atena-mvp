"""Conservative training adaptation signals.

These are review prompts, not automatic program edits or medical advice.
Pain/discomfort data is only available when the user has separately consented.
"""
from datetime import date


def _ordered(sessions):
    valid = []
    for item in sessions if isinstance(sessions, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            day = date.fromisoformat(item.get("session_date", ""))
        except (TypeError, ValueError):
            continue
        session = item.get("session")
        if isinstance(session, dict):
            valid.append((day, session))
    return sorted(valid, key=lambda pair: pair[0], reverse=True)


def assess_next_step(sessions):
    """Return a transparent conservative next-step signal from recent session feedback."""
    recent = _ordered(sessions)[:3]
    completed = [(day, s) for day, s in recent if s.get("completed") is True]

    discomfort_sessions = [
        s for _, s in recent if s.get("discomfort_reported") is True
    ]
    if discomfort_sessions:
        # Only a complete, tolerated, mild and stable localized report may be
        # isolated to one exercise. Legacy/incomplete reports fail safe.
        details = [s.get("discomfort_details") for s in discomfort_sessions]
        localized = all(
            isinstance(d, dict)
            and isinstance(d.get("exercise_id"), str)
            and isinstance(d.get("pain_during"), int)
            and not isinstance(d.get("pain_during"), bool)
            and 0 <= d["pain_during"] <= 4
            and d.get("worsened") is False
            and d.get("tolerated") is True
            and d.get("acute_warning_signs") == []
            and {"reduced_load", "slow_tempo", "reduced_range"}.issubset(set(d.get("modifications_applied", [])))
            for d in details
        )
        if localized:
            return {
                "decision": "modify_symptomatic_exposure",
                "progression_allowed": False,
                "volume_change": "symptomatic_exercise_only",
                "reason_codes": ["mild_stable_localized_discomfort"],
                "affected_exercise_ids": sorted({d["exercise_id"] for d in details}),
                "message": (
                    "Blago, stabilno nelagodje je vezano na posamezno vajo. Pri tej vaji "
                    "ohrani konservativno prilagoditev; ostale vaje se presojajo ločeno. "
                    "Če se bolečina stopnjuje ali ni več sprejemljiva, vajo prekini."
                ),
            }
        return {
            "decision": "pause_and_review",
            "progression_allowed": False,
            "volume_change": "none_automatic",
            "reason_codes": ["discomfort_requires_review"],
            "message": (
                "Zabeleženo nelagodje nima popolne potrditve, da je blago, stabilno in "
                "sprejemljivo. Prizadeto vajo za zdaj prekini oziroma razjasni; ob akutnih, "
                "izrazitih ali slabšajočih se znakih poišči ustrezno strokovno oceno."
            ),
        }

    if recent and recent[0][1].get("completed") is not True:
        return {
            "decision": "review_volume_reduction",
            "progression_allowed": False,
            "volume_change": "reduce_next_program_sets",
            "reason_codes": ["session_not_completed"],
            "message": "Zadnji trening ni bil zaključen. Ob tvoji zahtevi bo naslednji program konservativno zmanjšal število serij; pred tem preveri razlog in regeneracijo.",
        }

    if recent and (recent[0][1].get("difficulty") == "hard" or recent[0][1].get("recovery") == "poor"):
        reasons = []
        if recent[0][1].get("difficulty") == "hard":
            reasons.append("last_session_hard")
        if recent[0][1].get("recovery") == "poor":
            reasons.append("poor_recovery")
        return {
            "decision": "review_volume_reduction",
            "progression_allowed": False,
            "volume_change": "reduce_next_program_sets",
            "reason_codes": reasons,
            "message": "Zadnji trening je bil ocenjen kot težek ali regeneracija ni bila ustrezna. Naslednji program bo ob tvoji zahtevi zmanjšal število serij; obremenitve ne povečuj.",
        }

    if len(recent) >= 2 and all(s.get("completed") is True for _, s in recent[:2]) and all(s.get("difficulty") == "easy" for _, s in recent[:2]) and all(s.get("recovery", "normal") != "poor" for _, s in recent[:2]):
        observations = [
            exercise
            for _, session in recent[:2]
            for exercise in session.get("exercises", [])
            if isinstance(exercise, dict)
        ]
        if observations and all(isinstance(x.get("rir"), int) and x["rir"] >= 3 for x in observations):
            return {
                "decision": "progression_candidate",
                "progression_allowed": True,
                "volume_change": "maintain",
                "reason_codes": ["two_easy_completed_sessions", "rir_at_least_3"],
                "message": (
                    "Dva zaporedna treninga sta bila lahka, zaključena in zabeleženi RIR je vsaj 3. "
                    "To je kandidat za ločeno odločitev o progresiji; tedenski obseg za zdaj ostane enak."
                ),
            }

    return {
        "decision": "maintain_and_monitor",
        "progression_allowed": False,
        "volume_change": "maintain",
        "reason_codes": ["insufficient_or_mixed_feedback"],
        "message": (
            "Podatki ne upravičujejo spremembe. Ohrani načrtovani obseg in zberi še povratne "
            "informacije o izvedbi, RIR, počutju in regeneraciji."
        ),
    }
