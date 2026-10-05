from flask import Flask, request, jsonify

app = Flask(__name__)

def decide(data):
    goal = data.get("goal", {})
    response = data.get("response", {})
    state = data.get("state", {})
    question = data.get("question", "")

    performance = response.get("performance")
    rpe = response.get("rpe")
    recovery = response.get("recovery")
    symptoms = response.get("symptoms")

    # Minimal ATENA v0.1 decision logic
    if performance == "declining" and not recovery and not symptoms:
        return {
            "assessment": "Performance is declining, but the available context is insufficient to identify the cause.",
            "decision": "collect_data",
            "action": "Collect the highest-value missing recovery and training-load information before changing the program.",
            "monitor": ["performance", "RPE", "sleep", "wellness", "recent training load"],
            "decision_rule": "If performance continues to decline after the missing context is clarified, reassess fatigue cost and program structure.",
            "uncertainty": "High",
            "confidence": 0.82
        }

    if recovery in ["poor", "declining"] or (rpe is not None and isinstance(rpe, (int, float)) and rpe >= 9):
        return {
            "assessment": "The current response suggests increased fatigue cost relative to the desired training stimulus.",
            "decision": "reduce_fatigue_cost",
            "action": "Reduce the smallest appropriate training variable while preserving the primary goal stimulus.",
            "monitor": ["performance", "RPE", "sleep", "wellness", "symptoms"],
            "decision_rule": "If recovery improves and performance stabilizes, gradually restore the stimulus.",
            "uncertainty": "Moderate",
            "confidence": 0.90
        }

    return {
        "assessment": "The current system appears sufficiently stable from the supplied information.",
        "decision": "maintain_or_progress",
        "action": "Maintain the current structure and use a small progression only if the positive trend continues.",
        "monitor": ["performance", "RPE", "recovery"],
        "decision_rule": "If performance declines together with rising fatigue or worsening recovery, reassess before progressing.",
        "uncertainty": "Low to moderate",
        "confidence": 0.88
    }

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "ATENA", "version": "0.1"})

@app.post("/decision")
def decision():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400
    return jsonify(decide(data))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
