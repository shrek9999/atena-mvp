import json

from flask import Flask

from training.coaching_protocols import RDL_TECHNIQUE_PROTOCOL

import coach_routes


class FakeGeminiResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "Predlagam Goblet počep."}]}
            }]
        }).encode("utf-8")


def test_chat_adds_verified_exercise_alternatives_for_substitution_request(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeGeminiResponse()

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)
    app = Flask(__name__)
    app.register_blueprint(coach_routes.coach_bp)
    client = app.test_client()

    response = client.post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={"messages": [
            {
                "role": "user",
                "content": (
                    "Moj vadbeni profil:\n- Glavni cilj: mišična masa"
                    "\n- Varnost: nimam bolečin, poškodb ali omejitev"
                    "\n- Izkušnje: nekaj izkušenj"
                    "\n- Oprema: polno opremljen fitnes"
                    "\nTrenutni strukturirani program ATENE:"
                    "\nTrening A\n- Počep z ročkama ob telesu: 3 × 8–12"
                ),
            },
            {"role": "model", "content": "Razumem."},
            {"role": "user", "content": "Lahko zamenjava počep z ročkama ob telesu?"},
        ]},
    )

    assert response.status_code == 200
    assert response.get_json()["reply"] == "Predlagam Goblet počep."
    assert captured["timeout"] == 65
    prompt = captured["body"]["systemInstruction"]["parts"][0]["text"]
    assert "VERIFIED AVAILABLE ALTERNATIVES" in prompt
    assert "Goblet počep" in prompt
    assert "Počep z ročkama na ramenih" in prompt
    assert "Počep z ročkama ob telesu [squat]" in prompt


def test_chat_keeps_timeout_as_a_controlled_gateway_error(monkeypatch):
    import socket

    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

    def timeout_urlopen(_request, timeout):
        assert timeout == 65
        raise socket.timeout()

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", timeout_urlopen)
    app = Flask(__name__)
    app.register_blueprint(coach_routes.coach_bp)
    response = app.test_client().post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={"messages": [{"role": "user", "content": "Živjo."}]},
    )
    assert response.status_code == 504
    assert "predolgo" in response.get_json()["error"]



def test_chat_uses_rdl_technique_protocol_for_hinge_learning_request(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeGeminiResponse()

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)
    app = Flask(__name__)
    app.register_blueprint(coach_routes.coach_bp)
    response = app.test_client().post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={"messages": [
            {
                "role": "user",
                "content": "Z RDL imam težave. Kako naj ohranim raven hrbet pri predklonu?",
            },
            {"role": "model", "content": "Ali gre za bolečino ali učenje tehnike?"},
            {
                "role": "user",
                "content": "Ne boli me, nimam drugih omejitev, želim se naučiti tehnike.",
            },
        ]},
    )

    assert response.status_code == 200
    prompt = captured["body"]["systemInstruction"]["parts"][0]["text"]
    assert "RDL / predklon z nevtralno hrbtenico" in prompt
    assert "predklon z nevtralno hrbtenico ob steni" in prompt
    assert "bolečino/nelagodje" in prompt
    assert "Ne dodajaj elastike, ovite okoli stopal" in prompt


def test_rdl_protocol_remains_active_when_followup_does_not_repeat_exercise_name(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeGeminiResponse()

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)
    app = Flask(__name__)
    app.register_blueprint(coach_routes.coach_bp)
    response = app.test_client().post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={"messages": [
            {"role": "user", "content": "Pri RDL mi zaokroži hrbet. Kako naj se naučim pravilnega predklona?"},
            {"role": "model", "content": "Najprej preveriva, ali gre za bolečino ali učenje tehnike."},
            {"role": "user", "content": "Ne boli me, samo tehnike se želim naučiti."},
        ]},
    )

    assert response.status_code == 200
    prompt = captured["body"]["systemInstruction"]["parts"][0]["text"]
    assert "RDL / predklon z nevtralno hrbtenico" in prompt
    assert "predklon z nevtralno hrbtenico ob steni" in prompt


