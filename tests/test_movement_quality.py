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


def test_horizontal_push_uses_a_stable_raised_support_not_wall_pushups():
    rubric = get_movement_rubric("horizontal_push")
    combined = " ".join(rubric["manipulations"] + rubric["coaching_options"]).lower()
    assert "stabilno" in combined
    assert "višji opori" in combined
    assert "skleca ob steni" not in combined
    assert "wall_push_up" not in combined


def test_hinge_uses_neutral_spine_language_and_four_point_dowel_learning():
    rubric = get_movement_rubric("hinge")
    assert "nevtralno hrbtenico" in rubric["task"].lower()
    description = rubric["criteria"]["dowel_neutral_spine"].lower()
    assert "tri stične točke" in description
    assert "četrto kontrolno točko" in description
    assert "ledveni krivini" in description
    assert "ne sme spreminjati" in description


def test_horizontal_pull_is_a_bent_over_row_with_a_stable_torso_angle():
    rubric = get_movement_rubric("horizontal_pull")
    assert "veslanje v predklonu" in rubric["task"].lower()
    assert "kot predklona" in rubric["criteria"]["trunk_control"].lower()
    assert "vertikalni" not in rubric["task"].lower()


def test_squat_pelvic_control_explicitly_limits_uncontrolled_butt_wink():
    description = MOVEMENT_RUBRICS["squat"]["criteria"]["pelvic_control"].lower()
    assert "butt-wink" in description
    assert "brez nenadzorovanega" in description
    assert "amplitudi" in description
    assert "globino omeji" in description
