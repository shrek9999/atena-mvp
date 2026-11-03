"""Longitudinal response signals across recent logged training sessions.

This module describes repeated patterns in recorded sessions. It does not infer
missed scheduled workouts, diagnose fatigue, or change a training programme.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date


WINDOW_SIZE = 5
MIN_HISTORY = 3


def _recent_unique_sessions(sessions):
    """Return up to five latest unique training dates, newest date first.

    The storage API returns newest-created entries first for duplicate dates;
    preserve that first entry and never count same-day duplicates twice.
    """
    by_day = {}
    for item in sessions if isinstance(sessions, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("session"), dict):
            continue
        try:
            day = date.fromisoformat(item.get("session_date", ""))
        except (TypeError, ValueError):
            continue
        if day.isoformat() not in by_day:
            by_day[day.isoformat()] = (day, item["session"])
    return sorted(by_day.values(), key=lambda row: row[0], reverse=True)[:WINDOW_SIZE]


def summarize_longitudinal_response(sessions):
    """Summarize recovery, technique and session-completion patterns conservatively."""
    recent = _recent_unique_sessions(sessions)
    base = {
        "method": "last_five_unique_logged_sessions",
        "window_size": len(recent),
        "minimum_history": MIN_HISTORY,
        "automatic_program_changes": False,
        "signals": [],
    }
    if len(recent) < MIN_HISTORY:
        return {
            **base,
            "status": "building_baseline",
            "review": "continue_collecting",
            "counts": {
                "completed": sum(session.get("completed") is True for _, session in recent),
                "incomplete": sum(session.get("completed") is False for _, session in recent),
                "poor_recovery": sum(session.get("recovery") == "poor" for _, session in recent),
                "hard": sum(session.get("difficulty") == "hard" for _, session in recent),
            },
            "primary_question": "Zabeleživa še nekaj treningov, da lahko ločim posamezen slab dan od ponavljajočega se vzorca.",
            "reason": "Za dolgoročno presojo potrebujem vsaj tri različne zabeležene vadbene dni.",
        }

    counts = {
        "completed": sum(session.get("completed") is True for _, session in recent),
        "incomplete": sum(session.get("completed") is False for _, session in recent),
        "poor_recovery": sum(session.get("recovery") == "poor" for _, session in recent),
        "hard": sum(session.get("difficulty") == "hard" for _, session in recent),
    }
    technique_dates = defaultdict(set)
    symptom_dates = []
    for day, session in recent:
        if session.get("discomfort_reported") is True:
            symptom_dates.append(day.isoformat())
        exercises = session.get("exercises", [])
        if not isinstance(exercises, list):
            continue
        seen = set()
        for exercise in exercises:
            if (
                isinstance(exercise, dict)
                and exercise.get("execution_quality") == "needs_attention"
                and isinstance(exercise.get("exercise_id"), str)
                and exercise["exercise_id"] not in seen
            ):
                technique_dates[exercise["exercise_id"]].add(day.isoformat())
                seen.add(exercise["exercise_id"])

    signals = []
    if symptom_dates:
        signals.append({
            "code": "symptom_review",
            "priority": "safety",
            "review": "pause_and_review",
            "message": "V zgodovini je zabeleženo nelagodje. Pred progresijo preveri trenutno stanje.",
            "question": "Ali je nelagodje še prisotno, se je umirilo ali se je ponovilo?",
        })

    recurring_technique = sorted(
        exercise_id for exercise_id, days in technique_dates.items() if len(days) >= 2
    )
    if recurring_technique:
        signals.append({
            "code": "recurring_technique_concern",
            "priority": "movement_quality",
            "review": "coach_technique_review",
            "exercise_ids": recurring_technique,
            "message": "Pri isti vaji je bila v več različnih treningih označena slabša kakovost izvedbe.",
            "question": "Ali se težava pri tej vaji pojavi že od začetka ali šele ob utrujenosti oziroma proti koncu serij?",
        })

    if counts["poor_recovery"] >= 2:
        signals.append({
            "code": "recurring_poor_recovery",
            "priority": "recovery",
            "review": "review_recovery_and_training_dose",
            "message": "Slabša regeneracija je bila zabeležena pri več treningih v zadnjem obdobju.",
            "question": "Se slabša regeneracija pojavlja tudi med treningi ali predvsem po zahtevnejših vadbah?",
        })

    if counts["incomplete"] >= 2:
        signals.append({
            "code": "repeated_incomplete_sessions",
            "priority": "training_adherence_context",
            "review": "clarify_session_constraints",
            "message": "Več zabeleženih treningov ni bilo dokončanih. Sam zapis ne pove razloga in ne pomeni pomanjkanja motivacije.",
            "question": "Kaj najpogosteje prekine trening: pomanjkanje časa, utrujenost, zahtevnost, oprema ali kaj drugega?",
        })

    if signals:
        primary = signals[0]
        return {
            **base,
            "status": "pattern_review",
            "review": primary["review"],
            "counts": counts,
            "signals": signals,
            "primary_question": primary["question"],
            "reason": "Več zabeleženih odzivov kaže vzorec, ki ga je treba razjasniti pred spremembo odmerka. Nobena sprememba programa ni samodejna.",
        }

    return {
        **base,
        "status": "no_repeated_concern_detected",
        "review": "continue_monitoring",
        "counts": counts,
        "signals": [],
        "primary_question": "Kako se počutiš med treningi in med posameznimi vadbenimi dnevi?",
        "reason": "V zadnjih zabeleženih treningih ni dovolj ponavljajočih se opozorilnih signalov za poseben pregled. To ni dokaz, da težav ni.",
    }
