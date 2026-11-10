"""Conservative, self-reported movement-competence intake for ATENA.

This module records task-specific experience only. It is not a clinical screen,
a movement diagnosis, or an automatic clearance to progress training.
"""
from __future__ import annotations

ASSESSMENT_VERSION = "1.3"
MOVEMENT_TASKS = {
    "squat": "vstajanje s stola",
    "hinge": "pobiranje lahkega predmeta s tal",
    "lunge": "izpadni korak",
    "push": "potisk",
    "pull": "poteg",
    "overhead": "doseganje nad višino ramen",
    "ankle_dorsiflexion": "pomik kolena naprej nad stopalo ob peti na tleh",
    "hip_mobility": "aktivni upogib kolka v leže (koleno proti prsnemu košu)",
    "shoulder_mobility": "dvig rok nad glavo brez siljenja",
    "single_leg_balance": "ravnotežje na eni nogi",
    "coordination": "izmenično dotikanje nasprotne dlani in kolena",
    "body_awareness": "zaznavanje položaja telesa in nadzor tempa",
    "locomotion": "hoja po ravni podlagi",
}
VALID_STATUSES = {
    "comfortable",
    "needs_support",
    "uncertain",
    "symptoms_reported",
    "not_assessed",
}

# Self-report is task-specific. It does not diagnose a joint or spread a
# symptom beyond the movement patterns explicitly connected to the task.
TASK_PATTERNS = {
    "squat": {"squat"},
    "hinge": {"hinge"},
    "lunge": {"lunge"},
    "push": {"horizontal_push", "vertical_push"},
    "pull": {"horizontal_pull", "vertical_pull"},
    "overhead": {"vertical_push"},
    "ankle_dorsiflexion": {"squat", "lunge"},
    "hip_mobility": {"squat", "hinge", "lunge"},
    "shoulder_mobility": {"vertical_push"},
    "single_leg_balance": {"balance"},
    "coordination": {"coordination"},
    # Body awareness is retained as a coaching prompt, not translated into
    # an assumed weakness or an automatic trunk-stability exercise.
    "body_awareness": set(),
    "locomotion": {"locomotion"},
}

# Candidate order is conservative. The programme generator verifies goal,
# equipment, exclusions, pattern and exercise level before using a variant.
SUPPORTED_VARIANTS = {
    "squat": ("chair_sit_to_stand", "reaching_squat", "air_squat"),
    "hinge": ("wall_hip_hinge", "bodyweight_hip_hinge"),
    "horizontal_push": ("push_up_incline",),
    "vertical_push": ("band_overhead_press",),
    "horizontal_pull": ("band_row", "trx_row"),
    "vertical_pull": ("band_assisted_pull_up", "foot_assisted_pull_up", "band_lat_pulldown"),
    "lunge": ("supported_split_squat",),
    # A report of needing support for a lunge is not clearance for brisk walking.
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
            "body_awareness_is_a_prompt_not_a_diagnosis": True,
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