def test_clarified_balance_issue_does_not_repeat_the_same_guardrail_question():
    messages = [
        {"role": "user", "content": "Pri počepu izgubljam ravnotežje."},
        {"role": "model", "content": "V kateri fazi počepa izgubiš ravnotežje in ali je prisotna bolečina?"},
        {
            "role": "user",
            "content": (
                "Pri dvigu iz spodnjega položaja. Ne boli me, nimam poškodb ali omejitev. "
                "Kako naj izboljšam nadzor?"
            ),
        },
    ]

    reply = coach_routes._coaching_guardrail_reply(messages)
    assert reply is not None
    assert "Ali se enaka nestabilnost pojavi tudi pri počepu z lastno težo" in reply
    assert "Goblet" not in reply


def test_clarified_ankle_mobility_asks_about_observable_heel_lift():
    messages = [
        {"role": "user", "content": "Pri počepu me omejuje gibljivost gležnja."},
        {"role": "model", "content": "Ali gre za obseg, bolečino ali ravnotežje?"},
        {
            "role": "user",
            "content": (
                "Ne boli me, nimam poškodb; gre samo za omejen obseg gibanja v gležnju, "
                "ne za izgubo ravnotežja. Kako naj prilagodim počep?"
            ),
        },
    ]

    reply = coach_routes._coaching_guardrail_reply(messages)
    assert reply is not None
    assert "ali se ti pri počepu peta dvigne od tal" in reply


def test_unclarified_balance_issue_still_stops_for_assessment():
    messages = [
        {"role": "user", "content": "Pri počepu izgubljam ravnotežje."},
    ]

    reply = coach_routes._coaching_guardrail_reply(messages)

    assert reply is not None
    assert "V kateri fazi počepa" in reply


def test_verified_exercise_context_filters_bodyweight_profile_without_inventing_load():
    messages = [{
        "role": "user",
        "content": (
            'Profil: {"goal":"hypertrophy","experience":"beginner",'
            '"equipment":["bodyweight"],"sessions_per_week":2}'
        ),
    }]

    context = coach_routes._verified_exercise_catalogue_context(messages)

    assert "Počep z lastno težo (air squat)" in context
    assert "Goblet počep" not in context
    assert "Počep z ročkama na ramenih" not in context


def test_verified_exercise_context_includes_only_declared_dumbbell_options():
    messages = [{
        "role": "user",
        "content": (
            'Profil: {"goal":"hypertrophy","experience":"beginner",'
            '"equipment":["dumbbell","bodyweight"]}'
        ),
    }]

    context = coach_routes._verified_exercise_catalogue_context(messages)

    assert "Goblet počep" in context
    assert "Počep z lastno težo (air squat)" in context
    assert "Počep zadaj" not in context


def test_band_row_requires_explicitly_confirmed_anchor_point():
    base = {
        "goal": "functional",
        "experience": "intermediate",
        "equipment": ["resistance_band", "dumbbell", "bodyweight"],
    }
    without_anchor = coach_routes._verified_exercise_catalogue_context([{
        "role": "user", "content": "Profil: " + json.dumps(base),
    }])
    with_anchor = coach_routes._verified_exercise_catalogue_context([{
        "role": "user", "content": "Profil: " + json.dumps({**base, "equipment": base["equipment"] + ["anchor_point"]}),
    }])

    assert "Veslanje z elastiko" not in without_anchor
    assert "Veslanje z elastiko" in with_anchor


def test_power_sanitizer_removes_unsupported_nervous_response_recovery_claim():
    answer = (
        "Dolgi odmori so nujni, da se mišični sistem in živčni odziv "
        "v celoti spočijeta za naslednji poskus."
    )

    cleaned = coach_routes._sanitize_power_and_progression_claims(answer)

    assert "živčni odziv" not in cleaned
    assert "mišični sistem" not in cleaned
    assert "hitrosti in kakovosti ponovitev" in cleaned


def test_onboarding_safety_gate_precedes_equipment_question():
    messages = [
        {"role": "user", "content": "Rad bi izboljšal splošno telesno pripravljenost doma."},
        {"role": "model", "content": "Kakšno opremo imaš na voljo doma?"},
    ]

    reply = coach_routes._coaching_guardrail_reply(messages)

    assert reply is not None
    assert "najprej preveriti varnost" in reply
    assert "bolečine, poškodbe" in reply
    assert "kakšno opremo" not in reply


def test_onboarding_safety_gate_precedes_time_question():
    messages = [
        {"role": "user", "content": "Želim redno trenirati, vendar nimam vedno enako časa."},
        {"role": "model", "content": "Koliko časa imaš običajno na voljo za vadbo?"},
    ]

    reply = coach_routes._coaching_guardrail_reply(messages)

    assert reply is not None
    assert "najprej preveriti varnost" in reply


