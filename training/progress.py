"""Conservative descriptive progress summaries from recorded ATENA sessions.

This module reports trends only. It does not diagnose, estimate 1RM, or prescribe
load increases. Missing data is treated as unknown, never as evidence of readiness.
"""
from collections import defaultdict
from datetime import date


def _session_parts(item):
    if not isinstance(item, dict):
        return None, {}
    session = item.get("session", {})
    if not isinstance(session, dict):
        session = {}
    try:
        session_date = date.fromisoformat(item.get("session_date", ""))
    except (TypeError, ValueError):
        session_date = None
    return session_date, session


def summarize_progress(profile_record, sessions):
    """Summarize up to 50 saved sessions into transparent, non-prescriptive trends."""
    profile = profile_record.get("profile", {}) if isinstance(profile_record, dict) else {}
    valid = []
    for item in sessions if isinstance(sessions, list) else []:
        session_date, session = _session_parts(item)
        if session_date is not None:
            valid.append((session_date, session))
    valid.sort(key=lambda pair: pair[0])

    completed = [(day, s) for day, s in valid if s.get("completed") is True]
    by_week = defaultdict(int)
    for day, _ in completed:
        year, week, _ = day.isocalendar()
        by_week[f"{year}-W{week:02d}"] += 1

    exercise_history = defaultdict(list)
    for day, session in completed:
        exercises = session.get("exercises", [])
        if not isinstance(exercises, list):
            continue
        for exercise in exercises:
            if not isinstance(exercise, dict) or not isinstance(exercise.get("exercise_id"), str):
                continue
            exercise_history[exercise["exercise_id"]].append({
                "date": day.isoformat(),
                "sets": exercise.get("sets_completed"),
                "reps": exercise.get("reps_completed"),
                "work_seconds": exercise.get("work_seconds_completed"),
                "load_kg": exercise.get("load_kg"),
                "rir": exercise.get("rir"),
            })

    trends = []
    for exercise_id, entries in sorted(exercise_history.items()):
        entries.sort(key=lambda entry: entry["date"])
        recent = entries[-3:]
        latest = recent[-1]
        previous = recent[-2] if len(recent) >= 2 else None
        status = "insufficient_data"
        if previous is not None:
            old_load, new_load = previous.get("load_kg"), latest.get("load_kg")
            old_reps, new_reps = previous.get("reps"), latest.get("reps")
            if old_load is not None and new_load is not None:
                if new_load > old_load:
                    status = "load_increased"
                elif new_load < old_load:
                    status = "load_reduced"
                elif new_reps is not None and old_reps is not None and new_reps > old_reps:
                    status = "repetitions_increased"
                else:
                    status = "stable"
            elif latest.get("work_seconds") is not None and previous.get("work_seconds") is not None:
                old_work, new_work = previous["work_seconds"], latest["work_seconds"]
                status = "work_duration_increased" if new_work > old_work else (
                    "stable" if new_work == old_work else "work_duration_reduced"
                )
            elif new_reps is not None and old_reps is not None:
                status = "repetitions_increased" if new_reps > old_reps else (
                    "stable" if new_reps == old_reps else "repetitions_reduced"
                )
        trends.append({
            "exercise_id": exercise_id,
            "status": status,
            "sessions_recorded": len(entries),
            "recent_observations": recent,
        })

    safety_flags = []
    if any(s.get("discomfort_reported") is True for _, s in completed):
        safety_flags.append("discomfort_reported")
    if completed and completed[-1][1].get("difficulty") == "hard":
        safety_flags.append("last_session_reported_hard")
    if not completed:
        overview = "no_completed_sessions"
    elif len(completed) < 3:
        overview = "building_baseline"
    else:
        overview = "history_available"

    return {
        "goal": profile.get("goal"),
        "sessions_recorded": len(valid),
        "completed_sessions": len(completed),
        "weekly_completed_sessions": [
            {"week": week, "count": count} for week, count in sorted(by_week.items())[-8:]
        ],
        "overview": overview,
        "caution_flags": safety_flags,
        "exercise_trends": trends,
        "interpretation": (
            "Prikaz opisuje zabeležene treninge. Za odločitev o napredovanju preveri še tehniko, "
            "počutje, regeneracijo in morebitne omejitve; sistem samodejno ne povečuje obremenitev."
        ),
    }
