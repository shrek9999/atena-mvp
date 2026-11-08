import coach_routes
from training.adaptive_decision import decide_adaptation


def _row(day, **session):
    base = {"completed": True, "difficulty": "moderate", "recovery": "good"}
    base.update(session)
    return {"session_date": day, "session": base}


def test_positive_adaptation_feedback_is_explicitly_confirmed():
    result = decide_adaptation(
        [_row("2026-11-08")],
        prior_adaptation={"adaptation_id": "adapt-123", "outcome": "helped"},
    )
    assert result["decision"] == "confirm_successful_change"
    assert result["scope"] == "previous_adjustment"
    assert result["previous_adaptation_id"] == "adapt-123"
    assert result["previous_outcome"] == "helped"
    assert result["automatic_program_changes"] is False


def test_positive_feedback_holds_only_exercises_from_the_confirmed_adaptation(monkeypatch):
    sessions = [
        _row(
            "2026-11-08",
            adaptation_response={"adaptation_id": "adapt-123", "outcome": "helped"},
        ),
        _row("2026-11-07"),
    ]
    monkeypatch.setattr(
        coach_routes,
        "_build_adaptive_decision",
        lambda _history: {
            "adaptation_id": "adapt-123",
            "eligible_exercises": ["goblet_squat", "push_up"],
        },
    )
    recommendations = [
        {"exercise_id": "goblet_squat", "decision": "add_repetitions", "reason": "progress"},
        {"exercise_id": "push_up", "decision": "increase_work_time", "reason": "progress"},
        {"exercise_id": "row", "decision": "add_repetitions", "reason": "progress"},
    ]

    held = coach_routes._hold_successfully_confirmed_exercises(sessions, recommendations)

    assert held == ["goblet_squat", "push_up"]
    assert [item["decision"] for item in recommendations] == ["hold", "hold", "add_repetitions"]
    assert "pomagala" in recommendations[0]["reason"]


def test_stale_positive_feedback_does_not_hold_any_exercise(monkeypatch):
    sessions = [
        _row(
            "2026-11-08",
            adaptation_response={"adaptation_id": "stale-id", "outcome": "helped"},
        ),
        _row("2026-11-07"),
    ]
    monkeypatch.setattr(
        coach_routes,
        "_build_adaptive_decision",
        lambda _history: {
            "adaptation_id": "current-id",
            "eligible_exercises": ["goblet_squat"],
        },
    )
    recommendations = [
        {"exercise_id": "goblet_squat", "decision": "add_repetitions", "reason": "progress"},
    ]

    held = coach_routes._hold_successfully_confirmed_exercises(sessions, recommendations)

    assert held == []
    assert recommendations[0]["decision"] == "add_repetitions"
