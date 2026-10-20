"""Strukturno in podatkovno preverjanje ročnega evalvacijskega gradiva.

Ti testi preverjajo popolnost scenarijev, rubrike, oznak in obrazca.
Ne ocenjujejo odgovorov modela ter ne dokazujejo njihove semantične varnosti.
"""
import csv
import json
from pathlib import Path

import pytest


CASES_PATH = Path("tests/coach_quality_cases.json")
RUBRIC_PATH = Path("tests/coach_evaluation_rubric.json")
RESULTS_PATH = Path("tests/coach_evaluation_results_template.csv")
GUIDE_PATH = Path("tests/COACH_QUALITY_EVALUATION.md")

CASES_DATA = json.loads(CASES_PATH.read_text(encoding="utf-8"))
RUBRIC = json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))
CASES = CASES_DATA["cases"]
CATEGORY_IDS = {
    "varnost",
    "strokovna_ustreznost",
    "prilagojenost",
    "jasnost_casovna_skladnost",
    "slovenscina",
    "vprasanje_zgodovina",
}
EXPECTED_SCENARIOS = {
    "beginner_20min_no_equipment",
    "knee_pain_worsening",
    "shoulder_mobility_limit",
    "back_pain_exercise",
    "ankle_injury_incomplete_info",
    "red_flags_chest_pain_faintness",
    "hard_session_poor_recovery",
    "easy_session_good_recovery",
    "diagnosis_request",
    "false_persistent_memory_claim",
    "twenty_minute_timing",
    "ambiguous_request_followup",
    "plain_slovenian_general_population",
}
EXPECTED_CSV_COLUMNS = [
    "id_scenarija",
    "različica_prompta_sistema",
    "odgovor_za_oceno",
    "varnost_0_4",
    "strokovna_ustreznost_vadbe_0_4",
    "prilagojenost_kontekstu_0_4",
    "jasnost_in_časovna_skladnost_0_4",
    "slovenščina_0_4",
    "naslednje_vprašanje_in_zgodovina_0_4",
    "kritična_varnostna_napaka",
    "potrebna_strokovna_presoja",
    "odgovor_je_treba_izboljšati",
    "ni_mogoče_oceniti_pomanjkanje_konteksta",
    "utemeljitev_ocenjevalca",
    "predlagani_popravek",
    "datum_ocenjevanja",
    "oznaka_ocenjevalca",
}


def test_scenario_dataset_is_explicitly_synthetic_and_contains_no_answers():
    assert CASES_DATA["status"] == "scenarios_only_no_model_answers"
    assert "modelskih odgovorov" in CASES_DATA["notice"]
    assert CASES_DATA["validation_plan_reference"].endswith("/ATENA_VALIDATION_PLAN.md")
    assert CASES
    assert all(case.get("sintetičen") is True for case in CASES)
    assert all("reply" not in case and "odgovor_modela" not in case and "automated" not in case for case in CASES)


def test_scenario_ids_are_unique_and_cover_required_user_situations():
    ids = [case["id"] for case in CASES]

    assert len(ids) == len(set(ids))
    assert EXPECTED_SCENARIOS <= set(ids)


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_each_scenario_has_complete_input_risk_and_evaluation_criteria(case):
    assert case["id"].strip()
    assert isinstance(case["user_context"], dict) and case["user_context"]
    assert case["user_message"].strip()
    assert case["risk_level"] in CASES_DATA["risk_levels"]
    assert isinstance(case["conversation_history"], list)
    for turn in case["conversation_history"]:
        assert turn["role"] in {"user", "model"}
        assert turn["content"].strip()

    criteria = case["evaluation_criteria"]
    assert set(criteria) == CATEGORY_IDS
    for category in criteria.values():
        assert category["focus"].strip()
        assert isinstance(category["red_flags"], list)
        assert all(item.strip() for item in category["red_flags"])
        normalized = [item.casefold() for item in category["red_flags"]]
        assert len(normalized) == len(set(normalized))


def test_rubric_has_concrete_descriptors_for_each_score_and_dimension():
    assert "medicinska diagnoza" in RUBRIC["warning"]
    assert set(RUBRIC["categories"]) == CATEGORY_IDS

    for category in RUBRIC["categories"].values():
        assert category["title"].strip()
        assert set(category["scores"]) == {"0", "1", "2", "3", "4"}
        assert all(len(description.strip()) >= 30 for description in category["scores"].values())
        assert len(set(category["scores"].values())) == 5


def test_critical_safety_gate_cannot_be_hidden_by_other_scores():
    rule = RUBRIC["scoring_rule"]

    assert rule["critical_safety_gate"]
    assert "ne glede na" in rule["critical_safety_gate"]
    assert rule["no_averaging"]
    assert "povprečne" in rule["no_averaging"]


def test_required_evaluation_tags_are_present_once():
    tag_ids = [tag["id"] for tag in RUBRIC["tags"]]

    assert set(tag_ids) == {
        "kriticna_varnostna_napaka",
        "potrebna_strokovna_presoja",
        "odgovor_izboljsati",
        "ni_mogoce_oceniti_pomanjkanje_konteksta",
    }
    assert len(tag_ids) == len(set(tag_ids))
    assert all(tag["label"].strip() for tag in RUBRIC["tags"])


def test_results_template_has_expected_fields_without_personal_identifiers():
    with RESULTS_PATH.open(encoding="utf-8", newline="") as file:
        columns = next(csv.reader(file))

    assert columns == EXPECTED_CSV_COLUMNS
    forbidden_columns = {"ime_uporabnika", "priimek", "datum_rojstva", "api_ključ", "geslo"}
    assert not forbidden_columns.intersection(column.casefold() for column in columns)


def test_manual_process_documents_review_steps_and_limits():
    guide = GUIDE_PATH.read_text(encoding="utf-8").casefold()

    for required in (
        "1. izberite",
        "2. odgovor pridobite",
        "3. odgovor kopirajte",
        "4. ocenjevalec",
        "5. kritično varnostno napako",
        "6. rezultate povzemite",
        "kritična varnostna napaka",
        "ne izvajamo modelskega klica",
        "ne izračunavajte povprečne skupne ocene",
        "ni medicinska diagnoza",
    ):
        assert required in guide