def test_pending_safety_acknowledges_frequency_without_claiming_it_was_saved():
    messages = [
        {"role": "user", "content": "Rad bi bil bolj fit."},
        {"role": "model", "content": "Ali imaš bolečine, poškodbe ali omejitve?"},
        {"role": "user", "content": "Lahko vadim dvakrat na teden."},
    ]

    reply = coach_routes._coaching_guardrail_reply(messages)

    assert reply is not None
    assert "dvakrat tedensko" in reply
    assert "Zabeležil sem" not in reply
    assert "bolečine, poškodbe" in reply


def test_pending_safety_acknowledges_goal_change():
    messages = [
        {"role": "user", "content": "Rad bi bil bolj funkcionalen."},
        {"role": "model", "content": "Ali imaš bolečine, poškodbe ali omejitve?"},
        {"role": "user", "content": "Pomembnejša mi je vzdržljivost kot mišična masa."},
    ]

    reply = coach_routes._coaching_guardrail_reply(messages)

    assert reply is not None
    assert "prednost vzdržljivost" in reply
    assert "bolečine, poškodbe" in reply


def test_pending_safety_acknowledges_equipment_context():
    messages = [
        {"role": "user", "content": "Rad bi izboljšal kondicijo."},
        {"role": "model", "content": "Ali imaš bolečine, poškodbe ali omejitve?"},
        {"role": "user", "content": "Doma imam sobno kolo in lahko hodim na sprehode."},
    ]

    reply = coach_routes._coaching_guardrail_reply(messages)

    assert reply is not None
    assert "Sobno kolo in sprehodi" in reply
    assert "bolečine, poškodbe" in reply


def test_slovene_coaching_normalizer_fixes_live_benchmark_typos():
    answer = (
        "Predeniva greva na prvi korak. Lahko varno začutiva. "
        "V lasti imej 2 ponovitvi. Pri zglobom bodi pozoren. "
        "Njen namen je umiritev."
    )

    cleaned = coach_routes._normalize_slovene_coaching_terms(answer)

    assert "Preden greva" in cleaned
    assert "začneva" in cleaned
    assert "v rezervi imej" in cleaned.casefold()
    assert "pri sklepu" in cleaned.casefold()
    assert "Namen je" in cleaned


def test_progression_sanitizer_blocks_single_session_prihodnjic_promise():
    answer = (
        "Ko z izbrano težo brez težav opraviš zgornjo mejo ponovitev pri vseh serijah, "
        "lahko prihodnjič minimalno povečaš težo ali dodaš ponovitev."
    )

    cleaned = coach_routes._sanitize_power_and_progression_claims(answer)

    assert "prihodnjič minimalno povečaš" not in cleaned
    assert "vsaj dveh primerljivih treningih" in cleaned
    assert "ustrezno regeneracijo" in cleaned


def test_progression_sanitizer_separates_replacement_from_next_sentence():
    answer = (
        "Če je bilo lahko, naslednji teden povečaj obremenitev."
        "Napredovanje je primerno šele po dveh uspešnih treningih."
    )

    cleaned = coach_routes._sanitize_power_and_progression_claims(answer)

    assert "odmerek.\n\nNapredovanje" in cleaned


def test_structured_profile_equipment_is_authoritative_over_unavailable_mentions():
    messages = [{
        "role": "user",
        "content": (
            'Profil: {"goal":"hypertrophy","experience":"beginner",'
            '"equipment":["bodyweight"]}. Nimam ročk, klopi ali elastik.'
        ),
    }]

    available = coach_routes._profile_available_equipment(messages)
    context = coach_routes._verified_exercise_catalogue_context(messages)

    assert available == {"bodyweight"}
    assert "Goblet počep" not in context
    assert "Potisk z ročkami" not in context


def test_hinge_language_normalizer_uses_neutral_spine_not_flat_back():
    answer = (
        "Pri RDL izvedi predklon z ravnim hrbtom, kjer še držiš raven hrbet; "
        "hrbet ostane popolnoma raven."
    )
    cleaned = coach_routes._normalize_slovene_coaching_terms(answer)
    assert "z ravnim hrbtom" not in cleaned.casefold()
    assert "raven hrbet" not in cleaned.casefold()
    assert "z nevtralno hrbtenico" in cleaned.casefold()
    assert "nevtralni položaj hrbtenice" in cleaned.casefold()


