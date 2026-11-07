"""Versioned, validated event contract for ATENA's longitudinal decision history.

This module defines data shape only. Persistence and consent authorization remain
server-side responsibilities; never trust a client-supplied consent assertion.
"""
from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime

EVENT_SCHEMA_VERSION = 1
EVENT_TYPES = {
    "profile_updated",
    "movement_assessment_recorded",
    "symptom_context_recorded",
    "consent_changed",
    "program_created",
    "program_replaced",
    "session_started",
    "session_completed",
    "session_interrupted",
    "set_result_recorded",
    "feedback_recorded",
    "adaptation_decided",
    "referral_recommended",
}
EVENT_SOURCES = {"user", "coach", "system", "import"}
DATA_CLASSIFICATIONS = {"operational", "health_sensitive"}
MAX_EVENT_JSON_BYTES = 16_384
_REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "profile_id",
    "event_type",
    "occurred_at",
    "source",
    "data_classification",
    "payload",
}
_OPTIONAL_FIELDS = {
    "program_version_id",
    "correlation_id",
    "consent_verified_by_server",
}


class DecisionEventError(ValueError):
    """Raised when an event is malformed or unsafe to persist."""


def _text(value: object, field: str, *, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise DecisionEventError(f"{field} mora biti neprazen niz do {maximum} znakov.")
    return value.strip()


def _json_safe(value: object, path: str = "payload") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DecisionEventError(f"{path} vsebuje neveljavno število.")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_safe(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise DecisionEventError(f"{path} vsebuje ključ, ki ni niz.")
            _json_safe(item, f"{path}.{key}")
        return
    raise DecisionEventError(f"{path} vsebuje vrednost, ki ni združljiva z JSON.")


def validate_decision_event(event: object) -> dict:
    """Validate and defensively copy one immutable longitudinal event envelope.

    Health-sensitive payloads require an explicit server-side consent check.
    The caller must perform authorization before setting that verification flag.
    """
    if not isinstance(event, dict):
        raise DecisionEventError("Dogodek mora biti objekt.")
    missing = _REQUIRED_FIELDS - set(event)
    unknown = set(event) - _REQUIRED_FIELDS - _OPTIONAL_FIELDS
    if missing:
        raise DecisionEventError("Manjkajo obvezna polja: " + ", ".join(sorted(missing)))
    if unknown:
        raise DecisionEventError("Neznana polja dogodka: " + ", ".join(sorted(unknown)))
    if event["schema_version"] != EVENT_SCHEMA_VERSION:
        raise DecisionEventError("Nepodprta različica dogodka.")
    event_id = _text(event["event_id"], "event_id", maximum=128)
    profile_id = _text(event["profile_id"], "profile_id", maximum=128)
    event_type = event["event_type"]
    if event_type not in EVENT_TYPES:
        raise DecisionEventError("Vrsta dogodka ni podprta.")
    source = event["source"]
    if source not in EVENT_SOURCES:
        raise DecisionEventError("Vir dogodka ni podprt.")
    classification = event["data_classification"]
    if classification not in DATA_CLASSIFICATIONS:
        raise DecisionEventError("Razvrstitev podatkov ni podprta.")
    if not isinstance(event["payload"], dict):
        raise DecisionEventError("payload mora biti objekt.")

    occurred_at = _text(event["occurred_at"], "occurred_at", maximum=64)
    try:
        timestamp = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DecisionEventError("occurred_at mora biti veljaven ISO 8601 čas.") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise DecisionEventError("occurred_at mora vsebovati časovni pas.")

    normalized = deepcopy(event)
    normalized["event_id"] = event_id
    normalized["profile_id"] = profile_id
    normalized["occurred_at"] = timestamp.isoformat()
    for field in ("program_version_id", "correlation_id"):
        if field in normalized:
            normalized[field] = _text(normalized[field], field, maximum=128)

    consent_verified = normalized.get("consent_verified_by_server", False)
    if not isinstance(consent_verified, bool):
        raise DecisionEventError("consent_verified_by_server mora biti true ali false.")
    if classification == "health_sensitive" and consent_verified is not True:
        raise DecisionEventError("Zdravstveni dogodek zahteva predhodno preverjeno privolitev na strežniku.")
    if classification == "operational" and consent_verified:
        raise DecisionEventError("Operativni dogodek ne sme vsebovati nepotrebne zdravstvene privolitve.")

    _json_safe(normalized["payload"])
    try:
        encoded = json.dumps(normalized, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DecisionEventError("Dogodka ni mogoče varno serializirati.") from exc
    if len(encoded) > MAX_EVENT_JSON_BYTES:
        raise DecisionEventError("Dogodek presega dovoljeno velikost.")

    return normalized
