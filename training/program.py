"""Deterministic, catalogue-backed training-program generator with Phase 5 quality rules."""
from __future__ import annotations

from collections import Counter
from typing import Any

from training.catalogue import get_exercises
from training.movement_assessment import (
    MovementAssessmentError, SUPPORTED_VARIANTS, TASK_PATTERNS,
    assess_movement_competence,
)

SUPPORTED_GOALS = {"hypertrophy", "strength", "strength_hypertrophy", "fat_loss", "general_fitness", "functional", "power", "endurance", "mobility"}
SUPPORTED_LEVELS = {"beginner", "intermediate", "advanced"}
SUPPORTED_SESSIONS = {2, 3, 4}
PATTERN_LABELS = {
    "squat": "počep",
    "lunge": "izpadni korak",
    "hinge": "predklon z nevtralnim položajem hrbtenice",
    "hip_extension": "izteg kolkov",
    "horizontal_push": "horizontalni potisk",
    "horizontal_pull": "horizontalni poteg",
    "vertical_push": "vertikalni potisk",
    "vertical_pull": "vertikalni poteg",
    "carry": "nošenje",
    "anti_rotation": "preprečevanje rotacije",
    "trunk_stability": "stabilizacija trupa",
    "jump": "skok",
    "hinge_power": "eksplozivni izteg kolkov",
    "accessory": "dopolnilna vaja",
    "conditioning": "kondicijska vadba",
    "locomotion": "lokomocija",
    "mobility": "aktivna mobilnost",
    "mobility_stretch": "raztezanje",
    "knee_flexion": "upogib kolena",
    "balance": "ravnotežje",
    "coordination": "koordinacija",
}
GOAL_PRIMARY_PURPOSE = {
    "strength": "strength",
    "hypertrophy": "hypertrophy",
    "general_fitness": "general_fitness",
    "functional": "functional_fitness",
    "power": "power",
    "endurance": "cardiorespiratory_conditioning",
    "mobility": "mobility",
}
GOAL_PURPOSES = {
    "strength": {"strength"},
    "hypertrophy": {"hypertrophy"},
    "strength_hypertrophy": {"strength", "hypertrophy"},
    "fat_loss": {"strength", "hypertrophy", "general_fitness", "cardiorespiratory_conditioning"},
    "general_fitness": {"general_fitness", "functional_fitness", "strength", "cardiorespiratory_conditioning", "mobility", "balance", "coordination"},
    "functional": {"functional_fitness", "general_fitness", "strength", "cardiorespiratory_conditioning", "mobility", "balance", "coordination", "power"},
    "power": {"power", "strength"},
    "endurance": {"cardiorespiratory_conditioning", "muscular_endurance", "general_fitness"},
    "mobility": {"mobility", "strength", "general_fitness", "functional_fitness", "balance", "coordination"},
}
PATTERN_ORDER = [
    "squat", "lunge", "hinge", "hip_extension", "horizontal_push", "horizontal_pull",
    "vertical_push", "vertical_pull", "carry", "anti_rotation",
    "trunk_stability", "jump", "hinge_power", "conditioning", "locomotion", "mobility", "mobility_stretch", "knee_flexion", "balance", "coordination",
]


class ProgramValidationError(ValueError):
    """Raised when the supplied training profile cannot be safely planned."""


class ProgramSafetyBlock(ProgramValidationError):
    """Raised when feedback indicates that automatic programme adaptation must stop."""


def _validate_feedback(feedback: object) -> dict | None:
    if feedback is None:
        return None
    if not isinstance(feedback, dict):
        raise ProgramValidationError("Povratna informacija mora biti JSON objekt.")
    difficulty = feedback.get("difficulty", "right")
    completed = feedback.get("completed", True)
    discomfort = feedback.get("discomfort", "no")
    if not isinstance(difficulty, str) or difficulty not in {"easy", "right", "hard"}:
        raise ProgramValidationError("Težavnost mora biti easy, right ali hard.")
    if not isinstance(completed, bool):
        raise ProgramValidationError("completed mora biti true ali false.")
    if not isinstance(discomfort, str) or discomfort not in {"no", "yes"}:
        raise ProgramValidationError("discomfort mora biti yes ali no.")
    if discomfort == "yes":
        raise ProgramSafetyBlock(
            "Ob bolečini ali novem nelagodju ne bom samodejno spreminjal programa. " 
            "Prekini oziroma prilagodi vadbo; če so simptomi novi, izraziti ali vztrajajo, " 
            "se posvetuj z ustreznim zdravstvenim strokovnjakom."
        )
    movement_control = feedback.get("movement_control", "none")
    if not isinstance(movement_control, str) or movement_control not in {"none", "spinal_flexion", "bracing", "both"}:
        raise ProgramValidationError("movement_control mora biti none, spinal_flexion, bracing ali both.")
    recovery = feedback.get("recovery", "normal")
    if not isinstance(recovery, str) or recovery not in {"good", "normal", "poor"}:
        raise ProgramValidationError("recovery mora biti good, normal ali poor.")
    return {"difficulty": difficulty, "completed": completed, "movement_control": movement_control, "recovery": recovery}


def _positive_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ProgramValidationError(f"Polje {field} mora biti celo število med {minimum} in {maximum}.")
    return value


def validate_profile(profile: object) -> dict:
    if not isinstance(profile, dict):
        raise ProgramValidationError("Profil mora biti JSON objekt.")
    goal = profile.get("goal")
    if goal not in SUPPORTED_GOALS:
        raise ProgramValidationError(f"Cilj mora biti eden od: {', '.join(sorted(SUPPORTED_GOALS))}.")
    level = profile.get("experience")
    if level not in SUPPORTED_LEVELS:
        raise ProgramValidationError("Izkušnje morajo biti beginner, intermediate ali advanced.")
    sessions = _positive_int(profile.get("sessions_per_week"), "sessions_per_week", 2, 4)
    if sessions not in SUPPORTED_SESSIONS:
        raise ProgramValidationError("Za zdaj so podprti 2, 3 ali 4 treningi na teden.")
    duration = _positive_int(profile.get("session_minutes"), "session_minutes", 25, 120)
    equipment = profile.get("equipment")
    if not isinstance(equipment, list) or any(not isinstance(x, str) or not x.strip() for x in equipment):
        raise ProgramValidationError("equipment mora biti seznam razpoložljive opreme.")
    exclusions = profile.get("excluded_exercise_ids", [])
    excluded_patterns = profile.get("excluded_patterns", [])
    for field, values in (("excluded_exercise_ids", exclusions), ("excluded_patterns", excluded_patterns)):
        if not isinstance(values, list) or any(not isinstance(x, str) or not x.strip() for x in values):
            raise ProgramValidationError(f"{field} mora biti seznam nizov.")
    accessories = profile.get("include_accessories", level == "advanced")
    if not isinstance(accessories, bool):
        raise ProgramValidationError("include_accessories mora biti true ali false.")
    if accessories and level != "advanced":
        raise ProgramValidationError("Enosklepne dopolnilne vaje so v tej fazi na voljo le naprednim vadečim.")
    training_emphasis = profile.get("training_emphasis", "balanced")
    if training_emphasis not in {"balanced", "strength", "hypertrophy"}:
        raise ProgramValidationError("training_emphasis mora biti balanced, strength ali hypertrophy.")
    # Specialisation is available only to advanced users whose primary goal is
    # the combined strength-and-muscle-mass track.
    if level != "advanced" or goal != "strength_hypertrophy":
        training_emphasis = "balanced"
    pistol_squat_capable = profile.get("pistol_squat_capable", False)
    if not isinstance(pistol_squat_capable, bool):
        raise ProgramValidationError("pistol_squat_capable mora biti true ali false.")
    return {
        **profile,
        "pistol_squat_capable": pistol_squat_capable,
        "sessions_per_week": sessions,
        "session_minutes": duration,
        "equipment": sorted(set(equipment) | {"bodyweight"}),
        "excluded_exercise_ids": set(exclusions),
        "excluded_patterns": set(excluded_patterns),
        "include_accessories": accessories,
        "training_emphasis": training_emphasis,
    }


