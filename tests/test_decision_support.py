import json
from pathlib import Path

from app import decide, enrich_decision

CASES = json.loads(Path("tests/unseen_20_cases.json").read_text(encoding="utf-8"))["cases"]


def test_unseen_cases_expose_agent_value():
    for case in CASES:
        result = enrich_decision(case["input"], decide(case["input"]))
        support = result.get("decision_support")
        assert support, case["id"]
        assert support["value_added"].strip(), case["id"]
        assert support["decision_basis"].strip(), case["id"]
        assert support["decision_boundary"].strip(), case["id"]
        assert isinstance(support["detected_signals"], list), case["id"]
        assert f"decision_{result['decision']}" in result["reason_codes"], case["id"]


def test_declining_performance_without_context_prioritizes_information():
    case = {
        "goal": {"primary": "strength"},
        "state": {"performance": "declining", "symptoms": "none"}
    }
    result = enrich_decision(case, decide(case))
    assert result["decision"] == "collect_data"
    assert result["required_information"]
    assert "decision_uncertainty_requires_data" in result["reason_codes"]
    assert "uncertainty explicit" in result["decision_support"]["value_added"]


def test_red_flag_overrides_ordinary_progression():
    case = {
        "goal": {"primary": "strength"},
        "state": {"performance": "improving", "symptoms": "chest pain during exercise"}
    }
    result = enrich_decision(case, decide(case))
    assert result["decision"] == "refer"
    assert result["decision_support"]["value_added"].startswith("Enforces a safety boundary")


def test_no_false_fatigue_signal_from_absolute_rpe_eight():
    case = {
        "goal": {"primary": "strength"},
        "state": {"performance": 100, "rpe": 8, "recovery": "good", "symptoms": "none"}
    }
    result = enrich_decision(case, decide(case))
    assert result["decision"] == "maintain"
    assert "rpe_absolute" in result["decision_support"]["detected_signals"]
    assert "rpe_high_absolute" not in result["decision_support"]["detected_signals"]


def test_high_absolute_rpe_is_visible_but_not_overinterpreted():
    case = {
        "goal": {"primary": "strength"},
        "state": {"performance": "stable", "rpe": 9, "recovery": "good", "symptoms": "none"}
    }
    result = enrich_decision(case, decide(case))
    assert result["decision"] == "collect_data"
    assert "rpe_high_absolute" in result["decision_support"]["detected_signals"]
