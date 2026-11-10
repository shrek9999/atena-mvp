"""Six-pattern learning and exercise-option registry for ATENA.

The registry separates the movement pattern, the learning method and the
exercise variation. Candidate variations are options, not a mandatory linear
progression. This is a coaching aid, not a clinical screen or diagnosis.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from training.catalogue import get_exercise, load_catalogue

ASSESSMENT_VERSION = "six-pattern-coaching-v1"
VALID_DECISIONS = {"READY", "LEARN", "REGRESS", "UNASSESSABLE"}
LEVEL_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}

# Exercise IDs are intentionally explicit and verified against the live
# catalogue at runtime. The order is for presentation only, never a progression.
PATTERN_DEFINITIONS: dict[str, dict[str, Any]] = {
    "squat": {
        "label": "Počep",
        "task_id": "controlled_squat",
        "task": "Kontroliran počep v osebno ustrezni amplitudi; ne zahtevaj položaja počitka.",
        "exercise_ids": [
            "reaching_squat", "air_squat", "squat_goblet",
            "two_dumbbell_squat", "dumbbell_squat_side",
            "dumbbell_squat_front_rack", "back_squat", "front_squat",
        ],
        "learning_methods": [
            {
                "id": "reaching_counterbalance",
                "label": "Reaching squat s protiutežjo",
                "description": "Izteg rok oziroma lahek kolut pred telesom uporabi kot protiutež za lažje učenje ravnotežja in organizacije počepa.",
                "exercise_id": "reaching_squat",
            },
            {
                "id": "target_squat",
                "label": "Počep do stabilne tarče",
                "description": "Višino tarče prilagodi tako, da posameznik lahko ponovi nadzorovan spust in vstajanje.",
                "exercise_id": "chair_sit_to_stand",
            },
        ],
    },
    "hinge": {
        "label": "Predklon z nevtralno hrbtenico",
        "task_id": "dowel_rdl_pattern",
        "task": "Predklon z lahkim pripomočkom; amplituda se konča pred izgubo nadzora položaja hrbtenice.",
        "exercise_ids": [
            "wall_hip_hinge", "bodyweight_hip_hinge", "dumbbell_deadlift",
            "romanian_deadlift", "deadlift", "kettlebell_lateral_deadlift", "supported_single_leg_rdl", "single_leg_rdl",
        ],
        "learning_methods": [
            {
                "id": "dowel_four_point",
                "label": "Predklon s palico – tri stične in ena kontrolna točka",
                "description": (
                    "Palica ohranja stik s trtico oziroma križnično-sakralnim predelom, "
                    "torakalnim delom hrbtenice in zadnjim delom glave. Četrta kontrolna "
                    "točka je roka, ki drži palico v ledveni krivini. Položaj roke oziroma "
                    "ohranjena ledvena krivina se med predklonom ne sme spreminjati. "
                    "Cilj je ohraniti posameznikovo nevtralno krivino, ne izravnati hrbtenice."
                ),
                "exercise_id": None,
            },
            {
                "id": "wall_hip_hinge",
                "label": "Predklon ob steni",
                "description": "Uči pomik bokov nazaj in nadzorovan predklon z nevtralnim položajem hrbtenice.",
                "exercise_id": "wall_hip_hinge",
            },
        ],
    },
    "horizontal_push": {
        "label": "Horizontalni potisk – skleca",
        "task_id": "push_up",
        "task": "Skleca v različici, ki omogoča nadzor trupa, lopatic, komolcev in amplitude.",
        "exercise_ids": [
            "push_up_incline", "push_up", "push_up_decline",
            "dumbbell_bench_press", "barbell_bench_press",
        ],
        "learning_methods": [
            {
                "id": "incline_push_up",
                "label": "Skleca na povišani opori",
                "description": "Višino stabilne opore izberi tako, da je celotna ponovitev nadzorovana.",
                "exercise_id": "push_up_incline",
            },
        ],
    },
    "horizontal_pull": {
        "label": "Horizontalni poteg – veslanje",
        "task_id": "bent_over_row",
        "task": "Veslanje v predklonu z drogom, dvema ročkama, dvema kettlebelli ali lahko palico; pri predklonu ohrani nadzorovan položaj trupa in zabeleži pripomoček ter breme.",
        "exercise_ids": [
            "band_row", "trx_row", "ring_row", "one_arm_row",
            "kettlebell_one_arm_row", "dumbbell_bent_over_row", "barbell_bent_over_row",
        ],
        "learning_methods": [
            {
                "id": "band_row",
                "label": "Veslanje z elastiko",
                "description": "Omogoča učenje poti komolcev in lopatic z manjšo obremenitvijo trupa.",
                "exercise_id": "band_row",
            },
            {
                "id": "supported_row",
                "label": "Veslanje z oporo",
                "description": "Če predklon še ni stabilen, izberi katalogizirano veslanje z oporo namesto siljenja v predklon.",
                "exercise_id": "one_arm_row",
            },
        ],
    },
    "vertical_push": {
        "label": "Vertikalni potisk – potisk nad glavo",
        "task_id": "overhead_press",
        "task": "Potisk z zelo lahkim in zabeleženim pripomočkom v razpoložljivi nadzorovani amplitudi.",
        "exercise_ids": [
            "band_overhead_press", "overhead_press", "plate_overhead_press", "barbell_overhead_press", "pike_push_up",
        ],
        "learning_methods": [
            {
                "id": "light_implement_press",
                "label": "Potisk z zelo lahkim pripomočkom",
                "description": "Uporabi palico, lahko ploščo, ročki ali elastiko. Pripomoček in breme zabeleži; različne izvedbe niso samodejno enakovredne.",
                "exercise_id": None,
            },
            {
                "id": "band_overhead_press",
                "label": "Potisk nad glavo z elastiko",
                "description": "Elastika omogoča prilagoditev upora; preveri njeno stanje in varno postavitev.",
                "exercise_id": "band_overhead_press",
            },
        ],
    },
    "lunge": {
        "label": "Izpadni korak",
        "task_id": "controlled_lunge",
        "task": "Izpadni korak oziroma statični razkorak v nadzorovanem obsegu in z ustrezno oporo.",
        "exercise_ids": [
            "supported_split_squat", "split_squat", "reverse_lunge",
            "forward_lunge", "walking_lunge", "rear_foot_elevated_split_squat", "atg_split_squat",
        ],
        "learning_methods": [
            {
                "id": "supported_split_squat",
                "label": "Izpadni počep na mestu z oporo",
                "description": "Opora je namenjena ravnotežju; posameznik se nanjo ne sme sunkovito vleči navzgor.",
                "exercise_id": "supported_split_squat",
            },
            {
                "id": "static_split_squat",
                "label": "Statični izpadni počep",
                "description": "Najprej utrdi položaj stopal in nadzor spuščanja, nato izberi dinamično različico.",
                "exercise_id": "split_squat",
            },
        ],
    },
}


class MovementCoachingError(ValueError):
    """Raised when movement coaching data is invalid or unsupported."""


def _catalogue_index() -> dict[str, dict]:
    return {item["id"]: item for item in load_catalogue()}


def validate_pattern_registry() -> dict:
    """Validate all configured exercise and learning-method IDs."""
    catalogue = _catalogue_index()
    problems: list[str] = []
    for pattern, definition in PATTERN_DEFINITIONS.items():
        for exercise_id in definition["exercise_ids"]:
            exercise = catalogue.get(exercise_id)
            if exercise is None:
                problems.append(f"{pattern}: manjka ID vaje {exercise_id}")
            elif exercise.get("pattern") != pattern:
                problems.append(
                    f"{pattern}: {exercise_id} pripada vzorcu {exercise.get('pattern')}"
                )
        for method in definition["learning_methods"]:
            exercise_id = method.get("exercise_id")
            if exercise_id is None:
                continue
            exercise = catalogue.get(exercise_id)
            if exercise is None:
                problems.append(f"{pattern}: učna metoda {method['id']} kaže na neobstoječ ID {exercise_id}")
            elif exercise.get("pattern") != pattern:
                problems.append(f"{pattern}: učna metoda {method['id']} kaže na napačen vzorec {exercise_id}")
    if problems:
        raise MovementCoachingError("Neveljaven register gibalnih vzorcev: " + "; ".join(problems))
    return {
        "version": ASSESSMENT_VERSION,
        "patterns": len(PATTERN_DEFINITIONS),
        "exercise_links_checked": sum(
            len(item["exercise_ids"]) + sum(m["exercise_id"] is not None for m in item["learning_methods"])
            for item in PATTERN_DEFINITIONS.values()
        ),
        "valid": True,
    }


def get_pattern_coaching(pattern: str) -> dict:
    """Return learning methods and exercise options for one movement pattern."""
    if pattern not in PATTERN_DEFINITIONS:
        raise MovementCoachingError(f"Nepodprt osnovni gibalni vzorec: {pattern}.")
    validate_pattern_registry()
    result = deepcopy(PATTERN_DEFINITIONS[pattern])
    result["pattern"] = pattern
    result["learning_methods"] = [
        {**method, "exercise": get_exercise(method["exercise_id"]) if method["exercise_id"] else None}
        for method in result["learning_methods"]
    ]
    result["exercise_options"] = [get_exercise(item) for item in result.pop("exercise_ids")]
    return result


def _goal_matches(goal: str | None, exercise: dict) -> bool:
    if not goal:
        return True
    purposes = set(exercise.get("goals", []))
    if goal == "strength_hypertrophy":
        return bool(purposes & {"strength", "hypertrophy"})
    aliases = {
        "functional": {"functional", "general_fitness"},
        "general_fitness": {"general_fitness", "functional"},
        "fat_loss": {"general_fitness", "hypertrophy", "strength", "functional"},
        "power": {"strength", "power"},
        "mobility": {"mobility", "general_fitness"},
    }
    return goal in purposes or bool(purposes & aliases.get(goal, set()))


def get_exercise_options(
    pattern: str,
    equipment: list[str] | None = None,
    experience: str = "beginner",
    goal: str | None = None,
) -> list[dict]:
    """Return compatible options, without implying a fixed progression ladder."""
    if pattern not in PATTERN_DEFINITIONS:
        raise MovementCoachingError(f"Nepodprt osnovni gibalni vzorec: {pattern}.")
    if experience not in LEVEL_RANK:
        raise MovementCoachingError("Izkušnje morajo biti beginner, intermediate ali advanced.")
    available = set(equipment or []) | {"bodyweight"}
    catalogue = _catalogue_index()
    options = []
    for exercise_id in PATTERN_DEFINITIONS[pattern]["exercise_ids"]:
        exercise = catalogue[exercise_id]
        if LEVEL_RANK[exercise["level"]] > LEVEL_RANK[experience]:
            continue
        required = set(exercise.get("equipment", []))
        optional = set(exercise.get("equipment_any", []))
        if not required.issubset(available):
            continue
        if optional and not (optional & available):
            continue
        if not _goal_matches(goal, exercise):
            continue
        options.append(deepcopy(exercise))
    return options


def build_movement_decision(
    pattern: str,
    decision: str,
    *,
    observations: dict | None = None,
    equipment: list[str] | None = None,
    implement_variant: str | None = None,
    load: float | None = None,
    load_unit: str | None = None,
    camera_views: list[str] | None = None,
    capture_quality: str = "not_applicable",
    confidence: str = "not_assessed",
    limitations: list[str] | None = None,
    user_report: dict | None = None,
    selected_learning_method: str | None = None,
    selected_exercise_id: str | None = None,
    decision_reason: str = "",
) -> dict:
    """Build a versioned record while keeping symptoms separate from video evidence."""
    if pattern not in PATTERN_DEFINITIONS:
        raise MovementCoachingError(f"Nepodprt osnovni gibalni vzorec: {pattern}.")
    if decision not in VALID_DECISIONS:
        raise MovementCoachingError("Neveljavna odločitev za gibalni vzorec.")
    if not isinstance(decision_reason, str):
        raise MovementCoachingError("Razlog odločitve mora biti besedilo.")
    if load is not None and (isinstance(load, bool) or not isinstance(load, (int, float)) or load < 0):
        raise MovementCoachingError("Breme mora biti nenegativno število.")
    if selected_learning_method is not None and selected_learning_method not in {
        method["id"] for method in PATTERN_DEFINITIONS[pattern]["learning_methods"]
    }:
        raise MovementCoachingError("Izbrana učna metoda ne pripada temu vzorcu.")
    if selected_exercise_id is not None:
        exercise = get_exercise(selected_exercise_id)
        if exercise is None or exercise.get("pattern") != pattern:
            raise MovementCoachingError("Izbrana vaja ne obstaja ali ne pripada temu gibalnemu vzorcu.")
    if not isinstance(observations or {}, dict) or not isinstance(user_report or {}, dict):
        raise MovementCoachingError("Opažanja in uporabnikovo poročilo morata biti ločena objekta.")
    return {
        "assessment_version": ASSESSMENT_VERSION,
        "movement_pattern": pattern,
        "task_id": PATTERN_DEFINITIONS[pattern]["task_id"],
        "equipment": list(equipment or []),
        "implement_variant": implement_variant,
        "load": load,
        "load_unit": load_unit,
        "camera_views": list(camera_views or []),
        "capture_quality": capture_quality,
        "observations": deepcopy(observations or {}),
        "confidence": confidence,
        "limitations": list(limitations or []),
        "user_report": deepcopy(user_report or {}),
        "decision": decision,
        "selected_learning_method": selected_learning_method,
        "selected_exercise_id": selected_exercise_id,
        "decision_reason": decision_reason,
        "is_diagnosis": False,
    }
