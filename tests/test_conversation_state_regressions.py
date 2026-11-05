"""Regression tests for conversation state and conservative duration estimates."""

from coach_routes import _coaching_guardrail_reply, _sanitize_unverified_safety_claim, _has_explicit_safety_clearance
from training.program import _estimated_minutes


def test_unanswered_health_question_is_not_implicit_clearance():
    messages = [
        {"role": "user", "content": "Rad bi bil bolj funkcionalen."},
        {"role": "model", "content": "Ali imaš bolečine, poškodbe ali omejitve?"},
        {"role": "user", "content": "Pomembnejša mi je vzdržljivost kot mišična masa."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "še nisi odgovoril" in reply
    assert "ne bom sklepal" in reply


def test_explicit_negative_answer_is_respected():
    messages = [
        {"role": "user", "content": "Nimam bolečin, poškodb ali zdravstvenih omejitev."},
        {"role": "model", "content": "Kakšno opremo imaš?"},
        {"role": "user", "content": "Imam ročke in elastiko."},
    ]
    assert _coaching_guardrail_reply(messages) is None


def test_uncertain_health_answer_is_not_treated_as_clearance():
    assert not _has_explicit_safety_clearance("Nimam pojma, ali imam zdravstvene omejitve.")
    assert not _has_explicit_safety_clearance("Ne vem, ali imam kakšne bolečine.")


def test_model_cannot_invent_a_negative_health_confirmation():
    messages = [
        {"role": "user", "content": "Rad bi bil bolj funkcionalen."},
        {"role": "model", "content": "Ali imaš trenutno bolečine ali omejitve?"},
        {"role": "user", "content": "Pomembnejša mi je vzdržljivost kot mišična masa."},
    ]
    answer = "Odlično, ker si potrdil, da nimaš zdravstvenih omejitev, lahko začnemo."
    safe = _sanitize_unverified_safety_claim(answer, messages)
    assert "Tega še nisi izrecno potrdil" in safe
    second_claim = "Odlično, da nimaš nobenih poškodb ali omejitev."
    assert "Tega še nisi izrecno potrdil" in _sanitize_unverified_safety_claim(second_claim, messages)


def test_pain_followup_requests_only_missing_details():
    messages = [
        {"role": "user", "content": "Pri izpadnem koraku me boli koleno."},
        {"role": "model", "content": "Kje natančno se pojavi bolečina in kako močna je od 0 do 10?"},
        {"role": "user", "content": "Bolečino čutim spredaj v kolenu, ko se spuščam."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "Kolikšna je bolečina" in reply
    assert "po prenehanju giba" in reply
    assert "Kje natančno se pojavi bolečina" not in reply


def test_duration_estimate_rounds_up_conservatively():
    exercises = [{
        "prescription": {
            "sets": 2, "reps": "8–8",
            "tempo_seconds_per_rep": 2, "rest_seconds": 60,
        }
    }]
    assert _estimated_minutes(exercises, warm_up_minutes=5) == 7
