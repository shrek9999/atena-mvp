from training.camera_observations import CameraObservationError, validate_camera_observations


def protocol():
    return {
        "version": "six-pattern-camera-flow-v1",
        "dowel_three_contact_user_confirmed": False,
        "push_up_support_height": "floor",
        "video_stored": False,
        "video_uploaded": False,
    }


def test_optional_coordination_observation_is_validated_as_technical_context():
    observation = {
        "coordination": {
            "status": "observed",
            "quality": "adequate",
            "valid_frames": 18,
            "total_frames": 24,
            "observations": {
                "cross_body_alternation_observed": True,
                "left_to_right_contact_frames": 8,
                "right_to_left_contact_frames": 7,
                "alternating_transitions_proxy": 5,
            },
            "limitations": "Grobi 2D koordinacijski približek.",
            "source": "browser_pose_landmarker",
            "analysis_version": "six-pattern-proxy-v1",
        }
    }
    clean, clean_protocol = validate_camera_observations(observation, protocol())
    assert clean["coordination"]["observations"]["cross_body_alternation_observed"] is True
    assert clean["coordination"]["observations"]["alternating_transitions_proxy"] == 5
    assert clean_protocol["video_stored"] is False
    assert clean_protocol["video_uploaded"] is False


def test_coordination_observation_rejects_unapproved_fields():
    observation = {
        "coordination": {
            "status": "observed",
            "quality": "adequate",
            "valid_frames": 18,
            "total_frames": 24,
            "observations": {"clinical_coordination_score": 92},
            "limitations": "Grobi 2D koordinacijski približek.",
            "source": "browser_pose_landmarker",
            "analysis_version": "six-pattern-proxy-v1",
        }
    }
    try:
        validate_camera_observations(observation, protocol())
    except CameraObservationError:
        pass
    else:
        raise AssertionError("Unapproved coordination fields must be rejected")
