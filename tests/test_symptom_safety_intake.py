"""Tests for the one-time safety gate and movement-specific symptom handling."""
from coach_routes import (
    _has_adaptable_local_symptom_report,
    _has_initial_health_gate_clearance,
    _has_safety_intake_resolution,
)


def test_localized_knee_pain_during_squat_is_routed_to_regression_testing():
    report = "Bolečina v kolenu pri počepu."
    assert _has_adaptable_local_symptom_report(report)
    assert _has_safety_intake_resolution(report)


def test_initial_profile_safety_answer_is_recognized_without_repeating_question():
    profile_context = (
        "Varnostna potrditev: nimam večjih zdravstvenih omejitev, svežih poškodb "
        "ali zdravniških prepovedi za vadbo. Lokalizirano nelagodje preveriva "
        "pri konkretnem gibalnem vzorcu z regresijo."
    )
    assert _has_initial_health_gate_clearance(profile_context)
    assert _has_safety_intake_resolution(profile_context)


def test_red_flag_symptom_is_not_treated_as_adaptable_local_discomfort():
    report = "Huda bolečina v kolenu pri počepu z izrazito oteklino."
    assert not _has_adaptable_local_symptom_report(report)
    assert not _has_safety_intake_resolution(report)
