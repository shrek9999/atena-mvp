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
        "difficulty": session.get("difficulty", "unknown"),
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
    if not latest["sets_complete"] or not previous["sets_complete"]:
        return "hold", "V eni od zadnjih izvedb ni bilo zabeleženih vseh načrtovanih serij. Najprej preveri razlog in utrdi načrtovani odmerek."
    if min(latest["rirs"]) < 3 or min(previous["rirs"]) < 3:
        return "hold", "Rezerva ponovitev še ne potrjuje lahke izvedbe v dveh zaporednih treningih. Ohrani trenutno obremenitev in obseg."
    if latest["difficulty"] not in {"easy", "moderate"} or previous["difficulty"] not in {"easy", "moderate"}:
        return "hold", "Splošna zahtevnost treninga ne potrjuje še dveh stabilnih izpostavitev. Ohrani trenutno dozo."
    if latest["recovery"] == "poor" or previous["recovery"] == "poor":
        return "hold", "Regeneracija ni bila ustrezna v obeh zadnjih izpostavitvah. Progresijo zadrži."

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
                old_load = sum(previous["loads"]) / len(previous["loads"])
                new_load = sum(latest["loads"]) / len(latest["loads"])
                if new_load != old_load:
                    return "hold", "Obremenitev se je že spremenila. Najprej utrdi novo obremenitev v dveh primerljivih izvedbah."
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
    # A reported symptom is a global safety hold, not a signal to work around it.
    if any(session.get("discomfort_reported") is True for _, session in ordered[:3]):
        affected_ids = set()
        for _, session in ordered[:3]:
            exercises = session.get("exercises", [])
            if not isinstance(exercises, list):
                continue
            affected_ids.update(
                exercise["exercise_id"] for exercise in exercises
                if isinstance(exercise, dict) and isinstance(exercise.get("exercise_id"), str)
            )
        return [{
            "exercise_id": exercise_id,
            "decision": "pause_and_review",
            "exposures_recorded": 0,
            "reason": "Zabeleženo je bilo nelagodje. Samodejno napredovanje vseh vaj je ustavljeno do ustrezne presoje.",
        } for exercise_id in sorted(affected_ids)]

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
        exercise = get_exercise(item["exercise_id"])
        item["exercise_name"] = exercise.get("name") if isinstance(exercise, dict) else item["exercise_id"]
    return recommendations


def apply_exercise_progression(program, recommendations):
    """Attach exercise-specific next-step guidance to the generated programme.

    Only the rep target is adjusted by one rep where justified. No kilogram
    increase is invented or applied automatically.
    """
    if not isinstance(program, dict) or not isinstance(program.get("sessions"), list):
        return program
    by_id = {
        item.get("exercise_id"): item
        for item in recommendations if isinstance(item, dict) and isinstance(item.get("exercise_id"), str)
    }
    for session in program["sessions"]:
        for exercise in session.get("exercises", []) if isinstance(session, dict) else []:
            if not isinstance(exercise, dict):
                continue
            recommendation = by_id.get(exercise.get("exercise_id"))
            if not recommendation:
                continue
            prescription = exercise.get("prescription")
            if not isinstance(prescription, dict):
                continue
            decision = recommendation.get("decision")
            note = recommendation.get("reason", "")
            if decision == "add_repetitions":
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
    return program
