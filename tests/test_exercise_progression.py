from training.exercise_progression import (
    apply_exercise_progression,
    recommend_exercise_progression,
)


def record(day, exercises, *, difficulty="moderate", recovery="good", completed=True,
           discomfort=False, difficulty_scope="unknown", affected_exercise_id=None):
    session = {
        "difficulty": difficulty,
        "recovery": recovery,
        "completed": completed,
        "exercises": exercises,
        "difficulty_scope": difficulty_scope,
    }
    if affected_exercise_id is not None:
        session["affected_exercise_id"] = affected_exercise_id
    if discomfort:
        session["discomfort_reported"] = True
    return {"session_date": day, "session": session}


def exercise(exercise_id, *, reps=(10, 10, 10), load=20, rir=(4, 4, 3),
             quality="controlled", tempo="followed", tempo_target="3–1–1–0",
             target=(8, 12), sets=3):
    return {
        "exercise_id": exercise_id,
        "planned_sets": sets,
        "target_reps_min": target[0],
        "target_reps_max": target[1],
        "execution_quality": quality,
        "tempo_control": tempo,
        **({"tempo_target": tempo_target} if tempo_target is not None else {}),
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


def test_load_change_blocks_repetition_progression_before_top_of_range():
    latest = exercise("squat_goblet", reps=(10, 10, 10), load=22, rir=(4, 4, 3))
    previous = exercise("squat_goblet", reps=(9, 9, 9), load=20, rir=(4, 4, 3))
    sessions = [
        record("2026-11-03", [latest]),
        record("2026-10-30", [previous]),
    ]
    result = decision(recommend_exercise_progression(sessions), "squat_goblet")
    assert result["decision"] == "hold"
    assert "obremenitev" in result["reason"]


def test_per_set_loads_must_match_not_just_average_load():
    latest = exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3))
    previous = exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3))
    for item, load in zip(latest["set_results"], (15, 20, 25)):
        item["load_kg"] = load
    for item in previous["set_results"]:
        item["load_kg"] = 20
    sessions = [
        record("2026-11-03", [latest]),
        record("2026-10-30", [previous]),
    ]
    result = decision(recommend_exercise_progression(sessions), "squat_goblet")
    assert result["decision"] == "hold"
    assert "posameznih serijah" in result["reason"]


def test_missing_load_for_one_set_cannot_trigger_load_progression():
    latest = exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3))
    latest["set_results"][1].pop("load_kg")
    previous = exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3))
    sessions = [
        record("2026-11-03", [latest]),
        record("2026-10-30", [previous]),
    ]
    result = decision(recommend_exercise_progression(sessions), "squat_goblet")
    assert result["decision"] == "collect_data"
    assert "vsako serijo" in result["reason"]


def test_regressing_repetitions_do_not_trigger_an_increase():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", reps=(9, 9, 9), rir=(4, 4, 3))]),
        record("2026-10-30", [exercise("squat_goblet", reps=(10, 10, 10), rir=(4, 4, 3))]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "hold"


def test_changed_planned_set_count_is_not_a_comparable_exposure():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", reps=(12, 12), rir=(4, 4), sets=2)]),
        record("2026-10-30", [exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3), sets=3)]),
    ]
    result = decision(recommend_exercise_progression(sessions), "squat_goblet")
    assert result["decision"] == "hold"
    assert "število serij" in result["reason"]


def test_missing_planned_set_count_requests_more_data():
    missing = exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3))
    missing.pop("planned_sets")
    sessions = [
        record("2026-11-03", [missing]),
        record("2026-10-30", [missing]),
    ]
    result = decision(recommend_exercise_progression(sessions), "squat_goblet")
    assert result["decision"] == "collect_data"
    assert "načrtovanem številu serij" in result["reason"]


def test_one_positive_exposure_is_not_enough():
    result = recommend_exercise_progression([
        record("2026-11-03", [exercise("squat_goblet")])
    ])
    assert decision(result, "squat_goblet")["decision"] == "collect_data"


