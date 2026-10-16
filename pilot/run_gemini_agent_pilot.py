import json, os, random, time
from pathlib import Path
import requests

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = os.getenv("MODEL", "gemini-3.5-flash-lite")
ATENA_URL = os.getenv("ATENA_URL", "https://atena-mvp.onrender.com/decision")
OUT = Path(os.getenv("OUT", "pilot/results_gemini_raw.json"))
MAX_CASES = 5
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

SYSTEM = """You are an AI fitness and human-performance decision agent.
Decide the next appropriate action from the supplied case. Prioritize the stated goal,
current state, constraints, response and history. Do not diagnose medical conditions.
Give a concise final decision with rationale and action. If information is insufficient,
explicitly say what information is needed before changing the plan."""

TOOL = {
    "functionDeclarations": [{
        "name": "atena_decide",
        "description": "ATENA specialist decision-support layer. Use for meaningful uncertainty or trade-offs, conflicting performance/recovery signals, symptoms affecting training, competing goals, stimulus-versus-recovery cost, limited time/recovery, or longitudinal adaptation. Do not use for simple factual questions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal": {"type": "OBJECT"},
                "person": {"type": "OBJECT"},
                "constraints": {"type": "OBJECT"},
                "state": {"type": "OBJECT"},
                "response": {"type": "OBJECT"},
                "question": {"type": "STRING"},
                "history": {"type": "OBJECT"}
            },
            "required": ["goal", "person", "constraints", "state", "response", "question", "history"]
        }
    }]
}

def generate(contents, use_tool=False, system=None):
    body = {
        "systemInstruction": {"parts": [{"text": system or SYSTEM}]},
        "contents": contents,
        "generationConfig": {"temperature": 0, "maxOutputTokens": 512}
    }
    if use_tool:
        body["tools"] = [TOOL]
        body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
    response = requests.post(
        f"{API_BASE}/{MODEL}:generateContent",
        headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
        json=body, timeout=90
    )
    if response.status_code == 429:
        raise RuntimeError(f"Gemini rate/quota limit reached (HTTP 429); stopping without retries. {response.text[:500]}")
    if response.status_code in (401, 403):
        raise RuntimeError(f"Gemini authentication/permission error (HTTP {response.status_code}); check the secret and project tier. No retries.")
    # Retry only transient server errors. Never retry quota, auth, or client errors.
    # Two short retries are bounded and help with temporary provider-side 503s.
    for attempt in range(2):
        if response.status_code not in (500, 502, 503, 504):
            break
        delay = 2 ** (attempt + 1)
        print(f"Gemini transient HTTP {response.status_code}; retrying once in {delay}s (attempt {attempt + 1}/2).", flush=True)
        time.sleep(delay)
        response = requests.post(
            f"{API_BASE}/{MODEL}:generateContent",
            headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
            json=body, timeout=90
        )
        if response.status_code == 429:
            raise RuntimeError(f"Gemini rate/quota limit reached (HTTP 429); stopping without retries. {response.text[:500]}")
        if response.status_code in (401, 403):
            raise RuntimeError(f"Gemini authentication/permission error (HTTP {response.status_code}); check the secret and project tier. No retries.")
    response.raise_for_status()
    return response.json()

def text_from_response(response):
    parts = response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()

def usage(response):
    meta = response.get("usageMetadata", {})
    return {
        "input_tokens": meta.get("promptTokenCount", 0),
        "output_tokens": meta.get("candidatesTokenCount", 0),
        "total_tokens": meta.get("totalTokenCount", 0)
    }

def add_usage(total, response):
    for key, value in usage(response).items():
        total[key] += value or 0

def call_atena(args):
    response = requests.post(ATENA_URL, json=args, timeout=30)
    response.raise_for_status()
    return response.json()

def run_agent(case, with_atena):
    user_text = json.dumps(case["input"], ensure_ascii=False)
    history = [{"role": "user", "parts": [{"text": user_text}]}]
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    first = generate(history, use_tool=with_atena,
        system=SYSTEM + (" ATENA is available as a specialist tool. Use it only when trigger conditions are met; otherwise decide yourself." if with_atena else ""))
    add_usage(totals, first)
    if not with_atena:
        return {"final": text_from_response(first), "usage": totals}

    for _ in range(3):
        candidate = first.get("candidates", [{}])[0]
        model_content = candidate.get("content", {})
        parts = model_content.get("parts", [])
        calls = [p["functionCall"] for p in parts if "functionCall" in p]
        if not calls:
            return {"final": text_from_response(first), "usage": totals}
        history.append(model_content)
        response_parts = []
        for call in calls:
            name = call.get("name")
            if name != "atena_decide":
                raise RuntimeError(f"Unexpected function call: {name}")
            result = call_atena(call.get("args", {}))
            response_parts.append({"functionResponse": {"name": name, "response": {"result": result}}})
        history.append({"role": "user", "parts": response_parts})
        first = generate(history, use_tool=True,
            system=SYSTEM + " ATENA is available as a specialist tool. Use it only when trigger conditions are met; otherwise decide yourself.")
        add_usage(totals, first)
    raise RuntimeError("Agent exceeded the 3-round ATENA tool-call limit")

def save_results(status, results, requested_limit, error=None):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": "Google Gemini API",
        "model": MODEL,
        "status": status,
        "requested_limit": requested_limit,
        "completed_cases": len(results),
        "token_usage": {
            arm: {key: sum(item[arm].get("usage", {}).get(key, 0) for item in results)
                  for key in ("input_tokens", "output_tokens", "total_tokens")}
            for arm in ("agent_alone", "agent_plus_atena")
        },
        "cases": results
    }
    if error:
        payload["error"] = error[:1000]
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

def main():
    try:
        requested_limit = int(os.getenv("PILOT_LIMIT", "1"))
    except ValueError as exc:
        raise SystemExit("PILOT_LIMIT must be an integer from 1 to 5") from exc
    if not 1 <= requested_limit <= MAX_CASES:
        raise SystemExit("PILOT_LIMIT must be between 1 and 5")

    data = json.loads(Path("pilot/cases_v1.json").read_text())
    cases = data["cases"][:]
    random.Random(20261008).shuffle(cases)
    cases = cases[:requested_limit]
    results = []
    save_results("running", results, requested_limit)
    try:
        for i, case in enumerate(cases, 1):
            print(f"[{i}/{len(cases)}] {case['id']}", flush=True)
            alone = run_agent(case, False)
            plus = run_agent(case, True)
            results.append({"case_id": case["id"], "agent_alone": alone, "agent_plus_atena": plus})
            save_results("running", results, requested_limit)
            time.sleep(1.0)
    except Exception as exc:
        save_results("partial_failure", results, requested_limit, repr(exc))
        raise
    save_results("complete", results, requested_limit)
    print(f"Wrote {OUT}; completed {len(results)}/{requested_limit} cases")

if __name__ == "__main__":
    main()
