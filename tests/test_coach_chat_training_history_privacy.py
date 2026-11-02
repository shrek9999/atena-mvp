from coach_routes import _format_recent_training_context
from training.catalogue import load_catalogue


def test_recent_training_context_includes_performance_but_excludes_health_fields():
    exercise = load_catalogue()[0]
    context = _format_recent_training_context([{
        "session_date": "2026-11-01",
        "session": {
            "duration_minutes": 48,
            "difficulty": "moderate",
            "recovery": "good",
            "completed": True,
            "discomfort_reported": True,
            "private_symptom_note": "knee pain after walking",
            "diagnosis": "must never be sent to AI",
            "exercises": [{
                "exercise_id": exercise["id"],
                "sets_completed": 3,
                "reps_completed": 10,
                "load_kg": 22.5,
                "rir": 2,
            }],
        },
    }])

    assert "2026-11-01" in context
    assert exercise["name"] in context
    assert "3 sets" in context
    assert "~10 reps/set" in context
    assert "22.5 kg" in context
    assert "RIR 2" in context
    assert "discomfort" not in context.lower()
    assert "pain" not in context.lower()
    assert "knee" not in context.lower()
    assert "diagnosis" not in context.lower()