def test_normalizer_removes_malformed_inline_markup_and_repairs_vadeci_word():
    cleaned = coach_routes._normalize_slovene_coaching_terms(
        "Profil prilagodiva na raven srednje zahtevnega vad<strong>inega."
    )
    assert "<strong>" not in cleaned.casefold()
    assert "vadečega" in cleaned.casefold()


def test_strength_rest_guard_preserves_recovery_in_short_sessions():
    answer = (
        "Počep: 3 serije po 8 ponovitev, odmor 90 sekund. "
        "RDL: 3 serije po 8 ponovitev, odmor 90 sekund."
    )
    messages = [{"role": "user", "content": "Želim 30-minutni trening moči."}]
    cleaned = coach_routes._sanitize_strength_rest_intervals(answer, messages)
    assert "90 sekund" not in cleaned
    assert cleaned.count("2–3 min") == 2
    assert "zmanjša število vaj ali delovnih serij" in cleaned


def test_strength_rest_guard_does_not_change_accessory_rest_without_strength_context():
    answer = "Lateral raises: 3 serije po 12 ponovitev, odmor 90 sekund."
    messages = [{"role": "user", "content": "Želim lahek trening za splošno gibanje."}]
    cleaned = coach_routes._sanitize_strength_rest_intervals(answer, messages)
    assert "90 sekund" in cleaned


def test_progression_sanitizer_does_not_duplicate_existing_two_exposure_guidance():
    answer = (
        "To je prva uspešna izpostavitev. Počakajmo še na eno ponovitev istega dosežka. "
        "Za naslednji trening ohrani enako težo in ne dodajaj bremena."
    )
    cleaned = coach_routes._sanitize_power_and_progression_claims(answer)
    assert "počakajmo še na eno ponovitev istega dosežka" in cleaned.casefold()
    assert cleaned.count("Napredovanje je primerno šele") == 0
    assert "ne dodajaj bremena" in cleaned.casefold()
    assert "Ohrani trenutno obremenitev" not in cleaned


def test_rdl_protocol_includes_fourth_tactile_lumbar_control_point():
    assert "četrto taktilno kontrolno točko" in RDL_TECHNIQUE_PROTOCOL.casefold()
    assert "ne sili ledvene krivine v sploščanje" in RDL_TECHNIQUE_PROTOCOL.casefold()


def test_power_sanitizer_removes_unsupported_claim_of_nervous_system_adaptation():
    answer = "Telo in živčni sistem se lepo prilagodila na zadnja dva treninga."
    cleaned = coach_routes._sanitize_power_and_progression_claims(answer)
    assert "živčni sistem" not in cleaned
    assert "odziv na trening je bil dober" in cleaned


def test_hinge_language_normalizer_replaces_flat_back_cues_with_neutral_spine():
    answer = (
        "Pri predklonu z ravnim hrbtom naj hrbet ohranjaš povsem raven "
        "in stabilen skozi celoten gib."
    )
    cleaned = coach_routes._normalize_slovene_coaching_terms(answer)
    assert "z nevtralno hrbtenico" in cleaned
    assert "hrbtenica ohranja naravni nevtralni položaj" in cleaned
    assert "ravnim hrbtom" not in cleaned


def test_onboarding_sanitizer_replaces_equipment_first_question_with_safety_gate():
    messages = [{"role": "user", "content": "Želim izboljšati kondicijo brez teka."}]
    answer = "Katero opremo imaš doma in kakšne aktivnosti so ti všeč?"
    cleaned = coach_routes._sanitize_onboarding_questions(answer, messages)
    assert "bolečine, poškodbe" in cleaned
    assert cleaned.count("?") == 1
    assert "opremo" not in cleaned


def test_onboarding_sanitizer_keeps_only_safety_question_when_model_bundles_intake():
    messages = [{"role": "user", "content": "Rad bi pridobil mišično maso."}]
    answer = (
        "Kakšno opremo imaš na voljo? Ali imaš kakšne zdravstvene omejitve ali bolečine?"
    )
    cleaned = coach_routes._sanitize_onboarding_questions(answer, messages)
    assert "bolečine, poškodbe" in cleaned
    assert cleaned.count("?") == 1
    assert "opremo" not in cleaned


