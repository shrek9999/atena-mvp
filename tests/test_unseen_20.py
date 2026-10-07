import json
from app import decide

with open("tests/unseen_20_cases.json", "r", encoding="utf-8") as f:
    CASES = json.load(f)["cases"]

def test_unseen_20_decisions():
    failures = []
    for case in CASES:
        actual = decide(case["input"])["decision"]
        if actual != case["expected_decision"]:
            failures.append((case["id"], case["expected_decision"], actual))
    assert not failures, failures
