"""Regression tests for conversation state and conservative duration estimates."""

from coach_routes import _coaching_guardrail_reply, _sanitize_unverified_safety_claim, _has_explicit_safety_clearance
from training.program import _estimated_minutes


def test_unanswered_health_question_does_not_block_non_prescriptive_goal_context():
    messages = [
        {"role": "user", "content": "Rad bi bil bolj funkcionalen."},
        {"role": "model", "content": "Ali imaš bolečine, poškodbe ali omejitve?"},
        {"role": "user", "content": "Pomembnejša mi je vzdržljivost kot mišična masa."},
    ]
    assert _coaching_guardrail_reply(messages) is None


def test_pending_safety_question_allows_non_prescriptive_personal_context():
    messages = [
        {"role": "user", "content": "Rad bi bil bolj fit."},
        {
            "role": "model",
            "content": "Ali trenutno morda opaziš kakšne zdravstvene omejitve, poškodbe ali težave z gibanjem?",
        },
        {
            "role": "user",
            "content": "Predvsem bi rad imel več energije in se manj zadihal.",
        },
    ]
    assert _coaching_guardrail_reply(messages) is None


def test_individualized_program_remains_blocked_without_safety_clearance():
    messages = [
        {"role": "user", "content": "Želim pridobiti mišično maso."},
        {"role": "model", "content": "Ali imaš zdravstvene omejitve ali bolečine?"},
        {"role": "user", "content": "Imam ročke in lahko treniram trikrat tedensko. Sestavi mi program."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "Preden pripravim individualni trening" in reply


def test_equipment_and_schedule_are_not_discarded_while_safety_is_pending():
    messages = [
        {"role": "user", "content": "Rad bi treniral doma."},
        {"role": "model", "content": "Ali imaš zdravstvene omejitve ali bolečine?"},
        {"role": "user", "content": "Imam samo ročke in lahko vadim dvakrat na teden."},
    ]
    assert _coaching_guardrail_reply(messages) is None


def test_omitting_health_information_is_not_a_negative_confirmation():
    messages = [
        {"role": "user", "content": "Rad bi pridobil mišično maso."},
        {"role": "model", "content": "Ali imaš zdravstvene omejitve ali bolečine?"},
        {"role": "user", "content": "Treniram že tri leta in imam dostop do fitnesa."},
    ]
    answer = (
        "Ker v prejšnjem odgovoru nisi omenil zdravstvenih omejitev ali bolečin, "
        "predvidevam, da lahko začneva brez posebnih prilagoditev."
    )
    assert "Tega še nisi izrecno potrdil" in _sanitize_unverified_safety_claim(answer, messages)


def test_model_cannot_claim_safety_review_was_completed_without_answer():
    messages = [
        {"role": "user", "content": "Rad bi bil bolj fit."},
        {"role": "model", "content": "Ali imaš kakšne zdravstvene omejitve?"},
        {"role": "user", "content": "Želim izboljšati kondicijo."},
    ]
    answer = "Ker sva zdravstveni pregled že opravila, lahko nadaljujeva."
    assert "Tega še nisi izrecno potrdil" in _sanitize_unverified_safety_claim(answer, messages)


def test_emotional_reassurance_is_preserved_while_safety_answer_is_pending():
    messages = [
        {"role": "user", "content": "Ta teden sem opravil samo en trening."},
        {"role": "model", "content": "Ali imaš kakšne zdravstvene omejitve ali bolečine?"},
        {"role": "user", "content": "Zdaj imam občutek, da sem vse pokvaril."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "Ničesar nisi pokvaril" in reply
    assert "varnostnega vprašanja" in reply.casefold()


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


def test_bodyweight_only_regression_does_not_assume_wall_or_furniture():
    from coach_routes import _sanitize_unlisted_support

    messages = [{
        "role": "user",
        "content": 'Profil: {"goal":"strength_hypertrophy","experience":"beginner","equipment":["bodyweight"]}',
    }]
    answer = (
        "Skleca: 3 serije po 8–12 ponovitev. "
        "(Če je pretežko, začni z višjo oporo, npr. ob steno ali stabilen rob.)"
    )
    result = _sanitize_unlisted_support(answer, messages)
    assert "ob steno" not in result
    assert "stabilen rob" not in result
    assert "izvedbo sklece na kolenih" in result


def test_bodyweight_only_profile_does_not_rewrite_confirmed_chair_support():
    from coach_routes import _sanitize_unlisted_support

    messages = [{
        "role": "user",
        "content": 'Profil: {"goal":"strength","experience":"beginner","equipment":["bodyweight","chair"]}',
    }]
    answer = "Po potrebi uporabi stol za vstajanje."
    assert _sanitize_unlisted_support(answer, messages) == answer


def test_duration_estimate_rounds_up_conservatively():
    exercises = [{
        "prescription": {
            "sets": 2, "reps": "8–8",
            "tempo_seconds_per_rep": 2, "rest_seconds": 60,
        }
    }]
    assert _estimated_minutes(exercises, warm_up_minutes=5) == 7


def test_recurring_slovene_generation_typos_are_normalized():
    from coach_routes import _normalize_slovene_coaching_terms

    answer = "Prednoiva začneva, izboljšava srčno-žilne pripravljivosti."
    normalized = _normalize_slovene_coaching_terms(answer)
    assert "Preden začneva" in normalized
    assert "pripravljenosti" in normalized
