"""Explainable, conservative programme-level adaptation decisions for ATENA.

This layer reconciles recent session feedback with exercise and multi-week
signals. It proposes a scope and a reason; it does not diagnose or silently
rewrite a programme. Missing context remains unknown.
"""
from __future__ import annotations

from datetime import date


VALID_COMPLETION_REASONS = {
    "time_constraint", "high_difficulty", "poor_recovery", "external_interruption",
    "other", "unknown",
}
VALID_ADAPTATION_OUTCOMES = {"helped", "no_change", "worse", "not_tried"}


def _rows(sessions):
    rows = []
    for item in sessions if isinstance(sessions, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("session"), dict):
            continue
        try:
            day = date.fromisoformat(item.get("session_date", ""))
        except (TypeError, ValueError):
            continue
        rows.append((day, item["session"]))
    # Stable sort preserves newest-first ordering for same-day records.
    return sorted(rows, key=lambda row: row[0], reverse=True)


def _decision(decision, scope, reason_code, explanation, objective, *,
              question=None, progression_allowed=False, adjustment=None):
    success_signals = {
        "collect_baseline": [
            "Zabeleženi so vsaj trije primerljivi treningi z dejanskimi serijami, ponovitvami in RIR."
        ],
        "collect_context": [
            "Vzrok nedokončanega treninga je jasno opredeljen, preden se spremeni vadbeni odmerek."
        ],
        "restructure_session": [
            "Glavne vaje so opravljene v razpoložljivem času, brez hitenja in brez izpuščanja ključne kakovosti izvedbe."
        ],
        "recovery_review": [
            "Pred naslednjo zahtevno vadbo je regeneracija spet običajna in zmogljivost se ne slabša."
        ],
        "reduce_session_dose_review": [
            "Pri naslednji primerljivi izvedbi so načrtovane serije izvedljive s kontrolirano tehniko in ustreznim RIR."
        ],
        "maintain_and_reschedule": [
            "Naslednji primerljivi trening je izveden normalno; izpuščenega obsega ni treba nadomeščati."
        ],
        "maintain_and_monitor": [
            "V naslednjih primerljivih izvedbah ostanejo kakovost tehnike, RIR, zmogljivost in regeneracija stabilni."
        ],
        "reassess_previous_change": [
            "Naslednji drugačen ukrep izboljša vsaj en vnaprej določen znak, ne da bi poslabšal tehniko ali regeneracijo."
        ],
        "confirm_previous_change": [
            "Prejšnji predlog je dejansko preizkušen vsaj enkrat, preden se sprejme nova odločitev."
        ],
        "review_declining_exercise": [
            "Pri prizadeti vaji se zmogljivost stabilizira ali izboljša, medtem ko ostale vaje ostanejo nespremenjene."
        ],
        "review_conditioning_dose": [
            "Kondicijska zmogljivost se stabilizira brez slabšanja regeneracije ali kakovosti vadbe za moč."
        ],
        "exercise_specific_progression_review": [
            "Izbrana vaja doseže ciljni obseg ponovitev z nadzorovano izvedbo in predpisanim RIR."
        ],
        "review_session_dose": [
            "Naslednji trening je izvedljiv brez ponovitve previsoke zahtevnosti."
        ],
        "pause_and_review": [
            "Pred nadaljevanjem ni novih ali poslabšanih opozorilnih znakov; progresija ostane ustavljena do ponovne presoje."
        ],
        "technique_review": [
            "Pri naslednjih dveh primerljivih izvedbah je nadzor trupa in položaja potrjen kot stabilen, preden se progresija ponovno odpre."
        ],
    }
    result = {
        "decision": decision,
        "scope": scope,
        "reason_codes": [reason_code],
        "explanation": explanation,
        "objective": objective,
        "success_signals": success_signals.get(decision, [
            "Naslednja primerljiva vadba potrdi kakovost izvedbe, ustrezen RIR in normalno regeneracijo."
        ]),
        "progression_allowed": progression_allowed,
        "automatic_program_changes": False,
        "adjustment": adjustment,
    }
    if question:
        result["clarifying_question"] = question
    return result


