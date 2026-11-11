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



def test_safety_gate_does_not_repeat_the_same_question_after_one_reminder():
    messages = [
        {"role": "user", "content": "Rad bi bil bolj fit."},
        {"role": "model", "content": "Ali imaš trenutno kakšne bolečine, poškodbe ali omejitve?"},
        {"role": "user", "content": "Rad bi imel več energije in se manj zadihal."},
        {"role": "model", "content": "Ali imaš trenutno kakršne koli bolečine, poškodbe ali omejitve?"},
        {"role": "user", "content": "Trenutno skoraj nič ne treniram."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "ne bom sestavil individualnega programa" in reply
    assert "Ali imaš trenutno" not in reply
    assert "ali imaš" not in reply.casefold()
    assert "Ko boš pripravljen" in reply
    assert reply.count("?") == 0


def test_progression_prompt_returns_to_lower_end_of_rep_range_after_two_exposures():
    from coach_routes import SYSTEM_PROMPT

    assert "return to the lower part of the existing rep range" in SYSTEM_PROMPT
    assert "Do not prescribe repetitions above the stated upper limit" in SYSTEM_PROMPT


def test_foot_assisted_vertical_pull_supports_only_the_feet():
    from coach_routes import SYSTEM_PROMPT

    assert "only the feet contact" in SYSTEM_PROMPT
    assert "Never describe the knees as resting" in SYSTEM_PROMPT
    assert "A dumbbell row is a horizontal pull and never replaces a vertical pull-up" in SYSTEM_PROMPT



def test_unverified_exercise_dose_is_withheld_but_technique_context_is_preserved():
    from coach_routes import _sanitize_unverified_training_dose

    messages = [
        {"role": "user", "content": "Imam drog za zgibe in stabilno škatlo."},
        {"role": "model", "content": "Ali želiš lažjo različico vertikalnega zgiba?"},
        {"role": "user", "content": "Želim lažjo različico vertikalnega zgiba, ne veslanja."},
    ]
    answer = (
        "Razumem, govoriva o navpičnem zgibu, ne o veslanju.\n\n"
        "Predlagam 3 serije po 6 do 8 ponovitev."
    )
    result = _sanitize_unverified_training_dose(answer, messages)
    assert "navpičnem zgibu" in result
    assert "3 serije" not in result
    assert "Preden določim serije" in result


def test_verified_safety_clearance_allows_exercise_dose():
    from coach_routes import _sanitize_unverified_training_dose

    messages = [
        {"role": "user", "content": "Nimam bolečin, poškodb ali zdravstvenih omejitev."},
        {"role": "user", "content": "Pri počepu lahko naredim 3 serije po 8 ponovitev?"},
    ]
    answer = "Pri počepu izvedi 3 serije po 8 ponovitev."
    assert _sanitize_unverified_training_dose(answer, messages) == answer




def test_partial_safety_clearance_does_not_allow_individualized_exercise_dose():
    from coach_routes import _sanitize_unverified_training_dose

    assert not _has_explicit_safety_clearance("Nimam bolečin.")
    assert not _has_explicit_safety_clearance("Nimam poškodb.")
    assert not _has_explicit_safety_clearance("Nimam zdravstvenih omejitev.")
    assert not _has_explicit_safety_clearance("Nimam bolečin, vendar imam poškodbo in zdravstvene omejitve.")
    messages = [
        {"role": "user", "content": "Nimam bolečin."},
        {"role": "user", "content": "Pri počepu lahko naredim 3 serije po 8 ponovitev?"},
    ]
    answer = "Pri počepu izvedi 3 serije po 8 ponovitev."
    result = _sanitize_unverified_training_dose(answer, messages)
    assert "3 serije" not in result
    assert "Preden določim serije" in result


def test_exercise_dose_gate_uses_the_full_conversation_context():
    from coach_routes import _sanitize_unverified_training_dose

    messages = [
        {"role": "user", "content": "Rad bi izboljšal svoj počep."},
        {"role": "model", "content": "Kaj te zanima glede izvedbe?"},
        {"role": "user", "content": "Koliko serij in ponovitev naj naredim?"},
    ]
    answer = "Pri počepu naredi 3 serije po 8 ponovitev."
    result = _sanitize_unverified_training_dose(answer, messages)
    assert "3 serije" not in result
    assert "Preden določim serije" in result


def test_dumbbell_row_is_not_presented_as_a_vertical_pull_substitute():
    messages = [
        {"role": "user", "content": "V programu imam veslanje z ročkami v predklonu."},
        {"role": "model", "content": "Ali je to isto kot zgib?"},
        {"role": "user", "content": "Doma nimam droga za zgibe. Kako naj vseeno razmišljam o vadbi hrbta?"},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "horizontalni poteg" in reply
    assert "ne nadomesti vertikalnega zgiba" in reply
    assert "drog za zgibe" in reply


def test_repeated_table_row_warning_becomes_a_concise_follow_up():
    messages = [
        {"role": "user", "content": "Lahko delam veslanje pod mizo? Doma nimam nobene opreme."},
        {"role": "model", "content": "Veslanja pod mizo ne izvajaj, če ne moreš potrditi, da je miza stabilna."},
        {"role": "user", "content": "Na voljo imam samo lastno težo in tla."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert reply.startswith("Potem mize ne uporabljaj.")
    assert "ne enakovredna zamenjava" in reply
    assert len(reply) < 400

def test_progression_sanitizer_does_not_duplicate_the_same_rule():
    from coach_routes import _sanitize_power_and_progression_claims

    answer = (
        "Na naslednjem treningu povečaj težo. "
        "Pri naslednji vadbi dodaj breme, če je bilo vse lahko."
    )
    result = _sanitize_power_and_progression_claims(answer)
    assert result.count("Napredovanje je primerno šele") == 1


def test_programme_request_without_equipment_asks_instead_of_assuming_dumbbells_or_bench():
    messages = [{
        "role": "user",
        "content": (
            "Nimam bolečin, poškodb ali zdravstvenih omejitev. Želim izboljšati moč. "
            "Danes imam 30 minut in želim opraviti tri vaje."
        ),
    }]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "kaj imaš dejansko na voljo" in reply
    assert "če nimaš ničesar" in reply.casefold()
    assert "pogostost" not in reply.casefold()


def test_programme_request_with_schedule_and_gym_but_unknown_experience_asks_first():
    messages = [{
        "role": "user",
        "content": (
            "Nimam bolečin, poškodb ali zdravstvenih omejitev. Želim izboljšati "
            "funkcionalno pripravljenost. Imam polno opremljen fitnes in lahko "
            "treniram trikrat tedensko."
        ),
    }]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "izkušnje z vadbo moči" in reply
    assert "si začetnik" in reply


def test_known_experience_and_equipment_allow_onboarding_to_continue():
    messages = [{
        "role": "user",
        "content": (
            "Nimam bolečin, poškodb ali zdravstvenih omejitev. Sem začetnik, "
            "želim izboljšati moč, imam ročke in lahko treniram dvakrat tedensko."
        ),
    }]
    reply = _coaching_guardrail_reply(messages)
    assert reply is None


def test_absence_of_health_report_is_not_explicit_safety_clearance():
    assert not _has_explicit_safety_clearance(
        "Brez navedbe bolečin, poškodb ali gibalnih omejitev."
    )
    assert not _has_explicit_safety_clearance(
        "No pain, injuries or movement limitations reported."
    )


def test_missing_health_report_cannot_be_rephrased_as_user_confirmation():
    messages = [
        {"role": "user", "content": "Brez navedbe bolečin, poškodb ali gibalnih omejitev."},
    ]
    answer = "Ker si potrdil, da nimaš zdravstvenih omejitev ali bolečin, lahko začneva."
    cleaned = _sanitize_unverified_safety_claim(answer, messages)
    assert "Tega še nisi izrecno potrdil" in cleaned


def test_explicit_safety_clearance_still_overrides_a_missing_profile_note():
    assert _has_explicit_safety_clearance(
        "Brez navedbe bolečin, poškodb ali gibalnih omejitev. "
        "Nimam bolečin, poškodb ali zdravstvenih omejitev."
    )


def test_explicit_program_request_without_a_goal_must_ask_for_the_goal():
    messages = [
        {"role": "user", "content": (
            "Testni profil: uporabnik je izrecno potrdil, da nima bolečin, poškodb "
            "ali gibalnih omejitev. Profil: začetnik; na voljo ima ročke in lastno težo."
        )},
        {"role": "user", "content": (
            "V profilu imam zapisano, da sem začetnik, vendar treniram že deset let. "
            "Pripravi mi zahteven program."
        )},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "glavni cilj" in reply
    assert "moč" in reply
    assert "program" in reply


def test_weekly_program_request_requires_frequency_before_programming():
    messages = [
        {"role": "user", "content": (
            "Izrecno potrjujem, da nimam bolečin, poškodb ali zdravstvenih omejitev. "
            "Moj cilj je moč in mišična masa. Imam ročke in redno treniram že tri leta. "
            "Pripravi mi tedenski program."
        )},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "Kolikokrat na teden" in reply


def test_program_request_requires_session_duration_even_if_frequency_is_known():
    messages = [
        {"role": "user", "content": (
            "Izrecno potrjujem, da nimam bolečin, poškodb ali zdravstvenih omejitev. "
            "Moj cilj je moč in mišična masa. Imam ročke, redno treniram in lahko "
            "vadim trikrat tedensko. Pripravi mi program."
        )},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "Koliko časa" in reply


def test_programming_gate_allows_programme_after_goal_equipment_experience_and_schedule_are_known():
    messages = [
        {"role": "user", "content": (
            "Izrecno potrjujem, da nimam bolečin, poškodb ali zdravstvenih omejitev. "
            "Moj cilj je moč in mišična masa. Imam ročke in lastno težo, redno treniram že tri leta, "
            "lahko vadim trikrat tedensko, vsak trening pa naj traja 60 minut. "
            "Pripravi mi tedenski program."
        )},
    ]
    assert _coaching_guardrail_reply(messages) is None


def test_experience_prompt_does_not_claim_session_duration_is_known_from_frequency_alone():
    messages = [
        {"role": "user", "content": (
            "Nimam bolečin, poškodb ali omejitev. Moj cilj je moč. Imam ročke. "
            "Lahko treniram trikrat tedensko."
        )},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    assert "tedenska pogostost" in reply
    assert "trajanje treninga" not in reply