def test_onboarding_sanitizer_trims_compound_experience_and_duration_question():
    messages = [{
        "role": "user",
        "content": (
            "Izrecno potrjujem, da nimam bolečin, poškodb ali omejitev. "
            "Želim funkcionalno pripravljenost, imam fitnes in treniram trikrat tedensko."
        ),
    }]
    answer = (
        "Kako bi opisal svoje izkušnje z vadbo moči in koliko časa imaš na voljo?"
    )
    cleaned = coach_routes._sanitize_onboarding_questions(answer, messages)
    assert cleaned == "Kako bi opisal svoje izkušnje z vadbo moči?"
    assert cleaned.count("?") == 1


def test_onboarding_sanitizer_preserves_a_single_explicit_safety_question():
    messages = [{"role": "user", "content": "Želim izboljšati splošno pripravljenost."}]
    answer = "Ali imaš trenutno kakršne koli bolečine, poškodbe ali zdravstvene omejitve?"
    assert coach_routes._sanitize_onboarding_questions(answer, messages) == answer


def test_slovene_coaching_normalizer_cleans_common_exercise_instruction_typos():
    answer = (
        "Predenava izbereva vajo z dve ročkama. Trg in trup ostajata pokončna; "
        "spostiš ročke in razbremeniša gib."
    )
    cleaned = coach_routes._normalize_slovene_coaching_terms(answer)
    assert "Preden izbereva" in cleaned
    assert "z dvema ročkama" in cleaned
    assert "Trup naj ostane pokončen" in cleaned
    assert "spustiš ročke" in cleaned
    assert "razbremeniš gib" in cleaned


def test_deadlift_to_rdl_substitution_prompt_explains_non_equivalence(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeGeminiResponse()

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)
    app = Flask(__name__)
    app.register_blueprint(coach_routes.coach_bp)
    client = app.test_client()
    response = client.post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={"messages": [
            {
                "role": "user",
                "content": (
                    "Moj vadbeni profil:\n- Glavni cilj: moč in mišična masa"
                    "\n- Varnost: nimam bolečin, poškodb ali omejitev"
                    "\n- Izkušnje: redno treniram"
                    "\n- Oprema: ročke"
                    "\nTrenutni strukturirani program ATENE:"
                    "\nTrening A\n- Mrtvi dvig: 3 × 5"
                ),
            },
            {
                "role": "user",
                "content": "Nimam olimpijske palice. S čim lahko zamenjam mrtvi dvig?",
            },
        ]},
    )
    assert response.status_code == 200
    prompt = captured["body"]["systemInstruction"]["parts"][0]["text"]
    assert "not a mechanically identical replacement" in prompt
    assert "different range-of-motion and loading profile" in prompt


def test_deadlift_to_rdl_equivalence_claim_is_corrected():
    messages = [
        {"role": "user", "content": "Trenutni program: mrtvi dvig z drogom, 3 × 5."},
        {"role": "user", "content": "Nimam olimpijske palice. S čim lahko zamenjam mrtvi dvig?"},
    ]
    answer = (
        "RDL (romunski mrtvi dvig) popolnoma posnema mehaniko mrtvega dviga "
        "s poudarkom na kolčnem iztegu."
    )
    cleaned = coach_routes._sanitize_deadlift_substitution_claims(answer, messages)
    assert "ni biomehansko enak klasičnemu mrtvemu dvigu" in cleaned
    assert "popolnoma posnema mehaniko" not in cleaned

def test_deadlift_to_rdl_reply_does_not_invent_a_new_training_dose():
    messages = [
        {
            "role": "user",
            "content": (
                "Uporabnik nima bolečin, poškodb ali omejitev; želi ohraniti vzorec kolčnega iztega; "
                "na voljo ima ročke, nima pa palice ali klopi."
            ),
        },
        {"role": "user", "content": "Danes nimam dostopa do olimpijske palice. V programu imam mrtvi dvig. S čim ga lahko zamenjam?"},
        {"role": "user", "content": "Na voljo imam samo ročke in lastno težo, klopi nimam."},
        {"role": "user", "content": "Želim ohraniti vzorec kolčnega iztega in približno enak namen treninga."},
    ]
    answer = (
        "Predlagam RDL z ročkami: 3–4 serije po 8–12 ponovitev, tempo 2–1–1–0, "
        "RIR 2–3 in 2–3 minute odmora."
    )
    cleaned = coach_routes._sanitize_unverified_exercise_parameters(answer, messages)
    assert "ni biomehansko enak klasičnemu mrtvemu dvigu" in cleaned
    assert "3–4 serije" not in cleaned
    assert "8–12 ponovitev" not in cleaned
    assert "2–1–1–0" not in cleaned
    assert "RIR 2–3" not in cleaned
    assert "prvotni odmerek" in cleaned


