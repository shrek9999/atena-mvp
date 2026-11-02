"""Conservative, server-side conversational coach pilot for ATENA."""
import json
import os
import hmac
import logging
import urllib.error
import urllib.request
import secrets
import uuid
from datetime import date

from coach_store import (
    StorageUnavailable, ProfileNotFound, create_profile as store_create_profile,
    get_profile as store_get_profile, update_profile as store_update_profile,
    add_session as store_add_session, list_sessions as store_list_sessions,
    delete_profile as store_delete_profile, set_health_data_consent as store_set_health_data_consent,
    check_database_connection as store_check_database_connection, storage_enabled,
)
from training.catalogue import get_exercise, load_catalogue
from flask import Blueprint, jsonify, request
from training.program import ProgramSafetyBlock, ProgramValidationError, generate_program
from training.progress import summarize_progress
from training.adaptation import assess_next_step

logger = logging.getLogger(__name__)
coach_bp = Blueprint("coach", __name__)
ALLOWED_ORIGINS = {
    "https://gregajenko.si",
    "https://www.gregajenko.si",
    # Temporary, isolated Netlify Deploy Preview used for the closed pilot only.
    "https://deploy-preview-7--tiny-figolla-016703.netlify.app",
}

@coach_bp.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Pilot-Token, X-Profile-Token"
        response.headers["Access-Control-Max-Age"] = "600"
    return response

MAX_MESSAGE_CHARS = 1800
MAX_MESSAGES = 12

SYSTEM_PROMPT = """You are ATENA, Grega Jenko's pilot AI fitness coach. Reply in natural, grammatically correct Slovenian unless the user uses another language. Use clear, idiomatic wording, correct Slovenian grammar and punctuation, and concise headings/lists where helpful. Avoid awkward literal translations, excessive English jargon, and unsupported certainty.

ROLE AND METHOD
You are not a generic chatbot that simply prescribes an exercise in response to the last message. Act like a careful, proactive coach who first builds an adequate picture of the person, then gives a suitable next step and follows up over time. Use information already provided in the conversation; do not ask for it again. Do not pretend to remember information that is not in the conversation.

ONBOARDING AND QUESTIONS
Before prescribing an individualized workout or training plan, establish the minimum useful context:
1) main goal (e.g. strength, general fitness, mobility, return to activity);
2) current experience and approximate ability;
3) available equipment and realistic time;
4) relevant pain, injuries, movement limitations or medical restrictions;
5) weekly availability and, when relevant, age range or other factors affecting exercise selection.
Ask one concise, high-value question at a time. SAFETY-FIRST ORDER: if pain, injury, movement limitation or medical restriction has not yet been clarified, your first question must ask whether any of these are present. Do not ask about equipment, time or training frequency before this safety check. If the user confirms no relevant symptoms or restrictions, continue with the main goal, experience, equipment, realistic training time and weekly availability, one question at a time. Do not overwhelm the user with a long intake form. If the request is simple and low risk, you may give a clearly labelled general example while explaining that it is not yet individualized, and ask the most important follow-up question. If safety-relevant information is missing, ask before recommending demanding exercise.

PROACTIVE COACHING
- Explain briefly why the recommendation fits the known goal and ability.
- When a key detail is missing, say what you still need to know and ask one specific follow-up question.
- After giving a workout, proactively ask the user to report how it felt, effort (e.g. easy/moderate/hard), and any pain during or after it.
- Use the user's reports from earlier turns to adapt the next session, exercise variation, range of motion, volume, intensity and progression. Never claim persistent memory outside the conversation or an actual connected profile.
- Do not automatically increase difficulty. Progress gradually only when the prior session was tolerated well and recovery is adequate.
- Make the next useful step explicit; do not end every answer with a generic question unrelated to the plan.

TRAINING QUALITY
- Make duration arithmetic accurate. The sum of warm-up, work intervals, rest intervals, transitions and cool-down must equal the stated session duration. State sets, repetitions or work/rest intervals clearly and avoid contradictory timing.
- Match exercise selection and difficulty to the person's experience, goal, equipment and limitations. Include simple alternatives or easier versions when appropriate.
- Give practical intensity guidance (e.g. finish with 2–4 good repetitions in reserve for suitable strength exercises) only when appropriate for the user and exercise.
- Include a brief, realistic progression rule and explain when to stop or modify.
- Do not promise that a workout is risk-free or that it will cure pain. Avoid vague claims such as “without risk of overload.”
- Use the user's language consistently; proofread for grammar, spelling, terminology and internal consistency before answering.

SAFETY AND SCOPE
You are not a doctor or physiotherapist. Do not diagnose conditions, prescribe treatment, or claim to replace an in-person professional. Do not advise training through worsening pain. For severe, sudden, unexplained or worsening symptoms, recommend assessment by an appropriate healthcare professional. For chest pain, fainting, severe breathing difficulty, new weakness/numbness, or loss of bladder/bowel control with back pain, advise urgent local medical care. If relevant, ask about restrictions before suggesting exercise. Do not overreact to ordinary mild effort or soreness, but distinguish it from concerning or worsening symptoms.
Do not ask for full names, exact addresses or unnecessary personal data. Use health information only when needed. If uncertain, state the uncertainty rather than inventing facts, credentials, measurements, research or outcomes.

STYLE
Be warm, respectful, practical and encouraging without patronizing the user. Usually keep replies under 200 words, unless a plan or explanation genuinely needs more. Prioritize individualized reasoning and the next useful action over generic motivational text. This is a pilot, not individualized medical care."""

