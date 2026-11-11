from tests.run_live_conversation_quality_benchmark import select_scenarios


def test_empty_selection_runs_the_full_benchmark_suite():
    scenarios = [{"id": "G01"}, {"id": "G02"}, {"id": "G03"}]
    assert select_scenarios(scenarios, "") == scenarios


def test_targeted_selection_preserves_requested_order_and_excludes_other_cases():
    scenarios = [{"id": "G01"}, {"id": "G12"}, {"id": "G20"}, {"id": "G22"}, {"id": "G23"}]
    selected = select_scenarios(scenarios, "G22,G12,G23")
    assert [item["id"] for item in selected] == ["G22", "G12", "G23"]


def test_unknown_scenario_id_is_rejected_instead_of_silently_skipped():
    try:
        select_scenarios([{"id": "G01"}], "G01,G99")
    except ValueError as exc:
        assert "G99" in str(exc)
    else:
        raise AssertionError("Unknown benchmark scenario IDs must be rejected.")


def test_all_keyword_selects_the_full_benchmark_suite():
    scenarios = [{"id": "G01"}, {"id": "G02"}, {"id": "G03"}]
    assert select_scenarios(scenarios, "ALL") == scenarios


def test_full_keyword_is_case_insensitive():
    scenarios = [{"id": "G01"}, {"id": "G02"}]
    assert select_scenarios(scenarios, "full") == scenarios


def test_post_review_targeted_regression_set_selects_five_known_ids():
    scenarios = [
        {"id": "G04"},
        {"id": "G10"},
        {"id": "G12"},
        {"id": "G17"},
        {"id": "G19"},
        {"id": "G24"},
    ]
    selected = select_scenarios(scenarios, "G04,G10,G12,G17,G19")
    assert [item["id"] for item in selected] == ["G04", "G10", "G12", "G17", "G19"]