def test_deadlift_to_rdl_reply_keeps_existing_program_dose_context():
    messages = [
        {"role": "user", "content": "Trenutni program: mrtvi dvig 3 × 5."},
        {"role": "user", "content": "Nimam olimpijske palice. S čim lahko zamenjam mrtvi dvig?"},
    ]
    answer = "RDL z ročkami: 3 × 8 ponovitev."
    assert coach_routes._sanitize_unverified_exercise_parameters(answer, messages) == answer


def test_single_successful_squat_exposure_does_not_gain_invented_sets_or_tempo():
    messages = [
        {
            "role": "user",
            "content": (
                "Uporabnik je izrecno potrdil, da nima bolečin, poškodb ali gibalnih omejitev. "
                "Pri počepu je dosegel vse serije po 10 ponovitev z RIR 3, vendar je bil to "
                "šele prvi tak uspešen trening."
            ),
        },
        {"role": "user", "content": "Pri počepu sem opravil vse serije po 10 ponovitev in imel približno 3 ponovitve v rezervi."},
        {"role": "user", "content": "Tehnika je bila dobra, vendar je bil to šele prvi tak uspešen trening."},
        {"role": "user", "content": "Kaj naj naredim pri naslednji vadbi?"},
    ]
    answer = (
        "Izvedi 3 × 10 počepov z isto težo in tempom 2–1–1–0. "
        "Povečanje obremenitve počakaj do druge uspešne izpostavitve."
    )
    cleaned = coach_routes._sanitize_unverified_exercise_parameters(answer, messages)
    assert "enakim številom serij kot zadnjič" in cleaned
    assert "10 ponovitev" in cleaned
    assert "RIR 3" in cleaned
    assert "3 × 10" not in cleaned
    assert "2–1–1–0" not in cleaned
    assert "ne bom ugibal" in cleaned

def test_rdl_substitution_follow_up_acknowledges_equipment_without_repeating_full_answer():
    messages = [
        {"role": "user", "content": "Uporabnik nima bolečin ali omejitev; na voljo ima ročke, nima palice ali klopi."},
        {"role": "user", "content": "Danes nimam dostopa do olimpijske palice. V programu imam mrtvi dvig. S čim ga lahko zamenjam?"},
        {"role": "model", "content": "RDL je sorodna alternativa, vendar ni biomehansko enak mrtvemu dvigu. Kakšen je bil prvotni odmerek mrtvega dviga in katere teže ročk imaš?"},
        {"role": "user", "content": "Na voljo imam samo ročke in lastno težo, klopi nimam."},
    ]
    cleaned = coach_routes._sanitize_unverified_exercise_parameters(
        "Predlagam RDL z ročkami: 3 × 10 ponovitev.", messages
    )
    assert cleaned.startswith("Razumem: imaš ročke in lastno težo")
    assert "prvotni odmerek" in cleaned
    assert cleaned.count("?") == 1


def test_rdl_substitution_follow_up_acknowledges_training_intent():
    messages = [
        {"role": "user", "content": "Na voljo ima ročke, nima palice ali klopi."},
        {"role": "user", "content": "V programu imam mrtvi dvig. S čim ga lahko zamenjam?"},
        {"role": "model", "content": "RDL ni biomehansko enak mrtvemu dvigu. Kakšen je bil prvotni odmerek mrtvega dviga?"},
        {"role": "user", "content": "Želim ohraniti vzorec kolčnega iztega in približno enak namen treninga."},
    ]
    cleaned = coach_routes._sanitize_unverified_exercise_parameters(
        "RDL z ročkami: 3–4 serije po 8–12 ponovitev.", messages
    )
    assert cleaned.startswith("Se strinjam: ohraniva soroden vzorec predklona")
    assert "ni biomehansko enak" in cleaned
    assert cleaned.count("?") == 1