@coach_bp.route("/coach/chat", methods=["POST", "OPTIONS"])
def coach_chat():
    if request.method == "OPTIONS":
        return ("", 204)
    expected_token = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied_token = request.headers.get("X-Pilot-Token", "").strip()
    if not expected_token:
        return jsonify({"error": "Testni dostop še ni nastavljen na strežniku."}), 503
    if not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "Pilot še ni aktiviran: skrbnik mora na strežniku nastaviti GEMINI_API_KEY."}), 503
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Pričakovan je JSON objekt."}), 400
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
        return jsonify({"error": "Pošlji od 1 do 12 sporočil."}), 400
    contents = []
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in ("user", "model"):
            return jsonify({"error": "Neveljavna zgodovina pogovora."}), 400
        content = item.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_MESSAGE_CHARS:
            return jsonify({"error": "Sporočilo je prazno ali predolgo (največ 1800 znakov)."}), 400
        contents.append({"role": item["role"], "parts": [{"text": content.strip()}]})
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + api_key
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.35, "maxOutputTokens": 600}
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            data = json.loads(response.read().decode("utf-8"))
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        answer = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        if not answer:
            logger.warning("Gemini returned no text for model %s", model)
            return jsonify({"error": "Model ni vrnil odgovora. Poskusi znova."}), 502
        return jsonify({"reply": answer, "model": model, "pilot": True})
    except urllib.error.HTTPError as exc:
        # Log only status and model; never log provider body, API key, or secret-bearing URL.
        logger.error("Gemini provider returned HTTP %s for model %s", exc.code, model)
        if exc.code in (400, 401, 403):
            return jsonify({"error": "Povezava z modelom ni pravilno nastavljena. Skrbnik naj preveri ključ in model."}), 502
        if exc.code == 429:
            return jsonify({"error": "Trenutno je dosežena omejitev uporabe. Poskusi pozneje."}), 429
        return jsonify({"error": "Storitev trenutno ni dosegljiva. Poskusi znova."}), 502
    except (TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        logger.warning("Gemini request failed due to timeout, network error, or invalid JSON for model %s", model)
        return jsonify({"error": "Odgovor se je predolgo pripravljal ali povezava ni uspela. Poskusi znova."}), 504


@coach_bp.route("/coach/program", methods=["POST", "OPTIONS"])
def coach_program():
    """Return a deterministic programme generated only from the curated catalogue."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected_token = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied_token = request.headers.get("X-Pilot-Token", "").strip()
    if not expected_token:
        return jsonify({"error": "Testni dostop še ni nastavljen na strežniku."}), 503
    if not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Pričakovan je JSON objekt s profilom vadečega."}), 400
    profile = payload.get("profile", payload)
    feedback = payload.get("feedback")
    try:
        result = generate_program(profile, feedback=feedback)
    except ProgramSafetyBlock as exc:
        return jsonify({"blocked": True, "message": str(exc)}), 409
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, ValueError):
        logger.exception("ATENA catalogue/program generation failed")
        return jsonify({"error": "Programa trenutno ni mogoče sestaviti iz kataloga."}), 500
    return jsonify({"program": result, "source": "curated_exercise_catalogue", "pilot": True}), 200



@coach_bp.route("/coach/status", methods=["GET", "OPTIONS"])
def coach_status():
    """Read-only pilot readiness; exposes no credentials or user data."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    try:
        catalogue_count = len(load_catalogue())
    except (OSError, ValueError):
        catalogue_count = 0
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    return jsonify({
        "chat_available": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "program_available": catalogue_count > 0,
        "catalogue_count": catalogue_count,
        "chat_provider": "google_gemini" if os.getenv("GEMINI_API_KEY", "").strip() else None,
        "model": model if os.getenv("GEMINI_API_KEY", "").strip() else None,
    }), 200


@coach_bp.route("/coach/storage/check", methods=["GET", "OPTIONS"])
def coach_storage_check():
    """Pilot-token-protected, read-only DB connectivity check; creates no tables or user data."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    try:
        store_check_database_connection()
        return jsonify({"database": "reachable", "user_data_storage": "still_disabled"}), 200
    except StorageUnavailable as exc:
        logger.warning("ATENA database connectivity check failed: %s", type(exc).__name__)
        return jsonify({"database": "unavailable", "reason": exc.reason, "user_data_storage": "still_disabled"}), 503


@coach_bp.route("/coach/storage/status", methods=["GET", "OPTIONS"])
def coach_storage_status():
    """Return coarse operator-controlled storage readiness; never expose credentials."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    enabled = (
        os.getenv("ATENA_DATA_STORAGE_ENABLED", "").strip().lower() == "true"
        and os.getenv("ATENA_PRIVACY_NOTICE_APPROVED", "").strip().lower() == "true"
    )
    try:
        store_check_database_connection()
        return jsonify({
            "database": "reachable",
            "storage_enabled": enabled,
            "privacy_notice_version": os.getenv("ATENA_PRIVACY_NOTICE_VERSION", "pilot-draft-1").strip(),
        }), 200
    except StorageUnavailable as exc:
        return jsonify({
            "database": "unavailable",
            "storage_enabled": False,
            "reason": exc.reason,
        }), 503


