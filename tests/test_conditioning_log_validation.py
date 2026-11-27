from coach_routes import _normalize_conditioning_block


def test_conditioning_log_accepts_supported_modalities_and_optional_metrics():
    entry, error = _normalize_conditioning_block({
        "modality": "vo2max_intervals",
        "protocol_id": "rower-5x3min",
        "work_seconds": 900,
        "duration_seconds": 1500,
        "intervals_completed": 5,
        "rpe": 8,
        "distance_m": 3200,
        "average_heart_rate": 172,
    })
    assert error is None
    assert entry["modality"] == "vo2max_intervals"
    assert entry["intervals_completed"] == 5
    assert entry["average_heart_rate"] == 172


def test_conditioning_log_rejects_unknown_modality():
    entry, error = _normalize_conditioning_block({
        "modality": "random",
        "protocol_id": "test",
        "work_seconds": 300,
        "duration_seconds": 360,
        "rpe": 5,
    })
    assert entry is None
    assert "vrsta kondicijske" in error.lower()


def test_conditioning_log_rejects_work_longer_than_elapsed_duration():
    entry, error = _normalize_conditioning_block({
        "modality": "threshold_intervals",
        "protocol_id": "threshold-4x4",
        "work_seconds": 1200,
        "duration_seconds": 900,
        "intervals_completed": 4,
        "rpe": 8,
    })
    assert entry is None
    assert "trajanje" in error.lower()


def test_conditioning_log_rejects_invalid_rpe_and_boolean_numeric_values():
    base = {
        "modality": "aerobic_base",
        "protocol_id": "easy-run",
        "work_seconds": 1200,
        "duration_seconds": 1500,
        "rpe": True,
    }
    entry, error = _normalize_conditioning_block(base)
    assert entry is None
    assert "rpe" in error.lower()


def test_conditioning_log_rejects_unexpected_free_text_fields():
    entry, error = _normalize_conditioning_block({
        "modality": "metcon",
        "protocol_id": "fixed-circuit",
        "work_seconds": 600,
        "duration_seconds": 900,
        "rpe": 8,
        "notes": "anything",
    })
    assert entry is None
    assert "polja" in error.lower()
