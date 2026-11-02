import coach_routes


def test_system_prompt_has_non_bypassable_safety_gate():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "MANDATORY DECISION GATES – NON-NEGOTIABLE" in prompt
    assert '"none reported"' in prompt
    assert "ask one concise safety question and STOP" in prompt
    assert "do not include an exercise prescription" in prompt


def test_system_prompt_blocks_loaded_substitution_before_pain_clarification():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "first advise stopping that painful movement" in prompt
    assert "Do not diagnose" in prompt


def test_system_prompt_avoids_assumptions_about_balance_and_mobility():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "Do not assume the cause is ankle mobility" in prompt
    assert 'Never say a restriction can simply be "bypassed"' in prompt


def test_system_prompt_keeps_stabilization_conditional_and_tempo_exact():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "Do not add generic" in prompt
    assert "the phases are exactly 3 seconds eccentric, 1-second pause, 2 seconds concentric" in prompt


def test_system_prompt_requires_profile_and_persistence_honesty():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "Do not invent the user's name" in prompt
    assert "A chat reply does not itself save feedback" in prompt


def test_system_prompt_separates_general_education_from_exercise_prescription():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "GENERAL EDUCATION" in prompt
    assert "Do not append an irrelevant safety question" in prompt


def test_system_prompt_forbids_loaded_substitution_before_pain_context():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "Do not recommend any alternative loaded exercise" in prompt


def test_system_prompt_answers_saved_program_status_directly():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "answer that question directly first" in prompt
    assert "no saved change can be confirmed" in prompt


def test_system_prompt_does_not_confuse_coach_brand_with_user_identity():
    prompt = coach_routes.SYSTEM_PROMPT
    assert "not automatically the user" in prompt
    assert "do not address the user as Grega" in prompt



def _user_messages(*contents):
    return [{"role": "user", "content": content} for content in contents]


def test_server_guardrail_stops_individual_program_until_safety_is_confirmed():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        'Profil: {"goal":"hypertrophy","limitations":"none reported"}',
        "S star sem začetnik. Pripravi mi trening za celo telo.",
    ))
    assert reply is not None
    assert "Preden pripravim individualni trening" in reply
    assert "vaje in obremenitve" in reply


def test_none_reported_is_not_treated_as_safety_clearance():
    assert not coach_routes._has_explicit_safety_clearance('{"limitations":"none reported"}')


def test_explicit_no_pain_injury_and_limitation_confirmation_allows_next_step():
    text = "Nimam bolečin, poškodb ali gibalnih omejitev."
    assert coach_routes._has_explicit_safety_clearance(text)


def test_server_guardrail_stops_painful_exercise_before_substitution():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Pri izpadnem koraku me boli koleno. S čim naj zamenjam vajo?",
    ))
    assert reply is not None
    assert "ne nadomeščaj" in reply
    assert "Kje natančno se pojavi bolečina" in reply
    assert "Goblet počep" not in reply


def test_server_guardrail_asks_about_balance_before_suggesting_modification():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Pri počepu izgubljam ravnotežje. Kaj naj naredim?",
    ))
    assert reply is not None
    assert "V kateri fazi počepa" in reply
    assert "Podpora pod petami" not in reply


def test_server_guardrail_clarifies_ankle_restriction_before_modification():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Pri počepu me omejuje gibljivost gležnja. Kako prilagodim izvedbo?",
    ))
    assert reply is not None
    assert "omejen obseg gibanja v gležnju" in reply


def test_server_guardrail_does_not_interrupt_general_education():
    tempo_reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Kaj pomeni tempo 3-1-2-0 in ali je vedno najboljši?",
    ))
    assert tempo_reply is not None and "3 sekunde" in tempo_reply
    endurance_reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Ali naj delam samo MetCone za vzdržljivost?",
    ))
    assert endurance_reply is not None and "aerobne osnove" in endurance_reply


def test_server_guardrail_stops_progression_until_safety_confirmation():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Dva treninga sta bila lahka, vse serije sem končal z RIR 3+. Kaj zdaj?",
    ))
    assert reply is not None
    assert "Preden pripravim individualni trening" in reply


def test_server_guardrail_answers_persistence_question_directly():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Včeraj je bil trening pretežek. Ali si že prilagodil moj naslednji trening?",
    ))
    assert reply is not None
    assert "ne posodobi programa" in reply
    assert "Ne morem potrditi" in reply



def test_server_guardrail_detects_back_pain_during_rdl():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Pri RDL me zaboli v križu. Naj zmanjšam težo in nadaljujem?",
    ))
    assert reply is not None
    assert "ne izvajaj" in reply
    assert "obremenjeno vajo" in reply



def test_chat_short_circuits_to_server_safety_guardrail_without_calling_gemini(monkeypatch):
    from flask import Flask

    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    def forbidden_model_call(*_args, **_kwargs):
        raise AssertionError("Gemini must not be called when the server safety gate blocks prescription.")

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", forbidden_model_call)
    app = Flask(__name__)
    app.register_blueprint(coach_routes.coach_bp)
    response = app.test_client().post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={"messages": [{
            "role": "user",
            "content": "Profil: none reported. Pripravi mi individualni program za hipertrofijo.",
        }]},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["guardrail_applied"] is True
    assert body["response_source"] == "server_guardrail"
    assert "Preden pripravim individualni trening" in body["reply"]



def test_rep_and_load_question_is_blocked_until_safety_confirmation():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Moj cilj je razvoj moči, vendar sem začetnik. Kakšne ponovitve in obremenitve priporočaš?",
    ))
    assert reply is not None
    assert "Preden pripravim individualni trening" in reply


def test_metcon_education_is_accurate_and_not_a_personalized_schedule():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Želim izboljšati vzdržljivost. Ali naj delam samo metcone?",
    ))
    assert reply is not None
    assert "aerobne osnove" in reply
    assert "ni samodejno škodljiv" in reply
    assert "3 treninge tedensko" not in reply


def test_rom_education_uses_controlled_tolerable_range():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Ali moram pri vsaki vaji doseči čim večjo amplitudo?",
    ))
    assert reply is not None
    assert "nadzorovano" in reply
    assert "brez bolečine" in reply


def test_tempo_education_explains_all_four_phases_without_extra_safety_question():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Kaj pomeni tempo 3-1-2-0 in ali je vedno najboljši?",
    ))
    assert reply is not None
    assert "3 sekunde" in reply
    assert "1 sekundo" in reply
    assert "2 sekundi" in reply
    assert "0 sekund" in reply
    assert "bolečin" not in reply


def test_stabilization_question_is_answered_while_program_waits_for_safety():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Pripravi mi trening za hipertrofijo. Zakaj bi vključil stabilizacijske vaje?",
    ))
    assert reply is not None
    assert "ne dodajamo kot obveznega polnila" in reply
    assert "moram preveriti" in reply


def test_missed_training_does_not_trigger_double_volume():
    reply = coach_routes._coaching_guardrail_reply(_user_messages(
        "Prejšnji teden sem izpustil en trening. Naj danes naredim dvojni obseg?",
    ))
    assert reply is not None
    assert "ne nadomeščaj z dvojnim obsegom" in reply
