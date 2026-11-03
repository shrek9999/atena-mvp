from training.longitudinal_response import summarize_longitudinal_response


def _record(day, *, completed=True, recovery="good", difficulty="moderate",
            quality="controlled", discomfort=False, exercise_id="goblet_squat"):
    return {
        "session_date": day,
        "session": {
            "completed": completed,
            "recovery": recovery,
            "difficulty": difficulty,
            "discomfort_reported": discomfort,
            "exercises": [{
                "exercise_id": exercise_id,
                "execution_quality": quality,
            }],
        },
    }


def test_fewer_than_three_unique_days_builds_baseline():
    result = summarize_longitudinal_response([
        _record("2026-11-02"),
        _record("2026-11-01"),
    ])
    assert result["status"] == "building_baseline"
    assert result["automatic_program_changes"] is False


def test_duplicate_same_day_records_count_once_and_keep_newest_first():
    result = summarize_longitudinal_response([
        _record("2026-11-03", completed=False),
        _record("2026-11-03", completed=True),
        _record("2026-11-02"),
        _record("2026-11-01"),
    ])
    assert result["window_size"] == 3
    assert result["counts"]["incomplete"] == 1


def test_single_poor_recovery_day_is_not_labeled_a_longitudinal_pattern():
    result = summarize_longitudinal_response([
        _record("2026-11-03", recovery="poor"),
        _record("2026-11-02"),
        _record("2026-11-01"),
    ])
    assert result["status"] == "no_repeated_concern_detected"


def test_repeated_poor_recovery_triggers_review_without_deload():
    result = summarize_longitudinal_response([
        _record("2026-11-03", recovery="poor"),
        _record("2026-11-02"),
        _record("2026-11-01", recovery="poor"),
    ])
    assert result["status"] == "pattern_review"
    assert "recurring_poor_recovery" in [item["code"] for item in result["signals"]]
    assert result["review"] == "review_recovery_and_training_dose"
    assert result["automatic_program_changes"] is False


def test_technique_pattern_requires_same_exercise_on_two_distinct_days():
    result = summarize_longitudinal_response([
        _record("2026-11-03", quality="needs_attention"),
        _record("2026-11-02"),
        _record("2026-11-01", quality="needs_attention"),
    ])
    assert result["status"] == "pattern_review"
    signal = next(item for item in result["signals"] if item["code"] == "recurring_technique_concern")
    assert signal["exercise_ids"] == ["goblet_squat"]


def test_different_technique_concerns_on_different_exercises_are_not_merged():
    result = summarize_longitudinal_response([
        _record("2026-11-03", quality="needs_attention", exercise_id="goblet_squat"),
        _record("2026-11-02"),
        _record("2026-11-01", quality="needs_attention", exercise_id="push_up"),
    ])
    assert result["status"] == "no_repeated_concern_detected"


def test_repeated_incomplete_sessions_ask_for_context_not_motivation_judgment():
    result = summarize_longitudinal_response([
        _record("2026-11-03", completed=False),
        _record("2026-11-02"),
        _record("2026-11-01", completed=False),
    ])
    assert result["status"] == "pattern_review"
    signal = next(item for item in result["signals"] if item["code"] == "repeated_incomplete_sessions")
    assert "ne pomeni pomanjkanja motivacije" in signal["message"]
    assert "pomanjkanje časa" in signal["question"]


def test_symptom_review_has_priority_over_other_longitudinal_signals():
    result = summarize_longitudinal_response([
        _record("2026-11-03", discomfort=True, completed=False, recovery="poor", quality="needs_attention"),
        _record("2026-11-02", completed=False, recovery="poor", quality="needs_attention"),
        _record("2026-11-01", completed=False),
    ])
    assert result["review"] == "pause_and_review"
    assert result["signals"][0]["code"] == "symptom_review"
    assert len(result["signals"]) >= 3


def test_hard_training_alone_is_not_mistaken_for_poor_recovery():
    result = summarize_longitudinal_response([
        _record("2026-11-03", difficulty="hard"),
        _record("2026-11-02", difficulty="hard"),
        _record("2026-11-01", difficulty="hard"),
    ])
    assert result["status"] == "no_repeated_concern_detected"
    assert result["counts"]["hard"] == 3
