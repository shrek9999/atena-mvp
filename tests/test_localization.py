from training.localization import (
    language_instruction, localize_guardrail_reply, normalize_language,
    resolve_response_language,
)


def test_explicit_language_tag_takes_precedence_over_message_detection():
    messages = [{"role": "user", "content": "Želim izboljšati moč."}]
    assert resolve_response_language(messages, "en-US") == "en"
    assert resolve_response_language(messages, "sl-SI") == "sl"


def test_latest_user_turn_detects_slovene_and_defaults_to_english():
    assert resolve_response_language([{"role": "user", "content": "Želim trenirati."}]) == "sl"
    assert resolve_response_language([{"role": "user", "content": "I want to get stronger."}]) == "en"
    assert resolve_response_language([]) == "en"


def test_unsupported_language_tag_does_not_override_detection():
    assert normalize_language("fr-FR") is None
    assert resolve_response_language([{"role": "user", "content": "I want a plan."}], "fr-FR") == "en"


def test_language_instruction_is_explicit_and_single_language():
    assert "English (en)" in language_instruction("en")
    assert "Slovenian (sl-SI)" in language_instruction("sl")


def test_urgent_safety_guardrail_is_localized_without_changing_action():
    sl = (
        "Ker noge ne moreš normalno obremeniti, potrebuješ nujno zdravstveno oceno še danes. "
        "Ne izvajaj počepov, izpadnih korakov ali drugih obremenjenih vaj. Pokliči 112."
    )
    en = localize_guardrail_reply(sl, "en")
    assert "urgent medical assessment today" in en
    assert "Do not perform squats" in en
    assert "112" in en


def test_slovene_guardrail_remains_slovene_when_slovene_selected():
    sl = "Oteklina ali zaklepanje kolena sta opozorilna znaka."
    assert localize_guardrail_reply(sl, "sl") == sl


def test_english_individualized_dose_is_withheld_before_safety_clearance():
    from coach_routes import _sanitize_unverified_training_dose

    messages = [{"role": "user", "content": "Please give me a squat workout."}]
    answer = "Do 3 sets of 8 reps. Keep each repetition controlled."
    safe = _sanitize_unverified_training_dose(answer, messages, "en")
    assert "3 sets of 8 reps" not in safe
    assert "Before prescribing sets, repetitions, or a load" in safe
    assert "pain, injuries, movement limitations" in safe


def test_english_explicit_safety_clearance_allows_individualized_dose():
    from coach_routes import _sanitize_unverified_training_dose

    messages = [{
        "role": "user",
        "content": "I have no pain, injuries, or movement limitations.",
    }]
    answer = "Do 3 sets of 8 reps."
    assert _sanitize_unverified_training_dose(answer, messages, "en") == answer


def test_english_safety_claim_cannot_infer_clearance_from_missing_information():
    from coach_routes import _sanitize_unverified_safety_claim

    messages = [{"role": "user", "content": "I want to get stronger."}]
    answer = "Since you did not mention pain, I assume you have no injuries or limitations."
    safe = _sanitize_unverified_safety_claim(answer, messages)
    assert "You have not explicitly confirmed that" in safe
    assert "Do you currently have any pain" in safe


def test_english_unanswered_safety_question_still_blocks_programming():
    from coach_routes import _coaching_guardrail_reply

    messages = [
        {"role": "user", "content": "I want to improve my fitness."},
        {
            "role": "model",
            "content": "Do you currently have any pain, injuries, movement limitations, or medical restrictions?",
        },
        {"role": "user", "content": "I can train twice a week."},
    ]
    reply = _coaching_guardrail_reply(messages)
    assert reply is not None
    localized = localize_guardrail_reply(reply, "en")
    assert "clarify one safety point" in localized
    assert "pain, injury, movement limitation" in localized


def test_english_knee_swelling_triggers_a_safety_guardrail():
    from coach_routes import _coaching_guardrail_reply

    reply = _coaching_guardrail_reply([
        {"role": "user", "content": "My knee is swollen. Can I keep squatting?"},
    ])
    assert reply is not None
    localized = localize_guardrail_reply(reply, "en")
    assert "Knee swelling or locking" in localized
    assert "avoid squats" in localized


def test_english_no_pain_confirmation_is_recognized():
    from coach_routes import _has_explicit_no_pain_confirmation

    assert _has_explicit_no_pain_confirmation("I have no pain right now.")