# Longitudinal profile storage is opt-in and disabled by default. Hosted use
# requires a persistent PostgreSQL database and an operator-approved notice.
PROFILE_FIELDS = {"goal", "experience", "equipment", "sessions_per_week", "session_minutes", "available_days", "pistol_squat_capable"}
PROFILE_GOALS = {"strength", "hypertrophy", "general_fitness", "functional", "power", "endurance", "mobility"}
PROFILE_EXPERIENCE = {"beginner", "intermediate", "advanced"}
PROFILE_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
VALID_EQUIPMENT = {item for exercise in load_catalogue() for item in (exercise["equipment"] + exercise["equipment_any"])}


def _storage_error(exc):
    logger.warning("ATENA profile storage unavailable: %s", type(exc).__name__)
    return jsonify({"error": "Shranjevanje profila trenutno ni aktivirano."}), 503


def _validate_profile(value):
    if not isinstance(value, dict) or set(value) - PROFILE_FIELDS:
        raise ValueError("Profil vsebuje neveljavna ali nepodprta polja.")
    goal = value.get("goal")
    experience = value.get("experience")
    equipment = value.get("equipment")
    sessions = value.get("sessions_per_week")
    minutes = value.get("session_minutes")
    if goal not in PROFILE_GOALS:
        raise ValueError("Cilj vadbe ni veljaven.")
    if experience not in PROFILE_EXPERIENCE:
        raise ValueError("Raven izkušenj ni veljavna.")
    if not isinstance(equipment, list) or len(equipment) > 25 or any(
        not isinstance(item, str) or not item.strip() or len(item) > 40 for item in equipment
    ) or len(set(equipment)) != len(equipment) or not set(equipment).issubset(VALID_EQUIPMENT):
        raise ValueError("Seznam opreme vsebuje podvojeno ali nepodprto opremo.")
    if not isinstance(sessions, int) or isinstance(sessions, bool) or not 2 <= sessions <= 4:
        raise ValueError("Za zdaj so podprti 2, 3 ali 4 treningi na teden.")
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 25 <= minutes <= 120:
        raise ValueError("Trajanje treninga mora biti med 25 in 120 minutami.")
    days = value.get("available_days", [])
    if not isinstance(days, list) or len(days) > 7 or any(day not in PROFILE_DAYS for day in days):
        raise ValueError("Razpoložljivi dnevi niso veljavni.")
    pistol_squat_capable = value.get("pistol_squat_capable", False)
    if not isinstance(pistol_squat_capable, bool):
        raise ValueError("pistol_squat_capable mora biti true ali false.")
    return {
        "goal": goal, "experience": experience, "equipment": equipment,
        "sessions_per_week": sessions, "session_minutes": minutes,
        "available_days": days, "pistol_squat_capable": pistol_squat_capable,
    }