def test_duplicate_exercise_entries_in_one_session_count_as_one_exposure():
    result = recommend_exercise_progression([
        record("2026-11-03", [
            exercise("squat_goblet", reps=(12, 12, 12)),
            exercise("squat_goblet", reps=(12, 12, 12)),
        ])
    ])
    assert decision(result, "squat_goblet")["decision"] == "collect_data"
    assert decision(result, "squat_goblet")["exposures_recorded"] == 1


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


def test_aerobic_time_is_not_progressed_from_duration_and_rir_alone():
    aerobic = {
        "exercise_id": "running_easy",
        "planned_sets": 1,
        "target_work_seconds": 1200,
        "execution_quality": "controlled",
        "tempo_control": "not_applicable",
        "set_results": [{"work_seconds": 1200, "rir": 4}],
    }
    sessions = [
        record("2026-11-03", [aerobic]),
        record("2026-10-30", [aerobic]),
    ]
    result = decision(recommend_exercise_progression(sessions), "running_easy")
    assert result["decision"] == "collect_data"
    assert "intenzivnosti" in result["reason"]


def test_two_successful_timed_exposures_increase_work_by_a_meaningful_step():
    timed = {
        "exercise_id": "deep_squat_hold",
        "planned_sets": 3,
        "target_work_seconds": 30,
        "execution_quality": "controlled",
        "tempo_control": "not_applicable",
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


def test_progression_is_blocked_when_latest_tempo_was_not_followed():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", tempo="not_followed")]),
        record("2026-10-30", [exercise("squat_goblet")]),
    ]
    result = decision(recommend_exercise_progression(sessions), "squat_goblet")
    assert result["decision"] == "technique_review"
    assert "predpisanega tempa" in result["reason"].lower()


def test_inconsistent_tempo_holds_progression_without_increasing_the_dose():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", tempo="inconsistent")]),
        record("2026-10-30", [exercise("squat_goblet")]),
    ]
    result = decision(recommend_exercise_progression(sessions), "squat_goblet")
    assert result["decision"] == "hold"
    assert "tempo" in result["reason"].lower()


def test_missing_tempo_assessment_never_triggers_progression():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", tempo="unknown")]),
        record("2026-10-30", [exercise("squat_goblet", tempo="unknown")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "collect_data"


def test_tempo_target_must_match_between_the_two_exposures():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", tempo_target="3–1–1–0")]),
        record("2026-10-30", [exercise("squat_goblet", tempo_target="2–0–X–0")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "hold"


def test_previous_exposure_with_inconsistent_tempo_blocks_progression():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet")]),
        record("2026-10-30", [exercise("squat_goblet", tempo="inconsistent")]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "hold"


def test_exercises_without_a_tempo_target_can_use_not_applicable():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet", tempo="not_applicable", tempo_target=None)]),
        record("2026-10-30", [exercise("squat_goblet", tempo="not_applicable", tempo_target=None)]),
    ]
    assert decision(recommend_exercise_progression(sessions), "squat_goblet")["decision"] == "add_repetitions"


def test_hard_rating_from_one_exercise_does_not_block_progression_of_other_exercises():
    sessions = [
        record(
            "2026-11-03",
            [
                exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3)),
                exercise("push_up", reps=(12, 12, 12), rir=(4, 4, 3)),
            ],
            difficulty="hard",
            difficulty_scope="exercise",
            affected_exercise_id="push_up",
        ),
        record("2026-10-30", [
            exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3)),
            exercise("push_up", reps=(12, 12, 12), rir=(4, 4, 3)),
        ]),
    ]
    result = recommend_exercise_progression(sessions)
    assert decision(result, "squat_goblet")["decision"] == "increase_load"
    assert decision(result, "push_up")["decision"] == "hold"


def test_incomplete_session_holds_only_the_named_difficult_exercise():
    sessions = [
        record(
            "2026-11-04",
            [],
            difficulty="hard",
            completed=False,
            difficulty_scope="exercise",
            affected_exercise_id="push_up",
        ),
        record("2026-11-03", [
            exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3)),
            exercise("push_up", reps=(12, 12, 12), rir=(4, 4, 3)),
        ]),
        record("2026-10-30", [
            exercise("squat_goblet", reps=(12, 12, 12), rir=(4, 4, 3)),
            exercise("push_up", reps=(12, 12, 12), rir=(4, 4, 3)),
        ]),
    ]
    result = recommend_exercise_progression(sessions)
    assert decision(result, "squat_goblet")["decision"] == "increase_load"
    assert decision(result, "push_up")["decision"] == "hold"
    assert "Ostale vaje se presojajo ločeno" in decision(result, "push_up")["reason"]


