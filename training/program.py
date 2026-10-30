"""Deterministic, catalogue-backed training-program generator for ATENA Phase 2."""
from __future__ import annotations

from collections import Counter
from typing import Any

from training.catalogue import get_exercises

SUPPORTED_GOALS = {"hypertrophy", "strength", "general_fitness", "functional", "power"}
SUPPORTED_LEVELS = {"beginner", "intermediate", "advanced"}
SUPPORTED_SESSIONS = {2, 3, 4}
PATTERN_LABELS = {
    "squat": "počep",
    "lunge": "izpadni korak",
    "hinge": "predklon z ravnim hrbtom",
    "horizontal_push": "horizontalni potisk",
    "horizontal_pull": "horizontalni vlek",
    "vertical_push": "vertikalni potisk",
    "vertical_pull": "vertikalni vlek",
    "carry": "nošenje",
    "anti_rotation": "preprečevanje rotacije",
    "trunk_stability": "stabilizacija trupa",
    "jump": "skok",
    "hinge_power": "eksplozivni predklon z ravnim hrbtom",
    "accessory": "dopolnilna vaja",
}
PATTERN_ORDER = [
    "squat", "lunge", "hinge", "horizontal_push", "horizontal_pull",
    "vertical_push", "vertical_pull", "carry", "anti_rotation",
    "trunk_stability", "jump", "hinge_power",
]


class ProgramValidationError(ValueError):
    """Raised when the supplied training profile cannot be safely planned."""


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
    return {
        **profile,
        "sessions_per_week": sessions,
        "session_minutes": duration,
        "equipment": sorted(set(equipment) | {"bodyweight"}),
        "excluded_exercise_ids": set(exclusions),
        "excluded_patterns": set(excluded_patterns),
        "include_accessories": accessories,
    }


def _session_patterns(session_index: int, sessions: int, goal: str) -> list[str]:
    """Balanced full-body templates; rotate emphasis without omitting key patterns."""
    base = ["squat", "hinge", "horizontal_push", "horizontal_pull"]
    if sessions == 2:
        extras = [
            ["lunge", "vertical_push", "trunk_stability"],
            ["lunge", "vertical_pull", "anti_rotation"],
        ]
    elif sessions == 3:
        extras = [
            ["lunge", "vertical_push", "trunk_stability"],
            ["vertical_pull", "carry", "anti_rotation"],
            ["lunge", "vertical_push", "trunk_stability"],
        ]
    else:
        extras = [
            ["lunge", "vertical_push", "trunk_stability"],
            ["vertical_pull", "carry", "anti_rotation"],
            ["lunge", "vertical_push", "trunk_stability"],
            ["vertical_pull", "carry", "anti_rotation"],
        ]
    patterns = base + extras[session_index]
    if goal == "power":
        patterns += ["jump", "hinge_power"]
    return patterns


def _prescription(goal: str, level: str, pattern: str) -> dict:
    if goal == "strength":
        sets, reps, rir, rest = (4, "3–6", 2, 180) if level == "advanced" else (3, "4–6", 2, 150)
    elif goal == "hypertrophy":
        sets, reps, rir, rest = (3, "6–12", 2, 120) if level == "advanced" else (3, "8–12", 2 if level == "intermediate" else 3, 90)
    elif goal == "power" or pattern in {"jump", "hinge_power"}:
        sets, reps, rir, rest = 3, "3–5", 4, 120
    else:
        sets, reps, rir, rest = (3, "6–12", 3, 90) if level != "beginner" else (2, "8–12", 3, 75)
    if pattern in {"jump", "hinge_power"}:
        sets, reps, rir, rest = 3, "3–5", 4, 120
    return {"sets": sets, "reps": reps, "rir": rir, "rest_seconds": rest}


def _estimated_minutes(exercises: list[dict]) -> int:
    # Approximation includes execution, inter-set rests, and 75 s transitions.
    total_seconds = 6 * 60
    for item in exercises:
        prescription = item["prescription"]
        reps = int(prescription["reps"].split("–")[0])
        sets = prescription["sets"]
        execution = reps * 3 * sets
        rests = max(0, sets - 1) * prescription["rest_seconds"]
        total_seconds += execution + rests + 75
    return round(total_seconds / 60)