def _session_patterns(session_index: int, sessions: int, goal: str, include_accessories: bool = False, include_stability: bool = False, experience: str = "intermediate") -> list[str]:
    """Compact full-body templates; trunk-control work is added only when feedback supports it."""
    if goal == "fat_loss" and sessions >= 3 and session_index >= 2:
        # Two resistance-focused full-body days remain the foundation. Additional days
        # add a short aerobic/conditioning session rather than more lifting volume.
        return ["locomotion", "lunge", "conditioning"]
    if goal == "functional":
        # Keep sessions compact: distribute horizontal push and pull across the
        # week while preserving squat, hinge and the functional capacities.
        base = ["squat", "hinge", "horizontal_push" if session_index % 2 == 0 else "horizontal_pull"]
        # Training history is not a movement-readiness screen. Do not prescribe
        # plyometrics or rapid change-of-direction drills by default at any level.
        # Carry work, balance and controlled low-speed coordination preserve the
        # functional intent until landing/braking readiness can be assessed explicitly.
        functional_additions = [
            ["balance", "carry"],
            ["coordination", "conditioning"],
            ["balance", "carry"],
            ["coordination", "conditioning"],
        ]
        patterns = base + functional_additions[session_index]
        if include_stability:
            patterns.insert(0, "trunk_stability")
        if sessions >= 3:
            patterns.append("lunge" if session_index % 2 == 0 else ("vertical_push" if session_index % 4 == 1 else "vertical_pull"))
        return patterns
    if goal == "endurance":
        # Keep a minimum viable session even when no loaded carry equipment exists.
        # Carry is an optional fourth pattern and is omitted when no safe load is available.
        return ["locomotion", "lunge", "conditioning"]
    if goal == "mobility":
        # Mobility sessions stay compact and combine active range work with
        # foundational loaded patterns. Rotate emphasis across the week instead
        # of placing every mobility and strength pattern into one long session.
        mobility_templates = [
            ["mobility", "mobility", "mobility_stretch", "squat", "lunge", "horizontal_push"],
            ["mobility", "mobility", "mobility_stretch", "hinge", "horizontal_pull", "accessory"],
        ]
        patterns = mobility_templates[session_index % len(mobility_templates)]
        if include_stability:
            patterns = ["trunk_stability"] + patterns[:-1]
        return patterns
    base = ["squat", "hinge", "horizontal_push", "horizontal_pull"]
    if goal == "fat_loss":
        # Preserve two resistance-focused full-body sessions plus a controlled
        # conditioning element without stacking both vertical patterns as well.
        patterns = base + ["lunge", "conditioning"]
        if include_stability:
            patterns.insert(0, "trunk_stability")
        return patterns
    if sessions == 2:
        extras = [["lunge", "vertical_push"], ["lunge", "vertical_pull"]]
    elif sessions == 3:
        extras = [["lunge", "vertical_push"], ["vertical_pull", "lunge"], ["lunge", "vertical_push"]]
    else:
        extras = [["lunge", "vertical_push"], ["vertical_pull", "lunge"], ["lunge", "vertical_push"], ["vertical_pull", "lunge"]]
    patterns = base + (extras[session_index][:1] if include_stability else extras[session_index])
    if goal == "fat_loss":
        patterns.append("conditioning")
    if include_stability:
        patterns.insert(0, "trunk_stability")
    if goal == "power":
        patterns += ["jump", "hinge_power"]
    if include_accessories and len(patterns) < 7:
        patterns += ["accessory"]
    return patterns


