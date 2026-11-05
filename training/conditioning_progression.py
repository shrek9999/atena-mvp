"""Conservative conditioning trend signals, separate from resistance progression.

This module reports descriptive patterns only. It never changes a prescription,
infers physiological thresholds, or diagnoses overtraining.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

WINDOW_SIZE = 5
MIN_WINDOW_DAYS = 21
MODALITIES = {"aerobic_base", "threshold_intervals", "vo2max_intervals", "metcon"}


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


def _valid_number(value, minimum, maximum, *, integer=False):
    if integer:
        return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum
    return isinstance(value, (int, float)) and not isinstance(value, bool) and minimum <= value <= maximum


def _observation(block, session, day):
    if not isinstance(block, dict):
        return None
    modality = block.get("modality")
    protocol_id = block.get("protocol_id")
    if modality not in MODALITIES or not isinstance(protocol_id, str) or not protocol_id.strip() or len(protocol_id) > 80:
        return None

    values = {
        "work_seconds": (block.get("work_seconds"), 1, 14400),
        "duration_seconds": (block.get("duration_seconds"), 1, 21600),
        "rpe": (block.get("rpe"), 1, 10),
    }
    for key, (value, low, high) in values.items():
        if not _valid_number(value, low, high, integer=(key != "rpe")):
            return None

    intervals = block.get("intervals_completed", 1)
    if not _valid_number(intervals, 1, 100, integer=True):
        return None
    distance = block.get("distance_m")
    if distance is not None and not _valid_number(distance, 1, 100000, integer=False):
        return None
    heart_rate = block.get("average_heart_rate")
    if heart_rate is not None and not _valid_number(heart_rate, 30, 240, integer=True):
        return None

    return {
        "date": day.isoformat(),
        "modality": modality,
        "protocol_id": protocol_id.strip(),
        "work_seconds": values["work_seconds"][0],
        "duration_seconds": values["duration_seconds"][0],
        "intervals_completed": intervals,
        "rpe": float(values["rpe"][0]),
        "distance_m": float(distance) if distance is not None else None,
        "average_heart_rate": heart_rate,
        "recovery": session.get("recovery", "unknown"),
        "difficulty": session.get("difficulty", "unknown"),
        "discomfort_reported": session.get("discomfort_reported") is True,
    }


def summarize_conditioning_progress(sessions):
    """Summarize five comparable conditioning blocks across at least three weeks."""
    by_protocol = defaultdict(list)
    seen = set()
    for day, session in _session_rows(sessions):
        blocks = session.get("conditioning", [])
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            observation = _observation(block, session, day)
            if observation is None:
                continue
            key = (observation["protocol_id"], day.isoformat())
            if key in seen:
                continue
            seen.add(key)
            by_protocol[observation["protocol_id"]].append(observation)

    trends = []
    for protocol_id, observations in sorted(by_protocol.items()):
        window = observations[-WINDOW_SIZE:]
        first = window[0]
        result = {
            "protocol_id": protocol_id,
            "modality": first["modality"],
            "recorded_exposures": len(observations),
            "window_exposures": len(window),
            "window_start_date": first["date"],
            "window_end_date": window[-1]["date"],
            "status": "building_baseline",
            "review": "continue_collecting",
            "automatic_program_changes": False,
        }
        if any(item["modality"] != first["modality"] for item in window):
            result.update(status="not_comparable", review="stabilize_protocol")
            result["reason"] = "Vrsta kondicijskega dražljaja se je spremenila; primerjaj samo enako modaliteto."
            trends.append(result)
            continue
        if len(window) < WINDOW_SIZE:
            result["reason"] = "Za večtedensko presojo potrebujem pet zabeleženih izvedb istega protokola."
            trends.append(result)
            continue
        span = (date.fromisoformat(window[-1]["date"]) - date.fromisoformat(first["date"])).days
        if span < MIN_WINDOW_DAYS:
            result["reason"] = "Pet izvedb je zabeleženih v prekratkem obdobju za zanesljivo večtedensko presojo."
            trends.append(result)
            continue

        # The same protocol identifier must represent the same intended dose.
        # A changed work/rest structure or interval count is not directly comparable.
        if any(
            item["protocol_id"] != first["protocol_id"]
            or item["intervals_completed"] != first["intervals_completed"]
            for item in window
        ):
            result.update(status="not_comparable", review="stabilize_protocol")
            result["reason"] = "Protokol ali število intervalov se je spremenilo; trend zato ni neposredno primerljiv."
            trends.append(result)
            continue

        result["observations"] = [
            {
                "date": item["date"],
                "work_seconds": item["work_seconds"],
                "duration_seconds": item["duration_seconds"],
                "intervals_completed": item["intervals_completed"],
                "rpe": item["rpe"],
                "distance_m": item["distance_m"],
                "average_heart_rate": item["average_heart_rate"],
            }
            for item in window
        ]

        if any(item["discomfort_reported"] for item in window[-2:]):
            result.update(status="symptom_review", review="pause_progression_and_review")
            result["reason"] = "V eni od zadnjih dveh izvedb je bilo zabeleženo nelagodje. Pred nadaljnjo progresijo je potrebna individualna presoja."
        elif any(item["recovery"] == "poor" or item["difficulty"] == "hard" for item in window[-2:]):
            result.update(status="recovery_watch", review="review_recovery_before_progression")
            result["reason"] = "Ena od zadnjih dveh izvedb je bila povezana s slabo regeneracijo ali visoko zahtevnostjo. Pred progresijo preveri skupno obremenitev in regeneracijo."
        else:
            latest = window[-1]
            metric = "distance_m" if all(item["distance_m"] is not None for item in window) else "work_seconds"
            start_value = first[metric]
            latest_value = latest[metric]
            if latest_value > start_value and latest["rpe"] <= first["rpe"] + 0.5:
                result.update(status="improving", review="continue_current_dose")
                result["reason"] = "Pri primerljivem protokolu se je povečala opravljena količina brez pomembnega povečanja zaznanega napora."
            elif latest_value == start_value and latest["rpe"] < first["rpe"]:
                result.update(status="improving", review="continue_current_dose")
                result["reason"] = "Pri primerljivi količini je bil zaznani napor manjši."
            elif latest_value < start_value and latest["rpe"] > first["rpe"] + 1:
                result.update(status="performance_watch", review="review_recovery_and_context")
                result["reason"] = "Pri primerljivem protokolu se je zmanjšala opravljena količina, zaznani napor pa se je povečal. Preveri regeneracijo in okoliščine."
            elif all(item[metric] == start_value and item["rpe"] == first["rpe"] for item in window):
                result.update(status="stable", review="coach_review_required")
                result["reason"] = "Rezultat je bil v petih primerljivih izvedbah stabilen. To ni samodejna diagnoza stagnacije."
            else:
                result.update(status="mixed", review="coach_review_required")
                result["reason"] = "Podatki ne kažejo dovolj enotnega trenda za zanesljiv sklep."

        trends.append(result)

    return {
        "method": "last_five_comparable_conditioning_exposures",
        "minimum_window_days": MIN_WINDOW_DAYS,
        "automatic_program_changes": False,
        "conditioning_trends": trends,
        "interpretation": (
            "Kondicijski trendi so opisni signali. Srčni utrip, tempo in razdalja so odvisni "
            "od modalitete, okolja in merilne naprave; brez individualnega konteksta ne določajo "
            "pragov ali območij intenzivnosti."
        ),
    }
