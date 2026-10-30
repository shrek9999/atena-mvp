"""Conservative, server-side conversational coach pilot for ATENA."""
import json
import os
import hmac
import logging
import urllib.error
import urllib.request
from flask import Blueprint, jsonify, request
from training.program import ProgramValidationError, generate_program

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
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Pilot-Token"
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
Ask one concise, high-value question at a time, starting with the most important missing information. Do not overwhelm the user with a long intake form. If the request is simple and low risk, you may give a clearly labelled general example while explaining that it is not yet individualized, and ask the most important follow-up question. If safety-relevant information is missing, ask before recommending demanding exercise.

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
    try:
        result = generate_program(payload)
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, ValueError):
        logger.exception("ATENA catalogue/program generation failed")
        return jsonify({"error": "Programa trenutno ni mogoče sestaviti iz kataloga."}), 500
    return jsonify({"program": result, "source": "curated_exercise_catalogue", "pilot": True}), 200
