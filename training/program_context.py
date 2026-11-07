"""Safe bridge from canonical athlete state to programme generation.

The canonical profile is the source of truth for movement observations and
symptom context. This adapter never infers a limitation from missing data.
"""
from __future__ import annotations

from copy import deepcopy

from training.athlete_state import AthleteStateError, validate_athlete_state
from training.profile_state_adapter import legacy_profile_view
from training.program import ProgramSafetyBlock, ProgramValidationError, generate_program


CANONICAL_TO_ASSESSMENT_TASK = {
    "squat": "squat",
    "deep_squat_position": "squat",
    "hinge": "hinge",
    "lunge": "lunge",
    "push_up": "push",
    "overhead_press": "overhead",
}
PROVOKING_TASK_ALIASES = {
    "vstajanje s stola": "squat",
    "počep": "squat",
    "pobiranje lahkega predmeta s tal": "hinge",
    "predklon z nevtralnim položajem hrbtenice": "hinge",
    "izpadni korak": "lunge",
    "potisk": "push_up",
    "skleca": "push_up",
    "potisk nad glavo": "overhead_press",
    "potisk nad višino ramen": "overhead_press",
}
ASSESSMENT_PRIORITY = {
    "comfortable": 0,
    "not_assessed": 0,
    "uncertain": 1,
    "needs_support": 2,
    "symptoms_reported": 3,
}


class ProgramContextError(ValueError):
    """Raised when profile and canonical athlete state cannot be safely joined."""


def _movement_assessment(state: dict) -> dict:
    """Collapse canonical task statuses into the narrower programme task schema."""
    result = {}
    for task, assessment_task in CANONICAL_TO_ASSESSMENT_TASK.items():
        status = state["movement_assessment"]["tasks"][task]["status"]
        current = result.get(assessment_task)
        if current is None or ASSESSMENT_PRIORITY[status] > ASSESSMENT_PRIORITY[current]:
            result[assessment_task] = status
    return result


def _apply_symptom_context(state: dict, assessment: dict) -> dict:
    symptoms = state["symptoms"]
    status = symptoms["status"]
    if status == "asked_unanswered":
        raise ProgramSafetyBlock(
            "Vprašanje o trenutnih simptomih še nima odgovora. Pred pripravo programa razjasni, ali so prisotne bolečine, nelagodje ali omejitve."
        )
    if status in {"new_or_worsening", "concerning"}:
        raise ProgramSafetyBlock(
            "Simptomi so novi, se slabšajo ali zahtevajo dodatno presojo. "
            "ATENA zato ne bo samodejno ustvarila ali prilagodila programa. "
            "Najprej razjasni simptome in po potrebi pridobi strokovno oceno."
        )
    if status not in {"present_stable"}:
        return assessment

    items = symptoms["items"]
    if not items or any(not item.get("provoking_task") for item in items):
        raise ProgramSafetyBlock(
            "Simptom je naveden, vendar povezava z določeno gibalno nalogo ni jasna. "
            "Pred izbiro vaj razjasni, pri katerem gibu ali opravilu se pojavi."
        )
    for item in items:
        provoking_task = str(item["provoking_task"]).strip().casefold()
        provoking_task = PROVOKING_TASK_ALIASES.get(provoking_task, provoking_task)
        if provoking_task not in CANONICAL_TO_ASSESSMENT_TASK:
            raise ProgramSafetyBlock(
                "Navedeni sprožilec simptoma še ni povezan s preverjeno gibalno nalogo. "
                "ATENA ne bo ugibala, kateri vzorec je treba prilagoditi."
            )
        assessment_task = CANONICAL_TO_ASSESSMENT_TASK[provoking_task]
        assessment[assessment_task] = "symptoms_reported"
    return assessment


def generate_program_for_athlete(
    profile: object,
    *,
    feedback: object = None,
    feedback_history: object = None,
) -> dict:
    """Generate from a persisted profile envelope and its validated athlete_state."""
    if not isinstance(profile, dict):
        raise ProgramContextError("Profil mora biti objekt.")
    envelope = deepcopy(profile)
    candidate = envelope.get("athlete_state")
    try:
        state = validate_athlete_state(candidate)
    except AthleteStateError as exc:
        raise ProgramContextError(
            "Profil nima veljavnega kanoničnega stanja športnika; programa ni mogoče varno sestaviti."
        ) from exc

    if not isinstance(state.get("profile_id"), str) or not state["profile_id"].strip():
        raise ProgramContextError("Kanonično stanje nima veljavnega profile_id.")

    legacy = legacy_profile_view(envelope)
    if not legacy:
        raise ProgramContextError("Profil nima združljivih podatkov za pripravo programa.")
    # Do not silently combine stale legacy fields with a newer canonical state.
    if (
        legacy.get("experience") != state["experience"]
        or legacy.get("equipment") != state["equipment"]
        or legacy.get("sessions_per_week") != state["availability"]["sessions_per_week"]
        or legacy.get("session_minutes") != state["availability"]["session_duration_minutes"]
    ):
        raise ProgramContextError(
            "Stari profil in kanonično stanje se ne ujemata. Profil je treba najprej uskladiti."
        )

    movement = _movement_assessment(state)
    movement = _apply_symptom_context(state, movement)
    try:
        return generate_program(
            legacy,
            feedback=feedback,
            feedback_history=feedback_history,
            movement_assessment=movement or None,
        )
    except ProgramValidationError:
        raise
