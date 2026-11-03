from coach_routes import _normalize_logged_exercise


def test_exercise_log_preserves_planned_target_and_execution_quality():
    entry, error = _normalize_logged_exercise({
        "exercise_id": "goblet_squat",
        "planned_sets": 3,
        "target_reps_min": 8,
        "target_reps_max": 12,
        "execution_quality": "controlled",
        "set_results": [
            {"reps": 10, "load_kg": 20, "rir": 4},
            {"reps": 10, "load_kg": 20, "rir": 3},
            {"reps": 9, "load_kg": 20, "rir": 3},
        ],
    })
    assert error is None
    assert entry["planned_sets"] == 3
    assert entry["target_reps_min"] == 8
    assert entry["target_reps_max"] == 12
    assert entry["execution_quality"] == "controlled"
    assert entry["rir"] == 3


def test_exercise_log_rejects_unhashable_or_unknown_quality_value():
    entry, error = _normalize_logged_exercise({
        "exercise_id": "goblet_squat",
        "sets_completed": 3,
        "reps_completed": 10,
        "execution_quality": [],
    })
    assert entry is None
    assert "kakovosti izvedbe" in error.lower()


def test_exercise_log_rejects_invalid_target_range():
    entry, error = _normalize_logged_exercise({
        "exercise_id": "goblet_squat",
        "planned_sets": 3,
        "target_reps_min": 12,
        "target_reps_max": 8,
        "sets_completed": 3,
        "reps_completed": 10,
    })
    assert entry is None
    assert "območje ponovitev" in error.lower()
