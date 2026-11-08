import pytest

from training.movement_assessment import (
    MovementAssessmentError,
    assess_movement_competence,
)


def test_partial_assessment_keeps_unreported_tasks_unassessed():
    result = assess_movement_competence({"squat": "comfortable"})
    assert result["is_score"] is False
    assert result["is_diagnosis"] is False
    assert result["automatic_programme_change"] == "none"
    assert result["plyometric_readiness"] == "not_assessed"
    assert result["coaching_guidance"]["not_assessed_do_not_infer"] == [
        "hinge", "lunge", "push", "pull", "overhead",
        "ankle_dorsiflexion", "hip_mobility", "shoulder_mobility",
        "single_leg_balance", "coordination", "body_awareness", "locomotion",
    ]


def test_needs_support_generates_only_a_coaching_prompt_not_a_diagnosis():
    result = assess_movement_competence({
        "squat": "needs_support",
        "hinge": "comfortable",
    })
    assert result["coaching_guidance"]["consider_supported_or_simpler_variation"] == ["squat"]
    assert result["coaching_guidance"]["pause_automatic_changes_for"] == []
    assert result["is_diagnosis"] is False
    assert result["automatic_programme_change"] == "none"


def test_uncertain_and_symptom_reports_are_kept_separate():
    result = assess_movement_competence({
        "lunge": "uncertain",
        "overhead": "symptoms_reported",
    })
    assert result["coaching_guidance"]["clarify_before_relying_on_observation"] == ["lunge"]
    assert result["coaching_guidance"]["pause_automatic_changes_for"] == ["overhead"]


def test_no_status_automatically_clears_jumping_or_impact_readiness():
    result = assess_movement_competence({
        "squat": "comfortable",
        "single_leg_balance": "comfortable",
        "locomotion": "comfortable",
    })
    assert result["plyometric_readiness"] == "not_assessed"
    assert result["automatic_programme_change"] == "none"


def test_mobility_tasks_are_explicit_and_map_only_to_relevant_patterns():
    from training.movement_assessment import TASK_PATTERNS

    assert TASK_PATTERNS["ankle_dorsiflexion"] == {"squat", "lunge"}
    assert TASK_PATTERNS["hip_mobility"] == {"squat", "hinge", "lunge"}
    assert TASK_PATTERNS["shoulder_mobility"] == {"vertical_push"}


def test_coordination_is_not_inferred_from_general_training_experience():
    from training.movement_assessment import TASK_PATTERNS

    assert TASK_PATTERNS["coordination"] == {"coordination"}
    result = assess_movement_competence({"coordination": "uncertain"})
    assert result["coaching_guidance"]["clarify_before_relying_on_observation"] == ["coordination"]


def test_body_awareness_is_a_prompt_not_an_automatic_stability_prescription():
    from training.movement_assessment import TASK_PATTERNS

    assert TASK_PATTERNS["body_awareness"] == set()
    result = assess_movement_competence({"body_awareness": "needs_support"})
    assert result["coaching_guidance"]["consider_supported_or_simpler_variation"] == ["body_awareness"]
    assert result["coaching_guidance"]["body_awareness_is_a_prompt_not_a_diagnosis"] is True


@pytest.mark.parametrize("value", [None, [], "comfortable", 3])
def test_non_object_assessment_is_rejected(value):
    with pytest.raises(MovementAssessmentError):
        assess_movement_competence(value)


def test_empty_assessment_is_rejected():
    with pytest.raises(MovementAssessmentError):
        assess_movement_competence({})


def test_unknown_task_is_rejected():
    with pytest.raises(MovementAssessmentError, match="Neznane"):
        assess_movement_competence({"jump": "comfortable"})


def test_unknown_status_is_rejected():
    with pytest.raises(MovementAssessmentError, match="Neveljaven status"):
        assess_movement_competence({"squat": "pass"})


def test_all_supported_tasks_are_returned_with_explicit_unassessed_defaults():
    from training.movement_assessment import MOVEMENT_TASKS

    result = assess_movement_competence({"pull": "comfortable"})
    assert [item["movement_task"] for item in result["tasks"]] == list(MOVEMENT_TASKS)
    assert next(item for item in result["tasks"] if item["movement_task"] == "squat")["status"] == "not_assessed"


def test_public_task_labels_match_everyday_activities_in_the_user_interface():
    from training.movement_assessment import MOVEMENT_TASKS

    assert MOVEMENT_TASKS["locomotion"] == "hoja po ravni podlagi"
    assert MOVEMENT_TASKS["squat"] == "vstajanje s stola"
    assert MOVEMENT_TASKS["hinge"] == "pobiranje lahkega predmeta s tal"
    assert MOVEMENT_TASKS["overhead"] == "doseganje nad višino ramen"
    assert MOVEMENT_TASKS["ankle_dorsiflexion"] == "pomik kolena naprej nad stopalo ob peti na tleh"
