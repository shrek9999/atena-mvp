from flask import Flask, request, jsonify
import re

app = Flask(__name__)


def norm(value):
    if value is None:
        return ""
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def text_blob(*values):
    return " ".join(norm(v) for v in values if v is not None)


def first_value(*values):
    for v in values:
        if v is not None and v != "":
            return v
    return None


def parse_delta(value):
    """Return a numeric signed change when one is explicitly present."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    # Only treat a number as a signed delta when it has an explicit sign.
    # Otherwise phrases such as "declined 2 percent" must be classified by language.
    m = re.search(r"([+-]\d+(?:\.\d+)?)\s*%?", value.replace(",", "."))
    if m:
        return float(m.group(1))
    if re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", value.replace(",", ".")):
        return float(value.replace(",", ".").strip())
    return None


def classify_performance(value):
    s = norm(value)
    n = parse_delta(value)
    if n is not None:
        if n > 0:
            return "improving"
        if n < 0:
            return "declining"
        return "stable"
    if any(x in s for x in ["declined", "declining", "decreased", "worse", "down", "lost"]):
        return "declining"
    if any(x in s for x in ["improved", "improving", "increased", "better", "up", "gain"]):
        return "improving"
    if "stable" in s or "unchanged" in s or "maintain" in s:
        return "stable"
    return "unknown"


def classify_rpe(value):
    s = norm(value)
    n = parse_delta(value)
    if n is not None:
        if n > 0:
            return "increased"
        if n < 0:
            return "decreased"
        return "stable"
    if any(x in s for x in ["increased", "higher", "rising", "worse", "up"]):
        return "increased"
    if any(x in s for x in ["lower", "decreased", "down", "better"]):
        return "decreased"
    if "stable" in s or "normal" in s or "unchanged" in s:
        return "stable"
    return "unknown"


def classify_recovery(value):
    s = norm(value)
    if any(x in s for x in ["moderately_worse", "much_worse", "worse", "declining", "poor", "impaired"]):
        return "worsening"
    if any(x in s for x in ["slightly_worse", "slightly_declined"]):
        return "worsening"
    if any(x in s for x in ["good", "normal", "stable", "well_recovered"]):
        return "stable"
    if any(x in s for x in ["improved", "better"]):
        return "improving"
    return "unknown"


def has_symptoms(value):
    s = norm(value)
    return bool(s) and s not in {"none", "no", "absent", "nil", "false", "0"}


def goal_priority(goal):
    primary = norm(goal.get("primary"))
    secondary = norm(goal.get("secondary"))
    maintenance = goal.get("maintenance", [])
    if isinstance(maintenance, str):
        maintenance = [maintenance]
    return [
        g for g in [primary, secondary] + [norm(x) for x in maintenance]
        if g
    ]


def choose_budget_target(goal, state):
    """Return the lowest-priority goal whose stimulus can be reduced first."""
    priorities = goal_priority(goal)
    if len(priorities) >= 3:
        return priorities[-1]
    if len(priorities) == 2:
        return priorities[-1]
    return "auxiliary_volume"


def signal_summary(primary_perf_class, secondary_declining, rpe_class, recovery_class, fatigue, sleep, wellness, symptom_present):
    signals = []
    if primary_perf_class == "improving": signals.append("primary_performance_improving")
    if primary_perf_class == "declining": signals.append("primary_performance_declining")
    if secondary_declining: signals.append("secondary_performance_declining")
    if rpe_class == "increased": signals.append("rpe_increased")
    if recovery_class == "worsening": signals.append("recovery_worsening")
    if norm(fatigue) in {"high", "increased", "rising"}: signals.append("fatigue_increased")
    if norm(sleep) in {"poor", "worse", "declining", "reduced"}: signals.append("sleep_worsening")
    if norm(wellness) in {"poor", "worse", "declining", "reduced", "low"}: signals.append("wellness_worsening")
    if symptom_present: signals.append("symptom_present")
    return signals


def build_decision(decision, assessment, action, monitor, rule, uncertainty, confidence, reasons=None, priority=None):
    """Standard ATENA decision object. Reasons make the decision auditable."""
    return {
        "assessment": assessment,
        "decision": decision,
        "action": action,
        "monitor": monitor,
        "decision_rule": rule,
        "uncertainty": uncertainty,
        "confidence": confidence,
        "reason_codes": reasons or [],
        "priority": priority or {}
    }


def decide(data):
    goal = data.get("goal") or {}
    response = data.get("response") or {}
    state = data.get("state") or {}
    constraints = data.get("constraints") or {}
    history = data.get("history") or {}
    question = norm(data.get("question"))

    primary_goal = norm(goal.get("primary"))
    secondary_goal = norm(goal.get("secondary"))
    priorities = goal_priority(goal)

    # Accept both current-state and longitudinal response schemas.
    strength_state = first_value(state.get("strength"), state.get("performance"))
    strength_response = first_value(
        response.get("performance_response"),
        response.get("performance"),
        response.get("strength_response"),
    )
    performance = first_value(
        state.get("performance"),
        state.get("performance_change"),
        state.get("strength"),
        response.get("performance_response"),
        strength_response,
    )

    rpe = first_value(
        state.get("rpe"),
        state.get("rpe_change"),
        response.get("rpe_response"),
        response.get("rpe"),
    )
    recovery = first_value(
        state.get("recovery"),
        response.get("recovery_response"),
        response.get("recovery"),
    )
    symptoms = first_value(state.get("symptoms"), response.get("symptoms"))
    fatigue = first_value(state.get("fatigue"), response.get("fatigue"))
    wellness = first_value(state.get("wellness"), response.get("wellness"))
    sleep = first_value(state.get("sleep"), response.get("sleep"))

    perf_class = classify_performance(performance)
    rpe_class = classify_rpe(rpe)
    recovery_class = classify_recovery(recovery)
    symptom_present = has_symptoms(symptoms)

    # Explicit numeric RPE remains supported.
    numeric_rpe = rpe if isinstance(rpe, (int, float)) else None

    available_time = norm(constraints.get("available_time"))
    time_reduction = text_blob(
        constraints.get("time_change"),
        response.get("time_constraint_response"),
        constraints.get("available_time")
    )
    time_limited = (
        "limited" in available_time
        or "reduced" in time_reduction
        or "-20" in time_reduction
        or "decreased" in time_reduction
        or "lower" in time_reduction
    )

    # 1. Symptoms always take precedence over generic progression.
    if symptom_present:
        return {
            "assessment": "A symptom is present during the current training context, so the smallest relevant dose should be modified before removing a useful stimulus or inferring a diagnosis.",
            "decision": "modify",
            "action": "Reduce the smallest relevant variable (for example ROM, load, volume or variation) while preserving the desired stimulus, then observe the response.",
            "monitor": ["symptom intensity", "symptom during exercise", "response after training", "next-day response", "performance"],
            "decision_rule": "If symptoms improve with the modification, gradually restore the stimulus; if they worsen, persist or become unusual/progressive, reassess and consider referral.",
            "uncertainty": "Moderate",
            "confidence": 0.91
        }

    # 2. High uncertainty: declining performance with insufficient recovery context.
    recovery_missing = recovery_class == "unknown" and not fatigue and not sleep and not wellness
    if perf_class == "declining" and recovery_missing:
        return {
            "assessment": "Performance is declining, but the available context is insufficient to identify the cause.",
            "decision": "collect_data",
            "action": "Collect the highest-value missing recovery and recent training-load information before changing the program.",
            "monitor": ["performance", "RPE", "sleep", "wellness", "recent training load"],
            "decision_rule": "If performance continues to decline after the missing context is clarified, reassess fatigue cost and program structure.",
            "uncertainty": "High",
            "confidence": 0.82
        }

    # 3. Explicit conflict: do not add a hard secondary conditioning session
    # when strength is primary and recovery budget is limited.
    adding_hard_conditioning = (
        any(term in question for term in [
            "add", "third", "extra", "dodam", "dodati", "tretjo", "tretji", "dodatno"
        ])
        and any(term in question for term in [
            "hard_conditioning", "conditioning_session", "conditioning"
        ])
    )
    if primary_goal == "strength" and secondary_goal == "aerobic_fitness" and adding_hard_conditioning:
        return {
            "assessment": "Strength is the primary goal and the proposed hard conditioning adds recovery/interference cost without evidence that the current structure is failing.",
            "decision": "maintain",
            "action": "Do not add the extra hard conditioning session. Preserve the current strength structure and modify an existing aerobic session only if aerobic fitness actually requires it.",
            "monitor": ["strength performance", "RPE", "recovery", "aerobic response"],
            "decision_rule": "If aerobic fitness remains insufficient while strength and recovery remain stable, modify an existing aerobic session before adding another hard session.",
            "uncertainty": "Low to moderate",
            "confidence": 0.93
        }

    # 4. Clear positive response.
    if (
        perf_class == "improving"
        and rpe_class == "decreased"
        and recovery_class in {"stable", "improving"}
        and not symptom_present
    ):
        return {
            "assessment": "Performance is improving with lower or stable training cost and adequate recovery; the current stimulus is producing a positive response.",
            "decision": "progress",
            "action": "Make a small progression of the current primary stimulus while keeping volume and recovery cost controlled.",
            "monitor": ["performance", "RPE", "recovery"],
            "decision_rule": "If performance remains stable or improves and recovery remains adequate, continue small progression; if fatigue or RPE rises, reassess.",
            "uncertainty": "Low",
            "confidence": 0.92
        }

    # Pre-compute primary/secondary goal states so later cost rules can
    # distinguish a secondary decline from a global fatigue signal.
    if primary_goal == "strength":
        primary_perf_class = classify_performance(
            first_value(state.get("strength"), response.get("strength_response"))
        )
    elif primary_goal:
        primary_perf_class = classify_performance(
            first_value(state.get(primary_goal), response.get(f"{primary_goal}_response"))
        )
    else:
        primary_perf_class = perf_class
    primary_declining = primary_perf_class == "declining"
    secondary_declining = False
    if secondary_goal == "aerobic_fitness":
        aerobic_value = first_value(
            state.get("aerobic_fitness"),
            state.get("aerobic_fitness_change"),
            response.get("aerobic_fitness_response")
        )
        secondary_declining = classify_performance(aerobic_value) == "declining"

    # 5. Performance stable but cost is rising.
    if (
        perf_class == "stable"
        and rpe_class == "increased"
        and recovery_class == "worsening"
        and not symptom_present
        and not secondary_declining
    ):
        target = "auxiliary volume"
        return {
            "assessment": "Performance is stable but RPE and recovery have worsened, indicating that training cost is rising without additional performance benefit.",
            "decision": "reduce",
            "action": f"Reduce the smallest appropriate training variable, preferably {target}, while preserving the primary {primary_goal or 'training'} stimulus.",
            "monitor": ["performance", "RPE", "recovery", "sleep"],
            "decision_rule": "If RPE decreases and recovery improves while performance remains stable or improves, maintain the reduced load before progressing again.",
            "uncertainty": "Low to moderate",
            "confidence": 0.91
        }

    # 6. Goal-priority engine: limited time/recovery requires allocation,
    # not generic maintenance.
    # Evaluate the primary goal independently. Do not let a declining
    # secondary goal make the whole performance signal look like primary decline.
    recovery_worse = recovery_class == "worsening" or norm(wellness) in {"slightly_lower", "lower", "worse"}

    # Explicit energy-availability constraint: when the primary goal declines
    # together with rising effort under an energy deficit/stress load, reduce
    # training cost before assuming the program needs more stimulus.
    energy_text = text_blob(
        constraints.get("energy_deficit"),
        constraints.get("calorie_deficit"),
        constraints.get("energy_balance"),
        state.get("energy_balance"),
        response.get("energy_balance"),
        constraints.get("work_stress"),
        state.get("stress"),
        response.get("stress")
    )
    explicit_energy_change = parse_delta(constraints.get("energy_deficit"))
    energy_deficit = (explicit_energy_change is not None and explicit_energy_change < 0) or any(term in energy_text for term in [
        "deficit", "energy_deficit", "calorie_deficit", "caloric_deficit",
        "negative_energy"
    ])
    stress_load = any(term in energy_text for term in [
        "stress", "high_stress", "work_stress", "increased_stress"
    ])
    if (
        primary_goal == "strength"
        and primary_declining
        and rpe_class == "increased"
        and (energy_deficit or stress_load)
    ):
        return {
            "assessment": "Strength is declining while perceived effort is rising in the presence of an energy/stress constraint; increasing training stimulus is not justified.",
            "decision": "reduce",
            "action": "Reduce strength training volume modestly while preserving intensity and movement exposure; reduce or remove lower-priority conditioning cost if needed, and address the energy/stress constraint before adding load.",
            "monitor": ["strength performance", "RPE", "energy availability", "stress", "recovery"],
            "decision_rule": "If strength stabilizes and RPE/recovery improve, hold the reduced volume before progressing; if decline continues, reassess both training and energy availability.",
            "uncertainty": "Low to moderate",
            "confidence": 0.92
        }

    # Goal-priority allocation under a reduced time budget.
    if time_limited and primary_goal:
        if primary_declining and (rpe_class == "increased" or recovery_worse):
            target = choose_budget_target(goal, state)
            return {
                "assessment": f"The primary goal ({primary_goal}) is declining while training cost/recovery is worsening under a reduced time budget. The primary stimulus should be protected and lower-priority work should absorb the constraint.",
                "decision": "reduce",
                "action": f"Protect the primary {primary_goal} stimulus. Reduce or simplify the {target} stimulus first, keeping enough exposure to maintain it where possible.",
                "monitor": [f"{primary_goal} performance", "RPE", "recovery", "available training time"],
                "decision_rule": f"If {primary_goal} stabilizes and recovery improves, maintain the reduced {target} load before progressing; if it continues to decline, reassess the primary stimulus.",
                "uncertainty": "Low to moderate",
                "confidence": 0.93
            }

        if secondary_declining and not primary_declining:
            return {
                "assessment": "The primary goal is stable while the secondary aerobic goal has declined under a time constraint; protect strength and reallocate only lower-priority training resources.",
                "decision": "modify",
                "action": "Keep the primary strength work unchanged. Make the aerobic stimulus more time-efficient, while keeping power at the minimum effective maintenance dose; do not add sessions.",
                "monitor": ["strength performance", "aerobic response", "RPE", "recovery", "available training time"],
                "decision_rule": "If aerobic fitness recovers without deterioration in strength or recovery, maintain the revised aerobic dose; if strength begins to decline, reallocate time back toward strength.",
                "uncertainty": "Low to moderate",
                "confidence": 0.90
            }

    # Secondary goal decline is actionable even without a time constraint.
    # Preserve the primary goal and modify the smallest secondary stimulus.
    if secondary_declining and not primary_declining:
        return {
            "assessment": "The primary goal is stable while the secondary aerobic goal has declined; the secondary stimulus needs adjustment without unnecessarily changing the primary strength work.",
            "decision": "modify",
            "action": "Keep the primary strength work unchanged. Adjust the aerobic stimulus modestly (volume, intensity or density) and observe the response before adding sessions.",
            "monitor": ["strength performance", "aerobic response", "RPE", "recovery"],
            "decision_rule": "If aerobic fitness improves while strength and recovery remain stable, keep the revised aerobic dose; if recovery or strength worsens, reduce the added aerobic cost.",
            "uncertainty": "Low to moderate",
            "confidence": 0.89
        }

    # A positive primary trend with adequate recovery does not require a
    # reduction merely because RPE rose; the higher effort may be an expected
    # cost of productive progression.
    if primary_declining is False and primary_perf_class == "improving" and recovery_class in {"stable", "improving"} and not symptom_present:
        return {
            "assessment": "The primary goal is improving with adequate recovery; the higher effort signal alone is not sufficient evidence to reduce the current stimulus.",
            "decision": "maintain_or_progress",
            "action": "Maintain the current progression and monitor whether the higher effort persists or is accompanied by declining performance or recovery.",
            "monitor": [f"{primary_goal or 'primary goal'} performance", "RPE", "recovery"],
            "decision_rule": "If performance remains positive and recovery stays adequate, continue; if performance declines or a second fatigue signal appears, reassess cost.",
            "uncertainty": "Low to moderate",
            "confidence": 0.89
        }

    # 7. Fatigue-cost convergence: one isolated signal is not enough to
    # justify a reduction. Require converging evidence, unless the constraint
    # itself is strong (handled above). This prevents RPE alone from driving
    # an unnecessary deload.
    fatigue_signals = 0
    if recovery_class == "worsening":
        fatigue_signals += 1
    if rpe_class == "increased" or (numeric_rpe is not None and numeric_rpe >= 9):
        fatigue_signals += 1
    if norm(fatigue) in {"high", "increased", "rising"}:
        fatigue_signals += 1
    if norm(sleep) in {"poor", "worse", "declining", "reduced"}:
        fatigue_signals += 1
    if norm(wellness) in {"poor", "worse", "declining", "reduced", "low"}:
        fatigue_signals += 1

    if fatigue_signals >= 2:
        return {
            "assessment": "Multiple converging signals indicate that training cost is rising relative to the current response.",
            "decision": "reduce",
            "action": f"Reduce the smallest appropriate training variable while preserving the primary {primary_goal or 'goal'} stimulus.",
            "monitor": ["performance", "RPE", "sleep", "wellness", "recovery"],
            "decision_rule": "If recovery and perceived effort improve while performance stabilizes, hold the reduced cost before progressing again.",
            "uncertainty": "Low to moderate",
            "confidence": 0.91
        }

    if fatigue_signals == 1 and (rpe_class == "increased" or (numeric_rpe is not None and numeric_rpe >= 9)):
        return {
            "assessment": "A fatigue-related signal is present, but there is not enough converging evidence to justify an immediate training reduction.",
            "decision": "collect_data",
            "action": "Keep the current stimulus temporarily and collect the highest-value recovery/performance information before reducing training cost.",
            "monitor": ["performance", "RPE", "recovery", "sleep", "wellness"],
            "decision_rule": "If a second fatigue signal appears or performance declines, reduce the smallest appropriate training cost; if the signal resolves, maintain the current structure.",
            "uncertainty": "Moderate",
            "confidence": 0.86
        }

    # 8. Positive response to an explicit previous modification.
    previous_result = text_blob(response.get("result"), history.get("previous_response"), history.get("previous_result"))
    previous_modification = response.get("previous_modification")
    historical_decision = norm(history.get("previous_decision"))
    actual_modification = previous_modification or (
        historical_decision if any(x in historical_decision for x in ["reduce", "modify", "deload", "replace"]) else ""
    )
    positive_response = any(term in previous_result for term in [
        "improved", "positive", "better", "decreased_rpe", "performance_improved"
    ])
    if positive_response and actual_modification and not symptom_present:
        return {
            "assessment": "The previous modification produced a positive response; a small progression is reasonable while monitoring the response.",
            "decision": "progress",
            "action": "Gradually restore or progress the previously reduced training stimulus in a small step, then observe the response.",
            "monitor": ["performance", "RPE", "recovery", "symptoms", "next-day response"],
            "decision_rule": "If performance remains stable or improves and recovery remains stable, continue gradual progression; if symptoms or fatigue increase, reassess and modify.",
            "uncertainty": "Low to moderate",
            "confidence": 0.92
        }

    # Default is deliberately conservative: without a clear benefit/cost
    # imbalance, preserve the current system rather than inventing change.
    return build_decision(
        "maintain_or_progress",
        "The supplied signals do not show a clear benefit-cost imbalance that justifies a change.",
        "Maintain the current structure. Progress only when the next response provides a clear positive signal with adequate recovery.",
        ["performance", "RPE", "recovery"],
        "If performance improves with adequate recovery, progress in a small step; if performance declines with converging fatigue signals, reduce cost; if uncertainty increases, collect data.",
        "Low to moderate", 0.88, ["no_clear_imbalance"], {"primary": primary_goal, "secondary": secondary_goal}
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "ATENA", "version": "0.8"})


@app.post("/decision")
def decision():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400
    return jsonify(decide(data))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
