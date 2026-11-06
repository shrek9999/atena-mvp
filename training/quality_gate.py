"""Deterministic final quality gate for generated ATENA programmes.

The generator is the planner; this module is an independent last-pass audit.
It does not silently repair a plan. Any violation is returned to the caller so
that an invalid prescription cannot be presented as a verified programme.
"""
from __future__ import annotations

from training.catalogue import get_exercises


GOAL_PURPOSES = {
    "strength": {"strength"},
    "hypertrophy": {"hypertrophy"},
    "strength_hypertrophy": {"strength", "hypertrophy"},
    "fat_loss": {
        "strength", "hypertrophy", "general_fitness",
        "cardiorespiratory_conditioning", "muscular_endurance",
    },
    "general_fitness": {
        "general_fitness", "functional_fitness", "strength",
        "cardiorespiratory_conditioning", "mobility", "balance", "coordination",
    },
    "functional": {
        "functional_fitness", "general_fitness", "strength",
        "cardiorespiratory_conditioning", "mobility", "balance",
        "coordination", "power",
    },
    "power": {"power", "strength"},
    "endurance": {
        "cardiorespiratory_conditioning", "muscular_endurance", "general_fitness",
    },
    "mobility": {
        "mobility", "strength", "general_fitness", "functional_fitness",
        "balance", "coordination",
    },
}
def validate_generated_program(program: object, profile: object) -> list[str]:
    """Return all material quality failures in a generated programme.

    The checks are intentionally independent of the selection algorithm so a
    future refactor cannot accidentally remove a safety or quality invariant.
    """
    issues: list[str] = []
    if not isinstance(program, dict):
        return ["Program ni JSON objekt."]
    if not isinstance(profile, dict):
        return ["Profil ni JSON objekt."]

    sessions = program.get("sessions")
    if not isinstance(sessions, list):
        return ["Program nima veljavnega seznama treningov."]
    expected_sessions = profile.get("sessions_per_week")
    if len(sessions) != expected_sessions:
        issues.append("Število treningov ne ustreza profilu.")

    goal = profile.get("goal")
    experience = profile.get("experience")
    if program.get("goal") != goal:
        issues.append("Cilj v programu se ne ujema s profilom.")
    if program.get("experience") != experience:
        issues.append("Raven izkušenj v programu se ne ujema s profilom.")
    if program.get("sessions_per_week") != expected_sessions:
        issues.append("Pogostost treningov v povzetku se ne ujema s profilom.")
    if program.get("session_minutes") != profile.get("session_minutes"):
        issues.append("Trajanje treninga v povzetku se ne ujema s profilom.")
    allowed_purposes = GOAL_PURPOSES.get(goal, set())
    available = set(profile.get("equipment", [])) | {"bodyweight"}
    excluded_ids = set(profile.get("excluded_exercise_ids", []))
    excluded_patterns = set(profile.get("excluded_patterns", []))
    feedback = program.get("feedback_applied") or {}
    stability_was_requested = (
        isinstance(feedback, dict)
        and feedback.get("movement_control", "none") != "none"
    )
    catalogue = {item["id"]: item for item in get_exercises(include_accessories=True)}

    for session_index, session in enumerate(sessions, start=1):
        prefix = f"Trening {session_index}"
        if not isinstance(session, dict):
            issues.append(f"{prefix} ni veljaven objekt.")
            continue
        exercises = session.get("exercises")
        if not isinstance(exercises, list):
            issues.append(f"{prefix} nima seznama vaj.")
            continue
        if not 3 <= len(exercises) <= 7:
            issues.append(f"{prefix} mora vsebovati 3–7 smiselnih vaj.")
        if session.get("available_minutes") != profile.get("session_minutes"):
            issues.append(f"{prefix}: razpoložljivi čas ni skladen s profilom.")
        estimate = session.get("estimated_minutes")
        if not isinstance(estimate, int) or isinstance(estimate, bool) or estimate < 1:
            issues.append(f"{prefix}: ocena trajanja ni veljavna.")
        elif estimate > profile.get("session_minutes", 0):
            issues.append(f"{prefix}: ocenjeni čas presega razpoložljivi čas.")

        actual_sets = 0
        for exercise_index, exercise in enumerate(exercises, start=1):
            item_prefix = f"{prefix}, vaja {exercise_index}"
            if not isinstance(exercise, dict):
                issues.append(f"{item_prefix} ni veljaven objekt.")
                continue
            exercise_id = exercise.get("exercise_id")
            source = catalogue.get(exercise_id)
            if source is None:
                issues.append(f"{item_prefix}: vaja ni v preverjenem katalogu.")
                continue
            if exercise.get("name") != source.get("name"):
                issues.append(f"{item_prefix}: ime vaje se ne ujema s katalogom.")
            if exercise.get("pattern") != source.get("pattern"):
                issues.append(f"{item_prefix}: gibalni vzorec se ne ujema s katalogom.")
            if exercise_id in excluded_ids or exercise.get("pattern") in excluded_patterns:
                issues.append(f"{item_prefix}: uporabljena je izključena vaja ali vzorec.")

            selected_equipment = exercise.get("equipment")
            if not isinstance(selected_equipment, list) or any(
                not isinstance(value, str) for value in selected_equipment
            ):
                issues.append(f"{item_prefix}: zahteve glede opreme niso veljavne.")
            else:
                if not set(selected_equipment).issubset(available):
                    issues.append(f"{item_prefix}: program predpisuje nedostopno opremo.")
            required = set(source.get("equipment", []))
            optional = set(source.get("equipment_any", []))
            if not required.issubset(available):
                issues.append(f"{item_prefix}: manjkajo obvezne zahteve glede opreme.")
            if optional and not optional.intersection(available):
                issues.append(f"{item_prefix}: ni potrjene nobene zahtevane možnosti opreme.")

            purposes = set(exercise.get("training_purposes", []))
            purpose_matches_goal = bool(purposes.intersection(allowed_purposes))
            purpose_matches_targeted_stability = (
                stability_was_requested
                and source.get("stability_role") in {"primary", "supporting"}
                and bool(purposes.intersection({"stability", "trunk_bracing"}))
                and exercise.get("pattern") in {"trunk_stability", "anti_rotation"}
            )
            if allowed_purposes and not (
                purpose_matches_goal or purpose_matches_targeted_stability
            ):
                issues.append(f"{item_prefix}: namen vaje ni usklajen s ciljem.")
            if source.get("single_joint") and experience != "advanced":
                if not (goal == "mobility" and source.get("training_role") == "mobility"):
                    issues.append(f"{item_prefix}: enosklepna vaja ni primerna za privzeti profil.")
            # Carries and balance tasks have useful functional/strength roles even
            # though the catalogue labels their training_role as stability. The
            # explicit feedback requirement applies to targeted trunk-control drills.
            if exercise.get("pattern") in {"trunk_stability", "anti_rotation"} and not stability_was_requested:
                issues.append(f"{item_prefix}: ciljna vaja za nadzor trupa je vključena brez utemeljenega razloga.")

            prescription = exercise.get("prescription")
            if not isinstance(prescription, dict):
                issues.append(f"{item_prefix}: manjka strukturiran predpis.")
                continue
            sets = prescription.get("sets")
            if not isinstance(sets, int) or isinstance(sets, bool) or sets < 1:
                issues.append(f"{item_prefix}: število serij ni veljavno.")
            else:
                actual_sets += sets
            reps = prescription.get("reps")
            if not isinstance(reps, str) or not reps.strip():
                issues.append(f"{item_prefix}: manjka cilj ponovitev ali trajanja.")
            rest = prescription.get("rest_seconds")
            if not isinstance(rest, int) or isinstance(rest, bool) or rest < 0:
                issues.append(f"{item_prefix}: odmor ni veljaven.")
            tempo = prescription.get("tempo")
            if not isinstance(tempo, str) or not tempo.strip():
                issues.append(f"{item_prefix}: manjka predpisani tempo.")
            rir = prescription.get("rir")
            if rir is not None and (
                not isinstance(rir, int) or isinstance(rir, bool) or not 0 <= rir <= 10
            ):
                issues.append(f"{item_prefix}: RIR ni veljaven.")
            # Exercise-specific ROM guidance is optional; generic repeated filler is not required.
            rom_guidance = exercise.get("range_of_motion")
            if rom_guidance is not None and (
                not isinstance(rom_guidance, str) or not rom_guidance.strip()
            ):
                issues.append(f"{item_prefix}: navodilo za amplitudo ni veljavno.")
            if not isinstance(exercise.get("cues"), list) or not exercise["cues"]:
                issues.append(f"{item_prefix}: manjkajo izvedbeni napotki.")
            coaching_logic = exercise.get("coaching_logic")
            if not isinstance(coaching_logic, dict) or not all(
                isinstance(coaching_logic.get(key), list) and coaching_logic[key]
                for key in ("regress_when", "progress_when", "progression_order")
            ):
                issues.append(f"{item_prefix}: manjka jasna logika regresije in progresije.")

        if session.get("exercise_count") != len(exercises):
            issues.append(f"{prefix}: število vaj v povzetku ni pravilno.")
        if session.get("work_sets") != actual_sets:
            issues.append(f"{prefix}: število delovnih serij v povzetku ni pravilno.")

    return issues
