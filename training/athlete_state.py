"""Versioned, provenance-aware canonical athlete-state contract.

This is an isolated contract layer. It does not migrate stored profiles, change
programme generation, or infer health/movement facts from missing information.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from training.goal_taxonomy import canonicalize_goal

ATHLETE_STATE_SCHEMA_VERSION = 1
EXPERIENCE_LEVELS = {"beginner", "intermediate", "advanced"}
MOVEMENT_TASKS = {
    "squat",
    "lunge",
    "hinge",
    "push_up",
    "overhead_press",
    "deep_squat_position",
    "kneeling_heel_sit_position",
}
MOVEMENT_STATUSES = {
    "not_assessed",
    "comfortable",
    "needs_support",
    "uncertain",
    "symptoms_reported",
}
EVIDENCE_SOURCES = {"self_reported", "observed", "logged", "derived"}
SYMPTOM_STATUSES = {
    "not_asked",
    "asked_unanswered",
    "denied",
    "present_stable",
    "new_or_worsening",
    "concerning",
}
SYMPTOM_CONTEXT_FIELDS = {
    "location",
    "side",
    "provoking_task",
    "onset",
    "intensity",
    "trend",
    "functional_impact",
    "response_to_modification",
    "next_day_response",
}


class AthleteStateError(ValueError):
    """Raised when canonical athlete state is incomplete or contradictory."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AthleteStateError(f"{field} mora biti neprazen niz.")
    return value.strip()


