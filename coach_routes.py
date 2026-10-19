"""Conservative, server-side conversational coach pilot for ATENA."""
import json
import os
import hmac
import logging
import urllib.error
import urllib.request
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
coach_bp = Blueprint("coach", __name__)
ALLOWED_ORIGINS = {"https://gregajenko.si", "https://www.gregajenko.si"}

@coach_bp.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Pilot-Token"
        response.headers["Access-Control-Max-Age"] = "600"
    return response

MAX_MESSAGE_CHARS = 1800
MAX_MESSAGES = 12

SYSTEM_PROMPT = """You are Grega Jenko's pilot AI fitness coach, speaking Slovenian unless the user writes in another language.
Approach: functional fitness, strength, mobility, stability, capacity and gradual load management. Help users understand their goal, current ability, constraints, and response to exercise. Ask one concise follow-up question at a time when essential information is missing. Give practical, conservative, general exercise guidance, explain the reasoning briefly, and encourage gradual, reversible changes.
Safety: you are not a doctor or physiotherapist and must not diagnose injuries, prescribe treatment, or promise pain relief. Do not tell users to train through worsening pain. If symptoms are severe, sudden, unexplained or worsening, recommend assessment by an appropriate healthcare professional. For chest pain, fainting, severe breathing difficulty, new weakness/numbness, loss of bladder/bowel control with back pain, or other possible emergency symptoms, advise urgent local medical care. Do not ask for full names, exact addresses, or other unnecessary personal data. If a user shares health details, use only what is needed to answer. If unsure, say so. Never fabricate credentials, measurements, research or outcomes. Keep answers clear and warm, usually under 180 words. This is a pilot, not individualized medical care."""

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
