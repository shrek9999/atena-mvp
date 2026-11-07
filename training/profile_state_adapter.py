"""Compatibility adapter between persisted legacy profiles and canonical athlete state.

The profile JSON column remains the storage envelope. Legacy top-level fields are
kept for older programme code; the canonical, versioned state is stored beside
them under athlete_state.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from training.athlete_state import (
    AthleteStateError,
    create_athlete_state,
    validate_athlete_state,
)
from training.goal_taxonomy import canonicalize_goal


LEGACY_PROFILE_FIELDS = {
    "goal",
    "experience",
    "equipment",
    "sessions_per_week",
    "session_minutes",
    "available_days",
    "pistol_squat_capable",
}


class ProfileStateMigrationError(ValueError):
    """Raised when a legacy profile cannot be represented safely."""


def legacy_profile_view(profile: dict) -> dict:
    """Return only fields understood by the legacy programme generator."""
    if not isinstance(profile, dict):
        raise ProfileStateMigrationError("Profil mora biti objekt.")
    return {
        key: deepcopy(value)
        for key, value in profile.items()
        if key in LEGACY_PROFILE_FIELDS
    }


def _existing_state(profile: dict, profile_id: str) -> dict | None:
    candidate = profile.get("athlete_state")
    if candidate is None:
        return None
    try:
        state = validate_athlete_state(candidate)
    except AthleteStateError as exc:
        raise ProfileStateMigrationError(
            "Shranjeno kanonično stanje športnika ni veljavno; podatki niso bili prepisani."
        ) from exc
    if state["profile_id"] != profile_id:
        raise ProfileStateMigrationError(
            "Identifikator kanoničnega stanja se ne ujema s profilom."
        )
    return state


def attach_athlete_state(
    profile: dict,
    profile_id: str,
    *,
    previous_profile: dict | None = None,
) -> dict:
    """Return a profile envelope with a validated canonical state.

    Existing movement observations, symptom context and explicit constraints
    survive ordinary profile edits. Missing legacy data is never inferred.
    """
    if not isinstance(profile, dict):
        raise ProfileStateMigrationError("Profil mora biti objekt.")
    result = deepcopy(profile)
    previous = _existing_state(previous_profile or {}, profile_id)
    goal = result.get("goal")
    experience = result.get("experience")
    if not isinstance(goal, str) or not isinstance(experience, str):
        raise ProfileStateMigrationError("Stari profil nima veljavnega cilja ali izkušenj.")

    emphasis = None
    functional_focus = None
    current_goal = canonicalize_goal(goal, experience=experience)["canonical_goal"]
    if previous and previous["goal"]["canonical_goal"] == current_goal:
        if current_goal == "strength_muscle":
            emphasis = previous["goal"].get("strength_emphasis")
        elif current_goal == "functional_fitness":
            functional_focus = previous["goal"].get("functional_focus")

    movement_tasks = None
    symptoms = None
    excluded_patterns = None
    excluded_exercise_ids = None
    provenance = {
        "goal": {"source": "self_reported"},
        "experience": {"source": "self_reported"},
        "equipment": {"source": "self_reported"},
        "availability": {"source": "self_reported"},
    }
    if previous:
        movement_tasks = previous["movement_assessment"]["tasks"]
        symptoms = previous["symptoms"]
        excluded_patterns = previous["constraints"]["excluded_patterns"]
        excluded_exercise_ids = previous["constraints"]["excluded_exercise_ids"]
        provenance.update(previous["provenance"])

    try:
        state = create_athlete_state(
            profile_id=profile_id,
            goal=goal,
            experience=experience,
            training_emphasis=emphasis,
            functional_focus=functional_focus,
            equipment=result.get("equipment", []),
            sessions_per_week=result.get("sessions_per_week"),
            session_duration_minutes=result.get("session_minutes"),
            available_days=result.get("available_days", []),
            # The legacy boolean defaults to False when omitted. Do not turn
            # that default into a self-reported inability; only persist an
            # affirmative capability when the user explicitly supplied it.
            self_reported_capabilities=(
                {"pistol_squat": True}
                if result.get("pistol_squat_capable") is True
                else (
                    {"pistol_squat": True}
                    if previous and previous["capabilities"]["self_reported"].get("pistol_squat") is True
                    else {}
                )
            ),
            movement_tasks=movement_tasks,
            symptoms=symptoms,
            excluded_patterns=excluded_patterns,
            excluded_exercise_ids=excluded_exercise_ids,
            provenance=provenance,
        )
    except (AthleteStateError, TypeError) as exc:
        raise ProfileStateMigrationError(
            "Profil ni mogoče varno pretvoriti v kanonično stanje športnika."
        ) from exc

    result["athlete_state"] = state
    return result


def profile_needs_state_migration(profile: dict) -> bool:
    """Identify legacy records that do not yet persist the canonical state."""
    return not isinstance(profile, dict) or "athlete_state" not in profile


def update_athlete_assessment(
    profile: dict,
    profile_id: str,
    *,
    movement_tasks: dict | None = None,
    symptoms: dict | None = None,
) -> dict:
    """Update only explicitly supplied assessment fields in a stored profile.

    The canonical state is rebuilt through its constructor so the same
    validation rules apply to new and persisted observations.
    """
    if movement_tasks is None and symptoms is None:
        raise ProfileStateMigrationError("Navedi vsaj oceno gibanja ali kontekst simptomov.")
    if not isinstance(profile, dict):
        raise ProfileStateMigrationError("Profil mora biti objekt.")
    previous = _existing_state(profile, profile_id)
    if previous is None:
        raise ProfileStateMigrationError("Profil še nima kanoničnega stanja športnika.")

    tasks = deepcopy(previous["movement_assessment"]["tasks"])
    if movement_tasks is not None:
        if not isinstance(movement_tasks, dict) or not movement_tasks:
            raise ProfileStateMigrationError("movement_tasks mora biti neprazen objekt.")
        allowed_tasks = set(tasks)
        if set(movement_tasks) - allowed_tasks:
            raise ProfileStateMigrationError("Ocena vsebuje neznano gibalno nalogo.")
        recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for task, value in movement_tasks.items():
            if isinstance(value, str):
                value = {"status": value}
            if not isinstance(value, dict) or set(value) - {"status", "note"}:
                raise ProfileStateMigrationError("Podatek gibalne naloge vsebuje nepodprta polja.")
            status = value.get("status", "not_assessed")
            note = value.get("note")
            if note is not None and (not isinstance(note, str) or len(note) > 500):
                raise ProfileStateMigrationError("Opomba gibalne naloge je neveljavna.")
            tasks[task] = {
                "status": status,
                "source": "self_reported" if status != "not_assessed" else None,
                "recorded_at": recorded_at if status != "not_assessed" else None,
                "note": note,
            }

    symptom_data = deepcopy(previous["symptoms"] if symptoms is None else symptoms)
    goal = previous["goal"]
    goal_name = goal.get("canonical_goal") if isinstance(goal, dict) else goal
    try:
        updated_state = create_athlete_state(
            profile_id=previous["profile_id"],
            goal=goal_name,
            experience=previous["experience"],
            training_emphasis=goal.get("strength_emphasis") if isinstance(goal, dict) else None,
            functional_focus=goal.get("functional_focus") if isinstance(goal, dict) else None,
            equipment=previous["equipment"],
            sessions_per_week=previous["availability"]["sessions_per_week"],
            session_duration_minutes=previous["availability"]["session_duration_minutes"],
            available_days=previous["availability"]["available_days"],
            self_reported_capabilities=previous["capabilities"]["self_reported"],
            movement_tasks=tasks,
            symptoms=symptom_data,
            excluded_patterns=previous["constraints"]["excluded_patterns"],
            excluded_exercise_ids=previous["constraints"]["excluded_exercise_ids"],
            provenance=previous["provenance"],
        )
    except (AthleteStateError, TypeError) as exc:
        raise ProfileStateMigrationError("Ocene ali konteksta simptomov ni mogoče varno shraniti.") from exc

    result = deepcopy(profile)
    result["athlete_state"] = updated_state
    return result
