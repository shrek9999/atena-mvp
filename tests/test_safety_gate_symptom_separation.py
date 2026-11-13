"""Regression tests: local symptoms must not satisfy the global safety gate."""

from coach_routes import (
    _coaching_guardrail_reply,
    _has_initial_health_gate_clearance,
    _has_localized_symptom_report,
    _has_safety_clearance,
)


def test_localized_knee_pain_is_not_global_safety_clearance():
    messages = [
        {"role": "user", "content": "Želim izboljšati funkcionalno pripravljenost."},
        {"role": "model", "content": "Ali imaš trenutno kakršne koli bolečine, poškodbe, gibalne omejitve ali zdravstvene zadržke?"},
        {"role": "user", "content": "Bolečina v kolenu pri počepu."},
    ]
    assert _has_localized_symptom_report(messages[-1]["content"])
    assert not _has_safety_clearance(messages)
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "začetnega splošnega vprašanja ne bom ponavljal" in reply
    assert "Kolikšna je bolečina" in reply


def test_structured_initial_health_gate_answer_is_recognized():
    profile_answer = (
        "Varnostna potrditev: nimam večjih zdravstvenih omejitev, svežih poškodb "
        "ali zdravniških prepovedi za vadbo."
    )
    messages = [{"role": "user", "content": profile_answer}]
    assert _has_initial_health_gate_clearance(profile_answer)
    assert _has_safety_clearance(messages)


def test_local_symptom_alone_cannot_unlock_individualized_dose():
    from coach_routes import _sanitize_unverified_training_dose

    messages = [
        {"role": "user", "content": "Bolečina v kolenu pri počepu."},
        {"role": "user", "content": "Želim program za moč."},
    ]
    answer = "Pri počepu izvedi 3 serije po 8 ponovitev."
    safe = _sanitize_unverified_training_dose(answer, messages)
    assert "3 serije po 8 ponovitev" not in safe


def test_substitution_fallback_uses_the_standardized_one_time_safety_screen():
    messages = [
        {"role": "user", "content": "Želim zamenjati počep."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "akutno ostro bolečino" in reply
    assert "kakršne koli bolečine" not in reply
