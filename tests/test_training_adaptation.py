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


def test_incomplete_latest_session_triggers_conservative_volume_review():
    result = assess_next_step([
        record("2026-11-01", completed=False),
        record("2026-10-29", difficulty="easy"),
    ])
    assert result["decision"] == "review_volume_reduction"
    assert result["volume_change"] == "reduce_next_program_sets"
    assert result["progression_allowed"] is False


def test_hard_session_triggers_next_program_volume_reduction():
    result = assess_next_step([
        record("2026-11-01", difficulty="hard"),
        record("2026-10-29", difficulty="hard"),
    ])
    assert result["decision"] == "review_volume_reduction"
    assert result["volume_change"] == "reduce_next_program_sets"
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


def test_mild_stable_tolerated_localized_discomfort_is_scoped_to_one_exercise():
    session = record("2026-11-01", difficulty="easy", discomfort=True)
    session["session"]["discomfort_details"] = {
        "exercise_id": "barbell_squat",
        "pain_during": 3,
        "worsened": False,
        "tolerated": True,
        "acute_warning_signs": [],
        "modifications_applied": ["reduced_load", "slow_tempo", "range_within_tolerance"],
    }
    result = assess_next_step([session, record("2026-10-29", difficulty="easy")])
    assert result["decision"] == "modify_symptomatic_exposure"
    assert result["volume_change"] == "symptomatic_exercise_only"
    assert result["affected_exercise_ids"] == ["barbell_squat"]


def test_worsening_or_untolerated_discomfort_keeps_review_gate():
    session = record("2026-11-01", discomfort=True)
    session["session"]["discomfort_details"] = {
        "exercise_id": "barbell_squat",
        "pain_during": 3,
        "worsened": True,
        "tolerated": False,
        "acute_warning_signs": [],
        "modifications_applied": ["reduced_load"],
    }
    result = assess_next_step([session])
    assert result["decision"] == "stop_symptomatic_exposure"
    assert result["affected_exercise_ids"] == ["barbell_squat"]
    assert result["progression_allowed"] is False


def test_acute_or_untolerated_complete_symptom_report_is_localized_to_one_exercise():
    session = record("2026-11-02", difficulty="easy", discomfort=True)
    session["session"]["discomfort_details"] = {
        "exercise_id": "barbell_squat",
        "pain_during": 6,
        "worsened": True,
        "tolerated": False,
        "acute_warning_signs": ["acute_sharp_pain"],
        "modifications_applied": [],
    }
    result = assess_next_step([session])
    assert result["decision"] == "stop_symptomatic_exposure"
    assert result["affected_exercise_ids"] == ["barbell_squat"]
    assert result["volume_change"] == "symptomatic_exercise_only"
