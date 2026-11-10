import coach_routes


def _row(day, response=None):
    session = {"completed": True, "difficulty": "moderate", "recovery": "good"}
    if response is not None: session["adaptation_response"] = response
    return {"session_date": day, "session": session}


def test_positive_feedback_holds_only_exercises_in_exact_confirmed_decision(monkeypatch):
    sessions = [_row("2026-11-08", {"adaptation_id": "adapt-12345678", "outcome": "helped", "program_version_id": "program-v1"})]
    monkeypatch.setattr(coach_routes, "store_get_program_version", lambda profile, token, version: {"program_version_id": version, "decision": {"adaptive_decision": {"adaptation_id": "adapt-12345678", "feedback_contract": {"field": "adaptation_response"}, "eligible_exercises": ["goblet_squat", "push_up"]}}})
    recommendations = [{"exercise_id": "goblet_squat", "decision": "add_repetitions", "reason": "progress"}, {"exercise_id": "push_up", "decision": "increase_load", "reason": "progress"}, {"exercise_id": "row", "decision": "add_repetitions", "reason": "progress"}]
    held = coach_routes._hold_successfully_confirmed_exercises("profile", "token", sessions, recommendations)
    assert held == ["goblet_squat", "push_up"]
    assert [x["decision"] for x in recommendations] == ["hold", "hold", "add_repetitions"]


def test_stale_positive_feedback_does_not_hold_progression(monkeypatch):
    sessions = [_row("2026-11-08", {"adaptation_id": "stale-id", "outcome": "helped", "program_version_id": "program-v1"})]
    monkeypatch.setattr(coach_routes, "store_get_program_version", lambda *args: {"decision": {"adaptive_decision": {"adaptation_id": "current-id", "feedback_contract": {}, "eligible_exercises": ["goblet_squat"]}}})
    recommendations = [{"exercise_id": "goblet_squat", "decision": "add_repetitions", "reason": "progress"}]
    assert coach_routes._hold_successfully_confirmed_exercises("profile", "token", sessions, recommendations) == []
    assert recommendations[0]["decision"] == "add_repetitions"


def test_positive_feedback_without_exercise_scope_does_not_freeze_unrelated_progression(monkeypatch):
    sessions = [_row("2026-11-08", {"adaptation_id": "adapt-12345678", "outcome": "helped", "program_version_id": "program-v1"})]
    monkeypatch.setattr(coach_routes, "store_get_program_version", lambda *args: {"decision": {"adaptive_decision": {"adaptation_id": "adapt-12345678", "feedback_contract": {}}}})
    recommendations = [{"exercise_id": "goblet_squat", "decision": "add_repetitions", "reason": "progress"}]
    assert coach_routes._hold_successfully_confirmed_exercises("profile", "token", sessions, recommendations) == []
    assert recommendations[0]["decision"] == "add_repetitions"
