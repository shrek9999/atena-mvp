from training.proactive_checkin import build_proactive_checkin


def _session(*, completed=True, difficulty="moderate", recovery="good",
             discomfort=False, exercises=None):
    return {
        "session_date": "2026-11-02",
        "session": {
            "completed": completed,
            "difficulty": difficulty,
            "recovery": recovery,
            "discomfort_reported": discomfort,
            "exercises": exercises or [],
        },
    }


def test_no_history_asks_one_baseline_question():
    result = build_proactive_checkin([])
    assert result["status"] == "awaiting_first_session"
    assert result["question"].endswith("?")
    assert result["model_call_required"] is False
    assert result["reply_saved"] is False


def test_symptom_follow_up_has_highest_priority_and_holds_changes():
    result = build_proactive_checkin([
        _session(discomfort=True, difficulty="hard", recovery="poor")
    ])
    assert result["status"] == "symptom_follow_up"
    assert result["priority"] == "safety"
    assert "nelagodje" in result["question"].lower()
    assert result["automatic_program_changes"] is False


def test_incomplete_session_asks_for_reason():
    result = build_proactive_checkin([_session(completed=False)])
    assert result["status"] == "incomplete_session"
    assert "Kaj je preprečilo" in result["question"]


def test_poor_recovery_takes_priority_over_hard_session():
    result = build_proactive_checkin([
        _session(difficulty="hard", recovery="poor")
    ])
    assert result["status"] == "poor_recovery"


def test_hard_session_asks_which_part_was_difficult():
    result = build_proactive_checkin([_session(difficulty="hard")])
    assert result["status"] == "hard_session"
    assert "Kateri del" in result["question"]


def test_technique_issue_precedes_missing_rir_question():
    result = build_proactive_checkin([
        _session(exercises=[{
            "exercise_id": "goblet_squat",
            "execution_quality": "needs_attention",
            "set_results": [{"reps": 10}],
        }])
    ])
    assert result["status"] == "technique_follow_up"


def test_missing_rir_is_not_guessed_and_prompts_one_question():
    result = build_proactive_checkin([
        _session(exercises=[{
            "exercise_id": "goblet_squat",
            "execution_quality": "controlled",
            "set_results": [{"reps": 10, "load_kg": 20}],
        }])
    ])
    assert result["status"] == "missing_effort_feedback"
    assert "RIR" in result["question"]


def test_complete_quality_feedback_uses_short_reflection_question():
    result = build_proactive_checkin([
        _session(exercises=[{
            "exercise_id": "goblet_squat",
            "execution_quality": "controlled",
            "set_results": [{"reps": 10, "load_kg": 20, "rir": 3}],
        }])
    ])
    assert result["status"] == "standard_follow_up"
    assert "najbolje" in result["question"]


def test_latest_session_is_used():
    result = build_proactive_checkin([
        {"session_date": "2026-11-01", "session": {"completed": True, "difficulty": "hard"}},
        {"session_date": "2026-11-02", "session": {"completed": True, "difficulty": "easy"}},
    ])
    assert result["status"] == "standard_follow_up"


def test_duplicate_same_day_uses_newest_first_record_without_fabricating_history():
    result = build_proactive_checkin([
        _session(difficulty="hard"),
        _session(difficulty="easy"),
    ])
    # The storage API returns the newest-created record first for the same date.
    assert result["status"] == "hard_session"
