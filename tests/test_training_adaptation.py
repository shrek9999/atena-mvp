from training.adaptation import assess_next_step


def record(day, *, difficulty="moderate", completed=True, discomfort=None, rir=3):
    session = {
        "difficulty": difficulty,
        "completed": completed,
        "exercises": [{"exercise_id": "barbell_squat", "rir": rir}],
    }
    if discomfort is not None:
        session["discomfort_reported"] = discomfort
    return {"session_date": day, "session": session}


def test_discomfort_always_blocks_progression():
    result = assess_next_step([
        record("2026-11-01", difficulty="easy", discomfort=True),
        record("2026-10-29", difficulty="easy"),
    ])
    assert result["decision"] == "pause_and_review"
    assert result["progression_allowed"] is False
    assert result["volume_change"] == "none_automatic"


def test_incomplete_latest_session_triggers_conservative_volume_review():
    result = assess_next_step([
        record("2026-11-01", completed=False),
        record("2026-10-29", difficulty="easy"),
    ])
    assert result["decision"] == "review_volume_reduction"
    assert result["volume_change"] == "reduce_next_program_sets"
    assert result["progression_allowed"] is False


def test_hard_session_triggers_next_program_volume_reduction():
    result = assess_next_step([
        record("2026-11-01", difficulty="hard"),
        record("2026-10-29", difficulty="hard"),
    ])
    assert result["decision"] == "review_volume_reduction"
    assert result["volume_change"] == "reduce_next_program_sets"
    assert result["progression_allowed"] is False


def test_two_easy_sessions_with_reserve_are_progression_candidate_only():
    result = assess_next_step([
        record("2026-11-01", difficulty="easy", rir=3),
        record("2026-10-29", difficulty="easy", rir=4),
    ])
    assert result["decision"] == "progression_candidate"
    assert result["progression_allowed"] is True
    assert result["volume_change"] == "maintain"


def test_mixed_or_insufficient_data_maintains_plan():
    result = assess_next_step([record("2026-11-01", difficulty="easy")])
    assert result["decision"] == "maintain_and_monitor"
    assert result["progression_allowed"] is False


def test_missing_rir_does_not_create_progression_candidate():
    result = assess_next_step([
        record("2026-11-01", difficulty="easy", rir=None),
        record("2026-10-29", difficulty="easy", rir=4),
    ])
    assert result["decision"] == "maintain_and_monitor"



def test_two_easy_sessions_use_set_level_rir_for_progression_gate():
    def set_record(day, reserves):
        return {
            "session_date": day,
            "session": {
                "difficulty": "easy",
                "completed": True,
                "exercises": [{
                    "exercise_id": "barbell_squat",
                    "set_results": [{"reps": 10, "rir": value} for value in reserves],
                }],
            },
        }

    result = assess_next_step([
        set_record("2026-11-01", [4, 3, 3]),
        set_record("2026-10-29", [4, 4, 3]),
    ])
    assert result["decision"] == "progression_candidate"
    assert result["progression_allowed"] is True


def test_one_missing_set_level_rir_blocks_progression_candidate():
    def set_record(day, reserves):
        return {
            "session_date": day,
            "session": {
                "difficulty": "easy",
                "completed": True,
                "exercises": [{
                    "exercise_id": "barbell_squat",
                    "set_results": [{"reps": 10, "rir": value} for value in reserves],
                }],
            },
        }

    result = assess_next_step([
        set_record("2026-11-01", [4, None, 3]),
        set_record("2026-10-29", [4, 4, 3]),
    ])
    assert result["decision"] == "maintain_and_monitor"
    assert result["progression_allowed"] is False


def test_invalid_set_level_rir_blocks_progression_candidate():
    def set_record(day, reserves):
        return {
            "session_date": day,
            "session": {
                "difficulty": "easy",
                "completed": True,
                "exercises": [{
                    "exercise_id": "barbell_squat",
                    "set_results": [{"reps": 10, "rir": value} for value in reserves],
                }],
            },
        }

    result = assess_next_step([
        set_record("2026-11-01", [4, 11, 3]),
        set_record("2026-10-29", [4, 4, 3]),
    ])
    assert result["decision"] == "maintain_and_monitor"
    assert result["progression_allowed"] is False