def _profile_token():
    return request.headers.get("X-Profile-Token", "").strip()


def _profile_auth_error():
    return jsonify({"error": "Profil ne obstaja ali dostopni ključ ni pravilen."}), 404


@coach_bp.route("/coach/profile", methods=["POST", "OPTIONS"])
def create_coach_profile():
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Pričakovan je JSON objekt."}), 400
    if payload.get("privacy_notice_acknowledged") is not True:
        return jsonify({"error": "Pred shranjevanjem je treba potrditi seznanitev z obvestilom o zasebnosti."}), 400
    notice_version = os.getenv("ATENA_PRIVACY_NOTICE_VERSION", "pilot-draft-1").strip()
    if payload.get("privacy_notice_version") != notice_version:
        return jsonify({"error": "Različica obvestila o zasebnosti ni veljavna."}), 400
    health_consent = payload.get("health_data_consent", False)
    if not isinstance(health_consent, bool):
        return jsonify({"error": "Privolitev za zdravstvene podatke mora biti true ali false."}), 400
    try:
        profile = _validate_profile(payload.get("profile"))
        profile_id = str(uuid.uuid4())
        access_token = secrets.token_urlsafe(32)
        saved = store_create_profile(profile_id, access_token, profile, health_consent, notice_version)
        # The access token is returned once. Only its SHA-256 hash is stored.
        return jsonify({"profile": saved, "profile_access_token": access_token,
                        "token_notice": "Ključ shrani varno; pozneje ga ni mogoče ponovno prikazati."}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except StorageUnavailable as exc:
        return _storage_error(exc)


@coach_bp.route("/coach/profile/<profile_id>", methods=["GET", "PUT", "DELETE", "OPTIONS"])
def manage_coach_profile(profile_id):
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    if request.method == "GET":
        try:
            return jsonify({"profile": store_get_profile(profile_id, token)}), 200
        except ProfileNotFound:
            return _profile_auth_error()
        except StorageUnavailable as exc:
            return _storage_error(exc)
    if request.method == "PUT":
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Pričakovan je JSON objekt."}), 400
        try:
            profile = _validate_profile(payload.get("profile"))
            updated = store_update_profile(profile_id, token, profile)
            return jsonify({"profile": updated}), 200
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except ProfileNotFound:
            return _profile_auth_error()
        except StorageUnavailable as exc:
            return _storage_error(exc)
    try:
        store_delete_profile(profile_id, token)
        return jsonify({"deleted": True}), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)


