"""Evidence-gated four-week training-cycle guidance.

The module reports a suggested phase from completed sessions and recent feedback.
It never edits a programme, assigns a physiological training zone, or diagnoses
fatigue. The cycle advances by completed sessions rather than calendar time.
"""
from __future__ import annotations

from datetime import date


CYCLE_WEEKS = 4


def _completed_sessions(sessions):
    by_day = {}
    for item in sessions if isinstance(sessions, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("session"), dict):
            continue
        try:
            day = date.fromisoformat(item.get("session_date", ""))
        except (TypeError, ValueError):
            continue
        session = item["session"]
        if session.get("completed") is True:
            # At most one completed training exposure per calendar day.
            by_day[day.isoformat()] = (day, session)
    return [value for _, value in sorted(by_day.items())]


def summarize_training_cycle(profile, sessions, exercise_progressions=None,
                             longitudinal_progression=None,
                             conditioning_progression=None):
    """Return a four-week review framework without automatic programme changes."""
    profile = profile if isinstance(profile, dict) else {}
    frequency = profile.get("sessions_per_week", 2)
    if not isinstance(frequency, int) or isinstance(frequency, bool) or frequency not in {2, 3, 4}:
        frequency = 2

    completed = _completed_sessions(sessions)
    count = len(completed)
    base = {
        "cycle_length_weeks": CYCLE_WEEKS,
        "sessions_per_week_target": frequency,
        "completed_sessions_used": count,
        "automatic_program_changes": False,
    }
    if count == 0:
        return {
            **base,
            "cycle_number": 1,
            "cycle_week": 0,
            "phase": "baseline_setup",
            "status": "awaiting_first_session",
            "recommendation": (
                "Najprej zabeleži prve izvedbe. Začetni odmerek naj bo ponovljiv in "
                "prilagojen izkušnjam, opremi ter trenutnim zmožnostim."
            ),
            "progression_scope": "none",
        }

    # The block advances only after the target number of completed sessions,
    # so a missed week does not silently push the person into a harder phase.
    sessions_per_cycle = frequency * CYCLE_WEEKS
    cycle_number = ((count - 1) // sessions_per_cycle) + 1
    cycle_week = (((count - 1) % sessions_per_cycle) // frequency) + 1
    recent = completed[-3:]
    last_two = completed[-2:]

    if any(session.get("discomfort_reported") is True for _, session in recent):
        phase = "pause_and_review"
        status = "symptom_review"
        recommendation = (
            "Zabeleženo je nelagodje. Pred nadaljnjo progresijo preveri okoliščine in "
            "ustreznost vadbe; ob novih, izrazitih ali vztrajnih simptomih poišči strokovno presojo."
        )
        scope = "hold_all_progression"
    elif any(
        session.get("difficulty") == "hard" or session.get("recovery") == "poor"
        for _, session in last_two
    ):
        phase = "recovery_review"
        status = "recovery_priority"
        recommendation = (
            "Zadnji treningi kažejo visoko zahtevnost ali slabšo regeneracijo. Pred "
            "nadaljevanjem bloka preveri spanje, stres, skupno tedensko obremenitev in "
            "število delovnih serij. Razbremenitev je možnost za strokovni pregled, ne samodejni ukaz."
        )
        scope = "hold_progression"
    else:
        progressions = exercise_progressions if isinstance(exercise_progressions, list) else []
        longitudinal = (
            longitudinal_progression.get("exercise_trends", [])
            if isinstance(longitudinal_progression, dict) else []
        )
        conditioning = (
            conditioning_progression.get("conditioning_trends", [])
            if isinstance(conditioning_progression, dict) else []
        )
        blocked = any(
            item.get("decision") in {"pause_and_review", "technique_review", "reduce_dose"}
            for item in progressions if isinstance(item, dict)
        ) or any(
            item.get("status") in {"technique_review", "quality_unconfirmed", "declining_performance"}
            for item in longitudinal if isinstance(item, dict)
        ) or any(
            item.get("status") in {"symptom_review", "recovery_watch", "performance_watch"}
            for item in conditioning if isinstance(item, dict)
        )
        if blocked:
            phase = "individual_review"
            status = "mixed_or_blocked_signals"
            recommendation = (
                "Odziv posameznih vaj ali kondicijskih protokolov ni enoznačen. "
                "Ne spreminjaj celotnega tedenskega odmerka; najprej preglej označene vaje in protokole."
            )
            scope = "individual_review_only"
        elif cycle_week == 1:
            phase = "baseline"
            status = "establish_repeatable_dose"
            recommendation = (
                "Utrdi začetni odmerek in kakovost izvedbe. Zberi primerljive podatke; "
                "ne lovi hitrega povečanja obremenitve."
            )
            scope = "maintain"
        elif cycle_week == 2:
            phase = "accumulation"
            status = "build_consistency"
            recommendation = (
                "Ohrani osnovno strukturo in postopno gradi ponovljivost. Progresijo "
                "presojaj ločeno za vsako vajo, ne za celoten program."
            )
            scope = "exercise_specific_only"
        elif cycle_week == 3:
            eligible = [
                item for item in progressions
                if isinstance(item, dict) and item.get("decision") in {"add_repetitions", "increase_load", "progress_variation"}
            ]
            phase = "progression_review"
            status = "individual_progression_candidates" if eligible else "collect_more_evidence"
            recommendation = (
                "Preglej samo vaje, pri katerih je ločeni sistem potrdil kandidaturo za majhen korak. "
                "Spremeni eno spremenljivko naenkrat; ostale vaje ohrani."
                if eligible else
                "Za večino vaj še ni dovolj dokazov za progresijo. Ohrani odmerek in zberi "
                "še primerljive podatke o ponovitvah, obremenitvi, RIR in kakovosti izvedbe."
            )
            scope = "exercise_specific_only"
        else:
            phase = "consolidation"
            status = "consolidate_and_review"
            recommendation = (
                "Utrdi doseženo zmogljivost. Ohrani kakovost in preveri odziv na dosedanji "
                "odmerek; razbremenitev izberi le, če jo utemeljujejo regeneracija in trendi."
            )
            scope = "coach_review"
    return {
        **base,
        "cycle_number": cycle_number,
        "cycle_week": cycle_week,
        "phase": phase,
        "status": status,
        "recommendation": recommendation,
        "progression_scope": scope,
        "automatic_program_changes": False,
        "interpretation": (
            "Štiritedenski okvir je organizacijski pripomoček, ne tog koledar. Napreduje "
            "po zaključenih vadbah, upošteva izpuščene treninge in ne nadomešča presoje "
            "tehnike, regeneracije, simptomov ter individualnega odziva."
        ),
    }
