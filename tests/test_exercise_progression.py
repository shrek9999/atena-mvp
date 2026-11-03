from training.exercise_progression import (
    apply_exercise_progression,
    recommend_exercise_progression,
)


def record(day, exercises, *, difficulty="moderate", recovery="good", completed=True, discomfort=False):
    session = {
        "difficulty": difficulty,
        "recovery": recovery,
        "completed": completed,
        "exercises": exercises,
    }
    if discomfort:
        session["discomfort_reported"] = True
    return {"session_date": day, "session": session}


def exercise(exercise_id, *, reps=(10, 10, 10), load=20, rir=(4, 4, 3),
             quality="controlled", target=(8, 12), sets=3):
    return {
        "exercise_id": exercise_id,
        "planned_sets": sets,
        "target_reps_min": target[0],
        "target_reps_max": target[1],
        "execution_quality": quality,
        "set_results": [
            {"reps": rep, "load_kg": load, "rir": reserve}
            for rep, reserve in zip(reps, rir)
        ],
    }


def decision(items, exercise_id):
    return next(item for item in items if item["exercise_id"] == exercise_id)


def test_two_positive_exposures_progress_only_the_exercise_that_responded_well():
    sessions = [
        record("2026-11-03", [
            exercise("squat_goblet", reps=(11, 11, 10), rir=(4, 4, 3)),
            exercise("push_up", reps=(8, 8, 7), rir=(1, 1, 2)),
        ]),
        record("2026-10-30", [
            exercise("squat_goblet", reps=(10, 10, 10), rir=(4, 4, 3)),
            exercise("push_up", reps=(8, 8, 8), rir=(2, 2, 2)),
        ]),
    ]
    result = recommend_exercise_progression(sessions)
    assert decision(result, "squat_goblet")["decision"] == "add_repetitions"
    assert decision(result, "push_up")["decision"] == "reduce_dose"


def test_upper_rep_limit_in_two_exposures_suggests_small_load_step_not_automatic_load_change():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", reps=(12, 12, 12), load=20, rir=(4, 4, 3))]),
        record("2026-10-30", [exercise("squat_goblet", reps=(12, 12, 12), load=20, rir=(4, 3, 3))]),
    ]
    result = decision(recommend_exercise_progression(sessions), "squat_goblet")
    assert result["decision"] == "increase_load"
    assert result["recent_load_kg"] == 20
    assert "najmanjši razpoložljivi dvig" in result["reason"]


