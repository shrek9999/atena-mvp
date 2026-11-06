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

    if recent and recent[0][1].get("completed") is None:
        return {
            "decision": "collect_context",
            "progression_allowed": False,
            "volume_change": "maintain",
            "reason_codes": ["completion_status_unknown"],
            "message": "Manjka podatek, ali je bil trening zaključen. Ne sklepaj o nedokončani vadbi ali zmanjšanju odmerka; najprej dopolni zapis.",
        }

    if recent and recent[0][1].get("recovery") == "poor":
        return {
            "decision": "recovery_review",
            "progression_allowed": False,
            "volume_change": "maintain",
            "reason_codes": ["poor_recovery"],
            "message": "Regeneracija je bila slabša. Pred spremembo odmerka preveri spanec, stres, razmik med vadbami in ali je šlo za osamljen odziv.",
        }

    if recent and recent[0][1].get("completed") is False:
        reason = recent[0][1].get("completion_reason", "unknown")
        if reason == "time_constraint":
            decision, volume, code, message = (
                "maintain_and_reschedule", "maintain", "time_constraint",
                "Trening je bil prekinjen zaradi pomanjkanja časa. To ni dokaz previsokega odmerka; ohrani ključne vaje in ne nadomeščaj izpuščenega obsega.",
            )
        elif reason == "external_interruption":
            decision, volume, code, message = (
                "maintain_and_reschedule", "maintain", "external_interruption",
                "Trening je prekinila zunanja okoliščina. Program ostane nespremenjen; nadaljuj po načrtu.",
            )
        elif reason == "high_difficulty":
            decision, volume, code, message = (
                "review_session_dose", "maintain", "incomplete_due_to_high_difficulty",
                "Trening je bil prekinjen zaradi previsoke zahtevnosti. Najprej ugotovi, katera vaja ali del treninga je bil problem; ne zmanjšuj samodejno celotnega programa.",
            )
        else:
            decision, volume, code, message = (
                "collect_context", "maintain", "incomplete_reason_unknown",
                "Trening ni bil zaključen, vendar razlog ni znan. Pred spremembo programa je treba razjasniti, kaj se je zgodilo.",
            )
        return {
            "decision": decision,
            "progression_allowed": False,
            "volume_change": volume,
            "reason_codes": [code],
            "message": message,
        }

    if recent and recent[0][1].get("difficulty") == "hard":
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
