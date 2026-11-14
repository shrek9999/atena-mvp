"""Validation for browser-derived pose observations.

These observations are technical context only. They are never clinical findings
and are not inputs to the programme decision engine.
"""
from __future__ import annotations

from typing import Any

PATTERNS = {"squat", "hinge", "horizontal_push", "horizontal_pull", "vertical_push", "lunge", "coordination"}
SCALAR_KEYS = {
    "knee_flexion_proxy_deg", "heel_lift_visible", "heel_contact_check", "bilateral_lower_limb_visibility",
    "hip_angle_proxy_deg", "hip_angle_excursion_proxy_deg", "torso_to_head_hip_alignment_error_proxy", "trunk_tilt_proxy_deg",
    "scapular_control", "shoulder_elevation", "rib_trunk_control",
    "dowel_three_contact_check", "posterior_chain_range",
    "support_height", "elbow_bottom_proxy_deg", "elbow_top_proxy_deg",
    "shoulder_translation_between_phases_proxy", "scapular_pattern",
    "elbow_flexed_proxy_deg", "elbow_extended_proxy_deg",
    "left_arm_raise_proxy", "right_arm_raise_proxy", "side_to_side_difference_proxy",
    "trunk_shift_proxy", "elbow_visibility",
    "left_knee_angle_proxy_deg", "right_knee_angle_proxy_deg",
    "pelvis_level_difference_proxy", "stance_width_proxy",
    "cross_body_alternation_observed", "left_to_right_contact_frames",
    "right_to_left_contact_frames", "alternating_transitions_proxy",
    "knee_position_change_proxy_deg", "repetitions_detected", "range_of_motion_proxy",
    "left_knee_tracking_proxy", "right_knee_tracking_proxy", "knee_angle_asymmetry_proxy_deg",
    "hip_vertical_excursion_proxy", "pelvic_control",
    "observed_camera_side", "visible_side", "side_arm_raise_angle_proxy_deg",
    "side_trunk_tilt_proxy_deg", "side_elbow_angle_proxy_deg",
}


class CameraObservationError(ValueError):
    """Raised when browser pose observations do not match the supported schema."""


