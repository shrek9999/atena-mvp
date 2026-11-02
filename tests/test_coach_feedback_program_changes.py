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
    assert hypertrophy_squat["prescription"]["reps"] == "8–12"
    assert strength_squat["prescription"]["rest_seconds"] > hypertrophy_squat["prescription"]["rest_seconds"]
    assert strength_squat["prescription"]["tempo"] == "2–0–X–0"
    assert hypertrophy_squat["prescription"]["tempo"] == "3–1–2–0"


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


def test_intermediate_bodyweight_strength_uses_cossack_squat_and_single_leg_hinge():
    plan = generate_program(
        profile("strength", "intermediate", equipment=["bodyweight"])
    )
    chosen = exercises(plan)
    squat = next(x for x in chosen if x["pattern"] == "squat")
    hinge = next(x for x in chosen if x["pattern"] == "hinge")

    assert squat["exercise_id"] == "cossack_squat"
    assert hinge["exercise_id"] == "single_leg_rdl"


def test_advanced_bodyweight_strength_uses_cossack_until_pistol_skill_is_confirmed():
    plan = generate_program(
        profile("strength", "advanced", equipment=["bodyweight"], session_minutes=90)
    )
    squat = next(x for x in exercises(plan) if x["pattern"] == "squat")
    assert squat["exercise_id"] == "cossack_squat"

    assessed = generate_program(
        profile(
            "strength", "advanced", equipment=["bodyweight"],
            session_minutes=90, pistol_squat_capable=True
        )
    )
    assessed_squat = next(x for x in exercises(assessed) if x["pattern"] == "squat")
    assert assessed_squat["exercise_id"] == "pistol_squat"
    assert assessed_squat["joint_type"] == "multi_joint"
    assert assessed_squat["reps_per_side"] is True


def test_strength_and_hypertrophy_select_different_primary_press_variants():
    strength = generate_program(profile("strength", "intermediate"))
    hypertrophy = generate_program(profile("hypertrophy", "intermediate"))
    strength_press = next(x for x in exercises(strength) if x["pattern"] == "horizontal_push")
    hypertrophy_press = next(x for x in exercises(hypertrophy) if x["pattern"] == "horizontal_push")

    assert strength_press["exercise_id"] == "barbell_bench_press"
    assert hypertrophy_press["exercise_id"] == "dumbbell_bench_press"


def test_strength_and_hypertrophy_select_different_hinge_variants():
    strength = generate_program(profile("strength", "intermediate"))
    hypertrophy = generate_program(profile("hypertrophy", "intermediate"))
    strength_hinge = next(x for x in exercises(strength) if x["pattern"] == "hinge")
    hypertrophy_hinge = next(x for x in exercises(hypertrophy) if x["pattern"] == "hinge")

    assert strength_hinge["exercise_id"] == "deadlift"
    assert hypertrophy_hinge["exercise_id"] == "romanian_deadlift"


def test_strength_and_hypertrophy_select_different_horizontal_pull_variants():
    strength = generate_program(profile("strength", "intermediate"))
    hypertrophy = generate_program(profile("hypertrophy", "intermediate"))
    strength_pull = next(x for x in exercises(strength) if x["pattern"] == "horizontal_pull")
    hypertrophy_pull = next(x for x in exercises(hypertrophy) if x["pattern"] == "horizontal_pull")

    assert strength_pull["exercise_id"] == "barbell_bent_over_row"
    assert hypertrophy_pull["exercise_id"] in {"dumbbell_bent_over_row", "one_arm_row", "kettlebell_one_arm_row"}


def test_beginner_bodyweight_strength_uses_supported_single_leg_hinge_and_discloses_load_limit():
    plan = generate_program(
        profile("strength", "beginner", equipment=["bodyweight"])
    )
    hinge = next(x for x in exercises(plan) if x["pattern"] == "hinge")

    assert hinge["exercise_id"] == "supported_single_leg_rdl"
    assert any("Brez zunanjih bremen" in note for note in plan["limitations"])


def test_dumbbell_only_program_prefers_romanian_deadlift_over_dumbbell_deadlift():
    plan = generate_program(
        profile("strength", "intermediate", equipment=["dumbbell"])
    )
    hinge = next(x for x in exercises(plan) if x["pattern"] == "hinge")
    assert hinge["exercise_id"] == "romanian_deadlift"


def test_main_squat_avoids_dumbbells_held_at_sides():
    plan = generate_program(
        profile("hypertrophy", "intermediate", equipment=["dumbbell"])
    )
    squat = next(x for x in exercises(plan) if x["pattern"] == "squat")
    assert squat["exercise_id"] in {"squat_goblet", "dumbbell_squat_front_rack"}


def test_heel_elevated_squat_is_available_when_stable_support_is_selected():
    plan = generate_program(
        profile("strength", "beginner", equipment=["weight_plate"])
    )
    squat = next(x for x in exercises(plan) if x["pattern"] == "squat")
    assert squat["exercise_id"] == "heel_elevated_squat"
    assert "5–10 cm" in " ".join(squat["cues"])


def test_carries_are_not_inserted_as_default_filler():
    plan = generate_program(profile("strength", "intermediate"))
    assert all(x["pattern"] != "carry" for x in exercises(plan))
