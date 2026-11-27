import pytest

from training.movement_quality import (
    MOVEMENT_RUBRICS,
    MovementQualityError,
    get_movement_rubric,
    summarize_movement_observation,
)


def test_core_movement_patterns_have_observable_criteria_and_tempo():
    for pattern in ("squat", "hinge", "lunge", "horizontal_push", "horizontal_pull",
                    "vertical_push", "vertical_pull", "locomotion"):
        rubric = get_movement_rubric(pattern)
        assert rubric["criteria"]
        assert "tempo_control" in rubric["criteria"] or pattern == "locomotion"


def test_squat_rubric_includes_foot_tripod_knee_control_and_pelvic_context():
    criteria = MOVEMENT_RUBRICS["squat"]["criteria"]
    assert {"foot_tripod", "knee_control", "pelvic_control", "tempo_control"} <= set(criteria)


def test_observation_keeps_missing_evidence_unknown_and_suggests_manipulation():
    result = summarize_movement_observation(
        "squat",
        {"foot_tripod": "controlled", "ankle_dorsiflexion": "needs_attention"},
        tempo="3-1-1-0",
    )
    assert result["needs_attention"] == ["ankle_dorsiflexion"]
    assert "knee_control" in result["not_observed"]
    assert result["suggested_manipulations"]
    assert result["automatic_exercise_change"] == "none"
    assert result["automatic_readiness_clearance"] is False


def test_jump_landing_is_separate_and_never_auto_clears_readiness():
    result = summarize_movement_observation(
        "jump_landing", {"landing_foot_control": "controlled"}
    )
    assert result["requires_explicit_readiness_review"] is True
    assert result["automatic_readiness_clearance"] is False


def test_invalid_or_unknown_observation_is_rejected():
    with pytest.raises(MovementQualityError):
        summarize_movement_observation("squat", {"unknown": "controlled"})
    with pytest.raises(MovementQualityError):
        summarize_movement_observation("squat", {"foot_tripod": "pass"})
