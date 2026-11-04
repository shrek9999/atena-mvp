import pytest

from training.adaptive_decision import decide_adaptation


def row(day, **session):
    base = {"completed": True, "difficulty": "moderate", "recovery": "good"}
    base.update(session)
    return {"session_date": day, "session": base}


def test_no_history_requests_baseline_not_program_change():
    result = decide_adaptation([])
    assert result["decision"] == "collect_baseline"
    assert result["automatic_program_changes"] is False
    assert result["success_signals"]


def test_time_shortage_restructures_session_without_reducing_training_dose():
    result = decide_adaptation([
        row("2026-11-02", completed=False, completion_reason="time_constraint")
    ])
    assert result["decision"] == "restructure_session"
    assert result["scope"] == "session_structure"
    assert result["adjustment"] == "prioritise_main_exercises_and_defer_optional_accessories"


def test_high_difficulty_requests_session_review_and_clarification():
    result = decide_adaptation([
        row("2026-11-02", completed=False, completion_reason="high_difficulty")
    ])
    assert result["scope"] == "session"
    assert result["clarifying_question"]


def test_poor_recovery_is_not_mistaken_for_lack_of_time():
    result = decide_adaptation([
        row("2026-11-02", completed=False, completion_reason="poor_recovery")
    ])
    assert result["reason_codes"] == ["incomplete_due_to_recovery"]


def test_external_interruption_does_not_reduce_the_programme():
    result = decide_adaptation([
        row("2026-11-02", completed=False, completion_reason="external_interruption")
    ])
    assert result["decision"] == "maintain_and_reschedule"
    assert result["scope"] == "none"


def test_unknown_incomplete_reason_collects_context_instead_of_guessing():
    result = decide_adaptation([
        row("2026-11-02", completed=False)
    ])
    assert result["decision"] == "collect_context"
    assert result["clarifying_question"]


@pytest.mark.parametrize("outcome", ["worse", "no_change"])
def test_failed_previous_adaptation_is_not_repeated(outcome):
    result = decide_adaptation(
        [row("2026-11-02")],
        prior_adaptation={"adaptation_id": "adapt-123", "outcome": outcome},
    )
    assert result["decision"] == "reassess_previous_change"
    assert result["previous_adaptation_id"] == "adapt-123"


def test_untried_previous_adaptation_is_not_overwritten_by_a_new_one():
    result = decide_adaptation(
        [row("2026-11-02")],
        prior_adaptation={"adaptation_id": "adapt-123", "outcome": "not_tried"},
    )
    assert result["decision"] == "confirm_previous_change"


def test_pain_safety_gate_precedes_all_other_signals():
    result = decide_adaptation(
        [row("2026-11-02", discomfort_reported=True, completion_reason="time_constraint")],
        exercise_progressions=[{"exercise_id": "squat", "decision": "increase_load"}],
    )
    assert result["decision"] == "pause_and_review"
    assert result["scope"] == "all_progression"


def test_movement_control_issue_holds_progression_for_technique_review():
    result = decide_adaptation([
        row("2026-11-02", movement_control="bracing")
    ], exercise_progressions=[{"exercise_id": "squat", "decision": "increase_load"}])
    assert result["decision"] == "technique_review"
    assert result["scope"] == "session"
    assert result["success_signals"]


def test_multiweek_decline_limits_review_to_affected_exercise():
    result = decide_adaptation(
        [row("2026-11-02")],
        longitudinal_progression={"exercise_trends": [{"exercise_id": "squat", "status": "declining_performance"}]},
    )
    assert result["decision"] == "review_declining_exercise"
    assert result["scope"] == "affected_exercise"


def test_positive_exercise_signal_does_not_increase_whole_programme():
    result = decide_adaptation(
        [row("2026-11-02")],
        exercise_progressions=[{"exercise_id": "squat", "decision": "add_repetitions"}],
    )
    assert result["scope"] == "individual_exercise"
    assert result["progression_allowed"] is True
    assert result["automatic_program_changes"] is False


def test_no_evidence_means_no_change():
    result = decide_adaptation([row("2026-11-02")])
    assert result["decision"] == "maintain_and_monitor"
    assert result["scope"] == "none"
