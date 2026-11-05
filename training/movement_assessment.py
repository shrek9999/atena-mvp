"""Conservative, self-reported movement-competence intake for ATENA.

This module records task-specific experience only. It is not a clinical screen,
a movement diagnosis, or an automatic clearance to progress training.
"""
from __future__ import annotations

ASSESSMENT_VERSION = "1.1"
MOVEMENT_TASKS = {
    "squat": "počep",
    "hinge": "predklon z ravnim hrbtom",
    "lunge": "izpadni korak",
    "push": "potisk",
    "pull": "poteg",
    "overhead": "dvig roke nad glavo",
    "single_leg_balance": "ravnotežje na eni nogi",
    "locomotion": "hoja oziroma lahka lokomocija",
}
VALID_STATUSES = {
    "comfortable",
    "needs_support",
    "uncertain",
    "symptoms_reported",
    "not_assessed",
}

# A self-report applies only to the corresponding training pattern. It does
# not infer a diagnosis or spread a symptom to anatomically adjacent patterns.
TASK_PATTERNS = {
    "squat": {"squat"},
    "hinge": {"hinge"},
    "lunge": {"lunge"},
    "push": {"horizontal_push", "vertical_push"},
    "pull": {"horizontal_pull", "vertical_pull"},
    "overhead": {"vertical_push"},
    "single_leg_balance": {"balance"},
    "locomotion": {"locomotion"},
}

# Candidate order is intentionally conservative. The programme generator
# still verifies goal, equipment, exclusions, pattern and exercise level.
SUPPORTED_VARIANTS = {
    "squat": ("reaching_squat", "air_squat"),
    "hinge": ("bodyweight_hip_hinge",),
    # No supported lunge regression is currently represented as a catalogue ID;
    # fail closed instead of relabelling an ordinary split squat as a regression.
    "horizontal_push": ("push_up_incline", "wall_push_up"),
    "vertical_push": ("band_overhead_press",),
    "horizontal_pull": ("band_row", "trx_row"),
    "vertical_pull": ("band_assisted_pull_up", "foot_assisted_pull_up", "band_lat_pulldown"),
    "locomotion": ("brisk_walking",),
}


class MovementAssessmentError(ValueError):
    """Raised when a self-reported movement assessment is malformed."""


def assess_movement_competence(assessment: object) -> dict:
    """Translate task-specific self-report into conservative coaching prompts.

    Missing tasks remain unassessed. No score, diagnosis, pass/fail label, or
    automatic programme change is produced by this summary function.
    """
    if not isinstance(assessment, dict):
        raise MovementAssessmentError("Ocena mora biti JSON objekt.")
    if not assessment:
        raise MovementAssessmentError("Vnesi vsaj eno oceno gibalne naloge.")
    unknown = sorted(set(assessment) - set(MOVEMENT_TASKS))
    if unknown:
        raise MovementAssessmentError("Neznane gibalne naloge: " + ", ".join(unknown))

    normalized = {}
    for task, status in assessment.items():
        if not isinstance(status, str) or status not in VALID_STATUSES:
            raise MovementAssessmentError(
                f"Neveljaven status za {task}; dovoljeni so: "
                + ", ".join(sorted(VALID_STATUSES)) + "."
            )
        normalized[task] = status

    tasks = []
    needs_support = []
    clarify = []
    symptoms = []
    unassessed = []
    for task, label in MOVEMENT_TASKS.items():
        status = normalized.get(task, "not_assessed")
        tasks.append({"movement_task": task, "label": label, "status": status})
        if status == "needs_support":
            needs_support.append(task)
        elif status == "uncertain":
            clarify.append(task)
        elif status == "symptoms_reported":
            symptoms.append(task)
        elif status == "not_assessed":
            unassessed.append(task)

    return {
        "version": ASSESSMENT_VERSION,
        "scope": "self_reported_task_experience_not_clinical_assessment",
        "is_score": False,
        "is_diagnosis": False,
        "tasks": tasks,
        "coaching_guidance": {
            "consider_supported_or_simpler_variation": needs_support,
            "clarify_before_relying_on_observation": clarify,
            "pause_automatic_changes_for": symptoms,
            "not_assessed_do_not_infer": unassessed,
        },
        "automatic_programme_change": "none",
        "plyometric_readiness": "not_assessed",
        "safety_note": (
            "Odgovori opisujejo uporabnikovo izkušnjo pri posamezni nalogi. "
            "Ne dokazujejo poškodbe, šibkosti ali omejene gibljivosti. "
            "Pri novih, izrazitih, napredujočih ali nenavadnih simptomih "
            "prekinemo avtomatsko prilagajanje in priporočimo ustrezno "
            "zdravstveno presojo. Skoki in hitre spremembe smeri zahtevajo "
            "ločeno, namensko presojo pripravljenosti."
        ),
    }
