"""Exercise-by-exercise progression from recorded training performance.

Recommendations are deterministic, explainable and conservative. They do not
diagnose, estimate 1RM, or invent a load that the user did not record.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from training.catalogue import get_exercise


def _ordered_sessions(sessions):
    valid = []
    for item in sessions if isinstance(sessions, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("session"), dict):
            continue
        try:
            day = date.fromisoformat(item.get("session_date", ""))
        except (TypeError, ValueError):
            continue
        valid.append((day, item["session"]))
    return sorted(valid, key=lambda row: row[0], reverse=True)


def _exercise_observation(exercise, session, day):
    if not isinstance(exercise, dict) or not isinstance(exercise.get("exercise_id"), str):
        return None
    sets = exercise.get("set_results")
    if not isinstance(sets, list) or not sets:
        sets = []
    reps = []
    work = []
    loads = []
    rirs = []
    for item in sets:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("reps"), int) and not isinstance(item.get("reps"), bool):
            reps.append(item["reps"])
        if isinstance(item.get("work_seconds"), int) and not isinstance(item.get("work_seconds"), bool):
            work.append(item["work_seconds"])
        if isinstance(item.get("load_kg"), (int, float)) and not isinstance(item.get("load_kg"), bool):
            loads.append(float(item["load_kg"]))
        if isinstance(item.get("rir"), int) and not isinstance(item.get("rir"), bool):
            rirs.append(item["rir"])

    if not sets:
        if isinstance(exercise.get("reps_completed"), int):
            reps = [exercise["reps_completed"]]
        if isinstance(exercise.get("work_seconds_completed"), int):
            work = [exercise["work_seconds_completed"]]
        if isinstance(exercise.get("load_kg"), (int, float)):
            loads = [float(exercise["load_kg"])]
        if isinstance(exercise.get("rir"), int):
            rirs = [exercise["rir"]]

    catalogue_item = get_exercise(exercise["exercise_id"]) or {}
    effective_difficulty = session.get("difficulty", "unknown")
    if (
        session.get("difficulty_scope") == "exercise"
        and session.get("affected_exercise_id") != exercise["exercise_id"]
        and effective_difficulty == "hard"
    ):
        # A hard rating caused by one named exercise must not suppress
        # progression evidence for every other exercise in the same session.
        effective_difficulty = "moderate"
    return {
        "date": day.isoformat(),
        "exercise_id": exercise["exercise_id"],
        "pattern": catalogue_item.get("pattern"),
        "reps": reps,
        "work_seconds": work,
        "loads": loads,
        "rirs": rirs,
        # Only set-by-set feedback is sufficient for individual progression.
        # Legacy session summaries cannot prove that every set met the target.
        "rir_complete": bool(sets) and len(rirs) == len(sets),
        "reps_complete": bool(sets) and len(reps) == len(sets),
        "loads_complete": bool(sets) and len(loads) == len(sets),
        "work_complete": bool(sets) and len(work) == len(sets),
        "sets_complete": (
            exercise.get("planned_sets") is None
            or (len(sets) if sets else exercise.get("sets_completed")) == exercise.get("planned_sets")
        ),
        "planned_sets": exercise.get("planned_sets"),
        "target_reps_min": exercise.get("target_reps_min"),
        "target_reps_max": exercise.get("target_reps_max"),
        "target_work_seconds": exercise.get("target_work_seconds"),
        "execution_quality": exercise.get("execution_quality", "unknown"),
        "tempo_control": exercise.get("tempo_control", "unknown"),
        "tempo_target": exercise.get("tempo_target"),
        "difficulty": effective_difficulty,
        "recovery": session.get("recovery", "unknown"),
        "completed": session.get("completed") is True,
    }


def _valid_range(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _classify(history):
    latest = history[0]
    latest_rir = min(latest["rirs"]) if latest["rirs"] else None
    latest_reps = latest["reps"]
    latest_work = latest["work_seconds"]

    if latest["tempo_control"] == "not_followed":
        return "technique_review", "Predpisanega tempa nisi mogel ohraniti. Ne stopnjuj obremenitve; najprej izberi breme, pri katerem lahko nadzoruješ celoten predpisani tempo."
    if latest["tempo_control"] == "inconsistent":
        return "hold", "Tempo je bil v delu ponovitev neenakomeren. Ohrani trenutni odmerek in najprej utrdi predpisani ritem."
    if latest["tempo_control"] not in {"followed", "not_applicable"}:
        return "collect_data", "Nadzor predpisanega tempa še ni ocenjen. Pred progresijo zberi vsaj dve primerljivi izvedbi z zabeleženim tempom."
    if latest["execution_quality"] == "needs_attention":
        return "technique_review", "Tehnika oziroma nadzor izvedbe potrebuje pozornost. Za zdaj ne povečuj obremenitve; najprej utrdi kakovost izvedbe."
    if latest["execution_quality"] != "controlled":
        return "collect_data", "Kakovost izvedbe še ni bila potrjena kot nadzorovana. Pred progresijo zberi zanesljivo oceno izvedbe."
    if latest["difficulty"] == "hard" or latest["recovery"] == "poor":
        if latest_rir is not None and latest_rir <= 1:
            return "reduce_dose", "Zadnja izvedba je bila zelo zahtevna. Naslednjič ohrani vajo, vendar zmanjšaj obremenitev ali ciljne ponovitve za majhen korak."
        return "hold", "Zadnji trening ali regeneracija sta bila zahtevna. Ohrani odmerek te vaje in počakaj na boljši odziv."
    if latest_rir is not None and latest_rir <= 1:
        return "reduce_dose", "V vsaj eni seriji je ostala največ ena ponovitev v rezervi. Naslednjič zmanjšaj obremenitev ali ciljne ponovitve; serij še ne dodajaj."
    if len(history) < 2:
        return "collect_data", "Za individualno progresijo je za zdaj premalo primerljivih izvedb. Ohrani načrt in zabeleži še naslednji odziv."
    previous = history[1]
    if previous["tempo_control"] == "not_followed":
        return "technique_review", "V prejšnji izvedbi predpisan tempo ni bil ohranjen. Pred progresijo ga potrdi v naslednjem treningu."
    if previous["tempo_control"] == "inconsistent":
        return "hold", "V prejšnji izvedbi je bil tempo neenakomeren. Najprej potrdi dve zaporedni enakomerni izvedbi."
    if previous["tempo_control"] not in {"followed", "not_applicable"}:
        return "collect_data", "V prejšnji izvedbi manjka ocena nadzora tempa. Potrebna je še ena primerljiva, ocenjena izvedba."
    if latest["tempo_control"] != previous["tempo_control"] or latest["tempo_target"] != previous["tempo_target"]:
        return "hold", "Predpisani tempo se je med zadnjima izvedbama spremenil. Najprej zberi dve primerljivi izvedbi z enakim tempom."
    if previous["execution_quality"] == "needs_attention":
        return "technique_review", "Prejšnja izvedba je zahtevala več nadzora. Najprej potrdi kakovostno izvedbo, nato ponovno oceni progresijo."
    if previous["execution_quality"] != "controlled":
        return "collect_data", "V prejšnjem treningu kakovost izvedbe ni bila potrjena. Potrebna je še ena zanesljivo ocenjena izpostavitev."
    if previous["difficulty"] == "hard" or previous["recovery"] == "poor":
        return "hold", "Prejšnji odziv ni bil dovolj stabilen za progresijo. Ohrani odmerek in preveri naslednjo kakovostno izvedbo."
    if (
        not latest["rirs"] or not previous["rirs"]
        or not latest["rir_complete"] or not previous["rir_complete"]
    ):
        return "collect_data", "Manjka zanesljiva ocena RIR za vsako serijo v obeh zadnjih izvedbah. Brez popolnih podatkov ne bom sklepal, da je progresija upravičena."
    if not isinstance(latest["planned_sets"], int) or isinstance(latest["planned_sets"], bool) or latest["planned_sets"] < 1:
        return "collect_data", "Manjka zanesljiv podatek o načrtovanem številu serij. Pred progresijo ga je treba potrditi."
    if not isinstance(previous["planned_sets"], int) or isinstance(previous["planned_sets"], bool) or previous["planned_sets"] < 1:
        return "collect_data", "V prejšnji izvedbi manjka podatek o načrtovanem številu serij. Potrebna je še ena primerljiva izvedba."
    if latest["planned_sets"] != previous["planned_sets"]:
        return "hold", "Načrtovano število serij se je med zadnjima izvedbama spremenilo. Najprej utrdi enak obseg v dveh primerljivih izvedbah."
    if not latest["sets_complete"] or not previous["sets_complete"]:
        return "hold", "V eni od zadnjih izvedb ni bilo zabeleženih vseh načrtovanih serij. Najprej preveri razlog in utrdi načrtovani odmerek."
    if min(latest["rirs"]) < 3 or min(previous["rirs"]) < 3:
        return "hold", "Rezerva ponovitev še ne potrjuje lahke izvedbe v dveh zaporednih treningih. Ohrani trenutno obremenitev in obseg."
    if latest["difficulty"] not in {"easy", "moderate"} or previous["difficulty"] not in {"easy", "moderate"}:
        return "hold", "Splošna zahtevnost treninga ne potrjuje še dveh stabilnih izpostavitev. Ohrani trenutno dozo."
    if latest["recovery"] == "poor" or previous["recovery"] == "poor":
        return "hold", "Regeneracija ni bila ustrezna v obeh zadnjih izpostavitvah. Progresijo zadrži."

    # Load must remain comparable for every rep-based progression, not only
    # when the user reaches the top of the rep range.
    if latest["loads"] or previous["loads"]:
        if not latest["loads_complete"] or not previous["loads_complete"]:
            return "collect_data", "Obremenitev ni zabeležena za vsako serijo v obeh izvedbah. Pred progresijo potrebujeva popolne podatke."
        if len(latest["loads"]) != len(previous["loads"]) or any(
            current != prior for current, prior in zip(latest["loads"], previous["loads"])
        ):
            return "hold", "Obremenitev v posameznih serijah se je spremenila. Najprej utrdi enako obremenitev v dveh primerljivih izvedbah."

    target_min = latest["target_reps_min"]
    target_max = latest["target_reps_max"]
    if target_min is not None and target_max is not None:
        if not latest["reps_complete"] or not previous["reps_complete"]:
            return "collect_data", "Manjkajo dejanske ponovitve za vsako serijo v eni od zadnjih izvedb."
        if (
            previous["target_reps_min"] != target_min
            or previous["target_reps_max"] != target_max
        ):
            return "hold", "Ciljno območje ponovitev se je med izvedbama spremenilo. Najprej zberi dve primerljivi izvedbi."
        previous_reps = previous["reps"]
        if not latest_reps or not previous_reps:
            return "collect_data", "Za primerjavo manjka dejansko število ponovitev v eni od zadnjih izvedb."
        if (
            not all(value >= target_min for value in previous_reps)
            or not all(value >= target_min for value in latest_reps)
        ):
            return "hold", "Spodnja meja načrtovanega območja še ni bila dosežena v obeh zadnjih izvedbah. Ohrani trenutni odmerek."
        latest_at_top = all(value >= target_max for value in latest_reps)
        previous_at_top = all(value >= target_max for value in previous_reps)
        if latest_at_top and not previous_at_top:
            return "hold", "Zgornjo mejo si dosegel šele v zadnji izvedbi. Pred dvigom obremenitve jo potrdi še enkrat."
        if latest_at_top and previous_at_top:
            if latest["loads"] and previous["loads"]:
                return "increase_load", "Zgornjo mejo ponovitev si dosegel v vseh serijah v dveh zaporednih izvedbah z najmanj 3 RIR. Naslednjič lahko poskusiš najmanjši razpoložljivi dvig obremenitve; serije in ponovitve ohrani."
            if not latest["loads"] and not previous["loads"]:
                return "progress_variation", "Zgornjo mejo ponovitev si dosegel v obeh izvedbah z ustrezno rezervo. Če zunanja obremenitev ni na voljo, izberi le majhen korak zahtevnejše različice."
            return "collect_data", "Za primerjavo obremenitve manjka podatek iz ene od zadnjih izvedb."
        if any(current < prior for current, prior in zip(latest_reps, previous_reps)):
            return "hold", "Ponovitve v zadnji izvedbi še niso bile stabilne glede na prejšnjo. Ohrani trenutni odmerek."
        return "add_repetitions", "Dve zaporedni kakovostni izvedbi z vsaj 3 RIR in doseženo spodnjo mejo dopuščata majhen korak: naslednjič dodaj eno ponovitev na serijo, obremenitev in število serij pa ohrani."

    target_work = latest["target_work_seconds"]
    if target_work is not None:
        if latest["pattern"] not in {"mobility", "mobility_stretch", "trunk_stability", "anti_rotation", "balance"}:
            return "collect_data", "Časovni interval potrebuje še podatek o intenzivnosti oziroma tempu. Samo daljši čas ni dovolj za varno progresijo aerobne ali kondicijske naloge."
        if not latest["work_complete"] or not previous["work_complete"]:
            return "collect_data", "Manjka dejansko trajanje za vsako serijo v eni od zadnjih izvedb."
        if previous["target_work_seconds"] != target_work:
            return "hold", "Ciljno trajanje se je med izvedbama spremenilo. Najprej zberi dve primerljivi izvedbi."
        if (
            latest_work and previous["work_seconds"]
            and all(value >= target_work for value in latest_work)
            and all(value >= target_work for value in previous["work_seconds"])
        ):
            return "increase_work_time", "Načrtovano trajanje si dosegel v obeh izvedbah z ustrezno rezervo. Naslednjič podaljšaj delo za majhen korak, ostale spremenljivke ohrani."
        return "hold", "Načrtovano trajanje še ni bilo doseženo v obeh zadnjih izvedbah. Ohrani trenutni odmerek."
    return "collect_data", "Manjka primerljiv načrt ponovitev ali trajanja. Pred individualno progresijo zberi popolne podatke."


def recommend_exercise_progression(sessions):
    """Return one independently reasoned recommendation per exercise ID."""
    ordered = _ordered_sessions(sessions)
    # A complete mild/stable localized report affects only its named exercise.
    # Any legacy, incomplete or acute report retains the conservative global hold.
    symptom_details = []
    stop_symptomatic_ids = set()
    for _, session in ordered[:3]:
        if session.get("discomfort_reported") is not True:
            continue
        detail = session.get("discomfort_details")
        complete = (
            isinstance(detail, dict)
            and isinstance(detail.get("exercise_id"), str)
            and isinstance(detail.get("pain_during"), int)
            and not isinstance(detail.get("pain_during"), bool)
            and 0 <= detail["pain_during"] <= 10
            and isinstance(detail.get("worsened"), bool)
            and isinstance(detail.get("tolerated"), bool)
            and isinstance(detail.get("acute_warning_signs"), list)
        )
        if not complete:
            affected_ids = {
                exercise["exercise_id"]
                for _, item in ordered[:3]
                for exercise in item.get("exercises", [])
                if isinstance(exercise, dict) and isinstance(exercise.get("exercise_id"), str)
            }
            return [{
                "exercise_id": exercise_id,
                "decision": "pause_and_review",
                "exposures_recorded": 0,
                "reason": "Poročilo o nelagodju ni popolno ali ga ni mogoče povezati z eno vajo. Pred progresijo je potrebna razjasnitev.",
            } for exercise_id in sorted(affected_ids)]

        mild_tolerated = (
            detail["pain_during"] <= 4
            and detail["worsened"] is False
            and detail["tolerated"] is True
            and detail["acute_warning_signs"] == []
            and {"reduced_load", "slow_tempo"}.issubset(set(detail.get("modifications_applied", [])))
            and bool({"reduced_range", "range_within_tolerance"} & set(detail.get("modifications_applied", [])))
        )
        if mild_tolerated:
            symptom_details.append(detail)
        else:
            stop_symptomatic_ids.add(detail["exercise_id"])

    symptomatic_ids = {detail["exercise_id"] for detail in symptom_details}

    targeted_difficulty_ids = {
        session.get("affected_exercise_id")
        for _, session in ordered[:3]
        if (
            session.get("difficulty") == "hard"
            and session.get("difficulty_scope") == "exercise"
            and isinstance(session.get("affected_exercise_id"), str)
        )
    }

    by_exercise = defaultdict(list)
    for day, session in ordered:
        if session.get("completed") is not True:
            continue
        exercises = session.get("exercises", [])
        if not isinstance(exercises, list):
            continue
        seen_in_session = set()
        for exercise in exercises:
            observation = _exercise_observation(exercise, session, day)
            if observation and observation["exercise_id"] not in seen_in_session:
                seen_in_session.add(observation["exercise_id"])
                by_exercise[observation["exercise_id"]].append(observation)

    recommendations = []
    for exercise_id, observations in sorted(by_exercise.items()):
        history = observations[:3]
        decision, reason = _classify(history)
        latest = history[0]
        recommendations.append({
            "exercise_id": exercise_id,
            "decision": decision,
            "exposures_recorded": len(observations),
            "recent_rir_min": min(latest["rirs"]) if latest["rirs"] else None,
            "recent_load_kg": round(sum(latest["loads"]) / len(latest["loads"]), 2) if latest["loads"] else None,
            "recent_reps": latest["reps"],
            "reason": reason,
        })
    for item in recommendations:
        if item["exercise_id"] in stop_symptomatic_ids:
            item["decision"] = "stop_symptomatic_exposure"
            item["reason"] = (
                "Pri tej vaji so bili zabeleženi opozorilni, stopnjujoči se ali nesprejemljivi "
                "simptomi. Vajo izpusti do ustrezne razjasnitve; ob akutnih ali izrazitih znakih "
                "poišči strokovno oceno. Druge vaje se presojajo ločeno."
            )
        elif item["exercise_id"] in symptomatic_ids:
            item["decision"] = "modify_symptomatic_exposure"
            item["reason"] = (
                "Pri tej vaji je bilo zabeleženo blago, stabilno in sprejemljivo nelagodje. "
                "Naslednjič največ 2 seriji, najmanj 4 ponovitve v rezervi, tempo 4–1–2–0 "
                "in samo neboleč oziroma trenutno toleriran obseg. Breme zmanjšaj; ne stopnjuj."
            )
        exercise = get_exercise(item["exercise_id"])
        item["exercise_name"] = exercise.get("name") if isinstance(exercise, dict) else item["exercise_id"]
        if item["exercise_id"] in targeted_difficulty_ids:
            item["decision"] = "hold"
            item["reason"] = (
                "V zadnjem obdobju je bila visoka zahtevnost pripisana tej vaji. "
                "Ne stopnjuj je, dokler ne preveriš izvedbe in ustreznega odmerka. "
                "Ostale vaje se presojajo ločeno."
            )
    return recommendations


def apply_exercise_progression(program, recommendations):
    """Apply exercise-specific progression, modification, or omission guidance."""
    if not isinstance(program, dict) or not isinstance(program.get("sessions"), list):
        return program
    by_id = {
        item.get("exercise_id"): item
        for item in recommendations
        if isinstance(item, dict) and isinstance(item.get("exercise_id"), str)
    }
    for session in program["sessions"]:
        if not isinstance(session, dict) or not isinstance(session.get("exercises"), list):
            continue
        retained = []
        excluded = list(session.get("excluded_exercises", [])) if isinstance(session.get("excluded_exercises"), list) else []
        for exercise in session["exercises"]:
            if not isinstance(exercise, dict):
                retained.append(exercise)
                continue
            recommendation = by_id.get(exercise.get("exercise_id"))
            if not recommendation:
                retained.append(exercise)
                continue
            decision = recommendation.get("decision")
            note = recommendation.get("reason", "")
            if decision == "stop_symptomatic_exposure":
                excluded.append({
                    "exercise_id": exercise.get("exercise_id"),
                    "name": exercise.get("name") or recommendation.get("exercise_name") or exercise.get("exercise_id"),
                    "reason": note or "Vaja je začasno izpuščena do ustrezne razjasnitve simptomov.",
                })
                continue

            prescription = exercise.get("prescription")
            if not isinstance(prescription, dict):
                retained.append(exercise)
                continue
            if decision == "modify_symptomatic_exposure":
                if isinstance(prescription.get("sets"), int):
                    prescription["sets"] = min(2, prescription["sets"])
                elif isinstance(exercise.get("sets"), int):
                    exercise["sets"] = min(2, exercise["sets"])
                prescription["rir"] = max(
                    4,
                    prescription.get("rir", 4) if isinstance(prescription.get("rir", 4), int) else 4,
                )
                prescription["tempo"] = "4–1–2–0"
                prescription["load_guidance"] = (
                    "Zmanjšaj breme glede na zadnjo izvedbo; izberi obremenitev, pri kateri "
                    "ohraniš nadzor in najmanj 4 ponovitve v rezervi. ATENA ne določa "
                    "samodejne spremembe kilogramov."
                )
                prescription["symptom_range_guidance"] = (
                    "Uporabi samo trenutno toleriran obseg gibanja; ob stopnjevanju ali "
                    "nesprejemljivosti simptoma prekini vajo."
                )
            elif decision == "add_repetitions":
                reps = prescription.get("reps", "")
                parts = [int(value) for value in str(reps).split("–") if value.isdigit()]
                if len(parts) == 2 and parts[0] < parts[1]:
                    prescription["reps"] = f"{parts[0] + 1}–{parts[1]}"
            elif decision == "reduce_dose":
                reps = prescription.get("reps", "")
                parts = [int(value) for value in str(reps).split("–") if value.isdigit()]
                if len(parts) == 2:
                    low, high = parts
                    prescription["reps"] = f"{max(1, low - 1)}–{max(1, high - 1)}"
                    if prescription.get("rir") is not None:
                        prescription["rir"] = max(3, prescription["rir"])
                    prescription["rest_seconds"] = min(300, prescription.get("rest_seconds", 0) + 30)
            elif decision == "increase_work_time" and isinstance(prescription.get("work_seconds"), int):
                current_seconds = prescription["work_seconds"]
                increment = max(5, int(round(current_seconds * 0.05)))
                prescription["work_seconds"] = min(1800, current_seconds + increment)
            prescription["exercise_progression"] = {
                "decision": decision,
                "reason": note,
                "automatic_load_change": False,
            }
            if note:
                existing = prescription.get("adjustment_note", "")
                prescription["adjustment_note"] = (existing + " " + note).strip()
            retained.append(exercise)
        session["exercises"] = retained
        if excluded:
            session["excluded_exercises"] = excluded
    return program
