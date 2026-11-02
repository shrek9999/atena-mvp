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
