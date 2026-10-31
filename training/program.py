"""Deterministic, catalogue-backed training-program generator for ATENA Phase 2."""
from __future__ import annotations

from collections import Counter
from typing import Any

from training.catalogue import get_exercises

SUPPORTED_GOALS = {"hypertrophy", "strength", "general_fitness", "functional", "power", "endurance", "mobility"}
SUPPORTED_LEVELS = {"beginner", "intermediate", "advanced"}
SUPPORTED_SESSIONS = {2, 3, 4}
PATTERN_LABELS = {
    "squat": "počep",
    "lunge": "izpadni korak",
    "hinge": "predklon z ravnim hrbtom",
    "hip_extension": "izteg kolkov",
    "horizontal_push": "horizontalni potisk",
    "horizontal_pull": "horizontalni poteg",
    "vertical_push": "vertikalni potisk",
    "vertical_pull": "vertikalni poteg",
    "carry": "nošenje",
    "anti_rotation": "preprečevanje rotacije",
    "trunk_stability": "stabilizacija trupa",
    "jump": "skok",
    "hinge_power": "eksplozivni predklon z ravnim hrbtom",
    "accessory": "dopolnilna vaja",
    "conditioning": "kondicijska vadba",
    "locomotion": "lokomocija",
    "mobility": "mobilnost",
    "knee_flexion": "upogib kolena",
}
PATTERN_ORDER = [
    "squat", "lunge", "hinge", "hip_extension", "horizontal_push", "horizontal_pull",
    "vertical_push", "vertical_pull", "carry", "anti_rotation",
    "trunk_stability", "jump", "hinge_power", "conditioning", "locomotion", "mobility", "knee_flexion",
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
    return {
        **profile,
        "sessions_per_week": sessions,
        "session_minutes": duration,
        "equipment": sorted(set(equipment) | {"bodyweight"}),
        "excluded_exercise_ids": set(exclusions),
        "excluded_patterns": set(excluded_patterns),
        "include_accessories": accessories,
    }


def _session_patterns(session_index: int, sessions: int, goal: str, include_accessories: bool = False, include_stability: bool = False) -> list[str]:
    """Compact full-body templates; trunk-control work is added only when feedback supports it."""
    if goal == "endurance":
        return ["locomotion", "conditioning", "carry"] if session_index % 2 == 0 else ["locomotion", "lunge", "conditioning"]
    if goal == "mobility":
        return ["mobility", "squat", "lunge", "hinge", "horizontal_push"]
    base = ["squat", "hinge", "horizontal_push", "horizontal_pull"]
    if sessions == 2:
        extras = [["lunge", "vertical_push"], ["lunge", "vertical_pull"]]
    elif sessions == 3:
        extras = [["lunge", "vertical_push"], ["vertical_pull", "lunge"], ["lunge", "vertical_push"]]
    else:
        extras = [["lunge", "vertical_push"], ["vertical_pull", "lunge"], ["lunge", "vertical_push"], ["vertical_pull", "lunge"]]
    patterns = base + (extras[session_index][:1] if include_stability else extras[session_index])
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
    if goal == "mobility" or pattern == "mobility":
        sets, reps, rir, rest = 2, "5–8", None, 30
    elif goal == "endurance" and pattern == "locomotion":
        sets, reps, rir, rest = 1, "20–30 min", None, 0
    elif goal == "endurance" and pattern == "conditioning":
        sets, reps, rir, rest = 6, "30 s", None, 30
    elif goal == "endurance" and pattern in {"carry", "lunge"}:
        sets, reps, rir, rest = 2, "12–20", None, 45
    elif is_power:
        sets, reps, rir, rest = 3, "3–5", 4, 150
    elif level == "beginner":
        # For novices, movement skill and repeatable technique outrank maximal loading,
        # even when the selected long-term goal is strength.
        if is_stability:
            sets, reps, rir, rest = 2, "10–15", 3, 60
        elif pattern in {"lunge"} or unilateral:
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
            sets, reps, rir, rest = (4, "3–6", 2, 180) if level == "advanced" else (3, "5–8", 2, 150)
        elif is_stability:
            sets, reps, rir, rest = 2, "10–15", 3, 60
        elif pattern in {"carry", "hip_extension"}:
            sets, reps, rir, rest = 2, "8–12", 3, 75
        else:
            sets, reps, rir, rest = 3, ("6–8" if unilateral else "6–8"), 2, (120 if unilateral else 120)
    elif goal == "hypertrophy":
        if pattern in {"squat", "hinge"}:
            sets, reps, rir, rest = 3, "6–10", (2 if level != "beginner" else 3), 150 if level == "advanced" else 120
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
            sets, reps, rir, rest = 2, "10–15", 3, 60
        elif pattern in {"hip_extension", "carry"}:
            sets, reps, rir, rest = 2, "10–15", 3, 75
        else:
            sets, reps, rir, rest = (3, "6–12", 3, 90) if level != "beginner" else (2, "8–12", 3, 75)
    if goal == "mobility" or pattern == "mobility":
        tempo, tempo_description, tempo_seconds = "kontrolirano", "Aktivno raziskuj razpoložljivo amplitudo brez sunkov in prisiljevanja.", 4
    elif goal == "endurance":
        tempo, tempo_description, tempo_seconds = "ritmično", "Ohrani enakomeren ritem in intenzivnost, ki ustreza predpisanemu cilju.", 0
    elif is_power:
        tempo, tempo_description, tempo_seconds = "1–0–X–0", "Nadzorovan začetni položaj; dvig oziroma odriv izvedi hitro in tehnično čisto; med ponovitvami se ponastavi.", 3
    elif is_stability:
        tempo, tempo_description, tempo_seconds = "2–1–2–1", "2 s izteg oziroma odmik · 1 s nadzor · 2 s vrnitev · 1 s ponastavitev.", 6
    else:
        tempo, tempo_description, tempo_seconds = "3–0–1–0", "3 s spuščanje · brez odboja · 1 s dvig · brez zadrževanja v vrhu.", 4
    prescription = {
        "sets": sets,
        "reps": reps,
        "rest_seconds": rest,
        "rep_unit": "per_side" if (unilateral or exercise.get("reps_per_side")) else "total",
        "tempo": tempo,
        "tempo_description": tempo_description,
        "tempo_seconds_per_rep": tempo_seconds,
    }
    if goal == "endurance" and pattern == "locomotion":
        prescription.update({"work_seconds": 1200, "time_label": "neprekinjene aerobne aktivnosti", "effort_target": "Zmeren pogovorni tempo; lahko govoriš v stavkih, vendar čutiš pospešeno dihanje."})
    elif goal == "endurance" and pattern == "conditioning":
        prescription.update({"work_seconds": 30, "time_label": "dela", "effort_target": "Intervali naj bodo zahtevni, vendar tehnično ponovljivi; ne začni z maksimalnim naporom."})
    elif goal == "mobility" or pattern == "mobility":
        prescription.update({"work_seconds": 20, "time_label": "aktivnega zadržanja oziroma dela", "effort_target": "Deluj v kontrolirani neboleči amplitudi; brez siljenja v končni položaj."})
    if is_stability:
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


def generate_program(profile: object, feedback: object = None) -> dict:
    """Generate a repeatable catalogue plan, conservatively adapting to the last session."""
    p = validate_profile(profile)
    response = _validate_feedback(feedback)
    reduce_load = bool(response and (
        response["difficulty"] == "hard" or not response["completed"] or response["recovery"] == "poor"
    ))
    include_stability = bool(response and response.get("movement_control", "none") != "none")
    goal_sources = {
        "functional": ["functional", "general_fitness", "strength", "mobility"],
        "general_fitness": ["general_fitness", "functional", "strength", "endurance"],
        "power": ["power", "strength", "general_fitness"],
        "endurance": ["endurance", "general_fitness"],
        "mobility": ["mobility", "functional", "general_fitness"],
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
            if reference is None or reference["id"] == current_id:
                continue
            if reference["pattern"] not in compatible_patterns:
                continue
            available = set(p["equipment"]) | {"bodyweight"}
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

    # Never prescribe an unloaded hinge drill as the main hypertrophy stimulus.
    if p["goal"] == "hypertrophy":
        has_external_load = bool({"barbell", "dumbbell", "kettlebell"} & set(p["equipment"]))
        hinge_candidates = [
            item for item in by_pattern.get("hinge", [])
            if item.get("loading_potential") in {"moderate", "high"}
            and (has_external_load or item["id"] != "single_leg_rdl")
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
            session_index, p["sessions_per_week"], p["goal"],
            p["include_accessories"] and p["session_minutes"] >= 75 and not include_stability, include_stability
        )
        warm_up_minutes = 5 if p["session_minutes"] <= 30 else (7 if p["session_minutes"] <= 60 else 10)
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
            def selection_priority(item: dict) -> int:
                if pattern == "horizontal_push":
                    if item["id"] == "bench_dip":
                        return 10
                    if item["id"] == "parallel_bar_dip":
                        return -5 if p["experience"] == "advanced" else 5
                    if item["id"] == "dumbbell_floor_press" and any(
                        candidate["id"] in {"push_up", "dumbbell_bench_press"} for candidate in candidates
                    ):
                        return 10
                    if item["id"] == "dumbbell_bench_press":
                        return 0 if {"dumbbell", "bench"}.issubset(set(p["equipment"])) else 5
                    if item["id"] == "push_up":
                        return 0
                if pattern == "hinge":
                    if item["id"] in {"romanian_deadlift", "dumbbell_deadlift", "deadlift"}:
                        return -10 if set(item["equipment"]).issubset(set(p["equipment"])) else 5
                    if p["goal"] == "hypertrophy" and item["id"] in {"slider_leg_curl", "long_lever_glute_bridge", "elevated_heel_hip_lift"}:
                        return -5
                    if item["id"] == "bodyweight_hip_hinge":
                        return 20 if p["goal"] == "hypertrophy" else 0
                return 0
            candidate = min(candidates, key=lambda item: (
                selection_priority(item),
                0 if p["goal"] != "hypertrophy" or item.get("loading_potential") != "low" else 1,
                0 if p["experience"] != "beginner" or item["level"] == "beginner" else 1,
                used_counts[item["id"]],
                item["level"] != p["experience"], item["id"]
            ))
            effective_pattern = candidate["pattern"]
            used_counts[candidate["id"]] += 1
            prescription = _prescription(p["goal"], p["experience"], effective_pattern, candidate)
            if p["goal"] == "endurance" and effective_pattern == "locomotion":
                prescription["work_seconds"] = max(600, int(p["session_minutes"] * 30))
            if reduce_load and p["goal"] not in {"endurance", "mobility"} and not candidate["single_joint"] and pattern not in {"trunk_stability", "anti_rotation"}:
                prescription["sets"] = max(2, prescription["sets"] - 1)
                if prescription.get("rir") is not None:
                    prescription["rir"] = min(4, prescription["rir"] + 1)
                    if prescription.get("rir_range") == "2–3":
                        prescription["rir_range"] = "3–4"
                prescription["rest_seconds"] += 30
            optional_equipment = sorted(
                set(candidate["equipment_any"]) & set(p["equipment"]),
                key=lambda item: (item == "bodyweight", item),
            )
            selected_equipment = candidate["equipment"] + optional_equipment[:1]
            regressions = safe_references(candidate["regressions"], candidate["id"], effective_pattern)
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
                "pattern_label": PATTERN_LABELS.get(effective_pattern, effective_pattern),
                "joint_type": candidate["joint_type"],
                "loading_potential": candidate["loading_potential"],
                "training_role": candidate["training_role"],
                "endurance_type": candidate.get("endurance_type"),
                "time_based": bool(candidate.get("time_based")),
                "reps_per_side": bool(candidate.get("unilateral") or candidate.get("reps_per_side")),
                "primary_muscles": candidate["primary_muscles"],
                "equipment": selected_equipment,
                "cues": candidate["cues"],
                "range_of_motion": candidate.get("range_of_motion") or (
                    "Uporabi največjo nebolečo amplitudo, ki jo dopuščata tvoja gibljivost in nadzor. "
                    "Ne krajšaj giba po nepotrebnem; amplitudo povečuj postopno, brez izgube položaja."
                ),
                "warnings": candidate["warnings"],
                "regressions": regressions,
                "alternatives": alternatives,
                "prescription": prescription,
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
            removal_priority = ("accessory", "hip_extension", "carry")
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
                 if item["pattern"] in {"squat", "hinge", "horizontal_push", "horizontal_pull"}
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
            "title": f"Trening {session_index + 1} – celotno telo",
            "warm_up_minutes": warm_up_minutes,
            "warm_up_range": "5–7 min" if p["session_minutes"] <= 30 else "5–10 min",
            "exercise_count": len(selected),
            "estimated_minutes": estimated,
            "available_minutes": p["session_minutes"],
            "volume_adjustments": volume_adjustments,
            "exercises": selected,
        })

    total_sets = sum(item["prescription"]["sets"] for session in plans for item in session["exercises"])
    pattern_session_frequency: Counter[str] = Counter()
    pattern_work_sets: Counter[str] = Counter()
    for session in plans:
        for item in session["exercises"]:
            pattern_session_frequency[item["pattern"]] += 1
            pattern_work_sets[item["pattern"]] += item["prescription"]["sets"]
    return {
        "program_version": "2.5.0",
        "goal": p["goal"],
        "experience": p["experience"],
        "sessions_per_week": p["sessions_per_week"],
        "session_minutes": p["session_minutes"],
        "methodology": {
            "exercise_source": "verified_catalogue_only",
            "compound_first": True,
            "single_joint_accessories": p["include_accessories"],
            "exercise_scaling": "Vsaka vaja ima označen potencial obremenitve, vlogo, zahteve glede opreme in stopnjevanje. Nizko obremenljive učne vaje niso privzeta glavna izbira za hipertrofijo.",
            "equipment_policy": "Brez uteži ne pomeni brez običajnih stabilnih gospodinjskih opor. Stol, kavč, miza, stopnica, brisača ali palica so dovoljeni le, kadar jih profil izrecno vključuje in so varni za uporabo.",
            "endurance_policy": "Vzdržljivost je ločen cilj; aerobne aktivnosti, intervali in mišična vzdržljivost so označeni ločeno.",
            "mobility_policy": "Mobilnost vključuje aktivne gibalne vaje, kontrolirano gibanje v končnih amplitudah in moč skozi razpoložljiv obseg, ne samo pasivnega raztezanja.",
            "experience_adaptation": (
                "Začetnik: prednost imajo učenje osnovnih gibalnih vzorcev, nadzorovana amplituda in ponovljiva tehnika. "
                "Tudi pri cilju moč začni večinoma z 8–12 ponovitvami in približno 2–3 ponovitvami v rezervi; "
                "šele z napredovanjem postopno preidi na nižje razpone in večje obremenitve."
                if p["experience"] == "beginner" else
                "Intermediate: uporablja bolj specifične razpone glede na cilj; pri glavnih vajah za moč je običajen razpon 5–8 ponovitev, "
                "pri hipertrofiji večinoma 6–12. Advanced: pri glavnih vajah za moč lahko uporablja 3–6 ponovitev, "
                "ob večji obremenitvi pa zahteva ustrezno tehniko, regeneracijo in daljše odmore."
            ),
            "tempo": "Tempo je predpisan pri vsaki vaji. Pri glavnih vajah je privzeto 3–0–1–0: 3 s spuščanje in 1 s dvig; brez odboja. Ciljno delo za stabilizacijo se doda samo ob konkretni povratni informaciji in je umeščeno takoj za splošno ogrevanje.",
            "range_of_motion": "Pri vsaki vaji uporabi največjo amplitudo, ki jo omogočata gibljivost in nadzor. "
                               "Amplitudo postopno razvijaj; ne žrtvuj položaja, stabilnosti ali neboleče izvedbe.",
            "progression": "Ko pri vseh serijah dosežeš zgornjo mejo ponovitev in ohraniš predpisano rezervo ter tempo, pri naslednjem treningu rahlo zvišaj obremenitev. Če tehnika ali regeneracija odstopata, obdrži ali znižaj obremenitev.",
            "deload": "Razbremenitev se ne določa avtomatično po koledarju; uporabi jo ob vztrajnem slabšanju zmogljivosti, regeneracije ali kakovosti izvedbe.",
            "last_session_adjustment": "reduce_sets_increase_reserve" if reduce_load else ("hold_and_progress_by_rule" if response and response["difficulty"] == "easy" else "maintain"),
        },
        "feedback_applied": response,
        "sessions": plans,
        "weekly_summary": {
            "total_work_sets": total_sets,
            "exercise_frequency": dict(used_counts),
            "primary_muscle_set_exposure": {key: value for key, value in exposure.items() if value > 0},
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
        ],
    }
