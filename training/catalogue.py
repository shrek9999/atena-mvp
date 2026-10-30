"""Validated exercise catalogue and deterministic filtering for ATENA Phase 1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

CATALOGUE_PATH = Path(__file__).with_name("exercises.json")
REQUIRED_FIELDS = {
    "id", "name", "name_en", "pattern", "joint_type", "goals", "equipment", "equipment_any",
    "level", "primary_muscles", "secondary_muscles", "cues", "common_errors",
    "regressions", "progressions", "alternatives", "warnings", "single_joint",
}
VALID_JOINT_TYPES = {"multi_joint", "single_joint"}
VALID_LEVELS = {"beginner", "intermediate", "advanced"}


class CatalogueValidationError(ValueError):
    """Raised when exercise data is incomplete or internally inconsistent."""


def load_catalogue(path: Path | str = CATALOGUE_PATH) -> list[dict]:
    """Load and validate the exercise dataset; fail closed on invalid records."""
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    validate_catalogue(data)
    return data


def validate_catalogue(exercises: object) -> None:
    if not isinstance(exercises, list) or not exercises:
        raise CatalogueValidationError("Katalog mora biti neprazen seznam vaj.")
    seen: set[str] = set()
    for index, exercise in enumerate(exercises):
        prefix = f"Vaja na mestu {index}"
        if not isinstance(exercise, dict):
            raise CatalogueValidationError(f"{prefix} ni objekt.")
        missing = REQUIRED_FIELDS - exercise.keys()
        if missing:
            raise CatalogueValidationError(f"{prefix} nima polj: {', '.join(sorted(missing))}.")
        exercise_id = exercise["id"]
        if not isinstance(exercise_id, str) or not exercise_id.strip():
            raise CatalogueValidationError(f"{prefix} nima veljavnega ID-ja.")
        if exercise_id in seen:
            raise CatalogueValidationError(f"Podvojen ID vaje: {exercise_id}.")
        seen.add(exercise_id)
        for field in ("name", "name_en", "pattern", "level"):
            if not isinstance(exercise[field], str) or not exercise[field].strip():
                raise CatalogueValidationError(f"{exercise_id}: polje {field} mora biti neprazen niz.")
        if exercise["joint_type"] not in VALID_JOINT_TYPES:
            raise CatalogueValidationError(f"{exercise_id}: neveljaven joint_type.")
        if exercise["level"] not in VALID_LEVELS:
            raise CatalogueValidationError(f"{exercise_id}: neveljavna zahtevnost.")
        if exercise["single_joint"] != (exercise["joint_type"] == "single_joint"):
            raise CatalogueValidationError(f"{exercise_id}: single_joint in joint_type nista usklajena.")
        if "unilateral" in exercise and not isinstance(exercise["unilateral"], bool):
            raise CatalogueValidationError(f"{exercise_id}: unilateral mora biti true ali false.")
        for field in ("goals", "equipment", "equipment_any", "primary_muscles", "secondary_muscles",
                      "cues", "common_errors", "regressions", "progressions",
                      "alternatives", "warnings"):
            value = exercise[field]
            if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise CatalogueValidationError(f"{exercise_id}: polje {field} mora biti seznam nepraznih nizov.")
        if not exercise["goals"] or not (exercise["equipment"] or exercise["equipment_any"]) or not exercise["primary_muscles"]:
            raise CatalogueValidationError(f"{exercise_id}: goals, vsaj ena zahteva glede opreme in primary_muscles ne smejo biti prazni.")


def get_exercises(
    goal: str | None = None,
    equipment: Iterable[str] | None = None,
    patterns: Iterable[str] | None = None,
    include_accessories: bool = False,
    level: str | None = None,
    path: Path | str = CATALOGUE_PATH,
) -> list[dict]:
    """Return deterministic matches; accessory work is opt-in by design.

    Equipment is interpreted as available equipment. Bodyweight is treated as
    universally available. No injury or symptom inference is performed here.
    """
    records = load_catalogue(path)
    available = set(equipment or [])
    wanted_patterns = set(patterns or [])
    result = []
    for exercise in records:
        if goal and goal not in exercise["goals"]:
            continue
        if wanted_patterns and exercise["pattern"] not in wanted_patterns:
            continue
        if level and exercise["level"] != level:
            continue
        if exercise["single_joint"] and not include_accessories:
            continue
        required = set(exercise["equipment"])
        optional_match = set(exercise["equipment_any"])
        if available:
            if not required.issubset(available | {"bodyweight"}):
                continue
            if optional_match and not (optional_match & (available | {"bodyweight"})):
                continue
        result.append(exercise)
    return result


def get_exercise(exercise_id: str, path: Path | str = CATALOGUE_PATH) -> dict | None:
    return next((item for item in load_catalogue(path) if item["id"] == exercise_id), None)
