import json
from pathlib import Path


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "conversation_quality_benchmark_v1.json"
)


def test_conversation_quality_benchmark_has_unique_multiturn_scenarios():
    benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert benchmark["benchmark_id"] == "atena-conversation-quality-v1"
    assert benchmark["language"] == "sl-SI"
    scenarios = benchmark["scenarios"]
    assert len(scenarios) >= 12

    ids = [scenario["id"] for scenario in scenarios]
    assert len(ids) == len(set(ids))

    for scenario in scenarios:
        assert len(scenario["turns"]) >= 2, scenario["id"]
        assert scenario["name"].strip(), scenario["id"]
        assert scenario["must_demonstrate"], scenario["id"]
        assert scenario["critical_failures"], scenario["id"]


def test_benchmark_covers_core_coaching_and_safety_cases():
    benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ids = {scenario["id"] for scenario in benchmark["scenarios"]}

    assert {
        "G01",  # general fitness goal clarification
        "G02",  # conditioning without running
        "G03",  # beginner strength
        "G04",  # hypertrophy
        "G05",  # limited equipment
        "G06",  # flexible time
        "G07",  # knee pain
        "G08",  # back pain during loaded hinge
        "G09",  # recovery
        "G10",  # progression
        "G11",  # corrected goal
        "G12",  # adherence
    }.issubset(ids)


def test_benchmark_does_not_claim_model_execution_or_results():
    benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "sam po sebi ne dokazuje kakovosti modela" in benchmark["purpose"]
