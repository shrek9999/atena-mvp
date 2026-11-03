from training.conditioning_progression import summarize_conditioning_progress


def _record(day, *, work=1200, duration=1500, intervals=1, rpe=4,
            distance=None, recovery="good", difficulty="moderate",
            completed=True, discomfort=False, modality="aerobic_base",
            protocol_id="easy-run-30"):
    block = {
        "modality": modality,
        "protocol_id": protocol_id,
        "work_seconds": work,
        "duration_seconds": duration,
        "intervals_completed": intervals,
        "rpe": rpe,
    }
    if distance is not None:
        block["distance_m"] = distance
    return {
        "session_date": day,
        "session": {
            "completed": completed,
            "recovery": recovery,
            "difficulty": difficulty,
            "discomfort_reported": discomfort,
            "conditioning": [block],
        },
    }


def _five(**overrides):
    defaults = [
        ("2026-10-01", {}),
        ("2026-10-08", {}),
        ("2026-10-15", {}),
        ("2026-10-22", {}),
        ("2026-10-29", {}),
    ]
    shared = {key: value for key, value in overrides.items() if key not in {day for day, _ in defaults}}
    return [
        _record(day, **shared, **overrides.get(day, {}))
        for day, _ in defaults
    ]


def _trend(records):
    result = summarize_conditioning_progress(records)
    return result["conditioning_trends"][0]


def test_five_comparable_aerobic_exposures_build_stable_baseline():
    trend = _trend(_five())
    assert trend["status"] == "stable"
    assert trend["automatic_program_changes"] is False


def test_more_distance_at_similar_rpe_is_improving():
    records = _five()
    records[-1] = _record("2026-10-29", distance=5200)
    for index, day in enumerate(("2026-10-01", "2026-10-08", "2026-10-15", "2026-10-22")):
        records[index] = _record(day, distance=5000)
    trend = _trend(records)
    assert trend["status"] == "improving"


def test_recent_poor_recovery_blocks_positive_trend():
    records = _five()
    records[-1] = _record("2026-10-29", work=1500, recovery="poor")
    trend = _trend(records)
    assert trend["status"] == "recovery_watch"


def test_discomfort_takes_priority_and_requires_review():
    records = _five()
    records[-1] = _record("2026-10-29", discomfort=True)
    trend = _trend(records)
    assert trend["status"] == "symptom_review"
    assert trend["review"] == "pause_progression_and_review"


def test_declining_work_with_higher_rpe_is_flagged_for_context_review():
    records = _five()
    records[-1] = _record("2026-10-29", work=900, rpe=6)
    trend = _trend(records)
    assert trend["status"] == "performance_watch"


def test_fewer_than_five_exposures_only_build_baseline():
    trend = _trend(_five()[:4])
    assert trend["status"] == "building_baseline"


def test_five_exposures_in_short_period_do_not_classify_trend():
    records = [_record(f"2026-10-{day:02d}") for day in (20, 22, 24, 26, 28)]
    assert _trend(records)["status"] == "building_baseline"


def test_duplicate_same_day_entries_do_not_inflate_exposures():
    records = [
        _record("2026-10-01"),
        _record("2026-10-08"),
        _record("2026-10-15"),
        _record("2026-10-22"),
        _record("2026-10-22"),
    ]
    trends = summarize_conditioning_progress(records)["conditioning_trends"]
    assert len(trends) == 2
    counts = sorted(item["recorded_exposures"] for item in trends)
    assert counts == [1, 4]
    assert all(item["status"] == "building_baseline" for item in trends)


def test_incomplete_or_invalid_conditioning_block_is_ignored():
    records = _five()
    records[-1] = _record("2026-10-29", work=0)
    assert _trend(records)["status"] == "building_baseline"


def test_uncompleted_sessions_do_not_count():
    records = _five()
    records[-1] = _record("2026-10-29", completed=False)
    assert _trend(records)["status"] == "building_baseline"


def test_different_protocols_are_not_combined():
    records = _five()
    records[-1] = _record("2026-10-29", protocol_id="different-interval")
    trend = _trend(records)
    assert trend["recorded_exposures"] == 4
    assert trend["status"] == "building_baseline"


def test_metcon_is_kept_as_its_own_modality():
    trend = _trend(_five(modality="metcon", protocol_id="fixed-circuit"))
    assert trend["modality"] == "metcon"