def decide_adaptation(sessions, *, exercise_progressions=None,
                      longitudinal_progression=None, conditioning_progression=None,
                      prior_adaptation=None):
    """Return one explainable next-step decision and its narrowest justified scope.

    Optional completion_reason values distinguish time, demand and recovery.
    prior_adaptation may contain {adaptation_id, outcome}; failed or untried
    proposals are not repeated blindly.
    """
    rows = _rows(sessions)
    recent = rows[:3]
    if not recent:
        return _decision(
            "collect_baseline", "none", "no_training_history",
            "ATENA še nima zabeleženih izvedb, zato nima podlage za spremembo.",
            "Zbrati prvo primerljivo izhodišče.",
            question="Kako je potekal zadnji trening in ali si lahko izvedel načrtovani obseg?",
        )

    if any(session.get("discomfort_reported") is True for _, session in recent):
        return _decision(
            "pause_and_review", "all_progression", "discomfort_reported",
            "V zadnjih treh zapisih je zabeleženo nelagodje. Varnostni signal ima prednost pred trendi in progresijo.",
            "Razjasniti trenutno stanje in varno nadaljevanje.",
            question="Ali je nelagodje še prisotno ali se je povsem umirilo?",
        )

    if any(session.get("movement_control") in {"spinal_flexion", "bracing", "both"} for _, session in recent):
        return _decision(
            "technique_review", "session", "movement_control_issue",
            "Zabeležena je težava z nadzorom trupa ali vzpostavljanjem znotrajtrebušnega pritiska. Pred progresijo je treba preveriti kakovost izvedbe osnovnih vzorcev.",
            "Potrditi nadzorovano izvedbo in ustrezno strategijo stabilizacije, ne pa samodejno dodajati stabilizacijskih vaj vsem treningom.",
            question="Pri katerem gibalnem vzorcu se je težava pokazala in ali se je pojavila pri eni ali več vajah?",
            adjustment="hold_affected_exercise_and_review_context",
        )

    latest_day, latest = recent[0]
    # A failed previous adjustment takes precedence over routine progression.
    feedback = prior_adaptation if isinstance(prior_adaptation, dict) else {}
    outcome = feedback.get("outcome")
    adaptation_id = feedback.get("adaptation_id")
    if outcome in {"worse", "no_change"}:
        return _decision(
            "reassess_previous_change", "affected_exercise_or_session",
            "previous_adjustment_not_successful",
            "Prejšnja prilagoditev ni prinesla pričakovanega učinka. ATENA je ne bo ponovila; najprej mora preveriti, kaj se je dejansko spremenilo in zakaj.",
            "Razumeti odziv na prejšnji ukrep in izbrati drugačen ali noben ukrep.",
            question="Kaj se je po prejšnji prilagoditvi spremenilo: izvedba, zahtevnost, regeneracija ali rezultat?",
        ) | {"previous_adaptation_id": adaptation_id, "previous_outcome": outcome}
    if outcome == "not_tried":
        return _decision(
            "confirm_previous_change", "none", "previous_adjustment_not_tried",
            "Prejšnji predlog še ni bil preizkušen. Nove spremembe bi onemogočile presojo, ali je prvi predlog deloval.",
            "Najprej preveriti izvedbo že predlaganega ukrepa.",
            question="Ali si prejšnjo prilagoditev preizkusil vsaj enkrat?",
        ) | {"previous_adaptation_id": adaptation_id, "previous_outcome": outcome}

    if outcome == "helped":
        return _decision(
            "maintain_and_monitor", "previous_adjustment", "previous_adjustment_helped",
            "Uporabnik je potrdil, da je prejšnja prilagoditev pomagala. ATENA jo ohrani brez dodatnega stopnjevanja; učinek spremlja pri naslednji primerljivi izvedbi.",
            "Ohraniti uspešno prilagoditev in preveriti, ali se dober učinek ponovi.",
        ) | {"previous_adaptation_id": adaptation_id, "previous_outcome": outcome}

    # Reconcile recent global feedback with exercise-specific and multi-week signals.
    if any(s.get("recovery") == "poor" for _, s in recent[:2]):
        return _decision(
            "recovery_review", "session", "recent_poor_recovery",
            "Slaba regeneracija je zabeležena v eni od zadnjih dveh vadb. Pred progresijo je treba preveriti spanec, stres, razmik med vadbami in skupno obremenitev.",
            "Preprečiti kopičenje utrujenosti in potrditi, ali je potreben poseg v celoten trening.",
            question="Je bila regeneracija slabša tudi izven treninga ali predvsem po zadnji vadbi?",
        )

    if latest.get("completed") is not True:
        reason = latest.get("completion_reason", "unknown")
        if reason == "time_constraint":
            return _decision(
                "restructure_session", "session_structure", "time_constraint",
                "Trening ni bil zaključen zaradi pomanjkanja časa. To samo po sebi ne dokazuje, da je bil vadbeni odmerek previsok.",
                "Ohraniti ključni dražljaj, skrajšati organizacijo treninga in začasno izpustiti najmanj pomembne dodatke.",
                question="Koliko časa si dejansko imel na voljo za trening?",
                adjustment="prioritise_main_exercises_and_defer_optional_accessories",
            )
        if reason == "poor_recovery":
            return _decision(
                "recovery_review", "session", "incomplete_due_to_recovery",
                "Trening je bil prekinjen zaradi slabe regeneracije. Pred spremembo programa je treba preveriti, ali gre za osamljen ali ponavljajoč se odziv.",
                "Razjasniti regeneracijo, preden se spremeni odmerek.",
                question="Je bila slabša regeneracija prisotna že pred treningom ali se je pojavila med njim?",
            )
        if reason == "high_difficulty":
            return _decision(
                "reduce_session_dose_review", "session", "incomplete_due_to_high_difficulty",
                "Trening ni bil zaključen zaradi previsoke zahtevnosti. To je močnejši signal za pregled odmerka kot zgolj manjkajoč zaključek.",
                "Ugotoviti, ali je bila zahtevna celotna vadba ali samo posamezna vaja.",
                question="Katera vaja oziroma del treninga je bil glavni razlog, da nisi mogel nadaljevati?",
                adjustment="review_session_volume_before_next_exposure",
            )
        if reason == "external_interruption":
            return _decision(
                "maintain_and_reschedule", "none", "external_interruption",
                "Trening je prekinil zunanji dejavnik. Ni dokaza, da je bil program neustrezen.",
                "Nadaljevati načrt brez nadomeščanja izpuščenega obsega.",
            )
        return _decision(
            "collect_context", "none", "incomplete_reason_unknown",
            "Manjkajoči zaključek sam po sebi ne pove, ali je bil vzrok čas, zahtevnost, regeneracija ali zunanja okoliščina.",
            "Pridobiti razlog, preden ATENA poseže v program.",
            question="Kaj je preprečilo zaključek: premalo časa, previsoka zahtevnost, slaba regeneracija ali zunanja okoliščina?",
        )

    trends = longitudinal_progression.get("exercise_trends", []) if isinstance(longitudinal_progression, dict) else []
    conditioning = conditioning_progression.get("conditioning_trends", []) if isinstance(conditioning_progression, dict) else []
    if any(isinstance(x, dict) and x.get("status") == "declining_performance" for x in trends):
        return _decision(
            "review_declining_exercise", "affected_exercise", "multiweek_decline",
            "Večtedenski trend kaže slabšanje pri vsaj eni primerljivi vaji. To ni razlog za avtomatično zmanjšanje celotnega programa; najprej preglej prizadeto vajo in njen kontekst.",
            "Ohraniti ostale stabilne dele programa in preveriti samo označeno vajo.",
            adjustment="hold_affected_exercise_and_review_context",
        )
    if any(isinstance(x, dict) and x.get("status") in {"recovery_watch", "performance_watch"} for x in conditioning):
        return _decision(
            "review_conditioning_dose", "conditioning_block", "conditioning_recovery_watch",
            "Kondicijski trend zahteva ločen pregled. Kondicijskega odmerka ne smemo zamenjati z odmerkom vaj za moč.",
            "Prilagoditi samo zadevni kondicijski protokol, če pregled potrdi potrebo.",
        )

    progressions = exercise_progressions if isinstance(exercise_progressions, list) else []
    candidates = [
        item for item in progressions
        if isinstance(item, dict)
        and isinstance(item.get("exercise_id"), str)
        and item["exercise_id"].strip()
        and item.get("decision") in {
            "add_repetitions", "increase_load", "progress_variation", "increase_work_time"
        }
    ]
    if candidates:
        return _decision(
            "exercise_specific_progression_review", "individual_exercise", "exercise_level_evidence",
            "Podatki podpirajo pregled progresije pri posamezni vaji. To ne upravičuje povečanja obsega ali intenzivnosti vseh vaj.",
            "Spremeniti največ eno spremenljivko pri potrjeni vaji, ostale dele programa pa ohraniti.",
            progression_allowed=True,
            adjustment="apply_only_confirmed_exercise_recommendations",
        ) | {"eligible_exercises": list(dict.fromkeys(x["exercise_id"] for x in candidates))}

    if any(isinstance(x, dict) and x.get("decision") in {"hold", "collect_data", "technique_review", "reduce_dose", "pause_and_review"} for x in progressions):
        return _decision(
            "maintain_and_monitor", "individual_exercise", "mixed_exercise_signals",
            "Vsaj ena vaja nima dovolj dokazov za progresijo ali potrebuje tehnični pregled. Stabilnih vaj ni treba spreminjati.",
            "Ohraniti odmerek in dopolniti podatke samo pri vajah z nejasnim odzivom.",
        )

    if latest.get("difficulty") == "hard":
        return _decision(
            "review_session_dose", "session", "high_session_difficulty",
            "Zadnja vadba je bila ocenjena kot težka, vendar brez podatka o prizadetih vajah ni mogoče utemeljiti globalnega zmanjšanja.",
            "Preveriti, kateri del vadbe je ustvaril previsoko zahtevnost.",
            question="Je bila težka celotna vadba ali samo ena oziroma dve vaji?",
        )

    return _decision(
        "maintain_and_monitor", "none", "no_change_justified",
        "Trenutni podatki ne kažejo dovolj jasnega razloga za spremembo. Ohrani program in spremljaj naslednjo primerljivo izvedbo.",
        "Ohraniti učinkovit dražljaj brez nepotrebnih sprememb.",
    )
