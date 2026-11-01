from training.adaptation import assess_next_step


def record(day, *, difficulty="moderate", completed=True, discomfort=None, rir=3):
    session = {
        "difficulty": difficulty,
        "completed": completed,
        "exercises": [{"exercise_id": "barbell_squat", "rir": rir}],
    }
    if discomfort is not None:
        session["discomfort_reported"] = discomfort
    return {"session_date": day, "session": session}


def test_discomfort_always_blocks_progression():
    result = assess_next_step([
        record("2026-11-01", difficulty="easy", discomfort=True),
        record("2026-10-29", difficulty="easy"),
    ])
    assert result["decision"] == "pause_and_review"
    assert result["progression_allowed"] is False
    assert result["volume_change"] == "none_automatic"


def test_incomplete_latest_session_requests_feedback():
    result = assess_next_step([
        record("2026-11-01", completed=False),
        record("2026-10-29", difficulty="easy"),
    ])
    assert result["decision"] == "collect_feedback"
    assert result["progression_allowed"] is False


def test_two_hard_sessions_trigger_volume_review_not_automatic_reduction():
    result = assess_next_step([
        record("2026-11-01", difficulty="hard"),
        record("2026-10-29", difficulty="hard"),
    ])
    assert result["decision"] == "review_volume_reduction"
    assert result["volume_change"] == "review_main_exercise_volume"
    assert result["progression_allowed"] is False


def test_two_easy_sessions_with_reserve_are_progression_candidate_only():
    result = assess_next_step([
        record("2026-11-01", difficulty="easy", rir=3),
        record("2026-10-29", difficulty="easy", rir=4),
    ])
    assert result["decision"] == "progression_candidate"
    assert result["progression_allowed"] is True
    assert result["volume_change"] == "maintain"


def test_mixed_or_insufficient_data_maintains_plan():
    result = assess_next_step([record("2026-11-01", difficulty="easy")])
    assert result["decision"] == "maintain_and_monitor"
    assert result["progression_allowed"] is False


def test_missing_rir_does_not_create_progression_candidate():
    result = assess_next_step([
        record("2026-11-01", difficulty="easy", rir=None),
        record("2026-10-29", difficulty="easy", rir=4),
    ])
    assert result["decision"] == "maintain_and_monitor"