def _prescription(goal: str, level: str, pattern: str, exercise: dict) -> dict:
    """Prescribe by goal, training age and movement class; beginners build skill first."""
    unilateral = bool(exercise.get("unilateral"))
    is_stability = pattern in {"trunk_stability", "anti_rotation"}
    is_power = pattern in {"jump", "hinge_power"}
    rir_range = None
    functional_conditioning_seconds = None
    carry_work_seconds = None
    if pattern == "carry":
        # Loaded carries are prescribed by distance, never by repetitions.
        if level == "beginner":
            sets, reps, rir, rest = 2, "15–20 m", None, 60
            carry_work_seconds = 20
        elif level == "intermediate":
            sets, reps, rir, rest = 2, "20–30 m", None, 75
            carry_work_seconds = 25
        else:
            sets, reps, rir, rest = 3, "25–40 m", None, 90
            carry_work_seconds = 35
    elif goal in {"functional", "general_fitness"} and pattern == "conditioning":
        # Functional conditioning is a short, controlled work interval rather than
        # a slow resistance exercise with RIR and a lifting tempo.
        kind = exercise.get("endurance_type")
        if kind == "aerobic":
            duration = {"beginner": 30, "intermediate": 40, "advanced": 45}[level]
            sets, rest = (2 if level == "beginner" else 3), 45
        elif kind == "anaerobic":
            duration = {"beginner": 15, "intermediate": 20, "advanced": 25}[level]
            sets, rest = (2 if level == "beginner" else 3), (60 if level != "advanced" else 75)
        else:
            duration = {"beginner": 20, "intermediate": 25, "advanced": 30}[level]
            sets, rest = (2 if level == "beginner" else 3), 60
        reps, rir = f"{duration} s", None
        functional_conditioning_seconds = duration
    elif goal == "mobility" and pattern == "mobility_stretch":
        sets, reps, rir, rest = (3, "20–30 s", None, 30) if level == "advanced" else (2, "20–30 s", None, 30)
    elif goal == "mobility" and exercise.get("mobility_strength"):
        sets, reps, rir, rest = (3, "6–10", 3, 90) if level == "advanced" else (2, "8–12", 3, 75)
    elif goal == "mobility" or pattern in {"mobility", "mobility_stretch"}:
        if level == "beginner":
            sets, reps, rir, rest = 2, "5–8", None, 30
        elif level == "intermediate":
            sets, reps, rir, rest = 2, "6–10", None, 30
        else:
            sets, reps, rir, rest = 3, "6–10", None, 45
    elif goal == "fat_loss" and pattern == "locomotion":
        duration = {"beginner": "6 min", "intermediate": "8 min", "advanced": "10 min"}[level]
        sets, reps, rir, rest = 1, duration, None, 0
    elif goal == "fat_loss" and pattern == "conditioning":
        kind = exercise.get("endurance_type")
        sets = {"beginner": 2, "intermediate": 3, "advanced": 4}[level]
        if kind == "aerobic":
            reps, rir, rest = "1 min", None, 60
        elif kind == "anaerobic":
            reps, rir, rest = "15–20 s", None, 60
        else:
            reps, rir, rest = "20–30 s", None, 60
    elif goal == "endurance" and pattern == "locomotion":
        sets, reps, rir, rest = 1, "20–30 min", None, 0
    elif goal == "endurance" and pattern == "conditioning":
        kind = exercise.get("endurance_type")
        # Keep the agreed four-interval structure; scale interval duration by experience below.
        sets = 4
        if kind == "aerobic":
            reps, rir, rest = "2–3 min", None, 90
        elif kind == "anaerobic":
            reps, rir, rest = "15–20 s", None, 90
        else:
            reps, rir, rest = "20–30 s", None, 60
    elif goal == "endurance" and pattern in {"carry", "lunge"}:
        sets, reps, rir, rest = 2, "12–20", None, 45
    elif is_power:
        sets, reps, rir, rest = 3, "3–5", 4, 180
    elif exercise.get("id") == "l_sit":
        sets, reps, rir, rest = 3, "8–15 s", None, 60
    elif pattern == "balance":
        sets, reps, rir, rest = 2, "5–8", None, 45
    elif pattern == "coordination":
        sets, reps, rir, rest = 3, "10–15 s", None, 45
    elif level == "beginner" and goal in {"strength", "hypertrophy", "strength_hypertrophy"}:
        # Beginners first build repeatable technique with moderate reps and a clear reserve.
        if pattern in {"lunge"} or unilateral:
            sets, reps, rir, rest = 2, "8–12", 3, 90
        elif pattern in {"vertical_push", "vertical_pull"}:
            sets, reps, rir, rest = 2, "8–12", 3, 90
        elif pattern in {"hip_extension", "carry"}:
            sets, reps, rir, rest = 2, "10–15", 3, 75
        else:
            sets, reps, rir, rest = 3, "8–12", 3, 120 if pattern in {"squat", "hinge"} else 90
        rir_range = "2–3"
    elif level == "intermediate" and goal in {"strength", "hypertrophy", "strength_hypertrophy"}:
        # Preserve the agreed practical base dose for less-experienced lifters;
        # exercise selection and tempo provide the next level of technical demand.
        if pattern in {"lunge"} or unilateral:
            sets, reps, rir, rest = 2, "8–12", 3, 90
        elif pattern in {"vertical_push", "vertical_pull"}:
            sets, reps, rir, rest = 2, "8–12", 3, 90
        elif pattern in {"hip_extension", "carry"}:
            sets, reps, rir, rest = 2, "10–15", 3, 75
        else:
            sets, reps, rir, rest = 3, "8–12", 3, 120 if pattern in {"squat", "hinge"} else 90
        rir_range = "2–3"
    elif level == "intermediate" and goal == "fat_loss":
        if pattern in {"lunge"} or unilateral:
            sets, reps, rir, rest = 2, "8–10", 2, 90
        elif pattern in {"vertical_push", "vertical_pull"}:
            sets, reps, rir, rest = 2, "8–12", 2, 90
        elif pattern in {"hip_extension", "carry"}:
            sets, reps, rir, rest = 2, "10–15", 2, 75
        elif pattern in {"squat", "hinge"}:
            sets, reps, rir, rest = 3, "6–10", 2, 120
        else:
            sets, reps, rir, rest = 3, "8–12", 2, 90
    elif level == "beginner":
        # Beginners still train toward the selected goal; the goal changes the
        # dose while technique and a conservative effort reserve remain priorities.
        if is_stability:
            sets, reps, rir, rest = 2, "10–15", 3, 60
        elif goal == "strength":
            if pattern in {"squat", "hinge"}:
                sets, reps, rir, rest = 3, "8–12", 3, 150
            elif pattern == "lunge" or unilateral:
                sets, reps, rir, rest = 2, "8–10", 3, 90
            elif pattern in {"vertical_push", "vertical_pull"}:
                sets, reps, rir, rest = 2, "8–12", 3, 90
            elif pattern in {"hip_extension", "carry"}:
                sets, reps, rir, rest = 2, "10–15", 3, 75
            else:
                sets, reps, rir, rest = 3, "8–12", 3, 90
        elif goal in {"hypertrophy", "fat_loss"}:
            if pattern in {"squat", "hinge"}:
                sets, reps, rir, rest = 3, "8–12", 3, 120
            elif pattern == "lunge" or unilateral:
                sets, reps, rir, rest = 2, "8–10", 3, 90
            elif pattern in {"vertical_push", "vertical_pull"}:
                sets, reps, rir, rest = 2, "10–15", 3, 90
            elif pattern in {"hip_extension", "carry"}:
                sets, reps, rir, rest = 2, "12–15", 3, 75
            else:
                sets, reps, rir, rest = 3, "10–15", 3, 90
        else:
            if pattern in {"lunge"} or unilateral:
                sets, reps, rir, rest = 2, "8–10", 3, 90
            elif pattern in {"vertical_push", "vertical_pull"}:
                sets, reps, rir, rest = 2, "8–12", 3, 90
            elif pattern in {"hip_extension", "carry"}:
                sets, reps, rir, rest = 2, "10–15", 3, 75
            else:
                sets, reps, rir, rest = 3, "8–12", 3, 90
        rir_range = "2–3"
    elif goal == "strength":
        if pattern in {"squat", "hinge"}:
            sets, reps, rir, rest = (4, "3–6", 2, 210) if level == "advanced" else (3, "5–8", 2, 180)
        elif is_stability:
            sets, reps, rir, rest = 2, "10–15", 3, 60
        elif pattern in {"carry", "hip_extension"}:
            sets, reps, rir, rest = 2, "8–12", 3, 75
        else:
            sets, reps, rir, rest = 3, "6–8", 2, 120
    elif goal == "strength_hypertrophy":
        if pattern in {"squat", "hinge"}:
            sets, reps, rir, rest = 3, "5–8", 2, 180
        elif is_stability:
            sets, reps, rir, rest = 2, "10–15", 3, 60
        elif pattern in {"lunge", "horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull"} or unilateral:
            sets, reps, rir, rest = 3, "8–12", 2, 90
        elif pattern in {"carry", "hip_extension"}:
            sets, reps, rir, rest = 2, "10–15", 2, 75
        else:
            sets, reps, rir, rest = 2, "10–15", 2, 75
    elif goal in {"hypertrophy", "fat_loss"}:
        if pattern in {"squat", "hinge"}:
            sets, reps, rir, rest = 3, "6–10", (2 if level != "beginner" else 3), 120 if level == "advanced" else 90
        elif pattern == "lunge" or unilateral:
            sets, reps, rir, rest = 2, "8–10", (2 if level != "beginner" else 3), 90
        elif pattern in {"vertical_push", "vertical_pull"}:
            sets, reps, rir, rest = 2, "8–12", (2 if level != "beginner" else 3), 90
        elif pattern in {"trunk_stability", "anti_rotation"}:
            sets, reps, rir, rest = 2, "10–15", 3, 60
        elif pattern in {"hip_extension", "carry"}:
            sets, reps, rir, rest = 2, "10–15", 2 if level != "beginner" else 3, 75
        else:
            sets, reps, rir, rest = 3, "8–12", (2 if level != "beginner" else 3), 90
    else:
        if pattern in {"trunk_stability", "anti_rotation"}:
            sets, reps, rir, rest = (2, "10–15", 3, 60) if level == "intermediate" else (3, "10–15", 2, 60)
        elif pattern in {"hip_extension", "carry"}:
            sets, reps, rir, rest = (2, "10–15", 3, 75) if level == "intermediate" else (3, "8–12", 2, 90)
        elif level == "intermediate":
            sets, reps, rir, rest = 3, "8–12", 3, 90
        else:
            sets, reps, rir, rest = 3, "6–10", 2, 120
    if pattern == "carry":
        tempo, tempo_description, tempo_seconds = "tekoče", "Hodi z enakomernim, nadzorovanim korakom; breme naj ne spremeni drže ali kakovosti hoje.", 0
    elif functional_conditioning_seconds is not None:
        tempo, tempo_description, tempo_seconds = "ritmično", "Ohrani enakomeren, nadzorovan ritem; interval končaj, ko se kakovost izvedbe poslabša.", 0
    elif pattern == "mobility_stretch":
        tempo, tempo_description, tempo_seconds = "zadržanje", "Zadrži blag do zmeren razteg, dihaj sproščeno in ne sili v končni položaj.", 0
    elif goal == "mobility" or pattern == "mobility":
        tempo, tempo_description, tempo_seconds = "kontrolirano", "Aktivno raziskuj razpoložljivo amplitudo brez sunkov in prisiljevanja.", 4
    elif goal == "endurance" or (goal == "fat_loss" and pattern in {"locomotion", "conditioning"}):
        tempo, tempo_description, tempo_seconds = "ritmično", "Ohrani enakomeren ritem in intenzivnost, ki ustreza predpisanemu cilju.", 0
    elif is_power:
        tempo, tempo_description, tempo_seconds = "1–0–X–0", "Nadzorovan začetni položaj; dvig oziroma odriv izvedi hitro in tehnično čisto; med ponovitvami se ponastavi.", 3
    elif pattern in {"balance", "coordination"}:
        tempo, tempo_description, tempo_seconds = "kontrolirano", "Najprej kakovost in nadzor; hitrost ali doseg povečuj šele, ko je izvedba ponovljiva.", 0
    elif is_stability:
        tempo, tempo_description, tempo_seconds = "2–1–2–1", "2 s izteg oziroma odmik · 1 s nadzor · 2 s vrnitev · 1 s ponastavitev.", 6
    elif goal == "strength_hypertrophy" and level == "beginner":
        # Agreed beginner combined-goal default: controlled, repeatable 2–1–1–0.
        tempo, tempo_description, tempo_seconds = "2–1–1–0", "2 s nadzorovan spust · 1 s nadzor v spodnjem položaju · 1 s dvig · brez premora v vrhu.", 4
    elif level == "beginner":
        # Foundational exercises use the same learning tempo across strength and hypertrophy goals.
        tempo, tempo_description, tempo_seconds = "3–1–1–0", "3 s nadzorovan spust · 1 s nadzor v spodnjem položaju · 1 s dvig · brez premora v vrhu.", 5
    elif goal == "strength_hypertrophy" and pattern in {"squat", "hinge"}:
        tempo, tempo_description, tempo_seconds = "2–0–X–0", "2 s nadzorovan spust · brez premora v spodnjem položaju · koncentrično fazo izvedi z maksimalno namero hitrosti (X), vendar brez izgube tehnike · brez premora v vrhu.", 3
    elif goal == "strength_hypertrophy":
        tempo, tempo_description, tempo_seconds = "3–1–2–0", "3 s nadzorovana ekscentrična faza · 1 s nadzor v spodnjem položaju · 2 s koncentrična faza · brez premora v vrhu.", 6
    elif goal == "strength":
        tempo, tempo_description, tempo_seconds = "2–0–X–0", "2 s nadzorovan spust · brez premora v spodnjem položaju · koncentrično fazo izvedi z maksimalno namero hitrosti (X), vendar brez izgube tehnike · brez premora v vrhu.", 3
    elif goal in {"hypertrophy", "fat_loss"}:
        tempo, tempo_description, tempo_seconds = "3–1–2–0", "3 s ekscentrična faza · 1 s nadzor v spodnjem položaju · 2 s koncentrična faza · brez premora v vrhu.", 6
    else:
        tempo, tempo_description, tempo_seconds = "2–0–1–0", "2 s nadzorovan spust · 1 s dvig; ohrani tekočo, tehnično čisto izvedbo.", 3
    prescription = {
        "sets": sets,
        "reps": reps,
        "rest_seconds": rest,
        "rep_unit": "per_side" if (unilateral or exercise.get("reps_per_side")) else "total",
        "tempo": tempo,
        "tempo_description": tempo_description,
        "tempo_seconds_per_rep": tempo_seconds,
    }
    if pattern == "carry":
        prescription.update({
            "distance_based": True,
            "work_seconds": carry_work_seconds,
            "time_label": "razdalje",
        })
    elif functional_conditioning_seconds is not None:
        prescription.update({
            "work_seconds": functional_conditioning_seconds,
            "time_label": "kondicijskega intervala",
        })
    elif exercise.get("id") == "l_sit":
        prescription.update({"reps": "8–15 s", "work_seconds": 12, "time_label": "zadržanja"})
    elif exercise.get("time_based") and pattern in {"trunk_stability", "anti_rotation"}:
        prescription.update({"reps": "8–15 s", "work_seconds": 10, "time_label": "zadržanja"})
    elif pattern == "coordination":
        prescription.update({"work_seconds": 12, "time_label": "koordinacijskega intervala"})
    if goal == "fat_loss" and pattern == "locomotion":
        prescription.update({"work_seconds": 480, "time_label": "kratka aerobna aktivnost", "effort_target": "Lahkoten do zmeren pogovorni tempo; izvedba naj ostane sproščena in ponovljiva."})
    elif goal == "fat_loss" and pattern == "conditioning":
        kind = exercise.get("endurance_type")
        work_seconds = 60 if kind == "aerobic" else (18 if kind == "anaerobic" else 25)
        prescription.update({"work_seconds": work_seconds, "time_label": "kratek kondicijski interval", "effort_target": "Nadzorovana intenzivnost; ne izvajaj maksimalno in ne žrtvuj tehnike."})
    elif goal == "endurance" and pattern == "locomotion":
        prescription.update({"work_seconds": 1200, "time_label": "neprekinjene aerobne aktivnosti", "effort_target": "Zmeren pogovorni tempo; lahko govoriš v stavkih, vendar čutiš pospešeno dihanje."})
    elif goal == "endurance" and pattern == "conditioning":
        kind = exercise.get("endurance_type")
        duration = (
            {"beginner": 120, "intermediate": 150, "advanced": 180}[level]
            if kind == "aerobic" else
            {"beginner": 15, "intermediate": 18, "advanced": 20}[level]
            if kind == "anaerobic" else
            {"beginner": 20, "intermediate": 25, "advanced": 30}[level]
        )
        target = (
            "Zmeren, enakomeren napor; ohrani pogovorni tempo in tehniko."
            if kind == "aerobic" else
            "Kratek intenzivnejši interval; kakovost izvedbe ostane pred hitrostjo."
            if kind == "anaerobic" else
            "Ponavljaj delo z enakomerno tehniko; končaj interval, ko se kakovost poslabša."
        )
        prescription.update({"work_seconds": duration, "time_label": "intervala", "effort_target": target})
    elif (goal == "mobility" or pattern in {"mobility", "mobility_stretch"}) and exercise.get("time_based"):
        duration = 30 if pattern == "mobility_stretch" else 20
        target = "Zadrži blag do zmeren razteg brez bolečine, mravljinčenja ali prisiljevanja." if pattern == "mobility_stretch" else "Deluj v kontrolirani neboleči amplitudi; brez siljenja v končni položaj."
        prescription.update({"work_seconds": duration, "time_label": "zadržanja" if pattern == "mobility_stretch" else "aktivnega zadržanja", "effort_target": target})
    if pattern == "carry":
        prescription["effort_target"] = "Ohrani pokončno držo, stabilen prijem in enakomerno hojo; prekini, ko se drža ali korak poslabšata."
    elif functional_conditioning_seconds is not None:
        prescription["effort_target"] = "Nadzorovana intenzivnost; končaj interval, ko se poslabša tehnika, ritem ali nadzor trupa."
    elif exercise.get("id") == "l_sit":
        prescription["effort_target"] = "Zadrži kakovosten položaj z aktivnim potiskom v oporo; končaj, preden izgubiš stabilen položaj ramen ali medenice."
    elif pattern == "balance":
        prescription["effort_target"] = "Ohrani stabilno oporo in nadzor; končaj serijo, ko se kakovost izvedbe poslabša."
    elif pattern == "coordination":
        prescription["effort_target"] = "Izvedi kratke, kakovostne ponovitve; ustavi interval, ko se poslabša koordinacija ali zaviranje."
    elif is_stability:
        prescription["effort_target"] = (
            "Serijo zaključi, preden izgubiš stabilen položaj ali nadzor nad gibanjem."
        )
    else:
        prescription["rir"] = rir
        if rir_range:
            prescription["rir_range"] = rir_range
    return prescription


