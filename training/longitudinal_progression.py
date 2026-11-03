"""Longitudinal, exercise-specific training trend signals.

This module describes patterns across several weeks. It never changes a
prescription, diagnoses a plateau, or triggers an automatic deload.
Only complete, comparable, set-by-set resistance-training records are used.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date


WINDOW_SIZE = 5
MIN_WINDOW_DAYS = 21


def _session_rows(sessions):
    rows = []
    for item in sessions if isinstance(sessions, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("session"), dict):
            continue
        try:
            day = date.fromisoformat(item.get("session_date", ""))
        except (TypeError, ValueError):
            continue
        session = item["session"]
        if session.get("completed") is True:
            rows.append((day, session))
    return sorted(rows, key=lambda row: row[0])


def _observation(exercise, session, day):
    if not isinstance(exercise, dict) or not isinstance(exercise.get("exercise_id"), str):
        return None
    sets = exercise.get("set_results")
    observation = {
        "date": day.isoformat(),
        "exercise_id": exercise["exercise_id"],
        "complete": False,
        "difficulty": session.get("difficulty", "unknown"),
        "recovery": session.get("recovery", "unknown"),
        "execution_quality": exercise.get("execution_quality", "unknown"),
    }
    if not isinstance(sets, list) or not sets:
        return observation

    planned_sets = exercise.get("planned_sets")
    if planned_sets is not None and (not isinstance(planned_sets, int) or isinstance(planned_sets, bool) or len(sets) != planned_sets):
        return observation

    reps = []
    rir = []
    loads = []
    load_presence = []
    for item in sets:
        if not isinstance(item, dict):
            return observation
        rep = item.get("reps")
        reserve = item.get("rir")
        load = item.get("load_kg")
        if rep is None and isinstance(item.get("work_seconds"), int):
            observation["supported"] = False
            return observation
        if not isinstance(rep, int) or isinstance(rep, bool) or rep < 1:
            return observation
        if not isinstance(reserve, int) or isinstance(reserve, bool) or not 0 <= reserve <= 10:
            return observation
        if load is not None and (
            not isinstance(load, (int, float)) or isinstance(load, bool) or load < 0
        ):
            return observation
        reps.append(rep)
        rir.append(reserve)
        load_presence.append(load is not None)
        if load is not None:
            loads.append(float(load))

    if any(load_presence) and not all(load_presence):
        return observation

    target_min = exercise.get("target_reps_min")
    target_max = exercise.get("target_reps_max")
    if (target_min is None) != (target_max is None):
        return observation
    if target_min is not None and (
        not isinstance(target_min, int) or isinstance(target_min, bool)
        or not isinstance(target_max, int) or isinstance(target_max, bool)
        or target_min < 1 or target_max < target_min
    ):
        return observation

    observation.update({
        "complete": True,
        "sets": len(sets),
        "total_reps": sum(reps),
        "minimum_rir": min(rir),
        "average_load_kg": round(sum(loads) / len(loads), 2) if loads else None,
        "target_reps_min": target_min,
        "target_reps_max": target_max,
    })
    return observation


def _same_programming_window(window):
    first = window[0]
    keys = ("sets", "target_reps_min", "target_reps_max")
    return all(
        all(item.get(key) == first.get(key) for key in keys)
        for item in window[1:]
    )


def summarize_longitudinal_progression(sessions):
    """Return conservative trend signals using the last five comparable exposures."""
    by_exercise = defaultdict(list)
    for day, session in _session_rows(sessions):
        exercises = session.get("exercises", [])
        if not isinstance(exercises, list):
            continue
        seen = set()
        for exercise in exercises:
            observation = _observation(exercise, session, day)
            if observation and observation["exercise_id"] not in seen:
                seen.add(observation["exercise_id"])
                by_exercise[observation["exercise_id"]].append(observation)

    results = []
    for exercise_id, observations in sorted(by_exercise.items()):
        window = observations[-WINDOW_SIZE:]
        result = {
            "exercise_id": exercise_id,
            "recorded_exposures": len(observations),
            "window_exposures": len(window),
            "window_start_date": window[0]["date"],
            "window_end_date": window[-1]["date"],
            "status": "building_baseline",
            "review": "continue_collecting",
            "automatic_program_changes": False,
        }

        if any(item.get("supported") is False for item in window):
            result.update({
                "status": "not_supported",
                "review": "use_modality_specific_assessment",
                "reason": "Časovne ali kondicijske naloge zahtevajo ločeno presojo intenzivnosti in odziva. Ta analiza je namenjena primerljivim serijam z uporom in ponovitvami.",
            })
            results.append(result)
            continue

        if not all(item["complete"] for item in window):
            result.update({
                "status": "incomplete_data",
                "review": "complete_set_by_set_logging",
                "reason": "V zadnjih zabeleženih izvedbah manjkajo popolni podatki za vse serije, ponovitve ali RIR. Trenda zato ne ocenjujem.",
            })
            results.append(result)
            continue

        if len(window) < WINDOW_SIZE:
            result["reason"] = "Za večtedensko presojo potrebujem pet popolnih, zabeleženih izvedb iste vaje."
            results.append(result)
            continue

        span_days = (date.fromisoformat(window[-1]["date"]) - date.fromisoformat(window[0]["date"])).days
        if span_days < MIN_WINDOW_DAYS:
            result["status"] = "building_baseline"
            result["reason"] = "Pet izvedb je zabeleženih v prekratkem obdobju za zanesljivo večtedensko presojo."
            results.append(result)
            continue

        if not _same_programming_window(window):
            result.update({
                "status": "not_comparable",
                "review": "stabilize_programming",
                "reason": "Število serij, ciljno območje ali obremenitev so se med izvedbami spreminjali. Pred presojo trenda je treba utrditi primerljiv odmerek.",
            })
            results.append(result)
            continue

        first, latest = window[0], window[-1]
        result["observations"] = [
            {
                "date": item["date"],
                "total_reps": item["total_reps"],
                "average_load_kg": item["average_load_kg"],
                "minimum_rir": item["minimum_rir"],
            }
            for item in window
        ]

        if any(item["recovery"] == "poor" or item["difficulty"] == "hard" for item in window[-2:]):
            result.update({
                "status": "recovery_watch",
                "review": "review_recovery_before_progression",
                "reason": "Ena od zadnjih dveh izvedb je bila povezana s slabo regeneracijo ali visoko zahtevnostjo. Pred nadaljnjo progresijo preveri regeneracijo in skupno obremenitev.",
            })
        elif latest["average_load_kg"] is not None and first["average_load_kg"] is not None and latest["average_load_kg"] > first["average_load_kg"] and latest["total_reps"] >= first["total_reps"]:
            result.update({
                "status": "improving",
                "review": "continue_current_progression",
                "reason": "V primerljivem obdobju se je povečala obremenitev, skupno število ponovitev pa se je ohranilo ali izboljšalo.",
            })
        elif latest["average_load_kg"] == first["average_load_kg"] and latest["total_reps"] > first["total_reps"] and latest["minimum_rir"] >= first["minimum_rir"] - 1:
            result.update({
                "status": "improving",
                "review": "continue_current_progression",
                "reason": "Pri enaki obremenitvi se je povečalo skupno število ponovitev, brez pomembnega poslabšanja rezerve.",
            })
        elif (
            all(item["average_load_kg"] == first["average_load_kg"] and item["total_reps"] == first["total_reps"] for item in window)
            and latest["minimum_rir"] >= first["minimum_rir"] - 1
        ):
            result.update({
                "status": "plateau_candidate",
                "review": "coach_review_required",
                "reason": "Pet primerljivih izvedb v najmanj treh tednih kaže enak rezultat. To je signal za strokovni pregled programa, ne samodejna diagnoza stagnacije ali ukaz za razbremenilni teden.",
            })
        elif latest["total_reps"] <= first["total_reps"] - 2 and latest["minimum_rir"] <= first["minimum_rir"] - 1:
            result.update({
                "status": "declining_performance",
                "review": "review_recovery_and_dose",
                "reason": "V primerljivem obdobju sta se zmanjšala skupno število ponovitev in rezerva. Preveri regeneracijo, tehniko, stres ter ustreznost trenutnega odmerka; ne povečuj obremenitve.",
            })
        else:
            result.update({
                "status": "mixed",
                "review": "coach_review_required",
                "reason": "Podatki ne kažejo dovolj enotnega trenda za samodejno odločitev. Potrebna je strokovna presoja konteksta.",
            })

        results.append(result)

    return {
        "method": "last_five_comparable_exposures",
        "minimum_window_days": MIN_WINDOW_DAYS,
        "automatic_program_changes": False,
        "exercise_trends": results,
        "interpretation": "Večtedenski trend je opisni signal iz zabeleženih izvedb. Ne nadomešča presoje tehnike, simptomov, regeneracije in ciljev posameznika.",
    }
