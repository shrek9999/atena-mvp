"""Programme integration for structured six-pattern movement decisions."""
from training.movement_coaching import build_movement_decision
from training.program import PATTERN_LABELS, ProgramValidationError, generate_program


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


def test_ready_decision_starts_conservatively_without_automatic_progression():
    baseline = generate_program(BASE)
    ready = build_movement_decision(
        "squat", "READY",
        decision_reason="Osnovni vzorec je bil udoben in nadzorovan.",
    )
    assessed = generate_program(BASE, movement_decisions={"squat": ready})
    selected = _pattern_exercises(assessed, "squat")
    assert selected
    assert all(item.get("loading_potential") != "high" for item in selected)
    assert [item["exercise_id"] for item in selected] != [
        item["exercise_id"] for item in _pattern_exercises(baseline, "squat")
    ]
    assert assessed["movement_adaptation"]["automatic_progression"] == "movement_assessment_does_not_trigger_progression"
    assert any(
        event["action"] == "ready_for_conservative_starting_variation"
        for event in assessed["movement_adaptation"]["events"]
    )


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


def test_hinge_user_facing_label_uses_neutral_spine_not_flat_back_language():
    assert PATTERN_LABELS["hinge"] == "predklon z nevtralno hrbtenico"


def test_loaded_bent_over_row_learning_requires_hinge_ready():
    row = build_movement_decision(
        "horizontal_pull", "LEARN",
        equipment=["dumbbell"],
        selected_learning_method="light_one_arm_hinge_row",
        selected_exercise_id="one_arm_row",
        decision_reason="Najprej utrdi koordinacijo lopatice in komolca z lahkim bremenom.",
    )
    try:
        generate_program(BASE, movement_decisions={"horizontal_pull": row})
    except ProgramValidationError as exc:
        assert "predklon" in str(exc).lower()
        assert "ready" in str(exc).lower()
    else:
        raise AssertionError("Loaded bent-over row must require a READY hinge assessment.")


def test_loaded_bent_over_row_is_allowed_after_hinge_is_marked_ready():
    hinge = build_movement_decision(
        "hinge", "READY",
        decision_reason="Uporabnik poroča o običajni nadzorovani izvedbi predklona.",
    )
    row = build_movement_decision(
        "horizontal_pull", "LEARN",
        equipment=["dumbbell"],
        selected_learning_method="light_one_arm_hinge_row",
        selected_exercise_id="one_arm_row",
        decision_reason="Utrdi koordinacijo lopatice in komolca z lahkim bremenom.",
    )
    plan = generate_program(BASE, movement_decisions={"hinge": hinge, "horizontal_pull": row})
    assert _pattern_exercises(plan, "horizontal_pull")


def test_band_row_learning_does_not_require_bent_over_hinge_readiness():
    row = build_movement_decision(
        "horizontal_pull", "LEARN",
        equipment=["resistance_band"],
        selected_learning_method="band_row",
        selected_exercise_id="band_row",
        decision_reason="Uporabi stabilno pritrjeno elastiko za učenje horizontalnega potega.",
    )
    plan = generate_program(BASE, movement_decisions={"horizontal_pull": row})
    assert _pattern_exercises(plan, "horizontal_pull")


def test_saved_needs_support_self_report_without_method_resolves_to_safe_wall_hinge():
    profile = {
        **BASE,
        "experience": "beginner",
        "equipment": ["wall", "household_support"],
    }
    decision = build_movement_decision(
        "hinge", "LEARN",
        user_report={"status": "needs_support"},
        decision_reason="Uporabnik potrebuje lažjo učno različico predklona.",
    )
    plan = generate_program(profile, movement_decisions={"hinge": decision})
    hinges = _pattern_exercises(plan, "hinge")
    assert hinges
    assert all(item["exercise_id"] == "wall_hip_hinge" for item in hinges)
    tasks = [
        task for session in plan["sessions"] for task in session["learning_tasks"]
        if task["movement_pattern"] == "hinge"
    ]
    assert tasks
    assert all(task["method_id"] == "wall_hip_hinge" for task in tasks)
    assert all(task["method"] == "Predklon ob steni" for task in tasks)
    assert all("pomik bokov nazaj" in task["description"] for task in tasks)


def test_needs_support_without_compatible_equipment_omits_only_that_pattern():
    profile = {
        **BASE,
        "experience": "beginner",
        "equipment": ["wall", "household_support"],
    }
    row = build_movement_decision(
        "horizontal_pull", "LEARN",
        user_report={"status": "needs_support"},
        decision_reason="Uporabnik potrebuje lažjo različico horizontalnega potega.",
    )
    vertical_push = build_movement_decision(
        "vertical_push", "LEARN",
        user_report={"status": "needs_support"},
        decision_reason="Uporabnik potrebuje lažjo različico vertikalnega potiska.",
    )
    plan = generate_program(
        profile,
        movement_decisions={"horizontal_pull": row, "vertical_push": vertical_push},
    )
    assert not _pattern_exercises(plan, "horizontal_pull")
    assert not _pattern_exercises(plan, "vertical_push")
    assert row["decision"] == "LEARN"
    assert vertical_push["decision"] == "LEARN"
    assert {"horizontal_pull", "vertical_push"} <= set(plan["weekly_summary"]["unfilled_patterns"])
    omissions = {
        event["pattern"]: event
        for event in plan["movement_adaptation"]["events"]
        if event["action"] == "omitted_no_equipment_compatible_learning_variant"
    }
    assert set(omissions) == {"horizontal_pull", "vertical_push"}
    assert all("oprema" in event["message"].lower() for event in omissions.values())


def test_kettlebell_only_hinge_row_uses_the_kettlebell_catalogue_variant():
    profile = {
        **BASE,
        "experience": "beginner",
        "equipment": ["kettlebell", "bodyweight", "chair", "wall", "household_support"],
    }
    hinge = build_movement_decision(
        "hinge", "READY",
        user_report={"status": "comfortable"},
        decision_reason="Predklon je bil samoocenjen kot običajno nadzorovan.",
    )
    row = build_movement_decision(
        "horizontal_pull", "LEARN",
        equipment=["kettlebell"],
        selected_learning_method="light_one_arm_hinge_row",
        selected_exercise_id="kettlebell_one_arm_row",
        user_report={"status": "needs_support"},
        decision_reason="Za učenje je izbrana kettlebell različica, ki ustreza opremi.",
    )
    plan = generate_program(profile, movement_decisions={"hinge": hinge, "horizontal_pull": row})
    rows = _pattern_exercises(plan, "horizontal_pull")
    assert rows
    assert all(item["exercise_id"] == "kettlebell_one_arm_row" for item in rows)

