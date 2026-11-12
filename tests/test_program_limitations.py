"""User-facing programme limitation tests."""

from training.program import PATTERN_LABELS, generate_program


def test_omitted_movement_patterns_are_explained_in_user_facing_limitations():
    plan = generate_program({
        "goal": "strength_hypertrophy",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 60,
        "equipment": ["bodyweight"],
    })

    omitted = plan["weekly_summary"]["unfilled_patterns"]
    assert omitted
    assert plan["limitations"]
    user_facing_labels = [PATTERN_LABELS.get(pattern, pattern) for pattern in omitted]
    assert all(
        any(label.casefold() in limitation.casefold() for limitation in plan["limitations"])
        for label in user_facing_labels
    ), f"omitted={omitted}; labels={user_facing_labels}; limitations={plan['limitations']}"
    combined_limitations = " ".join(plan["limitations"])
    assert "niso vključeni" in combined_limitations
    assert "niso nadomestila z drugo vrsto giba" in combined_limitations