def validate_camera_observations(observations: Any, protocol: Any) -> tuple[dict, dict]:
    if not isinstance(observations, dict) or not observations or len(observations) > len(PATTERNS):
        raise CameraObservationError("Kamerni podatki morajo vsebovati vsaj enega od šestih vzorcev ali koordinacijski preizkus.")
    normalized: dict[str, dict] = {}
    for pattern, record in observations.items():
        if pattern not in PATTERNS or not isinstance(record, dict):
            raise CameraObservationError("Kamerni podatki vsebujejo neznan gibalni vzorec.")
        if record.get("status") not in {"observed", "uncertain"}:
            raise CameraObservationError("Neveljaven status kamerne analize.")
        if record.get("quality") not in {"adequate", "insufficient"}:
            raise CameraObservationError("Neveljavna kakovost kamerne analize.")
        valid_frames, total_frames = record.get("valid_frames"), record.get("total_frames")
        if (not isinstance(valid_frames, int) or isinstance(valid_frames, bool) or
                not isinstance(total_frames, int) or isinstance(total_frames, bool) or
                valid_frames < 0 or total_frames < valid_frames or total_frames > 2000):
            raise CameraObservationError("Neveljavno število kamernih sličic.")
        if record.get("source") != "browser_pose_landmarker" or record.get("analysis_version") not in {"six-pattern-proxy-v1", "six-pattern-proxy-v2"}:
            raise CameraObservationError("Nepodprt vir ali različica kamerne analize.")
        limitations = record.get("limitations")
        values = record.get("observations")
        if not isinstance(limitations, str) or len(limitations) > 500 or not isinstance(values, dict) or len(values) > 12:
            raise CameraObservationError("Neveljavna vsebina kamernih opažanj.")
        clean_values: dict[str, str | int | float | bool] = {}
        for key, value in values.items():
            if key not in SCALAR_KEYS or not isinstance(value, (str, int, float, bool)) or (isinstance(value, str) and len(value) > 160):
                raise CameraObservationError("Kamerni podatki vsebujejo nepričakovano polje.")
            if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
                raise CameraObservationError("Kamerni podatki vsebujejo neveljavno številsko vrednost.")
            clean_values[key] = value
        if pattern == "coordination":
            required_coordination = {
                "cross_body_alternation_observed", "left_to_right_contact_frames",
                "right_to_left_contact_frames", "alternating_transitions_proxy",
            }
            if set(clean_values) != required_coordination:
                raise CameraObservationError("Koordinacijski približek nima vseh zahtevanih polj.")
            observed = clean_values["cross_body_alternation_observed"]
            left_frames = clean_values["left_to_right_contact_frames"]
            right_frames = clean_values["right_to_left_contact_frames"]
            transitions = clean_values["alternating_transitions_proxy"]
            if not isinstance(observed, bool):
                raise CameraObservationError("Koordinacijski status mora biti logična vrednost.")
            if any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in (left_frames, right_frames, transitions)
            ):
                raise CameraObservationError("Števci koordinacijskega približka morajo biti nenegativna cela števila.")
            if (
                left_frames > valid_frames or right_frames > valid_frames
                or transitions > max(0, valid_frames - 1)
                or (record["status"] == "observed" and (
                    not observed or valid_frames < 3 or left_frames < 1
                    or right_frames < 1 or transitions < 2
                ))
                or (record["status"] == "uncertain" and observed)
            ):
                raise CameraObservationError("Status in števci koordinacijskega približka si nasprotujejo.")
        normalized[pattern] = {
            "status": record["status"],
            "quality": record["quality"],
            "valid_frames": valid_frames,
            "total_frames": total_frames,
            "observations": clean_values,
            "limitations": limitations,
            "source": "browser_pose_landmarker",
            "analysis_version": record["analysis_version"],
        }
    if not isinstance(protocol, dict):
        raise CameraObservationError("Manjka protokol kamerne analize.")
    if (protocol.get("version") not in {"six-pattern-camera-flow-v1", "six-pattern-camera-flow-v3"} or
            not isinstance(protocol.get("dowel_three_contact_user_confirmed"), bool) or
            protocol.get("push_up_support_height") not in {"floor", "low_support", "chair", "table", "other"} or
            protocol.get("video_stored") is not False or protocol.get("video_uploaded") is not False):
        raise CameraObservationError("Protokol zasebnosti kamere ni veljaven.")
    if protocol["version"] == "six-pattern-camera-flow-v3":
        if (protocol.get("views") != 8 or protocol.get("repetitions") != 2 or
                protocol.get("tempo") != "3-1-1" or
                protocol.get("lunge_repetitions_total") != 2 or
                protocol.get("lunge_one_per_side") is not True):
            raise CameraObservationError("Protokol šestih testov ne ustreza dogovorjenemu zaporedju osmih pogledov.")
        clean_protocol = {
            "version": "six-pattern-camera-flow-v3",
            "views": 8,
            "repetitions": 2,
            "tempo": "3-1-1",
            "lunge_repetitions_total": 2,
            "lunge_one_per_side": True,
            "dowel_three_contact_user_confirmed": protocol["dowel_three_contact_user_confirmed"],
            "push_up_support_height": protocol["push_up_support_height"],
            "video_stored": False,
            "video_uploaded": False,
        }
    else:
        clean_protocol = {
            "version": "six-pattern-camera-flow-v1",
            "dowel_three_contact_user_confirmed": protocol["dowel_three_contact_user_confirmed"],
            "push_up_support_height": protocol["push_up_support_height"],
            "video_stored": False,
            "video_uploaded": False,
        }
    return normalized, clean_protocol
