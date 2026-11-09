import json

from flask import Flask

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
    assert "RDL / PREDKLON Z RAVNIM HRBTOM" in prompt
    assert "Predklon z ravnim hrbtom ob steni" in prompt
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
    assert "RDL / PREDKLON Z RAVNIM HRBTOM" in prompt
    assert "Predklon z ravnim hrbtom ob steni" in prompt


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
    assert "v rezervi imej" in cleaned
    assert "sklepom" in cleaned
    assert "Namen je" in cleaned


def test_progression_sanitizer_separates_replacement_from_next_sentence():
    answer = (
        "Lahko naslednji teden povečamo obremenitev."
        "Napredovanje je primerno šele po dveh uspešnih treningih."
    )

    cleaned = coach_routes._sanitize_power_and_progression_claims(answer)

    assert "obremenitev.\n\nNapredovanje" in cleaned


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
