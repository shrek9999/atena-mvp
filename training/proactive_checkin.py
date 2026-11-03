"""Deterministic, privacy-conscious post-session check-ins for ATENA.

This module creates one useful follow-up question from already saved training
feedback. It does not call an AI model, store a reply, or make programme changes.
"""
from __future__ import annotations

from datetime import date


def _latest_session(sessions):
    by_day = {}
    for item in sessions if isinstance(sessions, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("session"), dict):
            continue
        try:
            day = date.fromisoformat(item.get("session_date", ""))
        except (TypeError, ValueError):
            continue
        by_day[day.isoformat()] = (day, item["session"])
    ordered = sorted(by_day.values(), key=lambda row: row[0], reverse=True)
    return ordered[0][1] if ordered else None


def build_proactive_checkin(sessions):
    """Return one prioritized follow-up question without requesting a long intake."""
    session = _latest_session(sessions)
    base = {
        "automatic_program_changes": False,
        "reply_saved": False,
        "model_call_required": False,
    }
    if session is None:
        return {
            **base,
            "status": "awaiting_first_session",
            "priority": "baseline",
            "question": "Kako je potekal tvoj prvi trening in kako si se počutil po njem?",
            "reason": "ATENA še nima zabeleženega treninga, na katerega bi se lahko oprla.",
        }

    if session.get("discomfort_reported") is True:
        return {
            **base,
            "status": "symptom_follow_up",
            "priority": "safety",
            "question": (
                "Ali se je nelagodje po treningu umirilo ali je še prisotno? "
                "ATENA zaradi tega ne bo samodejno povečevala obremenitve."
            ),
            "reason": (
                "Najprej je treba razjasniti trenutno stanje. Pri novem, izrazitem ali "
                "vztrajnem simptomu je potrebna strokovna presoja."
            ),
        }

    if session.get("completed") is not True:
        return {
            **base,
            "status": "incomplete_session",
            "priority": "training_dose",
            "question": (
                "Kaj je preprečilo zaključek treninga: premalo časa, previsoka zahtevnost, "
                "utrujenost ali kaj drugega?"
            ),
            "reason": "Razlog za nedokončan trening je pomemben pred odločitvijo o naslednjem odmerku.",
        }

    if session.get("recovery") == "poor":
        return {
            **base,
            "status": "poor_recovery",
            "priority": "recovery",
            "question": (
                "Kaj je najbolj vplivalo na slabšo regeneracijo: zahtevnost treninga, "
                "premalo počitka ali druge okoliščine?"
            ),
            "reason": "Pred nadaljnjo progresijo je treba razumeti signal regeneracije.",
        }

    if session.get("difficulty") == "hard":
        return {
            **base,
            "status": "hard_session",
            "priority": "training_dose",
            "question": "Kateri del treninga je bil najzahtevnejši in zakaj?",
            "reason": "Skupna ocena težavnosti sama ne pove, kateri del odmerka je bil prevelik.",
        }

    exercises = session.get("exercises", [])
    if not isinstance(exercises, list):
        exercises = []
    technique_items = [
        item for item in exercises
        if isinstance(item, dict) and item.get("execution_quality") == "needs_attention"
    ]
    if technique_items:
        return {
            **base,
            "status": "technique_follow_up",
            "priority": "movement_quality",
            "question": (
                "Pri kateri vaji se je tehnika ali nadzor najbolj poslabšal? "
                "Ne poskušaj skozi utrujenost izsiliti ponovitev."
            ),
            "reason": "Najprej preveri kakovost izvedbe, šele nato presojaj progresijo.",
        }

    missing_rir = []
    for item in exercises:
        if not isinstance(item, dict):
            continue
        sets = item.get("set_results")
        if isinstance(sets, list) and sets and any(
            not isinstance(row, dict) or not isinstance(row.get("rir"), int)
            or isinstance(row.get("rir"), bool)
            for row in sets
        ):
            missing_rir.append(item.get("exercise_id", "vaji"))
    if missing_rir:
        return {
            **base,
            "status": "missing_effort_feedback",
            "priority": "data_quality",
            "question": (
                "Pri kateri vaji je bilo najtežje oceniti rezervo ponovitev (RIR)? "
                "Če ocene ne poznaš, je ne ugibaj."
            ),
            "reason": "Zanesljiv RIR pomaga presoditi odmerek; neznana vrednost mora ostati neznana.",
        }

    return {
        **base,
        "status": "standard_follow_up",
        "priority": "reflection",
        "question": (
            "Kaj je šlo pri zadnjem treningu najbolje in ali je bila katera vaja "
            "prelahka ali pretežka?"
        ),
        "reason": "Kratka povratna informacija pomaga izbrati naslednji smiseln korak.",
    }
