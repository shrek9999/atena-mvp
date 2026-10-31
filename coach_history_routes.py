"""Authenticated profile, programme and workout-history endpoints for ATENA."""
from __future__ import annotations

import hmac
import logging
import math
import os
import sqlite3

from flask import Blueprint, jsonify, request

from training.catalogue import get_exercise
from training.persistence import (
    create_profile,
    get_profile_by_token,
    get_program,
    latest_feedback,
    list_programs,
    list_workouts,
    save_check_in,
    save_program,
    save_workout,
    update_profile,
)
from training.program import ProgramSafetyBlock, ProgramValidationError, generate_program

logger = logging.getLogger(__name__)
coach_history_bp = Blueprint("coach_history", __name__)

ALLOWED_ORIGINS = {
    "https://gregajenko.si",
    "https://www.gregajenko.si",
    "https://deploy-preview-7--tiny-figolla-016703.netlify.app",
}


@coach_history_bp.after_request
def add_history_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Pilot-Token, X-Profile-Token"
        response.headers["Access-Control-Max-Age"] = "600"
    return response


def _pilot_authorized():
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected:
        return False, (jsonify({"error": "Testni dostop še ni nastavljen na strežniku."}), 503)
    if not supplied or not hmac.compare_digest(supplied, expected):
        return False, (jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403)
    return True, None


def _profile():
    token = request.headers.get("X-Profile-Token", "").strip()
    profile = get_profile_by_token(token)
    if profile is None:
        return None, (jsonify({"error": "Profil ni dostopen. Preveri osebni dostopni ključ."}), 403)
    return profile, None


def _json_body():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None
    return payload


def _validate_feedback(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("feedback mora biti JSON objekt.")
    difficulty = value.get("difficulty")
    completed = value.get("completed")
    discomfort = value.get("discomfort")
    movement_control = value.get("movement_control", "none")
    recovery = value.get("recovery", "normal")
    if difficulty not in {"easy", "right", "hard"}:
        raise ValueError("difficulty mora biti easy, right ali hard.")
    if not isinstance(completed, bool):
        raise ValueError("completed mora biti true ali false.")
    if discomfort not in {"yes", "no"}:
        raise ValueError("discomfort mora biti yes ali no.")
    if movement_control not in {"none", "spinal_flexion", "bracing", "both"}:
        raise ValueError("movement_control ni veljavna vrednost.")
    if recovery not in {"good", "normal", "poor"}:
        raise ValueError("recovery mora biti good, normal ali poor.")
    return {
        "difficulty": difficulty,
        "completed": completed,
        "discomfort": discomfort,
        "movement_control": movement_control,
        "recovery": recovery,
    }


def _storage_error():
    logger.exception("ATENA profile/history storage operation failed")
    return jsonify({"error": "Podatkov trenutno ni mogoče varno shraniti ali prebrati."}), 503


@coach_history_bp.route("/coach/profile", methods=["POST", "OPTIONS"])
def create_coach_profile():
    if request.method == "OPTIONS":
        return ("", 204)
    authorized, error = _pilot_authorized()
    if not authorized:
        return error
    payload = _json_body()
    if payload is None or not isinstance(payload.get("profile"), dict):
        return jsonify({"error": "Pošlji profil v polju profile."}), 400
    try:
        result = create_profile(payload["profile"])
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error):
        return _storage_error()
    return jsonify({
        **result,
        "security_note": "Osebni ključ je prikazan samo ob ustvarjanju profila. Shrani ga varno.",
        "storage_note": "Hramba je trajna samo, če ATENA_DATABASE_PATH kaže na trajni podatkovni nosilec.",
    }), 201


@coach_history_bp.route("/coach/profile", methods=["GET", "PUT", "OPTIONS"])
def coach_profile():
    if request.method == "OPTIONS":
        return ("", 204)
    profile, error = _profile()
    if error:
        return error
    if request.method == "GET":
        return jsonify({
            "profile_id": profile["profile_id"],
            "profile": profile["profile"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
        }), 200
    payload = _json_body()
    if payload is None or not isinstance(payload.get("profile"), dict):
        return jsonify({"error": "Pošlji posodobljen profil v polju profile."}), 400
    try:
        updated = update_profile(profile["profile_id"], payload["profile"])
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error):
        return _storage_error()
    if updated is None:
        return jsonify({"error": "Profila ni mogoče najti."}), 404
    return jsonify(updated), 200


@coach_history_bp.route("/coach/programs", methods=["GET", "POST", "OPTIONS"])
def coach_program_history():
    if request.method == "OPTIONS":
        return ("", 204)
    profile, error = _profile()
    if error:
        return error
    if request.method == "GET":
        try:
            return jsonify({"programs": list_programs(profile["profile_id"])}), 200
        except (OSError, sqlite3.Error):
            return _storage_error()
    try:
        feedback = latest_feedback(profile["profile_id"])
        program = generate_program(profile["profile"], feedback=feedback)
        program_id = save_program(profile["profile_id"], program)
    except ProgramSafetyBlock as exc:
        return jsonify({
            "blocked": True,
            "adaptation_blocked": True,
            "message": str(exc),
            "next_step": "Pred nadaljevanjem preveri trenutno počutje in omejitve. Zabeleži novo povratno informacijo šele, ko lahko zanesljivo potrdiš, da nelagodja ni več.",
        }), 409
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error):
        return _storage_error()
    return jsonify({
        "program_id": program_id,
        "program": program,
        "feedback_source": "latest_saved_training_response" if feedback else "none",
    }), 201


