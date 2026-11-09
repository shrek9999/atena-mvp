"""Regression tests for ATENA's general-population coaching standard."""

from training.catalogue import get_exercise, load_catalogue
from coach_routes import SYSTEM_PROMPT, _normalize_slovene_coaching_terms, _sanitize_power_and_progression_claims
from training.program import generate_program


def test_superman_is_a_verified_bodyweight_mat_accessory_not_a_primary_strength_lift():
    exercise = get_exercise("superman")
    assert exercise is not None
    assert exercise["equipment"] == ["bodyweight"]
    assert exercise["level"] == "beginner"
    assert exercise["training_role"] == "accessory"
    assert exercise["loading_potential"] == "low"
    assert "general_fitness" in exercise["goals"]
    assert exercise["regressions"]
    assert exercise["progressions"]
    assert any("ledven" in cue.casefold() for cue in exercise["common_errors"])


def test_catalogue_keeps_superman_available_as_a_complementary_exercise():
    records = load_catalogue()
    exercise = next(item for item in records if item["id"] == "superman")
    assert exercise["movement_pattern"] == "trunk_control"
    assert exercise["stability_role"] == "supporting"


def test_coach_prompt_prioritizes_simple_effective_bodyweight_exercises():
    prompt = SYSTEM_PROMPT.casefold()
    assert "a controlled bodyweight squat" in prompt
    assert "3 × 8 bodyweight squats" in prompt
    assert "do not replace them with advanced variations merely to make the plan look sophisticated" in prompt


def test_coach_prompt_requires_explicit_equipment_and_rejects_unsafe_table_rows():
    prompt = SYSTEM_PROMPT.casefold()
    assert "never assume a table" in prompt
    assert "do not prescribe table rows" in prompt
    assert "missing pulling option is a real limitation" in prompt


def test_coach_prompt_has_observable_regression_and_progression_criteria():
    prompt = SYSTEM_PROMPT.casefold()
    assert "across at least two exposures" in prompt
    assert "regression triggers" in prompt
    assert "progression triggers" in prompt
    assert "change one variable at a time" in prompt


def test_coach_prompt_keeps_mat_based_trunk_work_as_complementary_not_a_replacement_for_pulling():
    prompt = SYSTEM_PROMPT.casefold()
    assert "mat-based exercises" in prompt
    assert "do not pretend a prone back exercise fully replaces loaded pulling" in prompt


def test_coach_prompt_requires_concise_non_repetitive_exercise_cues():
    prompt = SYSTEM_PROMPT.casefold()
    assert "2–4 concise, non-repetitive coaching cues" in prompt
    assert "avoid repeating generic amplitude and safety paragraphs" in prompt



def test_coach_prompt_uses_beginner_strength_repetition_ranges_consistently():
    prompt = SYSTEM_PROMPT.casefold()
    assert "default to 8–12 repetitions (often begin around 10)" in prompt
    assert "about 2–3 repetitions in reserve" in prompt
    assert "do not use 6–10, 4–6 or 5–8 as a generic beginner strength range" in prompt
    assert "6–10 or 8–12 may be appropriate" not in prompt


def test_coach_prompt_avoids_unsupported_nervous_system_claims_for_power_training():
    prompt = SYSTEM_PROMPT.casefold()
    assert "do not claim \"complete recovery of the nervous system\"" in prompt
    assert "explain rest in terms of maintaining performance and movement speed" in prompt
    assert "do not describe rest as complete nervous-system recovery" in prompt


def test_coach_prompt_handles_poor_recovery_without_guessing_the_cause():
    prompt = SYSTEM_PROMPT.casefold()
    assert "poor recovery is an observed response, not a diagnosis of its cause" in prompt
    assert "do not assume the user trained near failure if that was not reported" in prompt
    assert "do not automatically change weekly frequency" in prompt


def test_coach_prompt_requires_two_comparable_exposures_before_promising_progression():
    prompt = SYSTEM_PROMPT.casefold()
    assert "at least two comparable exposures" in prompt
    assert "do not promise a fixed increase \"next week\"" in prompt


def test_power_language_is_normalized_to_output_and_technique_not_nervous_system_claims():
    answer = "Izvajaj z maksimalno hitrostjo in ustrezno spočitim živčno-mišičnim sistemom."
    cleaned = _sanitize_power_and_progression_claims(answer)
    assert "živčno-mišičnim sistemom" not in cleaned.casefold()
    assert "ohranjanje hitrosti in kakovosti ponovitev" in cleaned.casefold()


def test_progression_paragraph_requires_two_comparable_successful_exposures():
    answer = ("**Pravilo napredovanja:** Ko dosežeš zgornjo mejo v vseh serijah, "
              "lahko naslednji teden povečaš težo.\n\nSporoči, kako je šlo.")
    cleaned = _sanitize_power_and_progression_claims(answer)
    assert "vsaj dveh primerljivih treningih" in cleaned
    assert "naslednji teden povečaš" not in cleaned
    assert "Sporoči, kako je šlo." in cleaned


def test_unheaded_next_week_progression_promise_is_rewritten():
    answer = "Naslednji teden lahko povečaš obremenitev za malo."
    cleaned = _sanitize_power_and_progression_claims(answer)
    assert "vsaj dveh primerljivih treningih" in cleaned
    assert "Naslednji teden lahko povečaš" not in cleaned


def test_common_gemini_cue_heading_typos_are_normalized():
    answer = "Kuei: Trup naj bo čvrst.\nCua: Gib naj bo nadzorovan."
    cleaned = _normalize_slovene_coaching_terms(answer)
    assert "Kuei:" not in cleaned
    assert "Cua:" not in cleaned
    assert cleaned.count("Namigi:") == 2


def test_generated_program_exposes_internal_regression_and_progression_decision_criteria():
    plan = generate_program({
        "goal": "strength_hypertrophy",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 30,
        "equipment": ["bodyweight"],
    })
    exercises = [exercise for session in plan["sessions"] for exercise in session["exercises"]]
    assert exercises
    for exercise in exercises:
        logic = exercise["coaching_logic"]
        assert logic["regress_when"]
        assert logic["progress_when"]
        assert logic["progression_order"]
        assert logic["regressions"] == exercise["regressions"]
        assert logic["progressions"] == exercise["progressions"]
        assert any("dveh izpostavitvah" in rule for rule in logic["progress_when"])


def test_bodyweight_program_never_invents_equipment_or_furniture_rows():
    plan = generate_program({
        "goal": "strength_hypertrophy",
        "experience": "beginner",
        "sessions_per_week": 2,
        "session_minutes": 30,
        "equipment": ["bodyweight"],
    })
    for session in plan["sessions"]:
        for exercise in session["exercises"]:
            assert set(exercise["equipment"]).issubset({"bodyweight"})
            assert "table" not in exercise["name"].casefold()
            assert "miza" not in exercise["name"].casefold()