def test_single_exposure_progression_first_reply_holds_load_and_asks_about_recovery():
    messages = [
        {
            "role": "user",
            "content": (
                "KONTEKST TESTNEGA UPORABNIKA (podatki profila; upoštevaj kot podane, "
                "ne sklepaj več, kot piše): Uporabnik je izrecno potrdil, da nima bolečin, "
                "poškodb ali gibalnih omejitev. Pri počepu je dosegel vse serije po 10 "
                "ponovitev z RIR 3, vendar je bil to šele prvi tak uspešen trening."
                "\n\nUPORABNIKOVO SPOROČILO: Pri počepu sem opravil vse serije po 10 "
                "ponovitev in imel približno 3 ponovitve v rezervi. Lahko naslednjič povečam težo?"
            ),
        },
    ]
    cleaned = coach_routes._sanitize_unverified_exercise_parameters(
        "Povečaj težo za 2,5 kg in naredi 3 × 10.", messages
    )
    assert "Za zdaj še ne povečuj obremenitve" in cleaned
    assert "isto težo" in cleaned
    assert "enakim številom serij kot zadnjič" in cleaned
    assert "24–48 urah" in cleaned
    assert "2,5 kg" not in cleaned


def test_single_exposure_progression_technique_follow_up_does_not_ask_about_equipment():
    messages = [
        {"role": "user", "content": "Pri počepu sem dosegel vse serije po 10 ponovitev z RIR 3, vendar je bil to šele prvi tak uspešen trening."},
        {"role": "user", "content": "Tehnika je bila dobra, vendar je bil to šele prvi tak uspešen trening."},
    ]
    cleaned = coach_routes._sanitize_unverified_exercise_parameters(
        "Ali imaš za naslednji trening na voljo enako opremo?", messages
    )
    assert "tehnika je bila dobra" in cleaned.casefold()
    assert "isto obremenitev" in cleaned
    assert "regeneracijo" in cleaned
    assert "opremo" not in cleaned


def test_two_exposure_progression_waits_for_recovery_and_avoids_invented_load():
    profile = (
        "V programu je cilj 8–10 ponovitev; v dveh zaporednih primerljivih treningih "
        "je izvedel vse serije po 10 ponovitev z RIR 3 in stabilno tehniko."
    )
    messages = [
        {"role": "user", "content": profile},
        {"role": "user", "content": "Vse serije sem opravil. Na koncu vsake serije bi lahko naredil še približno tri ponovitve."},
    ]
    first = coach_routes._sanitize_unverified_exercise_parameters(
        "Povečaj obremenitev za 2 kg in naredi 3 × 8.", messages
    )
    assert "preveriva še regeneracijo" in first
    assert "2 kg" not in first
    assert "3 × 8" not in first

    messages.append({"role": "model", "content": first})
    messages.append({"role": "user", "content": "Tehnika je bila dobra in trening ni bil pretežek."})
    second = coach_routes._sanitize_unverified_exercise_parameters(
        "Izvedi 3 serije po 8 ponovitev.", messages
    )
    assert "regeneracijo" in second
    assert second.count("?") == 1

    messages.append({"role": "model", "content": second})
    messages.append({"role": "user", "content": "Naslednji dan sem se normalno počutil in bil spočit."})
    final = coach_routes._sanitize_unverified_exercise_parameters(
        "Povečaj za 2 kg in izvedi 3 × 8.", messages
    )
    assert "najmanjše razpoložljivo povečanje" in final
    assert "ne bom ugibal kilogramov" in final
    assert "2 kg" not in final
    assert "3 × 8" not in final



def test_english_rdl_technique_request_receives_english_protocol(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeGeminiResponse()

    monkeypatch.setattr(coach_routes.urllib.request, "urlopen", fake_urlopen)
    app = Flask(__name__)
    app.register_blueprint(coach_routes.coach_bp)
    response = app.test_client().post(
        "/coach/chat",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={"messages": [
            {"role": "user", "content": "My Romanian deadlift technique is poor; my back rounds. How can I learn the hip hinge?"},
            {"role": "model", "content": "Is this pain or a technique issue?"},
            {"role": "user", "content": "No pain, injury, or movement limitations. I only want to learn the technique."},
        ]},
    )

    assert response.status_code == 200
    prompt = captured["body"]["systemInstruction"]["parts"][0]["text"]
    assert "Romanian deadlift (RDL) – TECHNIQUE COACHING" in prompt
    assert "Wall hip hinge" in prompt
    assert "Do not demand excessive rigidity" in prompt
    assert "predklon z nevtralno hrbtenico ob steni" not in prompt