def generate_program(profile: object) -> dict:
    """Generate a repeatable weekly plan from validated catalogue entries only."""
    p = validate_profile(profile)
    goal_sources = {
        "functional": ["functional", "general_fitness", "strength"],
        "general_fitness": ["general_fitness", "functional", "strength"],
        "power": ["power", "strength", "general_fitness"],
    }.get(p["goal"], [p["goal"]])
    catalogue_by_id = {}
    for source_goal in goal_sources:
        for exercise in get_exercises(
            goal=source_goal,
            equipment=p["equipment"],
            include_accessories=p["include_accessories"],
        ):
            catalogue_by_id[exercise["id"]] = exercise
    catalogue = list(catalogue_by_id.values())
    catalogue = [
        item for item in catalogue
        if item["id"] not in p["excluded_exercise_ids"]
        and item["pattern"] not in p["excluded_patterns"]
    ]
    by_pattern: dict[str, list[dict]] = {}
    for exercise in catalogue:
        by_pattern.setdefault(exercise["pattern"], []).append(exercise)

    plans = []
    used_counts: Counter[str] = Counter()
    exposure: Counter[str] = Counter()
    missing_patterns: set[str] = set()

    for session_index in range(p["sessions_per_week"]):
        patterns = _session_patterns(session_index, p["sessions_per_week"], p["goal"])
        selected = []
        seen_patterns = set()
        for pattern in patterns:
            if pattern in seen_patterns:
                continue
            seen_patterns.add(pattern)
            candidates = by_pattern.get(pattern, [])
            if not candidates:
                # A vertical pull is not mandatory when the available catalogue/equipment cannot support it.
                if pattern in {"vertical_pull", "vertical_push", "carry", "anti_rotation", "trunk_stability"}:
                    missing_patterns.add(pattern)
                    continue
                missing_patterns.add(pattern)
                continue
            # Rotate variants across sessions and prefer the least-used exercise to distribute exposure.
            candidate = min(candidates, key=lambda item: (used_counts[item["id"]], item["level"] != p["experience"], item["id"]))
            used_counts[candidate["id"]] += 1
            prescription = _prescription(p["goal"], p["experience"], pattern)
            selected.append({
                "exercise_id": candidate["id"],
                "name": candidate["name"],
                "pattern": pattern,
                "pattern_label": PATTERN_LABELS.get(pattern, pattern),
                "joint_type": candidate["joint_type"],
                "primary_muscles": candidate["primary_muscles"],
                "equipment": candidate["equipment"] + candidate["equipment_any"],
                "cues": candidate["cues"],
                "warnings": candidate["warnings"],
                "regressions": candidate["regressions"],
                "alternatives": candidate["alternatives"],
                "prescription": prescription,
            })
            for muscle in candidate["primary_muscles"]:
                exposure[muscle] += prescription["sets"]

        # Keep the most important four-to-six items and reduce accessory load to fit the clock.
        while selected and _estimated_minutes(selected) > p["session_minutes"]:
            removable = next((i for i in range(len(selected) - 1, -1, -1)
                              if selected[i]["pattern"] in {"carry", "anti_rotation", "trunk_stability", "vertical_push", "vertical_pull", "lunge"}), None)
            if removable is None:
                break
            removed = selected.pop(removable)
            missing_patterns.add(removed["pattern"])
            used_counts[removed["exercise_id"]] -= 1
            for muscle in removed["primary_muscles"]:
                exposure[muscle] -= removed["prescription"]["sets"]

        estimated = _estimated_minutes(selected)
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
            "title": f"Trening {session_index + 1} – celotno telo",
            "warm_up_minutes": 6,
            "estimated_minutes": estimated,
            "available_minutes": p["session_minutes"],
            "exercises": selected,
        })

    total_sets = sum(item["prescription"]["sets"] for session in plans for item in session["exercises"])
    return {
        "program_version": "2.0.0",
        "goal": p["goal"],
        "experience": p["experience"],
        "sessions_per_week": p["sessions_per_week"],
        "session_minutes": p["session_minutes"],
        "methodology": {
            "exercise_source": "verified_catalogue_only",
            "compound_first": True,
            "single_joint_accessories": p["include_accessories"],
            "progression": "Ko pri vseh serijah dosežeš zgornjo mejo ponovitev in ohraniš predpisani RIR, pri naslednjem treningu rahlo zvišaj obremenitev. Če tehnika ali regeneracija odstopata, obdrži ali znižaj obremenitev.",
            "deload": "Razbremenitev se ne določa avtomatično po koledarju; uporabi jo ob vztrajnem slabšanju zmogljivosti, regeneracije ali kakovosti izvedbe.",
        },
        "sessions": plans,
        "weekly_summary": {
            "total_work_sets": total_sets,
            "exercise_frequency": dict(used_counts),
            "primary_muscle_set_exposure": {key: value for key, value in exposure.items() if value > 0},
            "unfilled_patterns": sorted(missing_patterns),
        },
        "limitations": [
            "Ocena trajanja je približek; dejanski čas je odvisen od hitrosti izvedbe, menjave opreme in individualnih odmorov.",
            "Katalog ne ocenjuje zdravstvenih stanj. Omejitve in simptome mora pred izbiro vaj pregledati trener oziroma ustrezen zdravstveni strokovnjak.",
            "Tedenska izpostavljenost mišičnih skupin pri večsklepnih vajah ni enaka številu neposrednih delovnih serij za posamezno mišico.",
        ],
    }
