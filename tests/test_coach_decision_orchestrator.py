from training.athlete_state import create_athlete_state
from training.coach_decision_orchestrator import decide_coach_next_action


def athlete_state(*, symptom_status="denied", symptom_items=None, movement_tasks=None):
    return create_athlete_state(
        profile_id="profile-001",
        goal="functional",
        experience="beginner",
        equipment=["bodyweight"],
        sessions_per_week=2,
        session_duration_minutes=45,
        symptoms={"status": symptom_status, "items": symptom_items or []},
        movement_tasks=movement_tasks or {},
    )


def test_concerning_symptoms_override_all_progression_signals():
    state = athlete_state(
        symptom_status="concerning",
        symptom_items=[{"location": "chest", "trend": "new"}],
    )
    result = decide_coach_next_action(
        state, [],
        exercise_progressions=[{"exercise_id": "squat", "decision": "increase_load"}],
    )
    assert result["decision"] == "refer_for_assessment"
    assert result["progression_allowed"] is False
    assert result["decision_authority"] == "coach_orchestrator"


def test_new_or_worsening_symptoms_override_progression():
    state = athlete_state(
        symptom_status="new_or_worsening",
        symptom_items=[{"location": "knee", "trend": "worsening"}],
    )
    result = decide_coach_next_action(state, [])
    assert result["decision"] == "pause_and_review"
    assert result["scope"] == "all_training_progression"


def test_unanswered_symptom_screen_collects_context_without_guessing():
    state = athlete_state(symptom_status="asked_unanswered")
    result = decide_coach_next_action(state, [])
    assert result["decision"] == "collect_context"
    assert result["reason_codes"] == ["symptom_screen_unanswered"]


def test_stable_symptom_with_known_task_limits_only_linked_pattern():
    state = athlete_state(
        symptom_status="present_stable",
        symptom_items=[{"location": "knee", "provoking_task": "squat", "trend": "stable"}],
    )
    result = decide_coach_next_action(state, [])
    assert result["decision"] == "review_symptom_linked_patterns"
    assert result["affected_patterns"] == ["squat"]
    assert result["progression_allowed"] is False


def test_stable_symptom_without_task_mapping_requests_clarification():
    state = athlete_state(
        symptom_status="present_stable",
        symptom_items=[{"location": "knee", "trend": "stable"}],
    )
    result = decide_coach_next_action(state, [])
    assert result["decision"] == "collect_context"
    assert result["reason_codes"] == ["stable_symptom_task_unclear"]


def test_uncertain_movement_assessment_blocks_affected_pattern_progression():
    state = athlete_state(
        movement_tasks={"hinge": {"status": "uncertain", "source": "observed"}},
    )
    result = decide_coach_next_action(state, [])
    assert result["decision"] == "movement_competence_review"
    assert "hinge" in result["affected_patterns"]
    assert result["progression_allowed"] is False


def test_support_needed_is_not_treated_as_failure_or_diagnosis():
    state = athlete_state(
        movement_tasks={"squat": {"status": "needs_support", "source": "observed"}},
    )
    result = decide_coach_next_action(state, [])
    assert result["decision"] == "movement_competence_review"
    assert "squat" in result["affected_patterns"]


def test_invalid_state_fails_closed():
    result = decide_coach_next_action({"schema_version": 999}, [])
    assert result["decision"] == "collect_context"
    assert result["progression_allowed"] is False


def test_clear_state_delegates_to_existing_specialist_reconciliation():
    state = athlete_state()
    result = decide_coach_next_action(state, [])
    assert result["decision"] == "collect_baseline"
    assert result["decision_authority"] == "specialist_reconciliation"
    assert result["automatic_program_changes"] is False
