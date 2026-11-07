import copy
import pytest

from training.decision_event import (
    DecisionEventError,
    EVENT_SCHEMA_VERSION,
    MAX_EVENT_JSON_BYTES,
    validate_decision_event,
)


def event(**overrides):
    value = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_id": "evt-001",
        "profile_id": "profile-001",
        "event_type": "session_completed",
        "occurred_at": "2026-11-07T10:15:00+01:00",
        "source": "user",
        "data_classification": "operational",
        "payload": {"completed": True, "difficulty": "normal"},
    }
    value.update(overrides)
    return value


def test_valid_event_is_normalized_and_defensively_copied():
    original = event()
    result = validate_decision_event(original)
    assert result["occurred_at"] == "2026-11-07T10:15:00+01:00"
    assert result == original
    result["payload"]["completed"] = False
    assert original["payload"]["completed"] is True


@pytest.mark.parametrize("field", [
    "schema_version", "event_id", "profile_id", "event_type",
    "occurred_at", "source", "data_classification", "payload",
])
def test_required_fields_cannot_be_omitted(field):
    value = event()
    value.pop(field)
    with pytest.raises(DecisionEventError):
        validate_decision_event(value)


def test_unknown_fields_are_rejected_to_force_explicit_schema_versioning():
    with pytest.raises(DecisionEventError, match="Neznana polja"):
        validate_decision_event(event(unreviewed_field="value"))


def test_naive_timestamp_is_rejected():
    with pytest.raises(DecisionEventError, match="časovni pas"):
        validate_decision_event(event(occurred_at="2026-11-07T10:15:00"))


def test_invalid_event_type_is_rejected():
    with pytest.raises(DecisionEventError):
        validate_decision_event(event(event_type="diagnosis_created"))


def test_health_sensitive_event_requires_server_verified_consent():
    value = event(
        event_type="symptom_context_recorded",
        data_classification="health_sensitive",
        payload={"location": "knee", "trend": "stable"},
    )
    with pytest.raises(DecisionEventError, match="preverjeno privolitev"):
        validate_decision_event(value)
    assert validate_decision_event(value, health_consent_verified=True)["payload"] == value["payload"]


def test_client_cannot_supply_server_consent_verification_field():
    value = event(data_classification="health_sensitive", consent_verified_by_server=True)
    with pytest.raises(DecisionEventError, match="Neznana polja"):
        validate_decision_event(value)


def test_health_consent_verification_argument_must_be_boolean():
    value = event(data_classification="health_sensitive")
    with pytest.raises(DecisionEventError):
        validate_decision_event(value, health_consent_verified="yes")


@pytest.mark.parametrize("bad_payload", [
    {"value": float("nan")},
    {"value": float("inf")},
    {"nested": {1: "not a string key"}},
    {"unsupported": object()},
])
def test_payload_must_be_strict_json(bad_payload):
    with pytest.raises(DecisionEventError):
        validate_decision_event(event(payload=bad_payload))


def test_oversized_event_is_rejected():
    with pytest.raises(DecisionEventError, match="velikost"):
        validate_decision_event(event(payload={"note": "x" * MAX_EVENT_JSON_BYTES}))


def test_optional_identifiers_must_be_nonempty_strings():
    with pytest.raises(DecisionEventError):
        validate_decision_event(event(program_version_id="  "))


def test_event_input_is_not_mutated():
    original = event(occurred_at="2026-11-07T09:15:00Z")
    before = copy.deepcopy(original)
    validate_decision_event(original)
    assert original == before


def test_boolean_schema_version_is_not_accepted_as_integer_version_one():
    with pytest.raises(DecisionEventError):
        validate_decision_event(event(schema_version=True))


def test_unhashable_enum_values_are_rejected_cleanly():
    with pytest.raises(DecisionEventError):
        validate_decision_event(event(event_type=[]))
