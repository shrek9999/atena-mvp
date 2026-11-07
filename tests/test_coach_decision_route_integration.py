from coach_routes import _build_adaptive_decision
from training.athlete_state import create_athlete_state


def _state(symptom_status="denied", symptom_items=None):
    return create_athlete_state(
        profile_id="profile-001",
        goal="functional",
        experience="beginner",
        equipment=["bodyweight"],
        sessions_per_week=2,
        session_duration_minutes=45,
        symptoms={"status": symptom_status, "items": symptom_items or []},
    )


def test_progress_decision_uses_canonical_safety_orchestrator():
    state = _state(
        symptom_status="concerning",
        symptom_items=[{"location": "chest", "trend": "new"}],
    )
    decision = _build_adaptive_decision(
        [],
        exercise_progressions=[],
        longitudinal_progression={"exercise_trends": []},
        conditioning_progression={"conditioning_trends": []},
        athlete_state=state,
    )
    assert decision["decision"] == "refer_for_assessment"
    assert decision["decision_authority"] == "coach_orchestrator"
    assert decision["progression_allowed"] is False
    assert decision["adaptation_id"]


def test_legacy_call_without_canonical_state_keeps_compatibility_path():
    decision = _build_adaptive_decision(
        [],
        exercise_progressions=[],
        longitudinal_progression={"exercise_trends": []},
        conditioning_progression={"conditioning_trends": []},
    )
    assert decision["decision"] == "collect_baseline"
    assert "decision_authority" not in decision
    assert decision["adaptation_id"]
