from coach_routes import _build_profile_adaptation


def wrapped_session(difficulty="easy", rir=3, recovery="good", completed=True, discomfort=False):
    return {
        "session": {
            "difficulty": difficulty,
            "completed": completed,
            "recovery": recovery,
            "discomfort_reported": discomfort,
            "exercises": [{"exercise_id": "goblet_squat", "rir": rir}],
        }
    }


def test_one_easy_session_does_not_trigger_progression():
    feedback, guidance = _build_profile_adaptation([wrapped_session()])
    assert feedback["difficulty"] == "right"
    assert guidance["progression_allowed"] is False


def test_two_easy_completed_sessions_with_rir_three_allow_small_progression():
    feedback, guidance = _build_profile_adaptation([
        wrapped_session(), wrapped_session()
    ])
    assert feedback["difficulty"] == "easy"
    assert guidance["progression_allowed"] is True


def test_two_easy_sessions_with_low_rir_do_not_trigger_progression():
    feedback, guidance = _build_profile_adaptation([
        wrapped_session(rir=2), wrapped_session(rir=3)
    ])
    assert feedback["difficulty"] == "right"
    assert guidance["progression_allowed"] is False


def test_hard_session_is_passed_through_for_immediate_reduction():
    feedback, guidance = _build_profile_adaptation([
        wrapped_session(difficulty="hard", rir=1)
    ])
    assert feedback["difficulty"] == "hard"
    assert guidance["action"] == "reduce_load"


def test_poor_recovery_holds_progression_and_preserves_recovery_signal():
    feedback, guidance = _build_profile_adaptation([
        wrapped_session(difficulty="easy", recovery="poor")
    ])
    assert feedback["difficulty"] == "right"
    assert feedback["recovery"] == "poor"
    assert guidance["progression_allowed"] is False


def test_discomfort_is_never_converted_to_a_normal_feedback_signal():
    feedback, guidance = _build_profile_adaptation([
        wrapped_session(discomfort=True)
    ])
    assert feedback["discomfort"] == "yes"
    assert guidance["action"] == "hold"


def test_no_history_returns_no_feedback_and_a_hold_guidance():
    feedback, guidance = _build_profile_adaptation([])
    assert feedback is None
    assert guidance["progression_allowed"] is False
