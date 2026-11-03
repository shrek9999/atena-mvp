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
            exercise("goblet_squat", reps=(11, 11, 10), rir=(4, 4, 3)),
            exercise("push_up", reps=(8, 8, 7), rir=(1, 1, 2)),
        ]),
        record("2026-10-30", [
            exercise("goblet_squat", reps=(10, 10, 10), rir=(4, 4, 3)),
            exercise("push_up", reps=(8, 8, 8), rir=(2, 2, 2)),
        ]),
    ]
    result = recommend_exercise_progression(sessions)
    assert decision(result, "goblet_squat")["decision"] == "add_repetitions"
    assert decision(result, "push_up")["decision"] == "reduce_dose"


def test_upper_rep_limit_in_two_exposures_suggests_small_load_step_not_automatic_load_change():
    sessions = [
        record("2026-11-03", [exercise("goblet_squat", reps=(12, 12, 12), load=20, rir=(4, 4, 3))]),
        record("2026-10-30", [exercise("goblet_squat", reps=(12, 12, 12), load=20, rir=(4, 3, 3))]),
    ]
    result = decision(recommend_exercise_progression(sessions), "goblet_squat")
    assert result["decision"] == "increase_load"
    assert result["recent_load_kg"] == 20
    assert "najmanjši razpoložljivi dvig" in result["reason"]


def test_one_positive_exposure_is_not_enough():
    result = recommend_exercise_progression([
        record("2026-11-03", [exercise("goblet_squat")])
    ])
    assert decision(result, "goblet_squat")["decision"] == "collect_data"


def test_missing_rir_never_counts_as_readiness_to_progress():
    missing = exercise("goblet_squat", rir=(None, None, None))
    sessions = [
        record("2026-11-03", [missing]),
        record("2026-10-30", [missing]),
    ]
    assert decision(recommend_exercise_progression(sessions), "goblet_squat")["decision"] == "collect_data"


def test_technique_flag_holds_progression_for_that_exercise():
    sessions = [
        record("2026-11-03", [exercise("goblet_squat", quality="needs_attention")]),
        record("2026-10-30", [exercise("goblet_squat")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "goblet_squat")["decision"] == "technique_review"


def test_hard_effort_or_low_rir_reduces_only_the_relevant_dose():
    sessions = [
        record("2026-11-03", [exercise("goblet_squat", rir=(1, 2, 2))]),
        record("2026-10-30", [exercise("goblet_squat", rir=(3, 3, 3))]),
    ]
    assert decision(recommend_exercise_progression(sessions), "goblet_squat")["decision"] == "reduce_dose"


def test_poor_recovery_holds_progression_even_when_rir_is_high():
    sessions = [
        record("2026-11-03", [exercise("goblet_squat")], recovery="poor"),
        record("2026-10-30", [exercise("goblet_squat")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "goblet_squat")["decision"] == "hold"


def test_discomfort_stops_all_exercise_progression():
    sessions = [
        record("2026-11-03", [exercise("goblet_squat")], discomfort=True),
        record("2026-10-30", [exercise("goblet_squat")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "goblet_squat")["decision"] == "pause_and_review"


def test_recommendations_are_applied_to_matching_exercises_only():
    program = {
        "sessions": [{
            "exercises": [
                {"exercise_id": "goblet_squat", "prescription": {"sets": 3, "reps": "8–12", "rir": 3, "rest_seconds": 90}},
                {"exercise_id": "push_up", "prescription": {"sets": 3, "reps": "8–12", "rir": 3, "rest_seconds": 90}},
            ]
        }]
    }
    recommendations = [
        {"exercise_id": "goblet_squat", "decision": "add_repetitions", "reason": "positive response"},
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
        record("2026-11-03", [exercise("goblet_squat")], completed=False),
        record("2026-10-30", [exercise("goblet_squat")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "goblet_squat")["decision"] == "collect_data"