def _estimated_minutes(exercises: list[dict], warm_up_minutes: int = 7) -> int:
    # Approximation includes flexible 5–10 min warm-up, execution, rests and transitions.
    total_seconds = warm_up_minutes * 60
    for item in exercises:
        prescription = item["prescription"]
        sets = prescription["sets"]
        sides = 2 if prescription.get("rep_unit") == "per_side" else 1
        if prescription.get("work_seconds") is not None:
            execution = prescription["work_seconds"] * sets * sides
        else:
            rep_bounds = [int(value) for value in prescription["reps"].split("–")]
            reps = round(sum(rep_bounds) / len(rep_bounds))
            execution = reps * prescription.get("tempo_seconds_per_rep", 4) * sets * sides
        rests = max(0, sets - 1) * prescription["rest_seconds"]
        total_seconds += execution + rests + 45
    return round(total_seconds / 60)


def _display_exercise_reference(value: str, names: dict[str, str]) -> str:
    """Translate catalogue IDs used in regressions/alternatives to user-facing names."""
    return names.get(value, value)


def generate_program(profile: object, feedback: object = None, movement_assessment: object = None) -> dict:
    """Generate a repeatable catalogue plan, conservatively adapting to the last session."""
    p = validate_profile(profile)
    planning_goal = p["goal"]
    if p["goal"] == "strength_hypertrophy" and p["experience"] == "advanced":
        if p["training_emphasis"] in {"strength", "hypertrophy"}:
            planning_goal = p["training_emphasis"]
    response = _validate_feedback(feedback)
    movement_summary = None
    movement_status_by_pattern: dict[str, str] = {}
    movement_tasks_by_pattern: dict[str, list[str]] = {}
    movement_adaptation_events = []
    if movement_assessment is not None:
        try:
            movement_summary = assess_movement_competence(movement_assessment)
        except MovementAssessmentError as exc:
            raise ProgramValidationError(str(exc)) from exc
        status_priority = {"comfortable": 0, "not_assessed": 0, "uncertain": 1, "needs_support": 2, "symptoms_reported": 3}
        for task, status in movement_assessment.items():
            for pattern in TASK_PATTERNS[task]:
                current = movement_status_by_pattern.get(pattern)
                if current is None or status_priority[status] > status_priority[current]:
                    movement_status_by_pattern[pattern] = status
                movement_tasks_by_pattern.setdefault(pattern, []).append(task)
    reduce_load = bool(response and (
        response["difficulty"] == "hard" or not response["completed"] or response["recovery"] == "poor"
    ))
    progress_load = bool(response and response["difficulty"] == "easy"
                         and response["completed"] and response["recovery"] != "poor")
    include_stability = bool(response and response.get("movement_control", "none") != "none")
    goal_sources = {
        "fat_loss": ["strength", "hypertrophy", "general_fitness", "endurance"],
        "strength_hypertrophy": ["strength", "hypertrophy"],
        "functional": ["functional", "general_fitness", "strength", "mobility"],
        "general_fitness": ["general_fitness", "functional", "strength", "endurance"],
        "power": ["power", "strength", "general_fitness"],
        "endurance": ["endurance", "general_fitness"],
        "mobility": ["mobility", "functional", "general_fitness"],
    }.get(planning_goal, [planning_goal])
    catalogue_by_id = {}
    allowed_purposes = set(GOAL_PURPOSES.get(planning_goal, {planning_goal}))
    if include_stability:
        allowed_purposes.add("stability")
    for source_goal in goal_sources:
        for exercise in get_exercises(
            goal=source_goal,
            equipment=p["equipment"],
            include_accessories=p["include_accessories"],
            purposes=allowed_purposes,
        ):
            catalogue_by_id[exercise["id"]] = exercise
    # Stability is an explicit coaching need, not an automatic accessory.
    # When feedback flags it, bring compatible stability-purpose options into
    # the candidate pool even if their legacy goal tags would otherwise omit them.
    if include_stability:
        for exercise in get_exercises(
            equipment=p["equipment"],
            include_accessories=p["include_accessories"],
            purposes={"stability"},
        ):
            catalogue_by_id[exercise["id"]] = exercise
    catalogue = list(catalogue_by_id.values())
    catalogue = [
        item for item in catalogue
        if item["id"] not in p["excluded_exercise_ids"]
        and item["pattern"] not in p["excluded_patterns"]
    ]
    reference_catalogue = get_exercises(include_accessories=True)
    catalogue_names = {item["id"]: item["name"] for item in reference_catalogue}
    reference_by_name = {item["name"]: item for item in reference_catalogue}

    def safe_references(values: list[str], current_id: str, current_pattern: str) -> list[str]:
        resolved = []
        compatible_patterns = {current_pattern}
        if current_pattern in {"anti_rotation", "trunk_stability"}:
            compatible_patterns.update({"anti_rotation", "trunk_stability"})
        for value in values:
            reference = next((item for item in reference_catalogue if item["id"] == value), None)
            if reference is None:
                reference = reference_by_name.get(value)
            available = set(p["equipment"]) | {"bodyweight"}
            if reference is None:
                # Curated descriptive variants may not need a separate catalogue record.
                # Keep them only when any explicitly named equipment is available.
                equipment_requirements = [
                    (("kettlebell",), {"kettlebell"}),
                    (("ročk",), {"dumbbell"}),
                    (("elastik",), {"resistance_band"}),
                    (("bradl", "dips"), {"dip_bars"}),
                    (("zgib",), {"pull_up_bar"}),
                    (("zaboj",), {"box"}),
                    (("step-up", "step up"), {"step", "box", "bench"}),
                    (("sani",), {"sled"}),
                    (("kolebn",), {"jump_rope"}),
                    (("vesla",), {"rowing_machine"}),
                    (("enoročno veslanje", "veslanje z eno roko"), {"dumbbell", "kettlebell", "barbell"}),
                    (("skierg",), {"ski_erg"}),
                    (("škrip", "napravi"), {"cable"}),
                    (("trap",), {"trap_bar"}),
                    (("medicink",), {"medicine_ball"}),
                    (("mrtvi dvig z dvignjenega položaja", "mrtvi dvig s premorom", "sprednji počep", "počep zadaj"), {"dumbbell", "kettlebell", "barbell", "trap_bar"}),
                    (("večjo obremenitvijo", "dodatno obremenitvijo", "dodatno obtežitvijo", "lažjim bremenom", "enoročne uteži", "uteži"), {"dumbbell", "kettlebell", "barbell", "weight_plate", "household_load", "backpack"}),
                    (("odrivom nog",), {"dumbbell", "kettlebell", "barbell"}),
                    (("nahrbtnik",), {"household_load", "backpack"}),
                    (("oporo prsnega koša", "povišani podlagi", "višji opori", "opori", "oporo", "stola", "klopi", "stol", "klop"), {"household_support", "chair", "bench", "wall", "step", "box"}),
                    (("lastno težo",), {"suspension_trainer", "gymnastic_rings", "household_support"}),
                    (("drsni upogib",), {"towel", "household_support"}),
                    (("drog",), {"barbell", "pull_up_bar"}),
                ]
                text_value = value.casefold()
                if "drog" in text_value:
                    bar_requirement = {"pull_up_bar"} if "zgib" in text_value else {"barbell"}
                    if not (bar_requirement & available):
                        continue
                if any(
                    any(term in text_value for term in terms) and not (required & available)
                    for terms, required in equipment_requirements
                ):
                    continue
                if value not in resolved:
                    resolved.append(value)
                continue
            if reference["id"] == current_id or reference["pattern"] not in compatible_patterns:
                continue
            if not set(reference["equipment"]).issubset(available):
                continue
            if reference["equipment_any"] and not set(reference["equipment_any"]).intersection(available):
                continue
            if reference["name"] not in resolved:
                resolved.append(reference["name"])
        return resolved
    by_pattern: dict[str, list[dict]] = {}
    for exercise in catalogue:
        by_pattern.setdefault(exercise["pattern"], []).append(exercise)

    # A beginner's unsupported bodyweight hinge drill is useful for learning,
    # but it is not a reliable main strength/hypertrophy stimulus. When no external
    # load is available, prefer a mechanically demanding hip-extension / knee-flexion
    # option that can actually approach the target effort reserve.
    if planning_goal in {"hypertrophy", "strength_hypertrophy"}:
        has_external_load = bool({"barbell", "dumbbell", "kettlebell"} & set(p["equipment"]))
        hinge_candidates = [
            item for item in by_pattern.get("hinge", [])
            if item.get("loading_potential") in {"moderate", "high"}
            and (
                has_external_load
                or (
                    p["experience"] != "beginner"
                    and item["id"] != "single_leg_rdl"
                )
            )
        ]
        if not hinge_candidates:
            hinge_candidates = by_pattern.get("hip_extension", []) + by_pattern.get("knee_flexion", [])
        if hinge_candidates:
            by_pattern["hinge"] = hinge_candidates

    plans = []
    used_counts: Counter[str] = Counter()
    exposure: Counter[str] = Counter()
    missing_patterns: set[str] = set()

    for session_index in range(p["sessions_per_week"]):
        patterns = _session_patterns(
            session_index, p["sessions_per_week"], planning_goal,
            p["include_accessories"] and p["session_minutes"] >= 75 and not include_stability, include_stability,
            p["experience"]
        )
        warm_up_minutes = 5 if p["session_minutes"] <= 30 else (7 if p["session_minutes"] <= 60 else 10)
        selected = []
        seen_patterns = set()
        for pattern in patterns:
            if pattern in seen_patterns and planning_goal != "mobility":
                continue
            seen_patterns.add(pattern)
            movement_status = movement_status_by_pattern.get(pattern)
            affected_tasks = movement_tasks_by_pattern.get(pattern, [])
            if pattern == "locomotion" and movement_status == "needs_support":
                raise ProgramValidationError(
                    "Pri hoji si navedel/-la uporabo opore ali pomoč druge osebe. ATENA ti ne bo samodejno predpisala hitre hoje. "
                    "Pred pripravo kondicijskega programa morava v pogovoru razjasniti, kakšna hoja je zate običajna in varna."
                )
            if movement_status == "symptoms_reported":
                missing_patterns.add(pattern)
                movement_adaptation_events.append({
                    "pattern": pattern, "tasks": affected_tasks,
                    "action": "omitted_pending_symptom_review",
                    "message": "Ta gibalni vzorec je iz programa izpuščen, ker si pri povezani nalogi navedel/-la bolečino ali nelagodje. ATENA ga ne nadomesti samodejno.",
                })
                continue
            candidates = by_pattern.get(pattern, [])
            if planning_goal in {"endurance", "fat_loss"} and pattern == "locomotion":
                candidates = [item for item in candidates if item.get("endurance_type") == "aerobic"]
            if planning_goal == "functional" and pattern == "coordination":
                # Lateral shuffle requires braking/change-of-direction competence;
                # it is not inferred from the user's training-experience label.
                candidates = [item for item in candidates if item["id"] != "lateral_shuffle"]
            if movement_status == "needs_support" and pattern != "balance":
                preferred_ids = SUPPORTED_VARIANTS.get(pattern, ())
                available_for_regression = set(p["equipment"]) | {"bodyweight"}
                supported_candidates = [
                    item for item in reference_catalogue
                    if item["id"] in preferred_ids
                    and item["pattern"] == pattern
                    and not item["single_joint"]
                    and item["level"] in {"beginner", p["experience"]}
                    and set(item["equipment"]).issubset(available_for_regression)
                    and (not item["equipment_any"] or bool(set(item["equipment_any"]) & available_for_regression))
                    and bool(set(item["training_purposes"]) & allowed_purposes)
                    and item["pattern"] not in p["excluded_patterns"]
                    and item["id"] not in p["excluded_exercise_ids"]
                ]
                if supported_candidates:
                    candidates = supported_candidates
                else:
                    missing_patterns.add(pattern)
                    movement_adaptation_events.append({
                        "pattern": pattern, "tasks": affected_tasks,
                        "action": "omitted_no_verified_supported_variant",
                        "message": "Za ta gibalni vzorec ni na voljo preverjene lažje različice z izbrano opremo. Vzorec je zato izpuščen, namesto da bi ATENA ugibala.",
                    })
                    continue
            if not candidates:
                # A vertical pull is not mandatory when the available catalogue/equipment cannot support it.
                if pattern in {"vertical_pull", "vertical_push", "carry", "anti_rotation", "trunk_stability"}:
                    missing_patterns.add(pattern)
                    continue
                missing_patterns.add(pattern)
                continue
            if planning_goal == "functional" and pattern == "hinge" and session_index > 0:
                # Rotate a hinge only when another unused, main-role, sufficiently
                # loadable option is valid for this experience level. Never force
                # a harder or poorly loaded variant merely for cosmetic variety.
                level_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
                target_rank = level_order[p["experience"]]
                unused_hinges = [
                    item for item in candidates
                    if used_counts[item["id"]] == 0
                    and item.get("training_role") == "main"
                    and not item.get("single_joint")
                    and item.get("loading_potential") in {"moderate", "high"}
                    and level_order.get(item.get("level"), 99) <= target_rank
                ]
                if unused_hinges:
                    candidates = unused_hinges
            # Rank variants by goal, experience and actual available loading.
            available_equipment = set(p["equipment"]) | {"bodyweight"}
            external_load_items = {"dumbbell", "kettlebell", "barbell", "resistance_band", "household_load", "backpack", "cable"}
            def effective_loading(item: dict) -> str:
                potential = item.get("loading_potential", "low")
                selected_options = set(item["equipment_any"]) & available_equipment
                has_external_load = bool((set(item["equipment"]) | selected_options) & external_load_items)
                if potential == "high" and not has_external_load and selected_options == {"bodyweight"}:
                    return "moderate"
                return potential

            def selection_priority(item: dict) -> int:
                if movement_status == "needs_support":
                    preferred = SUPPORTED_VARIANTS.get(pattern, ())
                    if item["id"] in preferred:
                        return -100 + preferred.index(item["id"])
                if pattern in {"trunk_stability", "anti_rotation"}:
                    # Use foundational trunk control when a stability need is flagged;
                    # advanced static calisthenics remain skill options, not default rehab-like drills.
                    if item["id"] == "dead_bug":
                        return -30
                    if item["id"] in {"l_sit", "tuck_sit", "hollow_body_hold"}:
                        return 30
                if planning_goal == "mobility" and pattern == "hinge":
                    if item["id"] == "romanian_deadlift" and ({"dumbbell", "barbell", "kettlebell"} & available_equipment):
                        return -15
                    if item["id"] == "single_leg_rdl" and p["experience"] != "beginner":
                        return -10
                if planning_goal == "mobility" and pattern == "squat":
                    if item["id"] == "loaded_deep_squat" and {"dumbbell", "kettlebell"} & available_equipment:
                        return -10
                    if item["id"] == "reaching_squat":
                        return -5
                if pattern == "squat" and planning_goal in {"hypertrophy", "strength"}:
                    weighted_squat_equipment = {"barbell", "dumbbell", "kettlebell"}
                    has_weighted_squat = bool(weighted_squat_equipment & available_equipment)
                    if not has_weighted_squat and p["experience"] == "advanced" and p["pistol_squat_capable"] and item["id"] == "pistol_squat":
                        return -20
                    if not has_weighted_squat and p["experience"] in {"intermediate", "advanced"} and item["id"] == "single_leg_box_squat":
                        return -20
                    if not has_weighted_squat and p["experience"] in {"intermediate", "advanced"} and item["id"] == "cossack_squat":
                        return -15
                    if item["id"] in {"back_squat", "front_squat"} and {"barbell", "rack"}.issubset(available_equipment):
                        return -10 if planning_goal == "strength" else -5
                    if item["id"] == "heel_elevated_squat" and {"weight_plate", "heel_wedge", "slant_board"} & available_equipment:
                        return -8
                    if item["id"] in {"dumbbell_squat_front_rack", "squat_goblet"} and {"dumbbell", "kettlebell"} & available_equipment:
                        return -10
                    if item["id"] in {"dumbbell_squat_side", "two_dumbbell_squat"}:
                        return 40
                    if item["id"] == "single_leg_box_squat" and not (external_load_items & available_equipment):
                        return -5
                if pattern == "horizontal_push":
                    if item["id"] == "barbell_bench_press":
                        if planning_goal in {"strength", "strength_hypertrophy"} and p["experience"] != "beginner":
                            # Preserve a strength-specific barbell exposure, then rotate a
                            # suitable bodyweight push variation into the next session.
                            return -10 if session_index % 2 == 0 else 5
                        return 5
                    if item["id"] == "dumbbell_bench_press" and planning_goal in {"hypertrophy", "strength_hypertrophy"}:
                        return -10 if session_index % 2 == 0 else 5
                    if item["id"] == "bench_dip":
                        return 10
                    if item["id"] == "parallel_bar_dip":
                        return -5 if p["experience"] == "advanced" else 5
                    if item["id"] == "dumbbell_floor_press" and any(
                        candidate["id"] in {"push_up", "dumbbell_bench_press"} for candidate in candidates
                    ):
                        return 10
                    if item["id"] == "dumbbell_bench_press":
                        return 0 if {"dumbbell", "bench"}.issubset(available_equipment) else 5
                    if item["id"] == "push_up":
                        # Bodyweight work is a deliberate part of mixed-equipment plans,
                        # not something discarded merely because weights are available.
                        return -5 if session_index % 2 == 1 else 0
                if pattern == "conditioning" and planning_goal == "endurance":
                    if item["id"] == "box_jump_intervals":
                        return 100
                    if item["id"] in {"rower_intervals", "ski_erg_intervals", "air_bike_intervals", "sled_push", "sled_backward_drag"}:
                        return -5
                    if item["id"] == "jump_rope":
                        return -3
                if pattern == "hinge" and p["experience"] == "beginner":
                    has_loaded_hinge = bool({"dumbbell", "kettlebell", "barbell"} & available_equipment)
                    if not has_loaded_hinge and item["id"] == "supported_single_leg_rdl":
                        return -25
                    if not has_loaded_hinge and item["id"] == "bodyweight_hip_hinge":
                        return -20
                if pattern == "horizontal_pull" and planning_goal in {"hypertrophy", "strength"}:
                    if planning_goal == "strength" and p["experience"] != "beginner" and item["id"] == "barbell_bent_over_row" and "barbell" in available_equipment:
                        return -10
                    if planning_goal == "hypertrophy" and session_index % 2 == 0 and item["id"] in {"dumbbell_bent_over_row", "one_arm_row", "kettlebell_one_arm_row"}:
                        return -10
                    if planning_goal == "hypertrophy" and session_index % 2 == 1 and item["id"] in {"band_row", "trx_row", "ring_row"}:
                        return -10
                    if session_index % 2 == 0 and item["id"] in {"dumbbell_bent_over_row", "one_arm_row", "kettlebell_one_arm_row"}:
                        return -5
                    if session_index % 2 == 1 and item["id"] in {"band_row", "trx_row", "ring_row"}:
                        return -5
                if pattern == "hinge":
                    has_dumbbell = "dumbbell" in available_equipment
                    has_barbell = "barbell" in available_equipment
                    if planning_goal in {"strength", "strength_hypertrophy"} and p["experience"] != "beginner" and item["id"] == "deadlift" and has_barbell:
                        return -15
                    if has_dumbbell and not has_barbell and item["id"] == "romanian_deadlift":
                        return -20
                    if item["id"] == "dumbbell_deadlift":
                        return 35
                    if item["id"] == "bodyweight_hip_hinge" and (has_dumbbell or has_barbell or "kettlebell" in available_equipment):
                        return 25
                    if planning_goal == "hypertrophy" and item["id"] == "romanian_deadlift":
                        return -15
                    if item["id"] in {"romanian_deadlift", "deadlift"}:
                        return -5 if set(item["equipment"]).issubset(available_equipment) else 5
                    if planning_goal == "hypertrophy" and item["id"] in {"slider_leg_curl", "long_lever_glute_bridge", "elevated_heel_hip_lift"}:
                        return -5
                    if item["id"] == "bodyweight_hip_hinge":
                        return 20 if planning_goal == "hypertrophy" else 0
                return 0

            level_rank = {"beginner": 0, "intermediate": 1, "advanced": 2}
            target_level = level_rank[p["experience"]]
            primary_purpose = GOAL_PRIMARY_PURPOSE.get(planning_goal)
            candidate = min(candidates, key=lambda item: (
                selection_priority(item),
                0 if primary_purpose and primary_purpose in item["training_purposes"] else 1,
                0 if item.get("training_role") == "main" or planning_goal not in {"hypertrophy", "strength_hypertrophy"} else 1,
                used_counts[item["id"]],
                abs(level_rank[item["level"]] - target_level),
                {"high": 0, "moderate": 1, "low": 2}[effective_loading(item)] if planning_goal in {"hypertrophy", "strength"} else 0,
                item["id"],
            ))
            effective_pattern = candidate["pattern"]
            used_counts[candidate["id"]] += 1
            prescription = _prescription(planning_goal, p["experience"], effective_pattern, candidate)
            movement_note = None
            if movement_status == "needs_support":
                if pattern == "balance":
                    movement_note = "Izvedi ob stabilni opori, ki jo lahko z roko dosežeš; obseg in trajanje prilagodi tako, da ostaneta nadzorovana."
                else:
                    movement_note = "Na podlagi tvoje samoocene je izbrana lažja različica istega gibalnega vzorca. Začni z največ dvema kakovostnima serijama in ohrani vsaj 3 ponovitve v rezervi; če ni udobno, vajo prekini in preveri ustreznost."
                    prescription["sets"] = min(2, prescription.get("sets", 2))
                    if prescription.get("rir") is not None:
                        prescription["rir"] = max(3, prescription["rir"])
                    if prescription.get("rir_range") is not None:
                        prescription["rir_range"] = "3–4"
                movement_adaptation_events.append({
                    "pattern": pattern, "tasks": affected_tasks,
                    "action": "simpler_catalogue_variant_selected" if pattern != "balance" else "stable_support_cue",
                    "exercise_id": candidate["id"], "exercise_name": candidate["name"],
                    "message": movement_note,
                })
            elif movement_status == "uncertain":
                movement_note = "Pri tej nalogi nisi prepričan/-a. ATENA zato ni spreminjala izbire na podlagi ugibanja; pred prvo delovno serijo preveri, ali je različica udobna in nadzorovana. Če nisi prepričan/-a, vprašaj trenerja za lažjo možnost."
                movement_adaptation_events.append({
                    "pattern": pattern, "tasks": affected_tasks,
                    "action": "kept_selection_pending_user_clarification",
                    "exercise_id": candidate["id"], "exercise_name": candidate["name"],
                    "message": movement_note,
                })
            if planning_goal == "endurance" and effective_pattern == "locomotion":
                # Reserve time for warm-up, transitions and interval work; locomotion is a flexible aerobic block.
                    prescription["work_seconds"] = max(600, int(p["session_minutes"] * 15))
            if reduce_load and response["recovery"] == "poor" and response["difficulty"] != "hard" and response["completed"]:
                # Poor recovery alone trims only optional training cost; preserve
                # accessory and non-compound work unless the session was also hard.
                is_compound = (
                    not candidate["single_joint"]
                    and pattern not in {
                        "trunk_stability", "anti_rotation", "mobility",
                        "mobility_stretch", "conditioning", "locomotion", "hip_extension"
                    }
                )
                if is_compound and prescription.get("sets", 1) > 2:
                    prescription["sets"] -= 1
                    if prescription.get("rir") is not None:
                        prescription["rir"] = min(4, prescription["rir"] + 1)
                    prescription["rest_seconds"] += 30
                    prescription["adjustment_note"] = (
                        "Regeneracija je bila slabša, zato je zmanjšan samo del glavnega "
                        "večsklepnega volumna; ostalo delo ostaja nespremenjeno."
                    )
            elif reduce_load:
                # A "too hard" report must change the actual next prescription,
                # including aerobic and mobility work, not only its explanatory text.
                if prescription.get("sets", 1) > 2:
                    prescription["sets"] -= 1
                elif prescription.get("work_seconds") is not None:
                    floor = 300 if pattern == "locomotion" else 10
                    prescription["work_seconds"] = max(floor, int(prescription["work_seconds"] * 0.85))
                else:
                    bounds = [int(value) for value in prescription.get("reps", "").split("–") if value.isdigit()]
                    if len(bounds) == 2:
                        low, high = bounds
                        prescription["reps"] = f"{low}–{max(low, high - 2)}"
                if prescription.get("rir") is not None:
                    prescription["rir"] = min(4, prescription["rir"] + 1)
                    if prescription.get("rir_range") == "2–3":
                        prescription["rir_range"] = "3–4"
                prescription["rest_seconds"] += 30
                prescription["adjustment_note"] = (
                    "Ker je bil zadnji trening pretežek oziroma regeneracija slabša, "
                    "je naslednji vadbeni odmerek konservativno zmanjšan. Ohrani nadzorovano izvedbo."
                )
            elif progress_load and movement_status not in {"needs_support", "uncertain"}:
                # One easy report earns only a small, reversible progression:
                # one additional target rep or a small work-time increase. Never
                # invent a kilogram increase without knowing the actual load.
                if prescription.get("work_seconds") is not None:
                    ceiling = 1800 if pattern == "locomotion" else 300
                    prescription["work_seconds"] = min(
                        ceiling, int(prescription["work_seconds"] * 1.05)
                    )
                    prescription["adjustment_note"] = (
                        "Ker je bil zadnji trening prelahek, je delovni interval "
                        "podaljšan za majhen korak. Ohrani predpisano ciljno intenzivnost."
                    )
                else:
                    bounds = [int(value) for value in prescription.get("reps", "").split("–") if value.isdigit()]
                    if len(bounds) == 2 and bounds[0] < bounds[1]:
                        low, high = bounds
                        prescription["reps"] = f"{low + 1}–{high}"
                    prescription["adjustment_note"] = (
                        "Ker je bil zadnji trening prelahek, je cilj naslednjič nekoliko višji: "
                        "dodaj eno kakovostno ponovitev na serijo. Breme povečaj šele, ko "
                        "večkrat dosežeš zgornjo mejo z ustrezno rezervo in tehniko."
                    )
            if movement_note:
                existing_note = prescription.get("adjustment_note")
                prescription["adjustment_note"] = movement_note + ((" " + existing_note) if existing_note else "")
            def equipment_priority(item: str) -> tuple[int, str]:
                if item in {"dumbbell", "kettlebell", "barbell", "resistance_band"}:
                    return (0, item)
                if item in {"backpack", "jump_rope", "bicycle", "rowing_machine", "ski_erg", "air_bike"}:
                    return (1, item)
                if item == "bodyweight":
                    return (2, item)
                if item in {"household_support", "household_load"}:
                    return (3, item)
                return (1, item)
            optional_equipment = sorted(
                set(candidate["equipment_any"]) & set(p["equipment"]),
                key=equipment_priority,
            )
            if candidate["equipment"]:
                optional_equipment = [item for item in optional_equipment if item != "bodyweight"]
            selected_equipment = candidate["equipment"] + optional_equipment[:1]
            regressions = safe_references(candidate["regressions"], candidate["id"], effective_pattern)
            progressions = safe_references(candidate["progressions"], candidate["id"], effective_pattern)
            alternatives = [
                value for value in safe_references(candidate["alternatives"], candidate["id"], effective_pattern)
                if value not in regressions
            ]
            exercise_category = (
                "stability" if effective_pattern in {"trunk_stability", "anti_rotation"}
                else "mobility" if candidate.get("training_role") == "mobility"
                else "conditioning" if candidate.get("training_role") == "conditioning"
                else "hip_extension" if effective_pattern == "hip_extension"
                else "accessory" if candidate["single_joint"]
                else "compound"
            )
            selected.append({
                "exercise_id": candidate["id"],
                "exercise_category": exercise_category,
                "name": candidate["name"],
                "pattern": effective_pattern,
                "movement_pattern": candidate["movement_pattern"],
                "training_purposes": candidate["training_purposes"],
                "stability_role": candidate["stability_role"],
                "stability_focus": candidate["stability_focus"],
                "pattern_label": PATTERN_LABELS.get(effective_pattern, effective_pattern),
                "joint_type": candidate["joint_type"],
                "loading_potential": effective_loading(candidate),
                "training_role": candidate["training_role"],
                "endurance_type": candidate.get("endurance_type"),
                "target_systems": candidate.get("target_systems", []),
                "target_regions": candidate.get("target_regions", []),
                "time_based": bool(candidate.get("time_based")),
                "reps_per_side": bool(candidate.get("unilateral") or candidate.get("reps_per_side")),
                "primary_muscles": candidate["primary_muscles"],
                "equipment": selected_equipment,
                "cues": candidate["cues"],
                # Keep exercise-specific ROM guidance here. General ROM guidance
                # is shown once in methodology, not repeated under every exercise.
                "range_of_motion": candidate.get("range_of_motion"),
                "warnings": candidate["warnings"],
                "regressions": regressions,
                "progressions": progressions,
                "alternatives": alternatives,
                # Machine-readable coaching criteria keep the progression logic
                # available to the application even when the UI stays minimal.
                "coaching_logic": {
                    "regress_when": [
                        "ne dosežeš spodnje meje predpisanih ponovitev z ustrezno tehniko",
                        "izgubiš nadzor, ravnotežje ali načrtovano amplitudo",
                        "predpisani RIR ni dosežen oziroma je napor previsok",
                        "pojavi se bolečina ali novo nelagodje; avtomatska progresija se ustavi",
                        "oprema ali opora ni varna oziroma je ni mogoče potrditi",
                    ],
                    "progress_when": [
                        "vse serije dosežejo zgornjo mejo ponovitev",
                        "tehnika in kontrolirana amplituda ostaneta ponovljivi",
                        "ohraniš predpisani RIR",
                        "enak uspeh se ponovi na najmanj dveh izpostavitvah in regeneracija je ustrezna",
                        "ni bolečine ali novega zaskrbljujočega simptoma",
                    ],
                    "progression_order": [
                        "najprej postopno dodaj ponovitve znotraj predpisanega razpona",
                        "nato dodaj majhno obremenitev, če je na voljo in varna",
                        "sicer uporabi naslednjo preverjeno progresijo iz kataloga",
                        "spreminjaj samo eno glavno spremenljivko naenkrat",
                    ],
                    "regressions": regressions,
                    "progressions": progressions,
                },
                "prescription": prescription,
                **({"movement_adaptation_note": movement_note} if movement_note else {}),
                **({
                    "coaching_note": "Ciljno pripravljalno delo za nadzor trupa, vključeno na podlagi tvoje povratne informacije. Izvedi po splošnem ogrevanju in pred glavnimi vajami."
                } if pattern == "trunk_stability" and include_stability else {}),
            })
            for muscle in candidate["primary_muscles"]:
                exposure[muscle] += prescription["sets"]

        # The session duration is an approximate envelope, not a rigid work/rest split.
        planning_budget = p["session_minutes"]
        # Preserve the main compound patterns; trim optional work first when needed.
        volume_adjustments = []
        while selected and _estimated_minutes(selected, warm_up_minutes) > planning_budget:
            # Remove truly optional work first; preserve the weekly movement-pattern map.
            removal_priority = ("accessory", "carry")
            removable = next(
                (next((i for i, item in enumerate(selected) if item["pattern"] == pattern), None)
                 for pattern in removal_priority
                 if any(item["pattern"] == pattern for item in selected)),
                None,
            )
            if removable is not None:
                removed = selected.pop(removable)
                missing_patterns.add(removed["pattern"])
                used_counts[removed["exercise_id"]] -= 1
                for muscle in removed["primary_muscles"]:
                    exposure[muscle] -= removed["prescription"]["sets"]
                continue

            # If the time budget is still exceeded, reduce a main compound lift
            # from three to two sets before dropping a foundational movement pattern.
            reducible = next(
                (item for item in selected
                 if item["pattern"] in {"squat", "hinge", "hip_extension", "knee_flexion", "horizontal_push", "horizontal_pull"}
                 and item["prescription"]["sets"] > 2),
                None,
            )
            if reducible is not None:
                reducible["prescription"]["sets"] -= 1
                for muscle in reducible["primary_muscles"]:
                    exposure[muscle] -= 1
                volume_adjustments.append(reducible["name"])
                continue

            # Only as a last resort trim non-core additions; keep trunk control work.
            final_priority = ("vertical_push", "vertical_pull", "lunge", "anti_rotation")
            final_index = next(
                (i for pattern in final_priority
                 for i, item in enumerate(selected) if item["pattern"] == pattern),
                None,
            )
            if final_index is None:
                break
            removed = selected.pop(final_index)
            missing_patterns.add(removed["pattern"])
            used_counts[removed["exercise_id"]] -= 1
            for muscle in removed["primary_muscles"]:
                exposure[muscle] -= removed["prescription"]["sets"]

        # Approximate set-volume bands are a planning guide, not a target to chase.
        # Keep the foundational patterns; trim excess sets before removing a secondary pattern.
        session_set_cap = 10 if p["session_minutes"] <= 30 else (15 if p["session_minutes"] <= 45 else None)
        if session_set_cap is not None:
            while sum(item["prescription"]["sets"] for item in selected) > session_set_cap:
                reducible = next(
                    (item for item in selected
                     if item["pattern"] in {"squat", "hinge", "hip_extension", "knee_flexion", "horizontal_push", "horizontal_pull"}
                     and item["prescription"]["sets"] > 2),
                    None,
                )
                if reducible is not None:
                    reducible["prescription"]["sets"] -= 1
                    for muscle in reducible["primary_muscles"]:
                        exposure[muscle] -= 1
                    volume_adjustments.append(reducible["name"])
                    continue

                removal_priority = ("vertical_push", "vertical_pull", "lunge", "carry")
                removal_index = next(
                    (i for pattern in removal_priority
                     for i, item in enumerate(selected) if item["pattern"] == pattern),
                    None,
                )
                if removal_index is None:
                    break
                removed = selected.pop(removal_index)
                missing_patterns.add(removed["pattern"])
                used_counts[removed["exercise_id"]] -= 1
                for muscle in removed["primary_muscles"]:
                    exposure[muscle] -= removed["prescription"]["sets"]

        estimated = _estimated_minutes(selected, warm_up_minutes)
        if estimated > p["session_minutes"]:
            raise ProgramValidationError(
                f"Z razpoložljivim časom {p['session_minutes']} min ni mogoče sestaviti uravnoteženega treninga. Povečaj čas ali zmanjša zahtevnost cilja."
            )
        if len(selected) < 3:
            raise ProgramValidationError(
                "Za izbrano opremo in omejitve ni dovolj preverjenih vaj. Potrebujem več opreme ali manj izključitev."
            )
        plans.append({
            "session": session_index + 1,
            "title": (f"Trening {session_index + 1} – vzdržljivost" if planning_goal == "endurance" else f"Trening {session_index + 1} – mobilnost in gibljivost" if planning_goal == "mobility" else f"Trening {session_index + 1} – funkcionalna pripravljenost" if planning_goal == "functional" else f"Trening {session_index + 1} – aerobna in kondicijska priprava" if planning_goal == "fat_loss" and session_index >= 2 else f"Trening {session_index + 1} – celotno telo"),
            "warm_up_minutes": warm_up_minutes,
            "warm_up_range": "5–7 min" if p["session_minutes"] <= 30 else "5–10 min",
            "exercise_count": len(selected),
            "work_sets": sum(item["prescription"]["sets"] for item in selected),
            "estimated_minutes": estimated,
            "available_minutes": p["session_minutes"],
            "volume_adjustments": volume_adjustments,
            "exercises": selected,
        })

    all_selected = [item for session in plans for item in session["exercises"]]
    total_sets = sum(item["prescription"]["sets"] for item in all_selected)
    timed_work_seconds = sum(
        item["prescription"].get("work_seconds", 0) * item["prescription"]["sets"] * (2 if item["prescription"].get("rep_unit") == "per_side" else 1)
        for item in all_selected
    )
    endurance_work_seconds: Counter[str] = Counter()
    for item in all_selected:
        if item.get("endurance_type") and item["prescription"].get("work_seconds") is not None:
            endurance_work_seconds[item["endurance_type"]] += item["prescription"]["work_seconds"] * item["prescription"]["sets"] * (2 if item["prescription"].get("rep_unit") == "per_side" else 1)
    pattern_session_frequency: Counter[str] = Counter()
    pattern_work_sets: Counter[str] = Counter()
    for session in plans:
        session_patterns_seen: set[str] = set()
        for item in session["exercises"]:
            if item["pattern"] not in session_patterns_seen:
                pattern_session_frequency[item["pattern"]] += 1
                session_patterns_seen.add(item["pattern"])
            pattern_work_sets[item["pattern"]] += item["prescription"]["sets"]
    return {
        "program_version": "3.0.0",
        "movement_adaptation": {
            "source": "self_reported_movement_assessment",
            "is_diagnosis": False,
            "automatic_progression": "movement_assessment_does_not_trigger_progression",
            "events": movement_adaptation_events,
            "summary": movement_summary,
        } if movement_summary is not None else None,
        "goal": p["goal"],
        "training_emphasis": p["training_emphasis"],
        "experience": p["experience"],
        "sessions_per_week": p["sessions_per_week"],
        "session_minutes": p["session_minutes"],
        "methodology": {
            "exercise_source": "verified_catalogue_only",
            "compound_first": True,
            "single_joint_accessories": p["include_accessories"],
            "training_emphasis": p["training_emphasis"],
            "exercise_scaling": "Vsaka vaja ima označen potencial obremenitve, vlogo, zahteve glede opreme in stopnjevanje. Nizko obremenljive učne vaje niso privzeta glavna izbira za hipertrofijo.",
            "equipment_policy": "Brez uteži ne pomeni brez običajnih stabilnih gospodinjskih opor. Stol, kavč, miza, stopnica, brisača ali palica so dovoljeni le, kadar jih profil izrecno vključuje in so varni za uporabo.",
            "endurance_policy": "Vzdržljivost je ločen cilj; aerobne aktivnosti, intervali in mišična vzdržljivost so označeni ločeno.",
            "mobility_policy": "Mobilnost vključuje aktivne gibalne vaje, kontrolirano gibanje v končnih amplitudah in razvoj moči skozi čim večji nadzorovan in toleriran obseg (npr. predklon z nevtralnim položajem hrbtenice/RDL, ATG izpadni počep, Cossack squat in obremenjeni globoki počep), ne samo pasivnega raztezanja.",
            "fat_loss_policy": "Pri uravnavanju telesne teže združi vadbo moči za ohranitev mišične mase s kratkimi, odmerjenimi kondicijskimi intervali v istem treningu; ob treh ali štirih treningih je lahko dodatna enota pretežno aerobna. MetCon naj bo nadzorovan, ne maksimalen in ne na račun tehnike ali regeneracije. Za zmanjšanje telesne maščobe je potreben vzdržen energijski primanjkljaj; vadba sama ga ne zagotavlja.",
            "experience_adaptation": (
                "Vzdržljivost: začetnik gradi predvsem enakomeren aerobni obseg v pogovornem tempu; intervale uvajaj postopno. Naprednejši lahko kombinira daljše aerobne enote, intervale in mišično vzdržljivost, vendar ne vsega maksimalno v isti vadbi."
                if planning_goal == "endurance" else
                "Hujšanje: ohrani kakovostna treninga moči kot osnovo, aerobno delo dodajaj glede na razpoložljiv čas in regeneracijo. Ne povečuj obsega vadbe zgolj zato, da bi porabil čim več kalorij."
                if planning_goal == "fat_loss" else
                "Mobilnost: začetnik začne z aktivnimi, podprtimi in kontroliranimi gibi. Napredovanje temelji na kakovosti, postopnem povečevanju neboleče amplitude in sposobnosti ustvarjanja sile v novih položajih; ne na siljenju v končni obseg."
                if planning_goal == "mobility" else
                "Začetnik: prednost imajo učenje osnovnih gibalnih vzorcev, nadzorovana amplituda in ponovljiva tehnika. Tudi pri cilju moč začni večinoma z 8–12 ponovitvami in približno 2–3 ponovitvami v rezervi; šele z napredovanjem postopno preidi na nižje razpone in večje obremenitve."
                if p["experience"] == "beginner" else
                "Intermediate: uporablja bolj specifične razpone glede na cilj; pri glavnih vajah za moč je običajen razpon 5–8 ponovitev, pri hipertrofiji večinoma 6–12. Advanced: pri glavnih vajah za moč lahko uporablja 3–6 ponovitev, ob večji obremenitvi pa zahteva ustrezno tehniko, regeneracijo in daljše odmore."
            ),
            "tempo": (
                "Začetnik pri kombiniranem cilju moč + hipertrofija: pri osnovnih počepih in predklonih z ravnim hrbtom uporabi tempo 2–1–1–0 (2 s nadzorovan spust, 1 s nadzor v spodnjem položaju, 1 s dvig, brez premora v vrhu). Druge začetniške vaje in posebni vzorci ohranijo svoj namenski tempo."
                if p["experience"] == "beginner" and planning_goal == "strength_hypertrophy" else
                "Začetnik: pri osnovnih vajah je privzeti tempo 3–1–1–0 (3 s nadzorovan spust, 1 s nadzor v spodnjem položaju, 1 s dvig, brez premora v vrhu). Eksplozivne, časovno določene, stabilizacijske in mobilnostne vaje imajo ustrezno specifičen tempo."
                if p["experience"] == "beginner" else
                "Tempo je določen glede na cilj in vrsto vaje: moč uporablja nadzorovano ekscentrično fazo ter hitro koncentrično namero, hipertrofija daljšo nadzorovano izvedbo, eksplozivne vaje hiter koncentrični del, vzdržljivost ritmično delo, mobilnost pa počasno aktivno raziskovanje obsega. Stabilizacijsko delo se doda ciljno, ne avtomatično."
            ),
            "range_of_motion": "Pri vsaki vaji uporabi največjo amplitudo, ki jo omogočata gibljivost in nadzor. Amplitudo postopno razvijaj; ne žrtvuj položaja, stabilnosti ali neboleče izvedbe. Pri mobilnosti kombiniraj aktivno gibanje in moč skozi razpoložljivo amplitudo.",
            "progression": ("Pri aerobni vzdržljivosti postopno povečuj trajanje ali obseg, nato po potrebi intenzivnost; pri intervalih spreminjaj le eno spremenljivko naenkrat. Ohraniti moraš ponovljivo tehniko in regeneracijo."
                if planning_goal == "endurance" else
                "Pri hujšanju ohrani ali postopno izboljšuj delovne obremenitve pri vajah za moč, da podpreš ohranitev mišične mase. Kondicijski obseg povečuj postopno; ne kompenziraj prehrane z nenadnim povečanjem treninga."
                if planning_goal == "fat_loss" else
                "Pri mobilnosti postopno povečuj nadzorovan obseg, kakovost končnega položaja in sposobnost ustvarjanja sile v njem. Ne sili v globino in ne napreduj skozi bolečino."
                if planning_goal == "mobility" else
                "Ko pri vseh serijah dosežeš zgornjo mejo ponovitev in ohraniš predpisano rezervo ter tehniko, povečaj dražljaj: najprej obremenitev, če je na voljo; sicer težjo različico, daljši vzvod, večjo nadzorovano amplitudo ali enostransko izvedbo. Če tehnika ali regeneracija odstopata, obdrži ali zmanjša zahtevnost."
            ),
            "deload": "Razbremenitev se ne določa avtomatično po koledarju; uporabi jo ob vztrajnem slabšanju zmogljivosti, regeneracije ali kakovosti izvedbe.",
            "last_session_adjustment": "reduce_sets_increase_reserve" if reduce_load else ("hold_and_progress_by_rule" if response and response["difficulty"] == "easy" else "maintain"),
        },
        "feedback_applied": response,
        "sessions": plans,
        "weekly_summary": {
            "total_work_sets": total_sets,
            "exercise_frequency": dict(used_counts),
            "primary_muscle_set_exposure": (
                {key: value for key, value in exposure.items() if value > 0}
                if planning_goal in {"hypertrophy", "strength", "strength_hypertrophy", "fat_loss"} else {}
            ),
            "time_based_work_seconds": timed_work_seconds,
            "endurance_type_work_seconds": dict(endurance_work_seconds),
            "pattern_session_frequency": dict(pattern_session_frequency),
            "pattern_work_sets": dict(pattern_work_sets),
            "unfilled_patterns": sorted(missing_patterns),
        },
        "limitations": [
            "Čas treninga je okviren; ogrevanje traja približno 5–10 minut, preostanek pa se prilagodi tempu, odmorom in zahtevnosti vaj.",
            "Stabilizacijske vaje niso privzeti dodatek k hipertrofiji; vključijo se ciljno, kadar povratna informacija pokaže težavo z nadzorom trupa.",
            "Ocena trajanja je približek; dejanski čas je odvisen od hitrosti izvedbe, menjave opreme in individualnih odmorov.",
            "Katalog ne ocenjuje zdravstvenih stanj. Omejitve in simptome mora pred izbiro vaj pregledati trener oziroma ustrezen zdravstveni strokovnjak.",
            "Tedenska izpostavljenost mišičnih skupin pri večsklepnih vajah ni enaka številu neposrednih delovnih serij za posamezno mišico.",
        ] + (
            [
                "Brez ustrezne opreme ni mogoče zagotoviti učinkovitega horizontalnega potega (npr. veslanja). Program tega ne nadomešča z neustreznimi samoupornimi vajami; za uravnotežen razvoj hrbtnih mišic dodaj varno oporo, elastiko, drog ali utež."
            ]
            if "horizontal_pull" in missing_patterns
            else []
        ) + (
            [
                "Brez zunanjih bremen je dolgoročno povečevanje moči in mišične mase omejeno. Program zato uporablja zahtevnejše enonožne in tempo različice; za nadaljnjo progresijo bo sčasoma koristna dodatna obremenitev."
            ]
            if planning_goal in {"strength", "hypertrophy", "strength_hypertrophy", "fat_loss"}
            and not ({"barbell", "dumbbell", "kettlebell"} & available_equipment)
            else []
        ),
    }
