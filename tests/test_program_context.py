import pytest

from training.athlete_state import create_athlete_state
from training.program import ProgramSafetyBlock
from training.program_context import ProgramContextError, generate_program_for_athlete


PROFILE = {
    "goal": "functional",
    "experience": "intermediate",
    "equipment": ["barbell", "rack", "dumbbell", "bench", "pull_up_bar", "kettlebell", "cable", "resistance_band", "box"],
    "sessions_per_week": 2,
    "session_minutes": 60,
    "available_days": ["monday", "thursday"],
}


def _profile(*, movement_tasks=None, symptoms=None):
    state = create_athlete_state(
        profile_id="athlete-test-1",
        goal=PROFILE["goal"],
        experience=PROFILE["experience"],
        equipment=PROFILE["equipment"],
        sessions_per_week=PROFILE["sessions_per_week"],
        session_duration_minutes=PROFILE["session_minutes"],
        available_days=PROFILE["available_days"],
        movement_tasks=movement_tasks,
        symptoms=symptoms,
    )
    return {**PROFILE, "athlete_state": state}


def test_canonical_movement_assessment_is_used_by_programme_generation():
    profile = _profile(movement_tasks={"squat": {"status": "needs_support", "source": "self_reported"}})
    plan = generate_program_for_athlete(profile)
    events = plan["movement_adaptation"]["events"]
    assert any(event["pattern"] == "squat" and event["action"] == "simpler_catalogue_variant_selected" for event in events)


def test_stable_symptom_is_limited_to_its_reported_provoking_task():
    profile = _profile(symptoms={
        "status": "present_stable",
        "items": [{"location": "knee", "provoking_task": "squat", "intensity": 2}],
    })
    plan = generate_program_for_athlete(profile)
    events = plan["movement_adaptation"]["events"]
    assert any(event["pattern"] == "squat" and event["action"] == "omitted_pending_symptom_review" for event in events)
    assert not any(event["pattern"] == "hinge" and event["action"] == "omitted_pending_symptom_review" for event in events)


def test_unanswered_symptom_screen_blocks_programme_generation():
    profile = _profile(symptoms={"status": "asked_unanswered", "items": []})
    with pytest.raises(ProgramSafetyBlock, match="še nima odgovora"):
        generate_program_for_athlete(profile)


@pytest.mark.parametrize("status", ["new_or_worsening", "concerning"])
def test_new_or_concerning_symptoms_block_automatic_programme_generation(status):
    profile = _profile(symptoms={
        "status": status,
        "items": [{"location": "knee", "provoking_task": "squat"}],
    })
    with pytest.raises(ProgramSafetyBlock):
        generate_program_for_athlete(profile)


def test_stable_symptom_without_clear_task_requires_clarification():
    profile = _profile(symptoms={
        "status": "present_stable",
        "items": [{"location": "knee"}],
    })
    with pytest.raises(ProgramSafetyBlock, match="ni jasna"):
        generate_program_for_athlete(profile)


def test_unassessed_movement_tasks_are_not_inferred_as_limitations():
    profile = _profile()
    plan = generate_program_for_athlete(profile)
    assert plan["movement_adaptation"]["events"] == []


def test_stale_legacy_profile_is_rejected_instead_of_mixed_with_canonical_state():
    profile = _profile()
    profile["equipment"] = ["dumbbell"]
    with pytest.raises(ProgramContextError, match="ne ujemata"):
        generate_program_for_athlete(profile)


def test_multiple_stable_symptoms_omit_only_their_linked_patterns():
    profile = _profile(symptoms={
        "status": "present_stable",
        "items": [
            {"location": "knee", "provoking_task": "squat"},
            {"location": "shoulder", "provoking_task": "push_up"},
        ],
    })
    plan = generate_program_for_athlete(profile)
    events = plan["movement_adaptation"]["events"]
    omitted = {
        event["pattern"]
        for event in events
        if event["action"] == "omitted_pending_symptom_review"
    }
    assert {"squat", "horizontal_push"}.issubset(omitted)


def test_horizontal_push_assessment_does_not_automatically_cover_overhead_press():
    from training.movement_assessment import TASK_PATTERNS
    assert TASK_PATTERNS["push"] == {"horizontal_push"}
    assert TASK_PATTERNS["overhead"] == {"vertical_push"}
