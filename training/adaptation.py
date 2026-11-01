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

    if any(s.get("discomfort_reported") is True for _, s in recent):
        return {
            "decision": "pause_and_review",
            "progression_allowed": False,
            "volume_change": "none_automatic",
            "reason_codes": ["discomfort_reported"],
            "message": (
                "Zabeleženo je nelagodje. Samodejno napredovanje se ustavi; najprej preveri "
                "okoliščine, vrsto in trajanje težave. Ob vztrajni ali izraziti bolečini poišči "
                "ustrezno zdravstveno oceno."
            ),
        }

    if recent and recent[0][1].get("completed") is not True:
        return {
            "decision": "collect_feedback",
            "progression_allowed": False,
            "volume_change": "none_automatic",
            "reason_codes": ["session_not_completed"],
            "message": "Trening ni bil zaključen. Pred spremembo programa je treba ugotoviti razlog.",
        }

    hard_count = sum(1 for _, s in completed[:2] if s.get("difficulty") == "hard")
    if hard_count >= 2:
        return {
            "decision": "review_volume_reduction",
            "progression_allowed": False,
            "volume_change": "review_main_exercise_volume",
            "reason_codes": ["two_recent_hard_sessions"],
            "message": (
                "Dva zadnja zaključena treninga sta bila ocenjena kot težka. Predlagan je pregled "
                "obsega glavnih vaj in regeneracije; obremenitev se ne spremeni samodejno."
            ),
        }

    if len(recent) >= 2 and all(s.get("completed") is True for _, s in recent[:2]) and all(s.get("difficulty") == "easy" for _, s in recent[:2]):
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
