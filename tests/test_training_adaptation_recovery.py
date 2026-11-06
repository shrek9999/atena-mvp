from training.adaptation import assess_next_step


def test_poor_recovery_triggers_next_program_volume_reduction():
    result = assess_next_step([{
        "session_date": "2026-11-01",
        "session": {"completed": True, "difficulty": "moderate", "recovery": "poor"},
    }])
    assert result["decision"] == "recovery_review"
    assert result["volume_change"] == "maintain"
    assert result["progression_allowed"] is False
    assert "poor_recovery" in result["reason_codes"]


def test_hard_session_triggers_next_program_volume_reduction():
    result = assess_next_step([{
        "session_date": "2026-11-01",
        "session": {"completed": True, "difficulty": "hard", "recovery": "normal"},
    }])
    assert result["decision"] == "review_volume_reduction"
    assert result["progression_allowed"] is False


def test_progression_candidate_requires_two_easy_sessions_and_no_poor_recovery():
    sessions = [
        {
            "session_date": "2026-11-01",
            "session": {
                "completed": True, "difficulty": "easy", "recovery": "normal",
                "exercises": [{"rir": 4}],
            },
        },
        {
            "session_date": "2026-10-29",
            "session": {
                "completed": True, "difficulty": "easy", "recovery": "poor",
                "exercises": [{"rir": 4}],
            },
        },
    ]
    result = assess_next_step(sessions)
    assert result["decision"] == "maintain_and_monitor"
    assert result["progression_allowed"] is False


def test_discomfort_stops_adaptation_before_any_progression():
    result = assess_next_step([{
        "session_date": "2026-11-01",
        "session": {"completed": True, "difficulty": "easy", "recovery": "good", "discomfort_reported": True},
    }])
    assert result["decision"] == "pause_and_review"
    assert result["progression_allowed"] is False