def _validate_string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise AthleteStateError(f"{field} mora biti seznam.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise AthleteStateError(f"{field} vsebuje neveljavno vrednost.")
    return list(dict.fromkeys(item.strip() for item in value))


def create_athlete_state(
    *,
    profile_id: str,
    goal: str,
    experience: str,
    training_emphasis: str | None = None,
    functional_focus: str | None = None,
    equipment: list[str],
    sessions_per_week: int,
    session_duration_minutes: int | None = None,
    movement_tasks: dict | None = None,
    symptoms: dict | None = None,
    excluded_patterns: list[str] | None = None,
    excluded_exercise_ids: list[str] | None = None,
    provenance: dict | None = None,
    recorded_at: str | None = None,
) -> dict:
    """Create a canonical state without inventing missing health or movement facts.

    Missing movement tasks are explicitly marked not_assessed. Missing symptom
    information remains not_asked. Equipment is supplied by the caller; this
    function never assumes access to gym equipment.
    """
    profile_id = _require_text(profile_id, "profile_id")
    if experience not in EXPERIENCE_LEVELS:
        raise AthleteStateError("Raven izkušenj ni veljavna.")
    if not isinstance(sessions_per_week, int) or isinstance(sessions_per_week, bool) or not 1 <= sessions_per_week <= 7:
        raise AthleteStateError("Število vadb na teden mora biti med 1 in 7.")
    if session_duration_minutes is not None and (
        not isinstance(session_duration_minutes, int)
        or isinstance(session_duration_minutes, bool)
        or not 10 <= session_duration_minutes <= 240
    ):
        raise AthleteStateError("Trajanje vadbe mora biti med 10 in 240 minutami.")

    canonical_goal = canonicalize_goal(
        goal, experience=experience, training_emphasis=training_emphasis,
        functional_focus=functional_focus,
    )
    equipment = _validate_string_list(equipment, "equipment")
    excluded_patterns = _validate_string_list(excluded_patterns or [], "excluded_patterns")
    excluded_exercise_ids = _validate_string_list(
        excluded_exercise_ids or [], "excluded_exercise_ids"
    )

    if movement_tasks is None:
        movement_tasks = {}
    if not isinstance(movement_tasks, dict):
        raise AthleteStateError("movement_tasks mora biti objekt.")
    unknown_tasks = set(movement_tasks) - MOVEMENT_TASKS
    if unknown_tasks:
        raise AthleteStateError("Neznane gibalne naloge: " + ", ".join(sorted(unknown_tasks)))
    normalized_tasks = {}
    for task in sorted(MOVEMENT_TASKS):
        item = movement_tasks.get(task, {})
        if isinstance(item, str):
            item = {"status": item}
        if not isinstance(item, dict):
            raise AthleteStateError(f"Podatek za {task} mora biti objekt.")
        status = item.get("status", "not_assessed")
        source = item.get("source")
        if status not in MOVEMENT_STATUSES:
            raise AthleteStateError(f"Neveljaven status gibalne naloge: {task}.")
        if source is not None and source not in EVIDENCE_SOURCES:
            raise AthleteStateError(f"Neveljaven vir podatka za {task}.")
        if status == "not_assessed" and source is not None:
            raise AthleteStateError(f"Neocenjena naloga {task} ne sme imeti vira dokaza.")
        normalized_tasks[task] = {
            "status": status,
            "source": source,
            "recorded_at": item.get("recorded_at"),
            "note": item.get("note"),
        }

    if symptoms is None:
        symptoms = {}
    if not isinstance(symptoms, dict):
        raise AthleteStateError("symptoms mora biti objekt.")
    symptom_status = symptoms.get("status", "not_asked")
    if symptom_status not in SYMPTOM_STATUSES:
        raise AthleteStateError("Status simptomov ni veljaven.")
    symptom_items = symptoms.get("items", [])
    if not isinstance(symptom_items, list) or any(not isinstance(x, dict) for x in symptom_items):
        raise AthleteStateError("symptoms.items mora biti seznam objektov.")
    normalized_symptom_items = []
    for item in symptom_items:
        unknown_fields = set(item) - SYMPTOM_CONTEXT_FIELDS
        if unknown_fields:
            raise AthleteStateError(
                "Neznana polja konteksta simptomov: " + ", ".join(sorted(unknown_fields))
            )
        normalized_symptom_items.append(deepcopy(item))
    if symptom_status == "denied" and normalized_symptom_items:
        raise AthleteStateError("Status denied ne sme vsebovati prijavljenih simptomov.")
    if symptom_status in {"present_stable", "new_or_worsening", "concerning"} and not normalized_symptom_items:
        raise AthleteStateError("Pri prisotnih simptomih je potreben vsaj osnovni kontekst.")

    if provenance is None:
        provenance = {}
    if not isinstance(provenance, dict):
        raise AthleteStateError("provenance mora biti objekt.")
    normalized_provenance = {}
    for field, entry in provenance.items():
        if not isinstance(field, str) or not field.strip() or not isinstance(entry, dict):
            raise AthleteStateError("Zapis provenance ni veljaven.")
        source = entry.get("source")
        if source not in EVIDENCE_SOURCES:
            raise AthleteStateError(f"Vir podatka za {field} ni veljaven.")
        normalized_provenance[field] = {
            "source": source,
            "recorded_at": entry.get("recorded_at"),
        }

    return {
        "schema_version": ATHLETE_STATE_SCHEMA_VERSION,
        "profile_id": profile_id,
        "recorded_at": recorded_at or _now_iso(),
        "goal": canonical_goal,
        "experience": experience,
        "equipment": equipment,
        "availability": {
            "sessions_per_week": sessions_per_week,
            "session_duration_minutes": session_duration_minutes,
        },
        "movement_assessment": {
            "version": 1,
            "tasks": normalized_tasks,
            "supplementary_positions": [
                "deep_squat_position",
                "kneeling_heel_sit_position",
            ],
        },
        "symptoms": {
            "status": symptom_status,
            "items": normalized_symptom_items,
        },
        "constraints": {
            "excluded_patterns": excluded_patterns,
            "excluded_exercise_ids": excluded_exercise_ids,
        },
        "provenance": normalized_provenance,
    }


def validate_athlete_state(state: object) -> dict:
    """Validate a persisted state and return a defensive copy."""
    if not isinstance(state, dict):
        raise AthleteStateError("Stanje športnika mora biti objekt.")
    if state.get("schema_version") != ATHLETE_STATE_SCHEMA_VERSION:
        raise AthleteStateError("Nepodprta različica podatkovnega modela športnika.")
    required = {
        "profile_id", "recorded_at", "goal", "experience", "equipment",
        "availability", "movement_assessment", "symptoms", "constraints", "provenance",
    }
    missing = required - set(state)
    if missing:
        raise AthleteStateError("Manjkajo obvezna polja: " + ", ".join(sorted(missing)))
    availability = state["availability"]
    if not isinstance(availability, dict):
        raise AthleteStateError("availability mora biti objekt.")
    movement = state["movement_assessment"]
    if not isinstance(movement, dict) or not isinstance(movement.get("tasks"), dict):
        raise AthleteStateError("movement_assessment.tasks mora biti objekt.")
    symptoms = state["symptoms"]
    if not isinstance(symptoms, dict):
        raise AthleteStateError("symptoms mora biti objekt.")
    # Recreate through the single constructor so persisted and new data share
    # exactly the same validation rules.
    goal_data = state["goal"]
    if isinstance(goal_data, dict):
        goal_name = goal_data.get("canonical_goal")
        training_emphasis = goal_data.get("strength_emphasis")
        functional_focus = goal_data.get("functional_focus")
    else:
        goal_name = goal_data
        training_emphasis = None
        functional_focus = None
    constraints = state["constraints"]
    if not isinstance(constraints, dict):
        raise AthleteStateError("constraints mora biti objekt.")
    rebuilt = create_athlete_state(
        profile_id=state["profile_id"],
        goal=goal_name,
        experience=state["experience"],
        training_emphasis=training_emphasis,
        functional_focus=functional_focus,
        equipment=state["equipment"],
        sessions_per_week=availability.get("sessions_per_week"),
        session_duration_minutes=availability.get("session_duration_minutes"),
        movement_tasks=movement["tasks"],
        symptoms=symptoms,
        excluded_patterns=constraints.get("excluded_patterns", []),
        excluded_exercise_ids=constraints.get("excluded_exercise_ids", []),
        provenance=state["provenance"],
        recorded_at=state["recorded_at"],
    )
    return rebuilt
