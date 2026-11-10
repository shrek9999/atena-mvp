"""Regression tests for conversation state and conservative duration estimates."""

from coach_routes import _coaching_guardrail_reply, _sanitize_unverified_safety_claim, _has_explicit_safety_clearance, _has_explicit_no_pain_confirmation, _chat_message_character_limit
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


def test_pending_safety_question_detects_health_restriction_wording():
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
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "še nisi odgovoril" in reply
    assert "ne bom sklepal" in reply


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
    assert "po prenehanju giba" not in reply
    assert "Kje natančno se pojavi bolečina" not in reply
    assert reply.count("?") == 1


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


def test_inability_to_bear_weight_after_knee_swelling_and_locking_triggers_urgent_assessment():
    messages = [
        {"role": "user", "content": "Po treningu mi je koleno oteklo in včasih se zaklene."},
        {"role": "model", "content": "Ali poleg otekline občutiš težave pri obremenitvi noge?"},
        {"role": "user", "content": "Zdaj noge ne morem normalno obremeniti."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "nujno zdravstveno oceno še danes" in reply
    assert "ne izvajaj počepov" in reply.casefold()
    assert "pokliči 112" in reply.casefold()


def test_knee_swelling_and_locking_remain_active_when_user_asks_for_a_light_squat():
    messages = [
        {"role": "user", "content": "Koleno mi je oteklo in se včasih zaklene."},
        {"role": "model", "content": "Priporočam zdravstveno oceno."},
        {"role": "user", "content": "Ali lahko naredim samo lažji počep?"},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "ne izvajaj počepov" in reply
    assert "zdravstveno oceno" in reply


def test_pain_context_is_retained_when_user_asks_to_reduce_load_and_continue():
    messages = [
        {"role": "user", "content": "Pri potisku nad glavo me zaboli rama. Naj vajo zamenjam s skleco?"},
        {"role": "model", "content": "Kje natančno se pojavi bolečina in kako močna je od 0 do 10?"},
        {"role": "user", "content": "Bolečina se pojavi, ko dvignem roko nad višino rame."},
        {"role": "model", "content": "Kolikšna je bolečina od 0 do 10 in ali po prenehanju izzveni?"},
        {"role": "user", "content": "Ali naj samo zmanjšam težo in nadaljujem?"},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "Ne nadaljuj istega bolečega giba" in reply
    assert "manjšo težo" in reply
    assert "varnostnega vprašanja" not in reply
    assert "po prenehanju giba" not in reply
    assert reply.count("?") == 1


def test_unverified_table_row_is_rejected_without_waiting_for_health_clearance():
    messages = [
        {"role": "user", "content": "Doma nimam nobene opreme. Lahko delam veslanje pod mizo? Ne vem, ali je miza stabilna."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "Veslanja pod mizo ne izvajaj" in reply
    assert "brez potrjenega sidrišča" in reply
    assert "Superman" in reply


def test_functional_fitness_not_only_metcon_is_not_misclassified_as_endurance_education():
    reply = _coaching_guardrail_reply([
        {"role": "user", "content": "Želim izboljšati funkcionalno pripravljenost, vendar nočem, da je vsak trening samo MetCon."},
    ])
    assert reply is None


def test_pull_up_bar_alias_recognises_nominative_slovene_wording():
    from coach_routes import _profile_available_equipment

    available = _profile_available_equipment([
        {"role": "user", "content": "Imam drog za zgibe in stabilno škatlo."},
    ])
    assert "pull_up_bar" in available
    assert "box" in available


def test_direct_address_does_not_assume_user_is_grega():
    from coach_routes import _sanitize_unrequested_user_name

    answer = _sanitize_unrequested_user_name("Grega, odlično delo! Nadaljuj postopno.")
    assert not answer.startswith("Grega")
    assert "odlično delo" in answer


def test_third_person_explicit_profile_clearance_is_not_misread_as_active_pain():
    profile = (
        "KONTEKST TESTNEGA UPORABNIKA: Uporabnik je izrecno potrdil, "
        "da nima bolečin, poškodb ali gibalnih omejitev."
    )
    assert _has_explicit_no_pain_confirmation(profile)
    assert _has_explicit_safety_clearance(profile)
    reply = _coaching_guardrail_reply([
        {"role": "user", "content": profile},
        {"role": "user", "content": "Danes nimam dostopa do olimpijske palice. S čim zamenjam mrtvi dvig?"},
    ])
    assert reply is None or "Ne nadaljuj istega bolečega giba" not in reply


def test_general_hiit_education_does_not_wait_for_health_clearance():
    reply = _coaching_guardrail_reply([
        {"role": "user", "content": "Ali moram za izgubo maščobe vsak dan delati HIIT?"},
    ])
    assert reply is not None
    assert "Vsakodnevni HIIT ni potreben" in reply
    assert "energijskim primanjkljajem" in reply
    assert "varnostnega vprašanja" not in reply


def test_heavy_set_rest_education_does_not_wait_for_health_clearance():
    reply = _coaching_guardrail_reply([
        {"role": "user", "content": "Koliko naj počivam med težjimi serijami?"},
    ])
    assert reply is not None
    assert "2–3 minute" in reply
    assert "3–5 minut" in reply
    assert "varnostnega vprašanja" not in reply


def test_short_30_minute_session_preserves_rest_before_reducing_volume():
    reply = _coaching_guardrail_reply([
        {"role": "user", "content": "Danes imam samo 30 minut za tri vaje po tri serije."},
        {"role": "user", "content": "Ali lahko skrajšam odmore, da vse spravim v 30 minut?"},
    ])
    assert reply is not None
    assert "Ne krajšaj pretirano odmorov" in reply
    assert "zmanjšaj število vaj" in reply


def test_initial_pain_guardrail_asks_only_one_question():
    reply = _coaching_guardrail_reply([
        {"role": "user", "content": "Pri potisku nad glavo me zaboli rama. Naj vajo zamenjam s skleco?"},
    ])
    assert reply is not None
    assert "ne nadomeščaj" in reply
    assert "Kje natančno se pojavi bolečina?" in reply
    assert reply.count("?") == 1



def test_chat_allows_longer_assistant_history_than_user_input():
    assert _chat_message_character_limit("user") == 1800
    assert _chat_message_character_limit("model") == 6000


def test_unrequested_name_is_removed_even_inside_a_sentence():
    from coach_routes import _sanitize_unrequested_user_name

    answer = _sanitize_unrequested_user_name("Odlično, Grega! Ker si opravil vse serije, nadaljuj postopno.")
    assert "Grega" not in answer
    assert "Odlično" in answer
    assert "nadaljuj postopno" in answer
