"""Regression tests for goal specificity and feedback-driven next-session changes."""
from training.program import generate_program


EQUIPMENT = [
    "barbell", "rack", "dumbbell", "bench", "pull_up_bar",
    "kettlebell", "cable", "resistance_band", "box",
]


def profile(goal="strength", experience="beginner", **overrides):
    return {
        "goal": goal,
        "experience": experience,
        "equipment": EQUIPMENT,
        "sessions_per_week": 2,
        "session_minutes": 75,
        **overrides,
    }


def exercises(plan):
    return [item for session in plan["sessions"] for item in session["exercises"]]


def test_beginner_strength_and_hypertrophy_have_distinct_dosing():
    strength = generate_program(profile("strength", "beginner"))
    hypertrophy = generate_program(profile("hypertrophy", "beginner"))
    strength_squat = next(x for x in exercises(strength) if x["pattern"] == "squat")
    hypertrophy_squat = next(x for x in exercises(hypertrophy) if x["pattern"] == "squat")

    assert strength_squat["prescription"]["reps"] == "8–12"
    assert hypertrophy_squat["prescription"]["reps"] == "10–15"
    assert strength_squat["prescription"]["rest_seconds"] > hypertrophy_squat["prescription"]["rest_seconds"]


def test_endurance_is_a_distinct_conditioning_program_not_a_strength_template():
    strength = generate_program(profile("strength", "intermediate"))
    endurance = generate_program(profile("endurance", "intermediate"))
    strength_patterns = {x["pattern"] for x in exercises(strength)}
    endurance_patterns = {x["pattern"] for x in exercises(endurance)}

    assert "squat" in strength_patterns and "hinge" in strength_patterns
    assert "locomotion" in endurance_patterns
    assert "conditioning" in endurance_patterns
    assert endurance_patterns != strength_patterns


def test_easy_feedback_changes_next_prescription_and_explains_why():
    base = generate_program(profile("strength", "intermediate"))
    adapted = generate_program(
        profile("strength", "intermediate"),
        feedback={
            "difficulty": "easy",
            "completed": True,
            "discomfort": "no",
            "recovery": "normal",
        },
    )
    before = {x["exercise_id"]: x["prescription"] for x in exercises(base)}
    after = {x["exercise_id"]: x["prescription"] for x in exercises(adapted)}

    changed = [
        exercise_id for exercise_id in before
        if before[exercise_id].get("reps") != after[exercise_id].get("reps")
        or before[exercise_id].get("work_seconds") != after[exercise_id].get("work_seconds")
    ]
    assert changed
    assert all(after[item].get("adjustment_note") for item in changed)
    assert adapted["feedback_applied"]["difficulty"] == "easy"


def test_hard_feedback_changes_next_prescription_and_explains_why():
    base = generate_program(profile("strength", "intermediate"))
    adapted = generate_program(
        profile("strength", "intermediate"),
        feedback={
            "difficulty": "hard",
            "completed": True,
            "discomfort": "no",
            "recovery": "normal",
        },
    )
    before = {x["exercise_id"]: x["prescription"] for x in exercises(base)}
    after = {x["exercise_id"]: x["prescription"] for x in exercises(adapted)}

    changed = [
        exercise_id for exercise_id in before
        if before[exercise_id].get("sets") != after[exercise_id].get("sets")
        or before[exercise_id].get("reps") != after[exercise_id].get("reps")
        or before[exercise_id].get("rir") != after[exercise_id].get("rir")
    ]
    assert changed
    assert all(after[item].get("adjustment_note") for item in changed)
    assert adapted["feedback_applied"]["difficulty"] == "hard"


def test_easy_and_hard_feedback_also_change_endurance_work():
    base = generate_program(profile("endurance", "intermediate"))
    easy = generate_program(
        profile("endurance", "intermediate"),
        feedback={"difficulty": "easy", "completed": True, "discomfort": "no", "recovery": "normal"},
    )
    hard = generate_program(
        profile("endurance", "intermediate"),
        feedback={"difficulty": "hard", "completed": True, "discomfort": "no", "recovery": "normal"},
    )

    def timed_work(plan):
        return {
            x["exercise_id"]: x["prescription"].get("work_seconds")
            for x in exercises(plan)
            if x["prescription"].get("work_seconds") is not None
        }

    baseline = timed_work(base)
    easier = timed_work(easy)
    harder = timed_work(hard)
    assert any(easier[key] > baseline[key] for key in baseline if key in easier)
    assert any(harder[key] < baseline[key] for key in baseline if key in harder)


def test_discomfort_still_blocks_automatic_adaptation():
    from training.program import ProgramSafetyBlock
    import pytest

    with pytest.raises(ProgramSafetyBlock):
        generate_program(
            profile("strength", "intermediate"),
            feedback={"difficulty": "hard", "completed": True, "discomfort": "yes"},
        )
