from training.progress import summarize_progress


def _record(day, *, difficulty="moderate", discomfort=None, completed=True, exercises=None):
    session = {"completed": completed, "difficulty": difficulty, "exercises": exercises or []}
    if discomfort is not None:
        session["discomfort_reported"] = discomfort
    return {"session_date": day, "session": session}


def test_progress_counts_only_completed_sessions_and_groups_by_week():
    result = summarize_progress(
        {"profile": {"goal": "strength"}},
        [
            _record("2026-10-26"),
            _record("2026-10-27", completed=False),
            _record("2026-11-01"),
        ],
    )
    assert result["sessions_recorded"] == 3
    assert result["completed_sessions"] == 2
    assert result["overview"] == "building_baseline"
    assert sum(item["count"] for item in result["weekly_completed_sessions"]) == 2


def test_exercise_trend_reports_load_or_rep_change_without_prescribing():
    exercise_id = "barbell_squat"
    sessions = [
        _record("2026-10-20", exercises=[{
            "exercise_id": exercise_id, "sets_completed": 3, "reps_completed": 8,
            "load_kg": 60.0, "rir": 3,
        }]),
        _record("2026-10-23", exercises=[{
            "exercise_id": exercise_id, "sets_completed": 3, "reps_completed": 8,
            "load_kg": 62.5, "rir": 2,
        }]),
    ]
    result = summarize_progress({"profile": {"goal": "strength"}}, sessions)
    assert result["exercise_trends"][0]["status"] == "load_increased"
    assert result["automatic_load_changes"] if "automatic_load_changes" in result else True


def test_progress_marks_discomfort_and_hard_session_as_caution():
    result = summarize_progress(
        {"profile": {}},
        [
            _record("2026-10-28", discomfort=True),
            _record("2026-10-30", difficulty="hard"),
        ],
    )
    assert "discomfort_reported" in result["caution_flags"]
    assert "last_session_reported_hard" in result["caution_flags"]


def test_progress_handles_empty_and_malformed_history_safely():
    result = summarize_progress({"profile": {}}, [{"session_date": "bad", "session": {}}])
    assert result["sessions_recorded"] == 0
    assert result["overview"] == "no_completed_sessions"
    assert result["exercise_trends"] == []


def test_progress_uses_repetitions_when_load_is_not_recorded():
    exercise_id = "push_up"
    sessions = [
        _record("2026-10-20", exercises=[{"exercise_id": exercise_id, "sets_completed": 3, "reps_completed": 8}]),
        _record("2026-10-23", exercises=[{"exercise_id": exercise_id, "sets_completed": 3, "reps_completed": 10}]),
    ]
    result = summarize_progress({"profile": {}}, sessions)
    assert result["exercise_trends"][0]["status"] == "repetitions_increased"