@coach_bp.route("/coach/profile/<profile_id>/sessions", methods=["GET", "POST", "OPTIONS"])
def coach_training_sessions(profile_id):
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    if request.method == "GET":
        try:
            return jsonify({"sessions": store_list_sessions(profile_id, token, limit=50)}), 200
        except ProfileNotFound:
            return _profile_auth_error()
        except StorageUnavailable as exc:
            return _storage_error(exc)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Pričakovan je JSON objekt."}), 400
    allowed = {"session_date", "duration_minutes", "difficulty", "completed", "exercises", "discomfort_reported", "recovery"}
    if set(payload) - allowed:
        return jsonify({"error": "Vadbeni zapis vsebuje nepodprta polja; prosto besedilo ni dovoljeno."}), 400
    session_date = payload.get("session_date")
    try:
        date.fromisoformat(session_date)
    except (TypeError, ValueError):
        return jsonify({"error": "Datum mora biti v obliki YYYY-MM-DD."}), 400
    duration = payload.get("duration_minutes")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 1 <= duration <= 240:
        return jsonify({"error": "Trajanje mora biti med 1 in 240 minutami."}), 400
    difficulty = payload.get("difficulty")
    if difficulty not in {"easy", "moderate", "hard"}:
        return jsonify({"error": "Težavnost mora biti easy, moderate ali hard."}), 400
    recovery = payload.get("recovery", "normal")
    if recovery not in {"good", "normal", "poor"}:
        return jsonify({"error": "Regeneracija mora biti good, normal ali poor."}), 400
    if not isinstance(payload.get("completed"), bool):
        return jsonify({"error": "Polje completed mora biti true ali false."}), 400
    exercises = payload.get("exercises")
    if not isinstance(exercises, list) or len(exercises) > 20:
        return jsonify({"error": "Vadbeni zapis lahko vsebuje največ 20 vaj."}), 400
    clean_exercises = []
    for item in exercises:
        if not isinstance(item, dict) or set(item) - {"exercise_id", "sets_completed", "reps_completed", "work_seconds_completed", "load_kg", "rir"}:
            return jsonify({"error": "Zapis vaje vsebuje neveljavna polja."}), 400
        exercise_id = item.get("exercise_id")
        if not isinstance(exercise_id, str) or get_exercise(exercise_id) is None:
            return jsonify({"error": "Vaja ni v preverjenem katalogu ATENA."}), 400
        sets = item.get("sets_completed")
        reps = item.get("reps_completed")
        work_seconds = item.get("work_seconds_completed")
        if not isinstance(sets, int) or isinstance(sets, bool) or not 1 <= sets <= 20:
            return jsonify({"error": "Število izvedenih serij ni veljavno."}), 400
        if reps is not None and (not isinstance(reps, int) or isinstance(reps, bool) or not 1 <= reps <= 100):
            return jsonify({"error": "Število ponovitev ni veljavno."}), 400
        if work_seconds is not None and (not isinstance(work_seconds, int) or isinstance(work_seconds, bool) or not 1 <= work_seconds <= 3600):
            return jsonify({"error": "Trajanje delovne serije ni veljavno."}), 400
        if reps is None and work_seconds is None:
            return jsonify({"error": "Za vajo je treba navesti ponovitve ali trajanje delovne serije."}), 400
        entry = {"exercise_id": exercise_id, "sets_completed": sets}
        if reps is not None:
            entry["reps_completed"] = reps
        if work_seconds is not None:
            entry["work_seconds_completed"] = work_seconds
        load = item.get("load_kg")
        if load is not None:
            if not isinstance(load, (int, float)) or isinstance(load, bool) or not 0 <= load <= 1000:
                return jsonify({"error": "Obremenitev ni veljavna."}), 400
            entry["load_kg"] = float(load)
        rir = item.get("rir")
        if rir is not None:
            if not isinstance(rir, int) or isinstance(rir, bool) or not 0 <= rir <= 10:
                return jsonify({"error": "RIR mora biti med 0 in 10."}), 400
            entry["rir"] = rir
        clean_exercises.append(entry)

    discomfort = payload.get("discomfort_reported")
    if discomfort is not None and not isinstance(discomfort, bool):
        return jsonify({"error": "discomfort_reported mora biti true ali false."}), 400
    session = {
        "duration_minutes": duration, "difficulty": difficulty,
        "recovery": recovery, "completed": payload["completed"], "exercises": clean_exercises,
    }
    try:
        profile = store_get_profile(profile_id, token)
        if discomfort is not None:
            if not profile["health_data_consent"]:
                return jsonify({"error": "Za shranjevanje podatka o nelagodju je potrebna ločena privolitev za zdravstvene podatke."}), 403
            session["discomfort_reported"] = discomfort
        saved = store_add_session(profile_id, token, str(uuid.uuid4()), session_date, session)
        return jsonify({"session": saved}), 201
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)


