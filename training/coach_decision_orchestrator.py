"""Single priority gate for ATENA Coach adaptation decisions.

Specialist modules provide evidence; this module owns the final priority order.
It never edits a programme. Callers must honor affected_patterns and must not
interpret missing information as a positive progression signal.
"""
from __future__ import annotations

from training.adaptive_decision import decide_adaptation
from training.athlete_state import (
    AthleteStateError,
    MOVEMENT_TASKS,
    validate_athlete_state,
)


def _result(decision, scope, reason_code, explanation, objective, *,
            question=None, progression_allowed=False, affected_patterns=None,
            adjustment=None):
    result = {
        "decision": decision,
        "scope": scope,
        "reason_codes": [reason_code],
        "explanation": explanation,
        "objective": objective,
        "progression_allowed": progression_allowed,
        "automatic_program_changes": False,
        "adjustment": adjustment,
        "decision_authority": "coach_orchestrator",
    }
    if affected_patterns is not None:
        result["affected_patterns"] = sorted(set(affected_patterns))
    if question:
        result["clarifying_question"] = question
    return result


def decide_coach_next_action(
    athlete_state,
    sessions,
    *,
    exercise_progressions=None,
    longitudinal_progression=None,
    conditioning_progression=None,
    prior_adaptation=None,
):
    """Return exactly one final decision after applying safety and context priority.

    Priority:
      1. concerning symptoms / referral;
      2. new or worsening symptoms / pause;
      3. unresolved symptom context;
      4. stable symptom-linked movement patterns;
      5. movement uncertainty or support needs;
      6. specialist adaptation evidence.
    """
    try:
        state = validate_athlete_state(athlete_state)
    except (AthleteStateError, TypeError, KeyError):
        return _result(
            "collect_context", "none", "invalid_athlete_state",
            "Kanonično stanje športnika manjka ali ni veljavno. ATENA ne bo sklepala o omejitvah, opremi ali pripravljenosti.",
            "Najprej varno popraviti oziroma dopolniti profil.",
            question="Lahko preveriva cilj, opremo in trenutno stanje profila?",
        )

    symptoms = state["symptoms"]
    symptom_status = symptoms["status"]
    symptom_items = symptoms["items"]

    if symptom_status == "concerning":
        return _result(
            "refer_for_assessment", "all_training_progression",
            "concerning_symptoms",
            "Zabeležen je opozorilni simptom. Samodejna progresija in individualno prilagajanje obremenitve se ustavita; potreben je ustrezen zdravstveni pregled.",
            "Pred nadaljevanjem vadbe razjasniti opozorilni znak pri ustreznem zdravstvenem strokovnjaku.",
            progression_allowed=False,
            adjustment="stop_automatic_progression_and_refer",
        )

    if symptom_status == "new_or_worsening":
        return _result(
            "pause_and_review", "all_training_progression",
            "new_or_worsening_symptoms",
            "Zabeleženi so novi ali slabšajoči se simptomi. Varnostni signal preglasi rezultate, regeneracijo in predloge progresije.",
            "Razjasniti spremembo simptomov in varno nadaljevanje; ob izrazitih ali zaskrbljujočih znakih poiskati zdravstveno oceno.",
            question="Kaj se je spremenilo, kdaj se je začelo in ali se težava pojavlja tudi pri vsakodnevnih dejavnostih?",
            progression_allowed=False,
            adjustment="hold_all_progression_pending_review",
        )

    if symptom_status == "asked_unanswered":
        return _result(
            "collect_context", "none", "symptom_screen_unanswered",
            "Vprašanje o simptomih je bilo zastavljeno, vendar odgovor manjka. Odsotnosti simptomov ni dovoljeno predpostaviti.",
            "Pridobiti odgovor pred individualno odločitvijo o nadaljnjem odmerku.",
            question="Ali trenutno opažaš bolečino, nelagodje ali novo zdravstveno oziroma gibalno omejitev?",
        )

    if symptom_status == "present_stable":
        linked_tasks = []
        unresolved = []
        for item in symptom_items:
            task = item.get("provoking_task")
            if isinstance(task, str) and task in MOVEMENT_TASKS:
                linked_tasks.append(task)
            else:
                unresolved.append(task)
        if unresolved or not linked_tasks:
            return _result(
                "collect_context", "none", "stable_symptom_task_unclear",
                "Simptom je označen kot stabilen, vendar povezava z gibalno nalogo ni dovolj jasna. ATENA ne bo ugibala, katere vaje so primerne.",
                "Razjasniti nalogo oziroma okoliščino, ki sproži simptom.",
                question="Pri katerem konkretnem gibu ali dejavnosti se težava pojavi?",
            )
        return _result(
            "review_symptom_linked_patterns", "affected_patterns",
            "stable_symptom_requires_task_specific_review",
            "Stabilen simptom je povezan z določeno gibalno nalogo. Pred progresijo je treba pregledati in po potrebi prilagoditi samo povezane vzorce; drugih vzorcev ne smemo samodejno označiti kot prizadete.",
            "Ohraniti varno vadbo in ločeno pregledati obremenitev prizadetih vzorcev.",
            progression_allowed=False,
            affected_patterns=linked_tasks,
            adjustment="hold_linked_patterns_pending_task_specific_review",
        )

    tasks = state["movement_assessment"]["tasks"]
    needs_review = [
        task for task, observation in tasks.items()
        if observation["status"] in {"uncertain", "needs_support", "symptoms_reported"}
    ]
    if needs_review:
        return _result(
            "movement_competence_review", "affected_patterns",
            "movement_readiness_not_confirmed",
            "Pri eni ali več gibalnih nalogah pripravljenost ni potrjena. Pred progresijo teh vzorcev je treba preveriti izvedbo, obseg giba, podporo in ustrezno regresijo.",
            "Najti nadzorovano različico vaje in potrditi kakovost izvedbe.",
            progression_allowed=False,
            affected_patterns=needs_review,
            adjustment="hold_affected_patterns_and_review_variation",
        )

    decision = decide_adaptation(
        sessions,
        exercise_progressions=exercise_progressions,
        longitudinal_progression=longitudinal_progression,
        conditioning_progression=conditioning_progression,
        prior_adaptation=prior_adaptation,
    )
    result = dict(decision)
    result["decision_authority"] = "specialist_reconciliation"
    return result
