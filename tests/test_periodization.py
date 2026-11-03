from training.periodization import summarize_training_cycle


PROFILE = {"sessions_per_week": 2}


def _session(day, *, completed=True, difficulty="moderate", recovery="good", discomfort=False):
    return {
        "session_date": day,
        "session": {
            "completed": completed,
            "difficulty": difficulty,
            "recovery": recovery,
            "discomfort_reported": discomfort,
            "exercises": [],
        },
    }


def _history(count, **last_overrides):
    days = [
        "2026-10-01", "2026-10-03", "2026-10-08", "2026-10-10",
        "2026-10-15", "2026-10-17", "2026-10-22", "2026-10-24",
        "2026-10-29", "2026-10-31",
    ]
    records = [_session(day) for day in days[:count]]
    if records and last_overrides:
        records[-1] = _session(days[count - 1], **last_overrides)
    return records


def test_no_history_waits_for_first_session():
    result = summarize_training_cycle(PROFILE, [])
    assert result["phase"] == "baseline_setup"
    assert result["cycle_week"] == 0
    assert result["automatic_program_changes"] is False


def test_first_training_week_establishes_repeatable_baseline():
    result = summarize_training_cycle(PROFILE, _history(2))
    assert result["cycle_week"] == 1
    assert result["phase"] == "baseline"


def test_second_week_builds_consistency_without_global_progression():
    result = summarize_training_cycle(PROFILE, _history(4))
    assert result["cycle_week"] == 2
    assert result["phase"] == "accumulation"
    assert result["progression_scope"] == "exercise_specific_only"


def test_third_week_only_allows_exercise_specific_progression_candidates():
    candidates = [{"decision": "increase_load", "exercise_id": "squat_goblet"}]
    result = summarize_training_cycle(PROFILE, _history(5), exercise_progressions=candidates)
    assert result["cycle_week"] == 3
    assert result["status"] == "individual_progression_candidates"
    assert result["progression_scope"] == "exercise_specific_only"


def test_third_week_collects_more_evidence_when_no_exercise_is_eligible():
    result = summarize_training_cycle(PROFILE, _history(6), exercise_progressions=[])
    assert result["phase"] == "progression_review"
    assert result["status"] == "collect_more_evidence"


def test_fourth_week_is_consolidation_not_an_automatic_deload():
    result = summarize_training_cycle(PROFILE, _history(8))
    assert result["cycle_week"] == 4
    assert result["phase"] == "consolidation"
    assert result["automatic_program_changes"] is False


def test_cycle_advances_only_after_completed_session_target_is_met():
    result = summarize_training_cycle(PROFILE, _history(9))
    assert result["cycle_number"] == 2
    assert result["cycle_week"] == 1


def test_recent_hard_session_or_poor_recovery_overrides_cycle_phase():
    result = summarize_training_cycle(
        PROFILE, _history(5, difficulty="hard"), exercise_progressions=[{"decision": "increase_load"}]
    )
    assert result["phase"] == "recovery_review"
    assert result["progression_scope"] == "hold_progression"


def test_recent_discomfort_holds_all_progression():
    result = summarize_training_cycle(PROFILE, _history(8, discomfort=True))
    assert result["phase"] == "pause_and_review"
    assert result["progression_scope"] == "hold_all_progression"


def test_declining_or_unconfirmed_exercise_trend_blocks_global_cycle_progression():
    result = summarize_training_cycle(
        PROFILE,
        _history(5),
        exercise_progressions=[{"decision": "increase_load"}],
        longitudinal_progression={"exercise_trends": [{"status": "quality_unconfirmed"}]},
    )
    assert result["phase"] == "individual_review"
    assert result["progression_scope"] == "individual_review_only"


def test_conditioning_recovery_watch_blocks_cycle_progression():
    result = summarize_training_cycle(
        PROFILE,
        _history(5),
        exercise_progressions=[{"decision": "increase_load"}],
        conditioning_progression={"conditioning_trends": [{"status": "recovery_watch"}]},
    )
    assert result["phase"] == "individual_review"


def test_duplicate_same_day_sessions_do_not_advance_cycle():
    records = _history(4)
    records.append(_session("2026-10-10"))
    result = summarize_training_cycle(PROFILE, records)
    assert result["completed_sessions_used"] == 4
    assert result["cycle_week"] == 2


def test_profile_frequency_controls_number_of_sessions_per_cycle_week():
    result = summarize_training_cycle(
        {"sessions_per_week": 3}, _history(6)
    )
    assert result["cycle_week"] == 2
    assert result["sessions_per_week_target"] == 3


def test_duplicate_same_day_periodization_uses_newest_first_record():
    records = [
        _session("2026-10-17", difficulty="hard", recovery="good"),
        _session("2026-10-17", difficulty="easy", recovery="good"),
        _session("2026-10-15"),
    ]
    result = summarize_training_cycle(PROFILE, records)
    assert result["completed_sessions_used"] == 2
    assert result["phase"] == "recovery_review"
