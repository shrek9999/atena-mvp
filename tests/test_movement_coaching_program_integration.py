"""Programme integration for structured six-pattern movement decisions."""
from training.movement_coaching import build_movement_decision
from training.program import generate_program


BASE = {
    "goal": "hypertrophy",
    "experience": "intermediate",
    "equipment": [
        "barbell", "rack", "dumbbell", "bench", "pull_up_bar",
        "kettlebell", "cable", "resistance_band", "box",
        "household_support", "wall", "anchor_point",
    ],
    "sessions_per_week": 2,
    "session_minutes": 60,
}


def _pattern_exercises(plan, pattern):
    return [
        item
        for session in plan["sessions"]
        for item in session["exercises"]
        if item["pattern"] == pattern
    ]


def test_learn_decision_selects_reaching_squat_and_adds_learning_task():
    decision = build_movement_decision(
        "squat", "LEARN",
        selected_learning_method="reaching_counterbalance",
        decision_reason="Najprej utrdi osnovno koordinacijo in ravnotežje.",
    )
    plan = generate_program(BASE, movement_decisions={"squat": decision})
    squats = _pattern_exercises(plan, "squat")
    assert squats
    assert all(item["exercise_id"] == "reaching_squat" for item in squats)
    assert all(item["prescription"]["sets"] <= 2 for item in squats)
    assert all(item["prescription"]["rir"] >= 3 for item in squats)
    tasks = [task for session in plan["sessions"] for task in session["learning_tasks"]]
    assert tasks
    assert all(task["method_id"] == "reaching_counterbalance" for task in tasks)


def test_dowel_hinge_learning_task_uses_a_catalogue_supported_low_skill_variant():
    decision = build_movement_decision(
        "hinge", "LEARN",
        equipment=["wall", "bodyweight"],
        implement_variant="broomstick",
        selected_learning_method="dowel_four_point",
        decision_reason="Utrdi tri stične točke in četrto kontrolo ledvene krivine.",
    )
    plan = generate_program(BASE, movement_decisions={"hinge": decision})
    hinges = _pattern_exercises(plan, "hinge")
    assert hinges
    assert all(item["exercise_id"] == "wall_hip_hinge" for item in hinges)
    tasks = [task for session in plan["sessions"] for task in session["learning_tasks"]]
    assert any(task["method_id"] == "dowel_four_point" for task in tasks)


def test_regress_decision_uses_verified_supported_split_squat():
    decision = build_movement_decision(
        "lunge", "REGRESS",
        equipment=["household_support", "bodyweight"],
        selected_learning_method="supported_split_squat",
        selected_exercise_id="supported_split_squat",
        decision_reason="Začasno uporabi oporo za ravnotežje.",
    )
    plan = generate_program(BASE, movement_decisions={"lunge": decision})
    lunges = _pattern_exercises(plan, "lunge")
    assert lunges
    assert all(item["exercise_id"] == "supported_split_squat" for item in lunges)
    assert all(item["prescription"]["sets"] <= 2 for item in lunges)


def test_ready_decision_does_not_trigger_automatic_progression_or_change_selection():
    baseline = generate_program(BASE)
    ready = build_movement_decision(
        "squat", "READY",
        decision_reason="Osnovna različica je bila ponovljiva in nadzorovana.",
    )
    assessed = generate_program(BASE, movement_decisions={"squat": ready})
    assert [item["exercise_id"] for item in _pattern_exercises(assessed, "squat")] == [
        item["exercise_id"] for item in _pattern_exercises(baseline, "squat")
    ]
    assert assessed["movement_adaptation"]["automatic_progression"] == "movement_assessment_does_not_trigger_progression"


def test_unassessable_omits_pattern_until_assessment_is_available():
    unassessable = build_movement_decision(
        "squat", "UNASSESSABLE",
        capture_quality="insufficient",
        limitations=["Stopala niso bila vidna v celotnem posnetku."],
        decision_reason="Ni dovolj dokazov za sklep.",
    )
    assessed = generate_program(BASE, movement_decisions={"squat": unassessable})
    assert not _pattern_exercises(assessed, "squat")
    assert any(
        event["action"] == "omitted_unassessable_pending_reassessment"
        for event in assessed["movement_adaptation"]["events"]
    )


def test_new_decision_contract_rejects_conflicting_legacy_assessment():
    decision = build_movement_decision("squat", "READY")
    try:
        generate_program(
            BASE,
            movement_assessment={"squat": "comfortable"},
            movement_decisions={"squat": decision},
        )
    except ValueError as exc:
        assert "ne kombiniraj" in str(exc)
    else:
        raise AssertionError("Conflicting assessment sources should be rejected.")


def test_structured_symptom_report_omits_only_affected_pattern_pending_review():
    decision = build_movement_decision(
        "squat", "UNASSESSABLE",
        user_report={"status": "symptoms_reported", "region": "knee"},
        decision_reason="Uporabnik je navedel nelagodje; potrebna je dodatna razjasnitev.",
    )
    plan = generate_program(BASE, movement_decisions={"squat": decision})
    assert not _pattern_exercises(plan, "squat")
    assert _pattern_exercises(plan, "hinge")
    event = next(event for event in plan["movement_adaptation"]["events"] if event["pattern"] == "squat")
    assert event["action"] == "omitted_pending_symptom_review"



def test_horizontal_push_never_selects_wall_push_up_even_when_wall_is_available():
    decision = build_movement_decision(
        "horizontal_push", "LEARN",
        equipment=["wall", "household_support", "bodyweight"],
        selected_learning_method="incline_push_up",
        selected_exercise_id="push_up_incline",
        decision_reason="Uporabi stabilno povišano oporo, brez sklece ob steni.",
    )
    plan = generate_program(BASE, movement_decisions={"horizontal_push": decision})
    pushes = _pattern_exercises(plan, "horizontal_push")
    assert pushes
    assert all(item["exercise_id"] != "wall_push_up" for item in pushes)
    assert all(item["exercise_id"] == "push_up_incline" for item in pushes)
