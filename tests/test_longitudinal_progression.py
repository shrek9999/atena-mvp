from training.longitudinal_progression import summarize_longitudinal_progression


def _record(day, *, reps=(10, 10, 10), load=20, rir=(4, 4, 3),
            quality="controlled", target=(8, 12), recovery="good",
            difficulty="moderate", completed=True, sets=3):
    results = []
    for index, rep in enumerate(reps):
        row = {"reps": rep, "rir": rir[index]}
        if load is not None:
            row["load_kg"] = load
        results.append(row)
    exercise = {
        "exercise_id": "squat_goblet",
        "planned_sets": sets,
        "target_reps_min": target[0],
        "target_reps_max": target[1],
        "execution_quality": quality,
        "set_results": results,
    }
    return {
        "session_date": day,
        "session": {
            "completed": completed,
            "difficulty": difficulty,
            "recovery": recovery,
            "exercises": [exercise],
        },
    }


def _five(**overrides):
    defaults = [
        ("2026-10-01", {}),
        ("2026-10-08", {}),
        ("2026-10-15", {}),
        ("2026-10-22", {}),
        ("2026-10-29", {}),
    ]
    records = []
    for day, values in defaults:
        values.update(overrides.get(day, {}))
        records.append(_record(day, **values))
    return records


def _trend(records):
    result = summarize_longitudinal_progression(records)
    return result["exercise_trends"][0]


def test_five_comparable_exposures_over_three_weeks_flag_plateau_for_coach_review_only():
    trend = _trend(_five())
    assert trend["status"] == "plateau_candidate"
    assert trend["review"] == "coach_review_required"
    assert trend["automatic_program_changes"] is False


def test_repetition_improvement_across_five_exposures_is_recognized():
    records = _five()
    records[-1] = _record("2026-10-29", reps=(11, 11, 11))
    trend = _trend(records)
    assert trend["status"] == "improving"
    assert trend["review"] == "continue_current_progression"


def test_load_improvement_with_repetitions_maintained_is_recognized():
    records = _five()
    records[-1] = _record("2026-10-29", reps=(10, 10, 10), load=22)
    trend = _trend(records)
    assert trend["status"] == "improving"


def test_sustained_declining_repetitions_and_rir_trigger_review_not_automatic_deload():
    records = _five()
    records[-2] = _record("2026-10-22", reps=(9, 9, 9), rir=(3, 3, 3))
    records[-1] = _record("2026-10-29", reps=(8, 8, 8), rir=(2, 2, 2))
    trend = _trend(records)
    assert trend["status"] == "declining_performance"
    assert trend["review"] == "review_recovery_and_dose"
    assert trend["automatic_program_changes"] is False


def test_recent_poor_recovery_takes_priority_over_plateau_signal():
    records = _five()
    records[-1] = _record("2026-10-29", recovery="poor")
    trend = _trend(records)
    assert trend["status"] == "recovery_watch"
    assert trend["review"] == "review_recovery_before_progression"


def test_incomplete_set_by_set_data_blocks_longitudinal_classification():
    records = _five()
    records[-1] = _record("2026-10-29", reps=(10, 10), rir=(4, 4), sets=3)
    trend = _trend(records)
    assert trend["status"] == "incomplete_data"


def test_fewer_than_five_exposures_only_build_a_baseline():
    trend = _trend(_five()[:4])
    assert trend["status"] == "building_baseline"


def test_five_exposures_in_too_short_a_period_do_not_claim_plateau():
    records = [
        _record("2026-10-20"),
        _record("2026-10-22"),
        _record("2026-10-24"),
        _record("2026-10-26"),
        _record("2026-10-28"),
    ]
    trend = _trend(records)
    assert trend["status"] == "building_baseline"


def test_changed_set_count_or_rep_target_makes_window_not_comparable():
    records = _five()
    records[-1] = _record("2026-10-29", target=(6, 10))
    trend = _trend(records)
    assert trend["status"] == "not_comparable"


def test_uncompleted_sessions_do_not_count_as_exposures():
    records = _five()
    records[-1] = _record("2026-10-29", completed=False)
    trend = _trend(records)
    assert trend["status"] == "building_baseline"



def test_time_based_conditioning_is_not_misclassified_as_resistance_progression():
    sessions = []
    for day in ("2026-10-01", "2026-10-08", "2026-10-15", "2026-10-22", "2026-10-29"):
        sessions.append({
            "session_date": day,
            "session": {
                "completed": True,
                "difficulty": "moderate",
                "recovery": "good",
                "exercises": [{
                    "exercise_id": "running_easy",
                    "planned_sets": 1,
                    "execution_quality": "controlled",
                    "set_results": [{"work_seconds": 1200, "rir": 4}],
                }],
            },
        })
    result = summarize_longitudinal_progression(sessions)
    assert result["exercise_trends"][0]["status"] == "not_supported"
    assert result["exercise_trends"][0]["review"] == "use_modality_specific_assessment"