def test_mild_stable_symptom_holds_only_affected_exercise_and_allows_other_exercise_review():
    symptomatic = exercise("squat_goblet")
    unaffected = exercise("push_up")
    session = record("2026-11-03", [symptomatic, unaffected], difficulty="easy", discomfort=True)
    session["session"]["discomfort_details"] = {
        "exercise_id": "squat_goblet",
        "pain_during": 2,
        "worsened": False,
        "tolerated": True,
        "acute_warning_signs": [],
        "modifications_applied": ["reduced_load", "slow_tempo", "reduced_range"],
    }
    previous = record("2026-10-30", [exercise("squat_goblet"), exercise("push_up")], difficulty="easy")
    result = recommend_exercise_progression([session, previous])
    assert decision(result, "squat_goblet")["decision"] == "modify_symptomatic_exposure"
    assert decision(result, "push_up")["decision"] != "pause_and_review"


def test_legacy_or_incomplete_discomfort_report_remains_conservative_global_hold():
    sessions = [
        record("2026-11-03", [exercise("squat_goblet"), exercise("push_up")], discomfort=True),
        record("2026-10-30", [exercise("squat_goblet"), exercise("push_up")]),
    ]
    result = recommend_exercise_progression(sessions)
    assert decision(result, "squat_goblet")["decision"] == "pause_and_review"
    assert decision(result, "push_up")["decision"] == "pause_and_review"


def test_acute_complete_symptom_report_stops_only_the_affected_exercise():
    session = record(
        "2026-11-04",
        [exercise("squat_goblet"), exercise("push_up")],
        discomfort=True,
    )
    session["session"]["discomfort_details"] = {
        "exercise_id": "squat_goblet",
        "pain_during": 7,
        "worsened": True,
        "tolerated": False,
        "acute_warning_signs": ["acute_sharp_pain"],
        "modifications_applied": [],
    }
    previous = record(
        "2026-11-01",
        [exercise("squat_goblet"), exercise("push_up")],
    )
    result = recommend_exercise_progression([session, previous])
    assert decision(result, "squat_goblet")["decision"] == "stop_symptomatic_exposure"
    assert decision(result, "push_up")["decision"] != "pause_and_review"



def test_apply_progression_omits_acute_symptomatic_exercise_but_keeps_other_exercises():
    program = {
        "sessions": [{
            "title": "Trening A",
            "exercises": [
                {"exercise_id": "squat_goblet", "name": "Goblet počep", "prescription": {"sets": 3, "reps": "8–12"}},
                {"exercise_id": "push_up", "name": "Skleca", "prescription": {"sets": 3, "reps": "8–12"}},
            ],
        }]
    }
    result = apply_exercise_progression(program, [
        {"exercise_id": "squat_goblet", "decision": "stop_symptomatic_exposure", "reason": "Opozorilni znaki."},
    ])
    session = result["sessions"][0]
    assert [item["exercise_id"] for item in session["exercises"]] == ["push_up"]
    assert session["excluded_exercises"] == [{
        "exercise_id": "squat_goblet",
        "name": "Goblet počep",
        "reason": "Opozorilni znaki.",
    }]


def test_apply_progression_adds_explicit_load_guidance_for_mild_symptoms():
    program = {
        "sessions": [{
            "exercises": [{
                "exercise_id": "squat_goblet",
                "prescription": {"sets": 3, "reps": "8–12", "rir": 3},
            }],
        }]
    }
    result = apply_exercise_progression(program, [
        {"exercise_id": "squat_goblet", "decision": "modify_symptomatic_exposure", "reason": "Blago nelagodje."},
    ])
    prescription = result["sessions"][0]["exercises"][0]["prescription"]
    assert prescription["sets"] == 2
    assert prescription["rir"] == 4
    assert prescription["tempo"] == "4–1–2–0"
    assert "Zmanjšaj breme" in prescription["load_guidance"]