@coach_history_bp.route("/coach/workouts", methods=["GET", "POST", "OPTIONS"])
def coach_workout_history():
    if request.method == "OPTIONS":
        return ("", 204)
    profile, error = _profile()
    if error:
        return error
    if request.method == "GET":
        try:
            raw_limit = request.args.get("limit", "30")
            limit = int(raw_limit)
            if not 1 <= limit <= 50:
                raise ValueError
        except ValueError:
            return jsonify({"error": "limit mora biti celo število med 1 in 50."}), 400
        try:
            return jsonify({"workouts": list_workouts(profile["profile_id"], limit=limit)}), 200
        except (OSError, sqlite3.Error):
            return _storage_error()

    payload = _json_body()
    if payload is None:
        return jsonify({"error": "Pričakovan je JSON objekt."}), 400
    program_id = payload.get("program_id")
    session_number = payload.get("session")
    if not isinstance(program_id, str) or not program_id or isinstance(session_number, bool) or not isinstance(session_number, int):
        return jsonify({"error": "program_id in številka treninga session sta obvezna."}), 400
    try:
        saved_program = get_program(profile["profile_id"], program_id)
        if saved_program is None:
            return jsonify({"error": "Programa ni mogoče najti za ta profil."}), 404
        sessions = saved_program["program"].get("sessions", [])
        if not 1 <= session_number <= len(sessions):
            return jsonify({"error": "Izbrana številka treninga ne obstaja v programu."}), 400
        session = next(item for item in sessions if item.get("session") == session_number)
        planned = {item.get("exercise_id") for item in session.get("exercises", [])}
        exercises = payload.get("exercises")
        if not isinstance(exercises, list) or not 1 <= len(exercises) <= 20:
            return jsonify({"error": "Pošlji od 1 do 20 izvedenih vaj."}), 400
        validated_exercises = []
        for item in exercises:
            if not isinstance(item, dict):
                return jsonify({"error": "Zapis vaje mora biti objekt."}), 400
            exercise_id = item.get("exercise_id")
            if not isinstance(exercise_id, str) or exercise_id not in planned or get_exercise(exercise_id) is None:
                return jsonify({"error": "Dnevnik lahko vsebuje samo vaje iz izbranega treninga."}), 400
            sets = item.get("sets")
            if not isinstance(sets, list) or not 1 <= len(sets) <= 12:
                return jsonify({"error": "Za vsako zabeleženo vajo pošlji od 1 do 12 serij."}), 400
            validated_sets = []
            for set_item in sets:
                if not isinstance(set_item, dict):
                    return jsonify({"error": "Zapis serije mora biti objekt."}), 400
                reps = set_item.get("reps")
                if isinstance(reps, bool) or not isinstance(reps, int) or not 1 <= reps <= 100:
                    return jsonify({"error": "Število ponovitev mora biti celo število med 1 in 100."}), 400
                row = {"reps": reps}
                if "load_kg" in set_item:
                    load = set_item["load_kg"]
                    if isinstance(load, bool) or not isinstance(load, (int, float)) or not math.isfinite(load) or not 0 <= load <= 1000:
                        return jsonify({"error": "load_kg mora biti število med 0 in 1000."}), 400
                    row["load_kg"] = float(load)
                if "rir" in set_item:
                    rir = set_item["rir"]
                    if isinstance(rir, bool) or not isinstance(rir, int) or not 0 <= rir <= 10:
                        return jsonify({"error": "RIR mora biti celo število med 0 in 10."}), 400
                    row["rir"] = rir
                validated_sets.append(row)
            validated_exercises.append({"exercise_id": exercise_id, "sets": validated_sets})
        feedback = _validate_feedback(payload.get("feedback"))
        duration = payload.get("duration_minutes")
        if duration is not None and (isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 240):
            return jsonify({"error": "duration_minutes mora biti celo število med 1 in 240."}), 400
        saved = save_workout(
            profile["profile_id"], program_id, session_number, duration,
            feedback, validated_exercises,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error):
        return _storage_error()
    return jsonify({
        **saved,
        "adaptation_status": "blocked_pending_review" if feedback["discomfort"] == "yes" else "feedback_saved",
        "message": (
            "Zabeleženo je nelagodje. Samodejno prilagajanje programa je ustavljeno."
            if feedback["discomfort"] == "yes"
            else "Trening in povratna informacija sta shranjena."
        ),
    }), 201


@coach_history_bp.route("/coach/check-ins", methods=["POST", "OPTIONS"])
def coach_check_in():
    if request.method == "OPTIONS":
        return ("", 204)
    profile, error = _profile()
    if error:
        return error
    payload = _json_body()
    if payload is None:
        return jsonify({"error": "Pričakovan je JSON objekt."}), 400
    try:
        feedback = _validate_feedback(payload.get("feedback"))
        saved = save_check_in(profile["profile_id"], feedback)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error):
        return _storage_error()
    return jsonify({
        **saved,
        "message": (
            "Zabeleženo je nelagodje; samodejno prilagajanje ostaja ustavljeno."
            if feedback["discomfort"] == "yes"
            else "Nova samoocena je shranjena. To ni zdravstvena presoja ali zdravniško dovoljenje za vadbo."
        ),
    }), 201
