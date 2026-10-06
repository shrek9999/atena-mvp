from flask import Flask, request, jsonify

app = Flask(__name__)

def decide(data):
    goal = data.get("goal", {})
    response = data.get("response", {})
    state = data.get("state", {})
    constraints = data.get("constraints", {})
    question = data.get("question", "").lower()
    history = data.get("history", {})

    primary_goal = str(goal.get("primary", "")).lower()
    secondary_goal = str(goal.get("secondary", "")).lower()
    recovery_capacity = str(constraints.get("recovery_capacity", "")).lower()

    performance = response.get("performance")
    rpe = response.get("rpe")
    recovery = response.get("recovery")
    symptoms = response.get("symptoms")

    # Read canonical v0.1 state fields as well as compact response fields.
    performance_change = state.get("performance_change")
    rpe_change = state.get("rpe_change")
    state_symptoms = state.get("symptoms")
    fatigue = str(state.get("fatigue", "")).lower()

    if performance is None and isinstance(performance_change, str):
        performance = "declining" if performance_change.strip().startswith("-") else performance
    if rpe is None and isinstance(rpe_change, str):
        rpe = 10 if rpe_change.strip().startswith("+") else rpe
    if symptoms is None and state_symptoms:
        symptoms = state_symptoms

    # 1. High uncertainty: do not guess when performance declines without a clear cause.
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

    # 2. Primary-goal protection: do not add a hard secondary stimulus when recovery is limited.
    adding_hard_conditioning = any(term in question for term in ["add", "third", "extra"]) and any(term in question for term in ["hard conditioning", "hard conditioning session", "conditioning session"])
    if primary_goal == "strength" and secondary_goal == "aerobic_fitness" and adding_hard_conditioning:
        return {
            "assessment": "Strength is the primary goal and the proposed third hard conditioning session adds interference and recovery cost without evidence that the current structure is failing.",
            "decision": "maintain",
            "action": "Do not add a third hard conditioning session. Preserve the current strength structure and improve aerobic stimulus within the existing recovery budget if needed.",
            "monitor": ["strength performance", "RPE", "recovery", "aerobic response"],
            "decision_rule": "If aerobic fitness remains insufficient while strength and recovery remain stable, modify an existing aerobic session before adding another hard session.",
            "uncertainty": "Low to moderate",
            "confidence": 0.93
        }

    # 3. Longitudinal response: a positive response to a previous modification supports progression.
    previous_result = str(response.get("result", "")).lower()
    previous_response = str(history.get("previous_response", history.get("previous_result", ""))).lower()
    positive_response = any(term in (previous_result + " " + previous_response) for term in [
        "improved", "positive", "better", "decreased rpe", "performance improved"
    ])
    previous_modification = response.get("previous_modification") or history.get("previous_decision")
    if positive_response and previous_modification and not symptoms:
        return {
            "assessment": "The previous modification produced a positive response, with stable recovery and no current symptoms; the next step can be a small progression while monitoring the response.",
            "decision": "progress",
            "action": "Gradually restore or progress the previously reduced training stimulus in a small step, then observe the response.",
            "monitor": ["performance", "RPE", "recovery", "symptoms", "next-day response"],
            "decision_rule": "If performance remains stable or improves and recovery remains stable, continue gradual progression; if symptoms or fatigue increase, reassess and modify.",
            "uncertainty": "Low to moderate",
            "confidence": 0.92
        }

    # 4. Symptoms: modify the smallest relevant dose before removing a useful exercise.
    if symptoms:
        return {
            "assessment": "A symptom is present during a specific training stimulus, so the first step is to modify the dose rather than automatically remove the exercise or infer a diagnosis.",
            "decision": "modify",
            "action": "Reduce the smallest relevant variable (for example ROM, load, volume or variation) while preserving the desired strength stimulus, then observe the response.",
            "monitor": ["symptom intensity", "symptom during exercise", "response after training", "next-day response", "performance"],
            "decision_rule": "If symptoms improve with the modification, gradually restore the stimulus; if symptoms worsen, persist or become unusual/progressive, reassess and consider referral.",
            "uncertainty": "Moderate",
            "confidence": 0.91
        }

    if recovery in ["poor", "declining"] or (rpe is not None and isinstance(rpe, (int, float)) and rpe >= 9) or fatigue == "high":
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