@coach_bp.route("/coach/profile/<profile_id>/consent", methods=["POST", "OPTIONS"])
def update_coach_health_consent(profile_id):
    if request.method == "OPTIONS":
        return ("", 204)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"health_data_consent"}:
        return jsonify({"error": "Pošlji samo polje health_data_consent."}), 400
    consent = payload.get("health_data_consent")
    if not isinstance(consent, bool):
        return jsonify({"error": "Privolitev mora biti true ali false."}), 400
    try:
        profile = store_set_health_data_consent(profile_id, _profile_token(), consent)
        return jsonify({
            "profile": profile,
            "notice": (
                "Privolitev za zdravstvene podatke je umaknjena; shranjeni podatki o nelagodju so izbrisani."
                if not consent else "Privolitev za zdravstvene podatke je zabeležena."
            ),
        }), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)



@coach_bp.route("/coach/profile/<profile_id>/progress", methods=["GET", "OPTIONS"])
def coach_training_progress(profile_id):
    """Return descriptive training trends; never prescribe automatic load increases."""
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=50)
        return jsonify({
            "progress": summarize_progress(profile, sessions),
            "source": "recorded_training_history",
            "automatic_load_changes": False,
        }), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)


@coach_bp.route("/coach/profile/<profile_id>/export", methods=["GET", "OPTIONS"])
def export_coach_profile(profile_id):
    """Export the authenticated user's profile and complete structured training history."""
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=5000)
        response = jsonify({
            "export_version": "1.0",
            "profile": profile,
            "sessions": sessions,
            "exported_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(timespec="seconds"),
        })
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Content-Disposition"] = (
            'attachment; filename="atena-profile-export.json"'
        )
        return response, 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)



@coach_bp.route("/coach/profile/<profile_id>/program", methods=["POST", "OPTIONS"])
def coach_profile_program(profile_id):
    """Build the next programme from the saved profile and most recent logged feedback."""
    if request.method == "OPTIONS":
        return ("", 204)
    if not storage_enabled():
        return _storage_error(StorageUnavailable("Profile storage is not enabled or approved."))
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"no_current_pain_or_restrictions"}:
        return jsonify({"error": "Potrjena mora biti samo trenutna varnostna izjava."}), 400
    if payload.get("no_current_pain_or_restrictions") is not True:
        return jsonify({
            "blocked": True,
            "message": "Programa nisem ustvaril. Ob trenutni bolečini, poškodbi ali zdravstveni omejitvi je potrebna individualna presoja ustreznega strokovnjaka.",
        }), 409
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=1)
        feedback = None
        if sessions:
            last = sessions[0].get("session", {})
            if last.get("discomfort_reported") is True:
                feedback = {
                    "difficulty": "right",
                    "completed": bool(last.get("completed", True)),
                    "discomfort": "yes",
                }
            else:
                difficulty = {"easy": "easy", "moderate": "right", "hard": "hard"}.get(
                    last.get("difficulty"), "right"
                )
                feedback = {
                    "difficulty": difficulty,
                    "completed": bool(last.get("completed", True)),
                    "discomfort": "no",
                    "recovery": last.get("recovery", "normal"),
                    "movement_control": "none",
                }
        result = generate_program(profile["profile"], feedback=feedback)
        return jsonify({
            "program": result,
            "profile": profile["profile"],
            "source": "saved_profile_and_recent_training_feedback",
            "pilot": True,
        }), 200
    except ProgramSafetyBlock as exc:
        return jsonify({"blocked": True, "message": str(exc)}), 409
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)


@coach_bp.route("/coach/profile/<profile_id>/adaptation", methods=["GET", "OPTIONS"])
def coach_training_adaptation(profile_id):
    """Return conservative next-step guidance from recent logged feedback."""
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=3)
        return jsonify({
            "adaptation": assess_next_step(sessions),
            "source": "recent_recorded_training_feedback",
            "automatic_program_changes": False,
        }), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)
