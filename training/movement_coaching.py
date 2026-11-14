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
            "supported_squat", "chair_sit_to_stand", "reaching_squat", "air_squat", "squat_goblet", "loaded_deep_squat",
            "two_dumbbell_squat", "dumbbell_squat_side",
            "dumbbell_squat_front_rack", "back_squat", "front_squat",
        ],
        "learning_methods": [
            {
                "id": "supported_squat_assistance",
                "label": "Počep z oporo rok",
                "description": "Za razbremenitev in ravnotežje uporabi TRX, varno pritrjeno elastiko, fiksiran drog v racku približno v višini prsnega koša ali stabilno nepremično oporo. Z rokami si pomagaj toliko, da lahko noge še vedno nadzorovano izvajajo gib.",
                "exercise_id": "supported_squat",
            },
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
                "description": "Uči pomik bokov nazaj in nadzorovan predklon z nevtralnim položajem hrbtenice. Pri nelagodju v hrbtu zmanjša amplitudo in obremenitev; začni ob steni, ohrani nadzor trupa in ne sili v globino.",
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
        "task": "Najprej nadzor gibanja lopatic in rok pri horizontalnem potegu brez bremena; obremenjeno veslanje v predklonu šele po potrjenem nadzoru predklona in koordinacije potega.",
        "exercise_ids": [
            "band_row", "trx_row", "ring_row", "one_arm_row",
            "kettlebell_one_arm_row", "dumbbell_bent_over_row", "barbell_bent_over_row",
        ],
        "learning_methods": [
            {
                "id": "scapular_coordination",
                "label": "Učenje gibanja lopatic brez dodatnega bremena",
                "description": (
                    "Najprej v pokončnem položaju in nato v predklonu vadi nadzorovano "
                    "pomikanje lopatic naprej in nazaj (protrakcija/retrakcija), brez "
                    "dvigovanja ramen proti ušesom. To je učna naloga, ne obremenjena vaja."
                ),
                "exercise_id": None,
            },
            {
                "id": "light_one_arm_hinge_row",
                "label": "Enoročno veslanje v predklonu z lahkim bremenom",
                "description": (
                    "Z zelo lahko ročko ali kettlebellom najprej utrdi koordinacijo lopatice "
                    "in komolca. Trup ostane stabilen; če položaja predklona še ne obvladaš, "
                    "uporabi katalogizirano različico veslanja z oporo."
                ),
                "exercise_id": "one_arm_row",
            },
            {
                "id": "light_barbell_row",
                "label": "Veslanje z lahko palico",
                "description": (
                    "Šele ko sta koordinacija lopatic in položaj predklona zanesljiva, "
                    "uvedi veslanje z lahko palico. Breme povečuj šele ob nespremenjeni "
                    "tehniki in nadzorovanem vračanju."
                ),
                "exercise_id": "barbell_bent_over_row",
            },
            {
                "id": "band_row",
                "label": "Veslanje z elastiko",
                "description": "Za manjši upor uporabi lažjo elastiko, počasen povratek in nadzor lopatic; sidrišče mora biti varno pritrjeno.",
                "exercise_id": "band_row",
            },
        ],
    },
    "vertical_push": {
        "label": "Vertikalni potisk – potisk nad glavo",
        "task_id": "overhead_press",
        "task": "Najprej nadzorovan dvig rok nad glavo brez bremena; zunanji upor se uvede šele po potrjenem nadzoru poti rok, trupa in tolerirane amplitude.",
        "exercise_ids": [
            "band_overhead_press", "overhead_press", "plate_overhead_press", "barbell_overhead_press", "pike_push_up",
        ],
        "learning_methods": [
            {
                "id": "unloaded_overhead_reach",
                "label": "Dvig rok nad glavo brez bremena",
                "description": "Vadi počasen dvig in spust rok brez zunanjega bremena. Ohrani nadzor trupa in reber ter se ustavi v amplitudi, ki jo lahko ponoviš brez kompenzacije.",
                "exercise_id": None,
            },
            {
                "id": "light_implement_press",
                "label": "Potisk z zelo lahkim pripomočkom",
                "description": "Uporabi palico, lahko ploščo, ročki ali elastiko. Pripomoček in breme zabeleži; različne izvedbe niso samodejno enakovredne.",
                "exercise_id": None,
            },
            {
                "id": "band_overhead_press",
                "label": "Potisk nad glavo z elastiko",
                "description": "Za ramo izberi zelo lahek upor in samo tolerirano amplitudo; gib izvedi počasi, elastiko pa varno pritrdi in preveri.",
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


ACUTE_WARNING_SIGNS = {
    "acute_sharp_pain",
    "new_swelling",
    "muscle_spasm",
    "sudden_loss_of_function",
    "rapidly_worsening_symptoms",
}


def validate_symptom_regression_report(
    user_report: dict,
    decision: str,
    selected_exercise_id: str | None,
    allowed_variants: tuple[str, ...],
) -> None:
    """Validate symptom response using tolerance, symptom behavior and acute warning signs."""
    if not isinstance(user_report, dict) or user_report.get("status") != "symptoms_reported":
        return
    report_flags = user_report.get("acute_warning_signs", [])
    if not isinstance(report_flags, list) or any(flag not in ACUTE_WARNING_SIGNS for flag in report_flags):
        raise MovementCoachingError("Seznam akutnih opozorilnih znakov ni veljaven.")
    test = user_report.get("regression_test")
    if report_flags:
        if decision != "UNASSESSABLE" or selected_exercise_id is not None or test is not None:
            raise MovementCoachingError("Ob akutnem opozorilnem znaku prizadeti vzorec ne sme biti vključen v program.")
        return
    if decision == "UNASSESSABLE":
        if selected_exercise_id is not None:
            raise MovementCoachingError("Neocenjen simptomatski vzorec ne sme imeti izbrane vaje.")
        if test is not None:
            if not isinstance(test, dict):
                raise MovementCoachingError("Ponovni preizkus mora biti objekt.")
            pain = test.get("pain_during")
            flags = test.get("acute_warning_signs", [])
            if (
                test.get("status") != "not_tolerated"
                or test.get("variation_id") not in allowed_variants
                or isinstance(pain, bool)
                or not isinstance(pain, (int, float))
                or not 0 <= pain <= 10
                or not isinstance(test.get("worsened"), bool)
                or not isinstance(flags, list)
                or any(flag not in ACUTE_WARNING_SIGNS for flag in flags)
                or (test.get("anchor_point_confirmed") is not None and not isinstance(test.get("anchor_point_confirmed"), bool))
            ):
                raise MovementCoachingError(
                    "Netoleriran preizkus mora vsebovati veljaven status, oceno bolečine in seznam opozorilnih znakov."
                )
        return

    if not isinstance(test, dict):
        raise MovementCoachingError("Za vključitev simptomatskega vzorca je potreben zabeležen ponovni preizkus.")
    pain = test.get("pain_during")
    flags = test.get("acute_warning_signs", [])
    support_method = test.get("support_method")
    valid_support_methods = {"trx", "band", "fixed_bar", "stable_support"}
    if support_method is not None and support_method not in valid_support_methods:
        raise MovementCoachingError("Neveljaven način opore pri regresijskem počepu.")
    if test.get("variation_id") == "supported_squat" and support_method not in valid_support_methods:
        raise MovementCoachingError(
            "Pri podprtem počepu mora biti navedena preverjena opora: TRX, elastika, fiksni drog ali stabilna opora."
        )
    if test.get("variation_id") in {"supported_squat", "band_row", "band_overhead_press"} and support_method == "band" and test.get("anchor_point_confirmed") is not True:
        raise MovementCoachingError("Za uporabo elastike mora biti potrjeno varno, namensko sidrišče.")
    if test.get("variation_id") == "trx_row" and support_method != "trx":
        raise MovementCoachingError("Za veslanje s TRX mora biti izrecno potrjena uporaba TRX.")
    if (
        decision != "REGRESS"
        or test.get("status") != "tolerated"
        or not selected_exercise_id
        or selected_exercise_id not in allowed_variants
        or test.get("variation_id") != selected_exercise_id
        or isinstance(pain, bool)
        or not isinstance(pain, (int, float))
        or not 0 <= pain <= 4
        or test.get("worsened") is not False
        or not isinstance(flags, list)
        or flags
        or any(flag not in ACUTE_WARNING_SIGNS for flag in flags)
        or test.get("tempo") != "slow_controlled"
        or test.get("load_adjustment") not in {"reduced", "bodyweight_or_assisted"}
        or test.get("range_adjustment") != "within_tolerance"
    ):
        raise MovementCoachingError(
            "Blago nelagodje do 4/10 je mogoče tolerirati le, če se ne stopnjuje, "
            "ni opozorilnih znakov ter so breme, tempo in amplituda ustrezno prilagojeni. "
            "Akutna bolečina, nova oteklina ali spazem zahtevajo prekinitev vadbe prizadetega področja."
        )


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
        if exercise_id == "supported_squat":
            # A band is only a support when anchored to a verified anchor point;
            # a fixed bar must be a stable rack, not an improvised loose bar.
            support_available = (
                "household_support" in available
                or "suspension_trainer" in available
                or {"resistance_band", "anchor_point"}.issubset(available)
                or "rack" in available
            )
            if not support_available:
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