def test_one_top_of_range_exposure_is_not_enough_for_load_increase():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", reps=(12, 12, 12), load=20, rir=(4, 4, 3))]),
        record("2026-10-30", [exercise("squat_goblet", reps=(10, 10, 10), load=20, rir=(4, 4, 3))]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "hold"


def test_load_change_between_exposures_must_be_consolidated_before_progression():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", reps=(12, 12, 12), load=22, rir=(4, 4, 3))]),
        record("2026-10-30", [exercise("squat_goblet", reps=(12, 12, 12), load=20, rir=(4, 4, 3))]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "hold"


def test_regressing_repetitions_do_not_trigger_an_increase():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", reps=(9, 9, 9), rir=(4, 4, 3))]),
        record("2026-10-30", [exercise("squat_goblet", reps=(10, 10, 10), rir=(4, 4, 3))]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "hold"


def test_one_positive_exposure_is_not_enough():
    result = recommend_exercise_progression([
        record("2026-11-03", [exercise("squat_goblet")])
    ])
    assert decision(result, "squat_goblet")["decision"] == "collect_data"


def test_missing_rir_never_counts_as_readiness_to_progress():
    missing = exercise("squat_goblet", rir=(None, None, None))
    sessions = [
        record("2026-11-03", [missing]),
        record("2026-10-30", [missing]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "collect_data"


def test_rir_must_be_recorded_for_every_set():
    partial = exercise("squat_goblet", rir=(4, None, 3))
    sessions = [
        record("2026-11-03", [partial]),
        record("2026-10-30", [partial]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "collect_data"


def test_reps_must_be_recorded_for_every_set():
    partial = {
        "exercise_id": "squat_goblet",
        "planned_sets": 3,
        "target_reps_min": 8,
        "target_reps_max": 12,
        "execution_quality": "controlled",
        "set_results": [
            {"reps": 12, "load_kg": 20, "rir": 4},
            {"reps": 12, "load_kg": 20, "rir": 4},
            {"load_kg": 20, "rir": 4},
        ],
    }
    sessions = [
        record("2026-11-03", [partial]),
        record("2026-10-30", [partial]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "collect_data"


def test_legacy_aggregated_rir_does_not_substitute_for_set_by_set_data():
    legacy = {
        "exercise_id": "squat_goblet",
        "sets_completed": 3,
        "reps_completed": 12,
        "load_kg": 20,
        "rir": 4,
        "planned_sets": 3,
        "target_reps_min": 8,
        "target_reps_max": 12,
        "execution_quality": "controlled",
    }
    sessions = [
        record("2026-11-03", [legacy]),
        record("2026-10-30", [legacy]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "collect_data"


def test_missing_planned_set_is_not_treated_as_full_success():
    partial = exercise("squat_goblet", reps=(12, 12), rir=(4, 4), sets=3)
    sessions = [
        record("2026-11-03", [partial]),
        record("2026-10-30", [partial]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "hold"


def test_technique_flag_holds_progression_for_that_exercise():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", quality="needs_attention")]),
        record("2026-10-30", [exercise("squat_goblet")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "technique_review"


def test_unknown_execution_quality_does_not_count_as_controlled():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", quality="unknown")]),
        record("2026-10-30", [exercise("squat_goblet")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "collect_data"


def test_hard_effort_or_low_rir_reduces_only_the_relevant_dose():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", rir=(1, 2, 2))]),
        record("2026-10-30", [exercise("squat_goblet", rir=(3, 3, 3))]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "reduce_dose"


def test_poor_recovery_holds_progression_even_when_rir_is_high():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet")], recovery="poor"),
        record("2026-10-30", [exercise("squat_goblet")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "hold"


def test_discomfort_stops_all_exercise_progression():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet")], discomfort=True),
        record("2026-10-30", [exercise("squat_goblet")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "pause_and_review"


def test_two_successful_timed_exposures_increase_work_by_a_meaningful_step():
    timed = {
        "exercise_id": "deep_squat_hold",
        "planned_sets": 3,
        "target_work_seconds": 30,
        "execution_quality": "controlled",
        "set_results": [
            {"work_seconds": 30, "rir": 4},
            {"work_seconds": 30, "rir": 4},
            {"work_seconds": 30, "rir": 3},
        ],
    }
    sessions = [
        record("2026-11-03", [timed]),
        record("2026-10-30", [timed]),
    ]
    result = decision(recommend_exercise_progression(sessions), "deep_squat_hold")
    assert result["decision"] == "increase_work_time"
    program = {"sessions": [{"exercises": [{
        "exercise_id": "deep_squat_hold",
        "prescription": {"work_seconds": 30},
    }]}]}
    apply_exercise_progression(program, [result])
    assert program["sessions"][0]["exercises"][0]["prescription"]["work_seconds"] == 35


def test_recommendations_are_applied_to_matching_exercises_only():
    program = {
        "sessions": [{
            "exercises": [
                {"exercise_id": "squat_goblet", "prescription": {"sets": 3, "reps": "8–12", "rir": 3, "rest_seconds": 90}},
                {"exercise_id": "push_up", "prescription": {"sets": 3, "reps": "8–12", "rir": 3, "rest_seconds": 90}},
            ]
        }]
    }
    recommendations = [
        {"exercise_id": "squat_goblet", "decision": "add_repetitions", "reason": "positive response"},
        {"exercise_id": "push_up", "decision": "reduce_dose", "reason": "low RIR"},
    ]
    result = apply_exercise_progression(program, recommendations)
    squat, push = result["sessions"][0]["exercises"]
    assert squat["prescription"]["reps"] == "9–12"
    assert push["prescription"]["reps"] == "7–11"
    assert squat["prescription"]["sets"] == 3
    assert push["prescription"]["sets"] == 3
    assert squat["prescription"]["exercise_progression"]["automatic_load_change"] is False


def test_incomplete_sessions_are_not_used_as_progression_exposures():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet")], completed=False),
        record("2026-10-30", [exercise("squat_goblet")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "collect_data"
