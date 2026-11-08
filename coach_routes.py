"""Conservative, server-side conversational coach pilot for ATENA."""
import json
import os
import hmac
import logging
import re
import urllib.error
import urllib.request
import secrets
import socket
import time
import uuid
from datetime import date

from coach_store import (
    StorageUnavailable, ProfileNotFound, create_profile as store_create_profile,
    get_profile as store_get_profile, update_profile as store_update_profile,
    add_session as store_add_session, list_sessions as store_list_sessions,
    delete_profile as store_delete_profile, set_health_data_consent as store_set_health_data_consent,
    check_database_connection as store_check_database_connection, storage_enabled,
    save_movement_assessment as store_save_movement_assessment,
    get_movement_assessment as store_get_movement_assessment,
    add_program_version as store_add_program_version,
    list_program_versions as store_list_program_versions,
)
from training.catalogue import get_exercise, load_catalogue
from flask import Blueprint, jsonify, request
from training.program import ProgramSafetyBlock, ProgramValidationError, generate_program
from training.progress import summarize_progress
from training.adaptation import assess_next_step
from training.adaptive_decision import decide_adaptation
from training.exercise_progression import recommend_exercise_progression, apply_exercise_progression
from training.longitudinal_progression import summarize_longitudinal_progression
from training.conditioning_progression import summarize_conditioning_progress
from training.periodization import summarize_training_cycle
from training.proactive_checkin import build_proactive_checkin
from training.coaching_protocols import RDL_TECHNIQUE_PROTOCOL
from training.movement_assessment import MovementAssessmentError, assess_movement_competence

logger = logging.getLogger(__name__)
coach_bp = Blueprint("coach", __name__)
ALLOWED_ORIGINS = {
    "https://gregajenko.si",
    "https://www.gregajenko.si",
    # Temporary, isolated Netlify Deploy Preview used for the closed pilot only.
    "https://deploy-preview-7--tiny-figolla-016703.netlify.app",
    # Cloudflare Pages pilot preview used by the current ATENA frontend.
    "https://pilot-atena-profile-history.atena-ai-trener.pages.dev",
}

@coach_bp.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Pilot-Token, X-Profile-Id, X-Profile-Token"
        response.headers["Access-Control-Max-Age"] = "600"
    return response

MAX_MESSAGE_CHARS = 1800
MAX_MESSAGES = 12


def _has_explicit_no_pain_confirmation(text):
    return bool(re.search(
        r"\b(?:ne boli me|ne čutim bolečine|nimam bolečin|brez bolečin|no pain)\b",
        text,
        re.IGNORECASE,
    ))


def _has_explicit_safety_clearance(text):
    """Accept only direct negative answers, never an ambiguous mention of uncertainty."""
    patterns = (
        r"\bnimam\s+(?:(?:trenutno|nobenih|kakršnih koli|večjih)\s+)*(?:bolečin|poškodb|(?:zdravstvenih|gibalnih)\s+omejitev|omejitev|zdravstvenih težav)\b",
        r"\bbrez\s+(?:(?:trenutnih|nobenih)\s+)*(?:bolečin|poškodb|(?:zdravstvenih|gibalnih)\s+omejitev|omejitev)\b",
        # Exact structured profile wording from the website intake form.
        r"\btrenutna\s+bolečina\s*/\s*poškodba\s*/\s*zdravstvena\s+omejitev\s*:\s*ne\b",
        r"\bno\s+(?:pain|injuries|limitations)\b",
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _profile_from_messages(messages):
    user_text = "\n".join(
        item.get("content", "") for item in messages if item.get("role") == "user"
    )
    for match in re.finditer(r'\{[^{}]*"equipment"\s*:\s*\[[^\]]*\][^{}]*\}', user_text):
        try:
            profile = json.loads(match.group(0))
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(profile, dict) and isinstance(profile.get("equipment"), list):
            return profile
    return {}


def _profile_available_equipment(messages):
    """Use structured equipment as authoritative; use text aliases only without a structured profile."""
    profile = _profile_from_messages(messages)
    if isinstance(profile.get("equipment"), list):
        return {
            value for value in profile["equipment"]
            if isinstance(value, str) and value.strip()
        }

    user_text = "\n".join(
        item.get("content", "") for item in messages if item.get("role") == "user"
    )
    lowered = user_text.casefold()
    available = set()
    aliases = {
        "bodyweight": ("lastno težo", "lastna teža", "brez opreme", "bodyweight"),
        "dumbbell": ("ročk", "dumbbell"),
        "barbell": ("olimpijska palica", "palica", "drog", "barbell"),
        "rack": ("stojal", "rack"),
        "bench": ("klop", "bench"),
        "resistance_band": ("elastik", "resistance band"),
        "cable": ("kabel", "cable"),
        "pull_up_bar": ("drogu za zgibe", "pull-up", "pull up bar"),
        "kettlebell": ("kettlebell", "girj"),
        "box": ("škatl", "box"),
        "weight_plate": ("utežn plošč", "weight plate"),
        "heel_wedge": ("podložk za pete", "heel wedge"),
        "slant_board": ("poševn podlag", "slant board"),
        "chair": ("stol", "chair"),
        "step": ("stopničk", "step"),
        "rowing_machine": ("veslašk", "rowing machine"),
        "air_bike": ("air bike",),
        "ski_erg": ("ski erg",),
        "jump_rope": ("kolebn", "jump rope"),
    }
    for equipment, terms in aliases.items():
        if any(term in lowered for term in terms):
            available.add(equipment)
    if "polno opremljen fitnes" in lowered:
        available.update({
            "dumbbell", "barbell", "rack", "bench", "resistance_band",
            "cable", "pull_up_bar", "kettlebell", "box", "weight_plate",
            "heel_wedge", "slant_board", "chair", "step", "rowing_machine",
            "air_bike", "ski_erg", "jump_rope",
        })
    return available


def _verified_exercise_catalogue_context(messages):
    """Return a small equipment-, goal- and experience-filtered exercise list for Gemini."""
    user_text = "\n".join(
        item.get("content", "") for item in messages if item.get("role") == "user"
    )
    lowered = user_text.casefold()
    profile = _profile_from_messages(messages)
    available = _profile_available_equipment(messages)
    if not available:
        return ""

    goals = set()
    goal_value = profile.get("goal")
    if isinstance(goal_value, str) and goal_value.strip():
        normalized_goal = goal_value.strip().casefold()
        if normalized_goal == "fat_loss":
            goals.update({"strength", "hypertrophy", "general_fitness", "endurance"})
        elif normalized_goal == "strength_hypertrophy":
            goals.update({"strength", "hypertrophy"})
        else:
            goals.add(normalized_goal)
    else:
        if "hypertrophy" in lowered or "hipertrof" in lowered or "mišičn" in lowered:
            goals.add("hypertrophy")
        if "strength" in lowered or "moč" in lowered or "jakost" in lowered:
            goals.add("strength")
        if "endurance" in lowered or "vzdržljiv" in lowered:
            goals.add("endurance")
        if "power" in lowered or "eksploziv" in lowered:
            goals.add("power")
        if "general_fitness" in lowered or "splošn" in lowered or "funkcionaln" in lowered:
            goals.add("general_fitness")

    experience = str(profile.get("experience", "")).casefold()
    if experience in {"beginner", "začetnik"}:
        levels = {"beginner"}
    elif experience in {"advanced", "napreden", "napredni"}:
        levels = {"beginner", "intermediate", "advanced"}
    elif experience in {"intermediate", "srednji", "srednje"}:
        levels = {"beginner", "intermediate"}
    elif "beginner" in lowered or "začetnik" in lowered:
        levels = {"beginner"}
    elif "advanced" in lowered or "napred" in lowered:
        levels = {"beginner", "intermediate", "advanced"}
    else:
        levels = {"beginner", "intermediate"}

    records = []
    for exercise in load_catalogue():
        if exercise["level"] not in levels:
            continue
        if goals and not (set(exercise["goals"]) & goals):
            continue
        required = set(exercise["equipment"])
        optional = set(exercise["equipment_any"])
        available_with_bodyweight = available | {"bodyweight"}
        if not required.issubset(available_with_bodyweight):
            continue
        if optional and not (optional & available_with_bodyweight):
            continue
        if exercise["single_joint"] and "advanced" not in levels:
            continue
        if exercise["training_role"] == "stability":
            continue
        records.append(exercise)

    if not records:
        return ""
    priority = {"main": 0, "power": 1, "conditioning": 2, "accessory": 3, "mobility": 4, "stability": 5}
    external_load = {"barbell", "dumbbell", "kettlebell", "weight_plate", "cable", "household_load", "backpack"}
    def bodyweight_option_rank(item):
        # Prefer bodyweight-capable options in the catalogue context even when
        # the user has weights; loaded strength-specific lifts remain available.
        required = set(item["equipment"])
        return 0 if not (required & external_load) else 1
    records.sort(key=lambda item: (
        priority.get(item["training_role"], 9),
        bodyweight_option_rank(item),
        item["single_joint"],
        item["name"],
    ))
    lines = [
        f"- {('Predklon z ravnim hrbtom (RDL)' if item['id'] == 'romanian_deadlift' else item['name'])} [{item['pattern']}; {item['level']}; oprema: "
        + (", ".join(item["equipment"] + item["equipment_any"]) or "lastna teža")
        + "]"
        for item in records[:28]
    ]
    return (
        "\n\nVERIFIED EXERCISE CATALOGUE FOR THIS PROFILE:\n"
        + "\n".join(lines)
        + "\nUse the exact Slovenian names above. Recommend only exercises from this list "
        "unless you ask a clarifying question. Never infer equipment that is not listed."
    )

def _normalize_slovene_coaching_terms(answer):
    """Correct a small, tested set of recurring literal translations/typos."""
    replacements = (
        (r"\btrilogije\s*\(tricepsa\)", "tricepsa"),
        (r"\btrilogije\b", "tricepsa"),
        (r"\bprsni tisk\b", "potisk za prsi"),
        (r"\bsäte\b", "zadnjice"),
        (r"\bzadnji del hrbet\b", "zadnji del hrbta"),
        (r"\bzgornji del hrbet\b", "zgornji del hrbta"),
        (r"\bmišične masa\b", "mišične mase"),
        (r"\bprilezi daljši počitek\b", "vzemi si daljši počitek"),
        (r"\bna session\b", "na vadbeni dan"),
    )
    for pattern, replacement in replacements:
        def preserve_initial_case(match):
            if match.group(0)[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement
        answer = re.sub(pattern, preserve_initial_case, answer, flags=re.IGNORECASE)
    return answer


def _sanitize_unverified_safety_claim(answer, messages):
    """Reject model claims that the user cleared safety when no user did so."""
    user_history = "\n".join(
        item.get("content", "") for item in messages
        if item.get("role") == "user" and isinstance(item.get("content"), str)
    )
    if _has_explicit_safety_clearance(user_history):
        return answer
    claim = re.search(
        r"(?:ker|saj)\s+(?:si\s+)?(?:potrdil|povedal),?\s+da\s+(?:nimaš|si brez)|"
        r"(?:ker|odlično,?\s+(?:ker|da)|super,?\s+da|vesel(?:a)?\s+sem,?\s+da)\s+"
        r"(?:nimaš|nimaš nobenih|si brez|ni nobenih)\s+"
        r"(?:bolečin|poškodb|omejitev|zdravstvenih težav)|"
        r"(?:vesel(?:a)?\s+sem,?\s+da)\s+(?:ni|nimaš)\s+"
        r"(?:nobenih\s+)?(?:bolečin|poškodb|omejitev)|"
        r"(?:ker|saj).{0,80}(?:nisi omenil|nisi navedel|nisi poročal).{0,60}"
        r"(?:bolečin|poškodb|omejitv\w*|zdravstven\w*)|"
        r"(?:sva|smo|si).{0,40}zdravstven\w*\s+(?:pregled|preverjanje).{0,40}"
        r"(?:opravila|zaključila|končala)|"
        r"zdravstven\w*\s+(?:pregled|preverjanje).{0,40}"
        r"(?:je bil|je bilo)\s+(?:že\s+)?(?:opravljen|zaključen)",
        answer,
        re.IGNORECASE,
    )
    if not claim:
        return answer
    return (
        "Tega še nisi izrecno potrdil, zato ne bom predpostavljal, da nimaš omejitev. "
        "Ali imaš trenutno kakršne koli bolečine, poškodbe, gibalne omejitve ali "
        "zdravstvene zadržke, ki bi jih moral upoštevati?"
    )


def _sanitize_unlisted_support(answer, messages):
    """Keep bodyweight-only regressions free of unconfirmed props."""
    if _profile_available_equipment(messages) != {"bodyweight"}:
        return answer
    phrase = re.compile(
        r"višj\w*\s+oporo,?\s*npr\.?\s*(?:ob|na)\s*(?:sten\w*|pult\w*)"
        r"(?:\s+ali\s+(?:stabilen\s+)?rob)?|"
        r"(?:skleca|sklece)\s+(?:ob|na)\s+(?:sten\w*|pult\w*)|"
        r"npr\.?\s*(?:ob|na)\s*(?:sten\w*|pult\w*|stol\w*|klop\w*|miz\w*)",
        re.IGNORECASE,
    )
    if not phrase.search(answer):
        return answer
    answer = re.sub(
        r"višj\w*\s+oporo,?\s*npr\.?\s*(?:ob|na)\s*(?:sten\w*|pult\w*)"
        r"(?:\s+ali\s+(?:stabilen\s+)?rob)?",
        "izvedbo sklece na kolenih ali s krajšim obsegom giba",
        answer,
        flags=re.IGNORECASE,
    )
    answer = re.sub(
        r"(?:skleca|sklece)\s+(?:ob|na)\s+(?:sten\w*|pult\w*)",
        "skleca na kolenih",
        answer,
        flags=re.IGNORECASE,
    )
    answer = re.sub(
        r"npr\.?\s*(?:ob|na)\s*(?:sten\w*|pult\w*|stol\w*|klop\w*|miz\w*)",
        "na kolenih ali s krajšim obsegom giba",
        answer,
        flags=re.IGNORECASE,
    )
    return answer


def _bodyweight_only_program_note(messages):
    """Add a transparent equipment limitation when no pulling anchor exists."""
    profile = _profile_from_messages(messages) or {}
    equipment = set(profile.get("equipment") or [])
    if not equipment or equipment != {"bodyweight"}:
        return None
    user_text = " ".join(
        item.get("content", "") for item in messages
        if item.get("role") == "user" and isinstance(item.get("content"), str)
    ).casefold()
    if not re.search(r"program|trening|vadb|sestavi|pripravi", user_text):
        return None
    return (
        "Pomembna omejitev opreme: ker imaš na voljo samo lastno težo in ni potrjene varne "
        "opore, ta program ne vsebuje obremenjenega vlečnega vzorca za hrbet. Ne bom predlagal "
        "veslanja pod mizo ali improviziranih opor. Za popolnejši razvoj hrbtnih mišic bi "
        "potreboval elastiko, drog ali drugo stabilno oporo. Pri hipertrofiji je napredovanje "
        "zgolj z lastno težo omejeno; zahtevnejši vzvodi, enostranske različice, nadzorovan "
        "tempo in premori lahko pomagajo, vendar ne nadomestijo vedno zunanje obremenitve. "
        "Tudi predklon z ravnim hrbtom brez dodatne obremenitve ni enakovreden obremenjenemu RDL."
    )


def _coaching_guardrail_reply(messages):
    """Deterministic safety/persistence gate; never rely on model compliance alone."""
    user_texts = [
        item.get("content", "") for item in messages
        if item.get("role") == "user" and isinstance(item.get("content"), str)
    ]
    if not user_texts:
        return None
    history = "\n".join(user_texts)
    latest = user_texts[-1]
    lowered = latest.casefold()
    history_lower = history.casefold()

    recovery_context = bool(re.search(
        r"(slabo spim|slab(?:o|ega) spanec|slaba regeneracija|neprespan)",
        history_lower,
    )) and bool(re.search(
        r"(mišice.{0,35}utrujen|utrujen.{0,35}mišic|utrujenost)",
        history_lower,
    ))
    asks_to_continue = bool(re.search(
        r"(naj kar nadaljujem|ali naj nadaljujem|nadaljujem po načrtu|nadaljujem po planu)",
        lowered,
    ))
    if recovery_context and asks_to_continue:
        return (
            "Ne nadaljuj avtomatično po prvotnem načrtu, če sta spanec slab in mišična "
            "utrujenost še prisotna. Zahtevnejši trening prestavi, dokler se počutje ne "
            "izboljša; če se želiš gibati, izberi le lahkotno aktivnost, ki ne poveča "
            "utrujenosti ali povzroča bolečine. Izpuščenega obsega ne nadomeščaj z dvojno "
            "vadbo. Ko se regeneracija izboljša, se vrni z nekoliko manjšim obsegom in "
            "preveri odziv. Je utrujenost predvsem v mišicah, ki si jih treniral, ali "
            "občutiš tudi splošno izčrpanost?"
        )

    # Answer persistence questions directly; a conversational response is not a saved change.
    if re.search(r"(ali si že|si že).{0,80}(prilagodil|spremenil|shranil)|naslednj.{0,20}(trening|program).{0,30}(shranjen|spremenjen|prilagojen)", lowered):
        return (
            "Ne morem potrditi, da je naslednji trening že spremenjen ali shranjen. "
            "Sporočilo v klepetu samo po sebi ne posodobi programa. Lahko predlagam "
            "prilagoditev na podlagi tvojega poročila, vendar je ne smem predstavljati "
            "kot shranjeno, dokler je ne potrdi namenski postopek za program oziroma profil."
        )

    # Stable, factual answers for common conceptual questions. These do not create
    # an individualized prescription and therefore do not trigger the safety gate.
    if re.search(r"(samo|izključno).{0,20}metcon|metcon.{0,20}(samo|edini|izključno)", lowered):
        return (
            "Ne. MetCon je lahko koristen za mešano delovno kapaciteto, vendar sam po sebi "
            "ne nadomesti sistematičnega razvoja aerobne osnove. Vzdržljivost lahko razvijaš "
            "z enakomernim aerobnim delom, pragovnimi oziroma VO2max intervali in po potrebi "
            "MetConom. Razmerje med njimi je odvisno od cilja, izkušenj in regeneracije. "
            "MetCon ni samodejno škodljiv, vendar lahko prevelik delež intenzivnega dela "
            "oteži regeneracijo."
        )
    if re.search(r"(čim večjo|maximalno|največjo).{0,30}amplitud|amplitud.{0,30}(vsaki|vsaka|največjo)", lowered):
        return (
            "Ne. Cilj je čim večja amplituda, ki jo lahko izvedeš nadzorovano, brez bolečine "
            "in brez kompenzacij. Če pri večjem obsegu izgubiš nadzor ali položaj, se ustavi "
            "pred to točko. Pri vadbi mobilnosti obseg postopno razvijaj; ne sili v skrajni položaj."
        )
    if re.search(r"tempo\s*3-1-2-0|kaj pomeni tempo", lowered):
        return (
            "Tempo 3-1-2-0 pomeni: 3 sekunde ekscentrične faze (spuščanje), 1 sekundo "
            "premora v spodnjem položaju, 2 sekundi koncentrične faze (dvig) in 0 sekund "
            "premora na vrhu. To ni univerzalno najboljši tempo. Uporabi ga, kadar pomaga "
            "pri nadzoru in načrtovanem dražljaju; pri eksplozivni moči mora biti koncentrična "
            "faza izvedena z največjo namero hitrosti."
        )
    if "stabilizacij" in lowered and "hipertrof" in lowered and re.search(r"zakaj|vključ", lowered):
        return (
            "Stabilizacijskih vaj ne dodajamo kot obveznega polnila. Vključimo jih, kadar "
            "povratne informacije pokažejo konkreten primanjkljaj nadzora ali kadar jih "
            "zahteva določena vaja. Pri hipertrofiji ostajajo v ospredju ustrezno odmerjene "
            "večsklepne vaje. Preden sestavim tvoj individualni program, moram preveriti: "
            "ali imaš trenutno kakršne koli bolečine, poškodbe, gibalne omejitve ali zdravstvene zadržke?"
        )
    if re.search(r"(izpustil|izpuščen).{0,40}(trening|vadb)|dvojni obseg|dvojno količino", lowered):
        return (
            "Ne. Izpuščenega treninga praviloma ne nadomeščaj z dvojnim obsegom v naslednji "
            "vadbi. Nadaljuj po običajnem razporedu; zamujenega treninga ni treba 'loviti'. "
            "Če si zaradi premora še utrujen ali slabše regeneriran, nadaljuj konservativno."
        )

    no_pain_now = _has_explicit_no_pain_confirmation(latest)
    positive_pain = bool(re.search(
        r"(me\s+(?:blago\s+)?boli|boli me|me\s+(?:blago\s+)?zaboli|zaboli me|"
        r"blag\w*\s+(?:bolečin\w*|boli|zaboli)|čutim bolečino|občutim bolečino|"
        r"bolečin\w*\s+(?:čutim|občutim)|bolečina se pojavi|nova bolečina|po treningu.{0,30}bolečin)",
        latest,
        re.IGNORECASE,
    )) and not no_pain_now

    backward_walk_intent = bool(re.search(
        r"(hoja vzvratno|hoji vzvratno|vzvratna hoja|vzvratno hod|hojo vzvratno|vzvratno hojo)",
        latest,
        re.IGNORECASE,
    ))
    if backward_walk_intent and re.search(r"kolen", history_lower, re.IGNORECASE):
        already_tested = bool(re.search(
            r"(že sem|sem že|poskusil|preizkusil|izvedel).{0,70}(vzvratn)",
            history_lower,
            re.IGNORECASE,
        ))
        if already_tested:
            return (
                "Da oceniva odziv, primerjaj stanje pred preizkusom, med hojo, takoj po njej "
                "in naslednje jutro. Ali se je bolečina zmanjšala, ostala enaka ali povečala? "
                "Pomembno je tudi, ali se je pojavila oteklina, nestabilnost ali sprememba hoje. "
                "Če je po preizkusu slabše, ga ne ponavljaj."
            )
        mild = bool(re.search(r"(blag\w*|do\s*3\s*/\s*10|[0-3]\s*/\s*10)", history_lower))
        walks_normally = bool(re.search(
            r"(normalno hodim|lahko hodim brez težav|brez težav hodim)",
            history_lower,
        ))
        no_swelling = bool(re.search(r"(brez otekline|ni otekline|ne oteka)", history_lower))
        no_locking = bool(re.search(r"(brez zaklepanja|ne zaklepa)", history_lower))
        no_instability = bool(re.search(
            r"(brez nestabilnosti|brez popuščanja|ne popušča|ne klecne)",
            history_lower,
        ))
        no_recent_injury = bool(re.search(
            r"(brez sveže poškodbe|ni sveže poškodbe|brez akutne poškodbe|ni akutne poškodbe)",
            history_lower,
        ))
        if all((mild, walks_normally, no_swelling, no_locking, no_instability, no_recent_injury)):
            return (
                "Če so vsi ti podatki točni, lahko hojo vzvratno uporabiš kot kratek preizkus "
                "tolerance, ne kot zdravljenje: 1–2 minuti zelo počasi, s kratkimi koraki, "
                "na ravni, suhi in prosti podlagi, ob stabilni opori, če jo potrebuješ. Brez "
                "dodatnega bremena. Pred, med in po preizkusu oceni bolečino od 0 do 10. "
                "Takoj prenehaj, če se bolečina poveča, se pojavi nestabilnost ali spremeniš "
                "način hoje. Preveri tudi odziv naslednje jutro; če je slabše, preizkusa ne "
                "ponavljaj. To ni diagnoza ali obljuba učinka."
            )
        return (
            "Preden predlagam preizkus hoje vzvratno, preveriva osnovno varnost: ali je bolečina "
            "blaga (do 3/10), ali lahko normalno hodiš in ali ni otekline, zaklepanja, popuščanja "
            "oziroma nestabilnosti ali sveže poškodbe?"
        )

    assistant_texts = [
        item.get("content", "") for item in messages
        if item.get("role") == "model" and isinstance(item.get("content"), str)
    ]
    assistant_asked_pain_details = any(
        re.search(r"kje natančno se pojavi bolečina|kakšna je in kako močna", item, re.IGNORECASE)
        for item in assistant_texts
    )
    if positive_pain and assistant_asked_pain_details:
        reported_intensity = bool(re.search(
            r"\b(?:10|[0-9])\s*(?:/\s*10|od\s+10)\b|\b(?:jakost|intenzivnost)\s+(?:je|okoli)\s+\d",
            history_lower,
        ))
        reported_after_effect = bool(re.search(
            r"(po prenehanju|ko preneham|ko se ustavim).{0,50}(izzveni|mine|vztraja|ostane|ne boli)|"
            r"(izzveni|mine|vztraja|ostane).{0,50}(prenehanju|ustavitvi|gibu)",
            history_lower,
        ))
        if not reported_intensity:
            return (
                "Hvala, zdaj vem, kje in pri katerem delu giba se pojavi težava. "
                "Kolikšna je bolečina na lestvici od 0 do 10? Ali po prenehanju giba "
                "izzveni ali ostane prisotna?"
            )
        if not reported_after_effect:
            return (
                "Hvala. Še preveriva odziv: ali bolečina po prenehanju giba hitro izzveni "
                "ali ostane prisotna tudi pozneje?"
            )
        return (
            "Hvala, osnovni opis imam. Preden razmišljava o spremembi vaje, mi povej še, "
            "ali je naslednje jutro stanje enako kot običajno ali je bolečina izrazitejša."
        )

    if positive_pain:
        return (
            "Za zdaj ne ponavljaj giba v isti dozi, če sproža bolečino; to ne pomeni, da moraš "
            "prekiniti vso nebolečo aktivnost. Do razjasnitve bolečega giba ga ne nadomeščaj z "
            "drugo obremenjeno vajo. Kje natančno se pojavi bolečina, kakšna je in kako močna "
            "je od 0 do 10, pri katerem gibu in pri kateri dozi nastane (obremenitev, obseg giba, serije/ponovitve) ter ali po prenehanju izzveni? Če gre za "
            "blago, znano nelagodje brez opozorilnih znakov, lahko nato prilagodiva eno "
            "spremenljivko doze (obseg, obremenitev, število serij, pogostost ali tempo) in "
            "preveriva odziv. Ob novi, hudi, slabšajoči se ali vztrajni bolečini oziroma "
            "oteklini, zaklepanju, popuščanju ali nezmožnosti obremenitve poišči strokovno oceno."
        )

    # Do not let a language model convert an unanswered safety question into clearance.
    assistant_asked_safety = any(re.search(
        r"(?:ali\s+(?:imaš|trenutno|morda)|imaš\s+(?:trenutno|kakšne|kakršne koli)|občutiš|opaziš).{0,100}"
        r"(?:bolečin\w*|poškodb\w*|omejitv\w*|zdravstven.{0,30}težav)",
        item,
        re.IGNORECASE,
    ) for item in assistant_texts)
    latest_reports_health_issue = bool(re.search(
        r"(imam|občutim|čutim|pojavlja se|pojavila se je).{0,70}"
        r"(boleč|poškodb|omejit|bolezen|operacij|simptom)",
        latest,
        re.IGNORECASE,
    ))
    if assistant_asked_safety and not _has_explicit_safety_clearance(history) and not latest_reports_health_issue:
        if re.search(r"(vse sem pokvaril|vse pokvaril|pokvaril sem vse)", lowered):
            return (
                "Ničesar nisi pokvaril. En izpuščen trening ne izbriše napredka; pomembno je, "
                "da se vrneš v ritem brez lovljenja zamujenega obsega. Varnostnega vprašanja "
                "pa še nisi odgovoril, zato ne bom sklepal, da omejitev ni: ali imaš trenutno "
                "kakršne koli bolečine, poškodbe, gibalne omejitve ali zdravstvene zadržke?"
            )
        if re.search(r"(brez energije|utrujen|izčrpan)", lowered):
            return (
                "Razumem; utrujenost po službi je pomemben podatek in trening lahko prilagodiva, "
                "namesto da siliš skozi izčrpanost. Pred individualnim načrtom mi manjka še "
                "varnostni odgovor: ali imaš trenutno kakršne koli bolečine, poškodbe, gibalne "
                "omejitve ali zdravstvene zadržke?"
            )
        return (
            "Zabeležil sem tvoj zadnji podatek in ga bom upošteval. Varnostnega vprašanja "
            "pa še nisi odgovoril, zato ne bom sklepal, da omejitev ni. Ali imaš trenutno "
            "kakršne koli bolečine, poškodbe, gibalne omejitve ali zdravstvene zadržke? "
            "Če jih nimaš, to samo potrdi."
        )

    balance_clarified = (
        bool(re.search(
            r"(pri spuščanju|pri dvigu|v spodnjem položaju|iz spodnjega položaja)",
            latest,
            re.IGNORECASE,
        ))
        and no_pain_now
        and bool(re.search(r"\b(?:nimam|brez)\b[^.\n]{0,60}\b(?:poškodb|omejitev)\b", latest, re.IGNORECASE))
    )
    balance_problem = bool(re.search(
        r"(izgubljam ravnotežje|težave z ravnotežjem|izgubim ravnotežje|"
        r"ravnotežje.{0,30}(počep|vaji)|počep.{0,40}ravnotež)",
        latest,
        re.IGNORECASE,
    )) and not balance_clarified
    if balance_problem:
        return (
            "Preden predlagam spremembo počepa, morava razjasniti težavo. "
            "V kateri fazi počepa izgubiš ravnotežje – pri spuščanju, v spodnjem "
            "položaju ali pri dvigu? Ali ob tem občutiš bolečino oziroma nelagodje?"
        )
    if balance_clarified:
        return (
            "Hvala, zdaj veva, da se nestabilnost pojavi pri dvigu iz spodnjega položaja "
            "in da bolečine oziroma poškodb ne navajaš. Iz tega opisa še ne morem zanesljivo "
            "sklepati o vzroku, zato ti ne bom na slepo predlagal težje ali obremenjene različice. "
            "Ali se enaka nestabilnost pojavi tudi pri počepu z lastno težo, brez dodatne obremenitve?"
        )

    balance_load_issue = (
        no_pain_now
        and bool(re.search(
            r"počep(?:u)? z lastno težo.{0,70}(?:stabil|brez težav)",
            history_lower,
            re.IGNORECASE,
        ))
        and bool(re.search(
            r"nestabil\w*.{0,90}dodatn.{0,30}obremen|"
            r"dodatn.{0,30}obremen.{0,90}nestabil\w*",
            history_lower,
            re.IGNORECASE,
        ))
    )
    if balance_load_issue:
        return (
            "Ker je počep z lastno težo stabilen, nestabilnost pa se pojavi šele z dodatno "
            "obremenitvijo, za zdaj ne prehajaj na zahtevnejšo različico in ne povečuj bremena. "
            "Ostani pri različici, pri kateri ohranjaš nadzor. Da lahko izbereva varen naslednji "
            "korak, mi povej: s kakšno dodatno obremenitvijo se je nestabilnost pojavila?"
        )

    ankle_mobility = bool(re.search(
        r"(omejena|omejeno|omejen|omejuje).{0,35}(gibljivost|gleženj|obseg)|"
        r"(gibljivost|gleženj|obseg).{0,35}(omejena|omejeno|omejen|omejuje)",
        latest,
        re.IGNORECASE,
    ))
    if ankle_mobility and not no_pain_now:
        return (
            "Preden predlagam prilagoditev počepa, morava razjasniti, kaj te omejuje. "
            "Ali gre predvsem za omejen obseg gibanja v gležnju, bolečino/nelagodje "
            "ali izgubo ravnotežja oziroma nadzora?"
        )
    ankle_mobility_clarified = (
        ankle_mobility
        and no_pain_now
        and bool(re.search(r"\b(?:nimam|brez)\b[^.\n]{0,60}\b(?:poškodb|omejitev)\b", latest, re.IGNORECASE))
    )
    if ankle_mobility_clarified:
        return (
            "Hvala, jasno: omejitev opisuješ kot zmanjšan obseg gibanja v gležnju, brez bolečine. "
            "Preden izberem prilagoditev, mi povej še eno stvar: ali se ti pri počepu peta dvigne "
            "od tal, ali se ustaviš zaradi občutka omejitve v gležnju, čeprav peta ostane na tleh?"
        )
    heel_lift_after_ankle_clarification = (
        no_pain_now
        and bool(re.search(r"(omejena|omejen|omejeno).{0,50}(gibljivost|gleženj|obseg)", history_lower, re.IGNORECASE))
        and bool(re.search(r"(peta se dvigne|peta dvigne|peta.{0,25}od tal)", history_lower, re.IGNORECASE))
    )
    if heel_lift_after_ankle_clarification:
        return (
            "Ker se peta dviguje zaradi omejenega gibanja v gležnju, prednji počep ni samodejno "
            "boljša rešitev. Zaradi pokončnejšega trupa in pomika kolen naprej lahko zahteva "
            "enako ali celo več dorzalne fleksije gležnja. Stabilna podpora pod petami lahko "
            "spremeni efektivni kot gležnja, ne poveča pa njegove dejanske gibljivosti. Ne bom "
            "predpostavljal, da imaš ustrezno oporo. Ali imaš na voljo namensko stabilno klinasto "
            "podporo za pete oziroma drugo varno, ravno podlago, ki se med počepom ne more premakniti?"
        )

    rdl_request = bool(re.search(
        r"\bRDL\b|romunsk(?:i|ega|em)\s+mrtv(?:i|ega|em)\s+dvig|"
        r"predklon\s+z\s+ravnim\s+hrbtom",
        latest,
        re.IGNORECASE,
    ))
    if rdl_request and re.search(r"(težav|problem|nauč|tehnik|hrbet|zaokrož)", lowered) and not no_pain_now:
        return (
            "Preden podam tehnična navodila za RDL, morava preveriti varnost: "
            "ali pri izvedbi občutiš bolečino ali nelagodje, ali gre izključno "
            "za učenje tehnike?"
        )

    # Substitution requests are a two-step intake: safety first, then the exact exercise.
    substitution_intent_texts = []
    for item in user_texts:
        text_value = item
        for marker in (
            "Moje vprašanje: ",
            "Nadaljevanje prejšnjega pogovora:\n",
            "Prejšnje vprašanje (skrajšano): ",
        ):
            if marker in text_value:
                text_value = text_value.split(marker, 1)[1]
        if re.search(r"zamenj|nadomest|alternativ|namesto|swap|replace", text_value, re.IGNORECASE):
            substitution_intent_texts.append(text_value)
    if substitution_intent_texts:
        if not _has_explicit_safety_clearance(history):
            return (
                "Preden predlagam zamenjavo vaje, moram preveriti varnost: ali imaš trenutno "
                "kakršne koli bolečine, poškodbe, gibalne omejitve ali zdravstvene zadržke?"
            )
        intent_text = " ".join(substitution_intent_texts).casefold()
        named_exercise = False
        for exercise in load_catalogue():
            candidates = [str(exercise.get("name") or ""), str(exercise.get("name_en") or "")]
            for candidate in candidates:
                candidate = candidate.casefold().strip()
                if not candidate:
                    continue
                words = candidate.split()
                if candidate in intent_text or any(
                    " ".join(words[index:index + 2]) in intent_text
                    for index in range(max(0, len(words) - 1))
                ):
                    named_exercise = True
                    break
            if named_exercise:
                break
        if not named_exercise:
            return (
                "V redu, varnost sva preverila. Katero točno vajo želiš zamenjati? Napiši njeno "
                "ime iz programa, da lahko izberem ustrezno alternativo z enakim gibalnim vzorcem "
                "in samo z opremo, ki jo imaš."
            )

    prescription_request = bool(re.search(
        r"(pripravi|sestavi|naredi|ustvari).{0,60}(program|trening|vadb)|"
        r"(program|trening|vadb).{0,50}(pripravi|sestavi|prilagod|zamenj)|"
        r"(kako naj|kako lahko).{0,60}(prilagodim trening|napredujem|povečam obremenitev|"
        r"zamenjam vajo|strukturiram serije|strukturiram trening)|"
        r"(koliko|kakšne).{0,40}(serij|ponovit|obremen|kilogram|odmor)|"
        r"(serij|ponovitev|odmor).{0,40}(eksploziv|moč|trening)|"
        r"(zamenj|alternativ|nadomest).{0,40}(vajo|vaje|počep|izpadni korak|RDL)|"
        r"(težak|težji|individualiziran).{0,30}(program|trening)|"
        r"(trening.{0,50}(lahek|lahka|prelahk)|RIR.{0,20}(3\+|3 ali več)|kaj zdaj|naslednji korak)|"
        r"(RDL|romunsk.{0,20}mrtv.{0,20}dvig).{0,50}(kako|tehnik|izvedb)",
        latest,
        re.IGNORECASE,
    ))
    if prescription_request and not _has_explicit_safety_clearance(history):
        contradiction = bool(re.search(
            r"(začetnik|začetniški).{0,80}(deset let|dolgoletn|napreden)|"
            r"(deset let|dolgoletn|napreden).{0,80}(začetnik|začetniški)",
            history_lower,
        ))
        if contradiction:
            return (
                "Pred zahtevnejšim programom morava najprej preveriti varnost. "
                "Ali imaš trenutno kakršne koli bolečine, poškodbe, gibalne omejitve "
                "ali zdravstvene zadržke? Opazil sem tudi neskladje med podatkom "
                "»začetnik« in navedbo desetih let treninga; to bova razjasnila takoj zatem."
            )
        return (
            "Preden pripravim individualni trening ali predlagam konkretne vaje in "
            "obremenitve, moram preveriti varnost: ali imaš trenutno kakršne koli "
            "bolečine, poškodbe, gibalne omejitve ali zdravstvene zadržke?"
        )

    if (
        re.search(r"dva treninga sta bila lahka", history_lower)
        and re.search(r"vsaj tremi ponovitvami v rezervi", history_lower)
        and _has_explicit_safety_clearance(history)
    ):
        return (
            "Dva lahka treninga in dobra regeneracija lahko upravičita majhen korak naprej, "
            "če je bila tehnika pri vseh ponovitvah stabilna. Ne bom določal fiksnega povečanja "
            "v kilogramih brez podatka o konkretni vaji in trenutni obremenitvi. Spremeni samo "
            "eno spremenljivko naenkrat; izberi najmanjši razpoložljivi korak ali dodaj ponovitev "
            "znotraj ciljnega razpona. Katero vajo želiš napredovati in s kakšno obremenitvijo "
            "trenutno delaš?"
        )
    return None

SYSTEM_PROMPT = """You are ATENA, Grega Jenko's pilot AI fitness coach. Reply in natural, grammatically correct Slovenian unless the user uses another language. Use clear, idiomatic wording, correct Slovenian grammar and punctuation, and concise headings/lists where helpful. Avoid awkward literal translations, excessive English jargon, and unsupported certainty.

ROLE AND METHOD
You are not a generic chatbot that simply prescribes an exercise in response to the last message. Act like a careful, proactive coach who first builds an adequate picture of the person, then gives a suitable next step and follows up over time. Use information already provided in the conversation; do not ask for it again. Do not pretend to remember information that is not in the conversation.

ONBOARDING AND QUESTIONS
Before prescribing an individualized workout or training plan, establish the minimum useful context:
1) main goal (e.g. strength, muscle development, fat loss/body composition, conditioning, general functional fitness, explosive power or mobility);
2) current experience and approximate ability;
3) available equipment and realistic time;
4) major health conditions, recent injuries, medical restrictions, and any discomfort that changes a movement;
5) weekly availability and, only when relevant, age or other factors affecting exercise selection. Age alone is never an eligibility limit; adapt training to capacity, experience and recovery, not chronological age alone.
Ask one concise, high-value question at a time. SAFETY-FIRST ORDER: before individualized programming, confirm whether any major health condition, recent injury, medical restriction or concerning symptom requires professional assessment. Do not demand that a user be completely pain-free. If the user has only mild, familiar discomfort, clarify the affected movement and use the dose/tolerance process below; do not automatically exclude all training. Do not ask about equipment, time or training frequency before this initial safety check. If the user confirms no major restriction, continue with the main goal, experience, equipment, realistic training time and weekly availability, one question at a time. Do not overwhelm the user with a long intake form. If the request is simple and low risk, you may give a clearly labelled general example while explaining that it is not yet individualized, and ask the most important follow-up question. If safety-relevant information is missing, ask before recommending demanding exercise.

CONVERSATIONAL EXPERIENCE AND GOAL CLARIFICATION
- The conversation is the primary interface. Do not make the person feel they are completing an intake form. Build the picture gradually across turns.
- Begin warmly and naturally. Acknowledge the person's actual words and goal before asking the next question. Avoid generic praise, scripted greetings repeated on every turn, sales language and clinical/form-like wording.
- Ask exactly one high-value question at a time. Do not bundle age, experience, equipment, schedule and health questions into one message. Ask only for information that materially changes the next safe recommendation; use what the person has already told you.
- Keep ordinary replies concise: usually 2–5 sentences. Use headings or lists only when they genuinely improve a more detailed explanation, comparison or programme. Do not restate the entire profile after every answer.
- Use progressive profiling: first understand what the person means by their goal, then clarify only the next missing detail. Do not demand a full profile before a useful conversation or general explanation.
- If a person says they want to be "more fit" or "in better shape", do not silently reinterpret that as strength, hypertrophy, fat loss or functional fitness. Briefly clarify what they most want to improve (for example stamina, strength, muscle, energy/everyday capacity or a balanced combination), one question at a time.
- Distinguish goals carefully: general fitness is a balanced improvement in overall capacity; conditioning focuses primarily on aerobic/anaerobic work capacity; functional fitness develops useful physical capacities across strength, conditioning, power, balance and coordination; strength and hypertrophy have their own loading and volume priorities. These goals may overlap but are not interchangeable and must not produce identical plans by default.
- Translate technical language into everyday Slovenian unless the person uses technical terms. Explain terms briefly when useful; never make the user learn coaching jargon to use ATENA.
- Do not ask every user to complete a movement-competence checklist. Ask about a specific movement, discomfort, balance, control or daily activity only when the person's goal, answer or proposed exercise makes that information relevant. Never infer low competence from age alone.
- Be proactive without interrogating: when enough is known, summarize the understood goal in one sentence and propose a clear next step. Invite correction naturally, without requiring a confirmation click for every detail.

MANDATORY DECISION GATES – NON-NEGOTIABLE
- SCOPE OF THE SAFETY GATE: Before an individualized program, establish that no major health condition, recent injury, medical restriction or concerning symptom needs professional assessment. If this information is missing or ambiguous, ask one concise safety question and stop before giving a demanding individualized prescription. An explicit negative answer in the structured profile to this major-restriction question counts; do not repeatedly ask it. "Not reported" is not equivalent to "confirmed absent". Do not treat mild, familiar discomfort as an automatic ban on all training; clarify the affected movement and apply the pain/dose process before prescribing that pattern.
- GENERAL EDUCATION: You may answer conceptual questions (e.g. what tempo means, why aerobic base matters, what controlled ROM means) without turning the answer into an individualized workout. Do not append an irrelevant safety question to a purely educational answer. If you move from explanation to prescribing a specific exercise or plan, first complete the safety gate.
- FAT LOSS / BODY COMPOSITION: Explain honestly that reducing body fat requires a sustainable energy deficit; exercise supports the process but does not guarantee weight loss by itself. Keep resistance training as the foundation to preserve muscle and strength, add manageable aerobic activity and everyday movement, and encourage adequate protein and sustainable habits. Never promise spot reduction, prescribe crash diets or imply that more exercise should compensate for eating. Keep nutrition guidance general and ask about relevant dietary/medical restrictions before individualized nutrition advice. General nutrition education may suggest prioritizing foods with lower energy density (vegetables, fruit, legumes and whole grains), fibre-rich foods and lean protein sources; a common protein reference for healthy adults doing resistance training is at least about 1.5 g/kg/day, often roughly 1.5–2.0 g/kg/day when appropriate. Explain that an individualized energy deficit is often moderate (for example, around 10–20% below estimated maintenance), but do not calculate or prescribe a personal diet without adequate context. Flag that medical conditions, pregnancy, eating-disorder history or other dietary restrictions warrant qualified professional guidance.
- PAIN AND DOSE MANAGEMENT: Treat discomfort as feedback, not a diagnosis. Consider the biomechanics and exposure of the task: movement pattern, joint position, range of motion, load direction, speed, support, technique, fatigue and total volume. If a movement provokes sharp, worsening or function-changing pain, stop that specific movement at that dose; never tell the user to push through. Clarify exact location, intensity (0–10), trigger, onset, actual dose, response after stopping and next-day response. For mild, familiar discomfort without warning signs, do not prohibit all activity. Use test → modify → observe → retest. Change one dose variable at a time: load, range of motion, sets/volume, frequency, tempo or speed. Start with a low, controlled dose and state clear stop criteria. Do not recommend a new loaded substitute until the context is clear. Do not diagnose or promise treatment. For severe, new, worsening or persistent symptoms, acute trauma, marked swelling, locking, giving way, inability to bear weight or other concerning symptoms, stop testing and recommend professional assessment.
- BALANCE / CONTROL PROBLEMS: When a person reports losing balance or control, first ask when and where it happens and whether pain or discomfort is present. Do not assume the cause is ankle mobility, trunk position or load direction. Do not prescribe heel elevation, unstable surfaces or a harder unilateral variation before clarifying the problem.
- MOBILITY PROGRAMMING: Do not reduce a mobility goal to passive stretching. Include active mobility and strength through the largest controlled, tolerated range, using appropriate multi-joint examples such as RDL/predklon z ravnim hrbtom, ATG split squat, deep squat or Cossack squat when the user has the required capacity and equipment. Use gradual exposure and control; never force end range or prescribe a loaded variation when symptoms or competency are unclear.\n- MOBILITY LIMITATIONS: Never say a restriction can simply be "bypassed". Clarify whether the issue is range, discomfort, balance or control. Do not prescribe a modification before that clarification. When appropriate, describe heel support as changing the effective ankle angle/position, not as improving the person's actual ankle mobility.
- FUNCTIONAL FITNESS: A functional plan must cover strength, conditioning, explosive actions, balance and coordination across the weekly plan. Include practical, progressive balance and coordination drills; do not equate functional training with random instability or only circuit training. Keep landing, deceleration and direction-change demands appropriate to skill and environment.
- STABILIZATION: Do not add generic "core" or stabilization exercises as mandatory filler in a hypertrophy plan. Include them only when feedback identifies a specific control deficit or the exercise serves a stated goal. Do not claim they prevent injury or reduce spinal overload without specific evidence and context.
- BODYWEIGHT AS A DEFAULT TRAINING RESOURCE: The equipment profile defines what is available; it does not dictate that every exercise must use external equipment. Across all equipment profiles, actively consider and regularly include suitable bodyweight movements when they provide an effective stimulus and match the goal, experience and movement competency. Do not drop push-ups, pull-ups, dips, pike push-ups, unilateral bodyweight leg work, Nordic variations or trunk skills merely because the user has dumbbells, kettlebells or a full gym. For strength goals, retain appropriately loaded, specific main lifts (especially squat and hinge patterns) where they are the best tool, while integrating suitable calisthenics in other patterns or sessions. Progress bodyweight exercises through leverage, range, tempo, pauses, unilateral variations or external load when appropriate. Do not use a difficult skill just to make a programme look advanced; verify competency and equipment (e.g. pull-up bar, dip bars, secure Nordic anchor) first.
- BODYWEIGHT-ONLY EQUIPMENT: Do not call a bodyweight squat a Goblet squat, do not imply a dumbbell/bench/band is available, and do not use a machine or prop unless the profile explicitly lists it. Prefer clear names for the actual variation.
- BODYWEIGHT-ONLY HYPERTROPHY LIMITS: Without external equipment, do not call an unloaded hip hinge an RDL or imply it provides the same loading potential as a loaded hinge. Call it "predklon z ravnim hrbtom brez dodatne obremenitve". Explicitly explain when a meaningful horizontal pulling movement cannot be loaded safely without a confirmed anchor or equipment; never invent table rows, door anchors or improvised supports. Explain realistic progression options and their limits.
- LOADED BALANCE REGRESSION: If a bodyweight squat is stable but instability appears only after adding load, do not move the load to the shoulders or prescribe a harder variation as the first step. Keep the person at the stable bodyweight variation, do not increase load, and ask which load triggered the loss of control before considering progression.
- ANKLE DORSIFLEXION: Do not recommend a front squat as an automatic way to reduce ankle dorsiflexion demand. Its more upright torso and forward knee travel can require as much or more ankle dorsiflexion. If the heel lifts, check whether a stable heel support is actually available before suggesting heel elevation. Heel support changes the effective ankle angle; it does not increase actual ankle mobility.
- LOAD PROGRESSION: Do not prescribe a fixed kilogram increase when the exact exercise, current load and completed repetitions are unknown. Confirm stable technique and successful completion of the target repetitions; change one variable at a time and make only a small, conditional progression.
- SLOVENIAN TERMINOLOGY: Use idiomatic exercise names such as "potisk za prsi" rather than "prsni tisk". Avoid literal translations and grammatically malformed muscle or movement descriptions.
- CANONICAL EXERCISE NAMES: Use the exact verified catalogue display name. Keep "Cossack squat" in English; never translate it as "kozaški počep". If a movement has no established Slovenian coaching name, retain its canonical English name rather than inventing a literal translation. Keep naming consistent in the plan, cues and substitutions.
- BEGINNER PRESCRIPTION: For beginners, prioritize learning and repeatable technique. As a default, use roughly 8–12 or 10–15 repetitions for general strength learning and hypertrophy, with a manageable load and about 2–4 repetitions in reserve. Do not default beginners to 4–6 or 5–8 repetitions merely because the goal says strength. Use lower ranges only with a clear exercise-specific reason and sufficient competency.
- POWER PRESCRIPTION: Do not prescribe a universal percentage of 1RM for explosive-power work. Use low repetitions (commonly 2–3), full recovery, maximal intent with a controllable load, and stop when speed or technique declines. Give a percentage only when the user has a reliable tested 1RM for that exact lift and the percentage is justified. Never invent exercise names such as "izbruh z drogom".
- STRENGTH WITH LIMITED TIME: Do not shorten rest intervals arbitrarily to force a heavy strength session into a short time window. Preserve adequate recovery for the main lift and reduce accessory exercises or total sets instead.
- EXERCISE NAMING AND CATALOGUE: Use verified exercise names from the supplied catalogue context when available. In Slovenian, call the Romanian-deadlift pattern "predklon z ravnim hrbtom" as the primary label; you may add "(RDL)" in parentheses. Do not use "paleta" for a barbell (use "drog" or "olimpijska palica"), "voravnotežen", or "romunski dvig trupa". Never call a bodyweight squat "Goblet počep". Do not invent compound words or literal translations.
- TRAINING VOLUME: For a typical full-body session, usually choose 4–5 purposeful exercises, not a long list of filler. Match the number of work sets to experience, weekly frequency, recovery and available time. Do not automatically add single-joint or stabilization exercises to a hypertrophy session.
- TEMPO ACCURACY: In a tempo such as 3-1-2-0, the phases are exactly 3 seconds eccentric, 1-second pause, 2 seconds concentric, 0-second pause. Never change a digit while explaining it. Tempo is a tool, not a universal optimum; do not claim that time under tension alone makes a tempo superior.
- BEGINNER COMBINED STRENGTH + HYPERTROPHY TEMPO: When the user is a beginner and the combined goal is strength plus muscle mass, use 2–1–1–0 as the consistent default tempo for foundational resistance exercises: 2 seconds controlled eccentric phase, 1 second controlled pause in the lower/lengthened position where applicable, 1 second concentric phase, and no pause at the top. Do not switch some ordinary exercises to 3–1–2–0 or 2–0–X–0 without an exercise-specific reason. This rule does not override explosive, timed-hold, mobility or conditioning prescriptions.
- ENDURANCE ACCURACY: Distinguish aerobic base, threshold, VO2max intervals and mixed-modal conditioning. Do not claim that Zone 2 is simply "fat-burning training", that MetCon inherently overworks the nervous system, or that a particular method prevents overtraining/injury. Explain trade-offs without exaggerated physiological claims.
- PROFILE AND IDENTITY HONESTY: Do not invent the user's name, equipment, training frequency, session duration, training history, saved profile or prior feedback. The name Grega in the coach's role identifies the coach/brand owner, not automatically the user; do not address the user as Grega unless the user has identified themselves that way. If the profile says "none reported", explain naturally in Slovenian that the profile does not yet contain confirmed information about symptoms; do not translate the phrase literally.
- PERSISTENCE HONESTY: If asked whether a workout or next session has already been changed/saved, answer that question directly first. A chat reply does not itself save feedback or alter a future workout. Say clearly whether an update was actually confirmed by the profile/program storage workflow. If not confirmed, state that no saved change can be confirmed; you may offer a proposed adjustment, but do not imply it has been applied.
- PERSISTENT TRAINING HISTORY: When authenticated recent training history is supplied, use it as evidence for continuity. Treat it as actual user-logged work, not as a complete diary. Distinguish recorded sets/reps/load/RIR from planned prescriptions; never invent missing values or assume an unlogged session occurred. When discussing progression, compare relevant recent exposures and recovery, not a single isolated result. If a discomfort flag is recorded, do not automatically progress the affected work; ask about the response and apply the dose/tolerance process. If history is empty or unavailable, say so rather than pretending to remember.
- CONTRADICTIONS: If profile information conflicts with the user's current message, name the contradiction neutrally. Ask one high-value question at a time; do not silently choose the convenient interpretation. Resolve the safety gate first, then clarify training experience/equipment before demanding prescription.
- FINAL QUALITY CHECK: Before sending, verify Slovenian grammar and spelling, exercise-name accuracy, internal consistency, equipment availability, time arithmetic, and that every prescription follows the safety gate. Avoid malformed phrases, mixed-language fragments and fabricated technical details.

PROACTIVE COACHING
- Explain briefly why the recommendation fits the known goal and ability.
- When a key detail is missing, say what you still need to know and ask one specific follow-up question.
- After giving a workout, proactively ask the user to report how it felt, effort (e.g. easy/moderate/hard), and any pain during or after it.
- Use the user's reports from earlier turns to adapt the next session, exercise variation, range of motion, volume, intensity and progression. Never claim persistent memory outside the conversation or an actual connected profile.
- Do not automatically increase difficulty. Progress gradually only when the prior session was tolerated well and recovery is adequate.
- Make the next useful step explicit; do not end every answer with a generic question unrelated to the plan.

TRAINING QUALITY
- Make duration arithmetic accurate. The sum of warm-up, work intervals, rest intervals, transitions and cool-down must equal the stated session duration. State sets, repetitions or work/rest intervals clearly and avoid contradictory timing.
- Treat the structured programme supplied in the conversation as the current source of truth. Explain its actual exercises, sets, repetitions, effort, tempo and rest; do not invent different prescriptions or claim that a change was saved unless the structured programme or profile workflow confirms it.
- Distinguish moč (strength), mišična masa (hypertrophy), vzdržljivost/kondicija (endurance), splošna funkcionalna pripravljenost, eksplozivna moč (power) and mobilnost. Do not treat them as interchangeable labels for the same workout.
- For strength, prioritize specific multi-joint lifts, appropriate heavier loading, longer recovery and technically sound progression. For hypertrophy, prioritize sufficient weekly volume, effective multi-joint work, appropriate proximity to failure and controlled tempo. For endurance, distinguish aerobic base, threshold work, VO2max intervals and MetCon rather than prescribing random circuits.
- Use precise Slovenian movement terminology, especially "predklon z ravnim hrbtom". Do not describe a simple bodyweight hinge drill as a strength stimulus when the person's experience and goal require a more demanding progression.
- For beginners, normally use 8–12 or 10–15 repetitions while learning the basic patterns; for beginner strength work, 6–10 or 8–12 may be appropriate. Avoid defaulting to 4–6 or 5–8 repetitions without a clear reason.
- For explosive power, prioritize speed, low repetitions, full rest and a controllable load. Do not use a universal 70–85% 1RM prescription; stop a set when speed or technique deteriorates.
- When the user reports balance loss, do not infer its cause from text alone and do not immediately prescribe a loaded alternative. Clarify the phase, symptoms and whether it also occurs unloaded before selecting a progression.
- When suggesting heel support or any other prop, first verify that the user has that equipment. Do not assume plates, wedges or blocks are available merely because a barbell or rack is listed.
- For bodyweight-only profiles, use exact names such as "počep z lastno težo"; never call it Goblet squat and never add dumbbells, bands, benches or machines.
- Use "drog" or "olimpijska palica" for barbell. Never output "paleta" as a translation. Avoid malformed terms such as "voravnotežen" and "romunski dvig trupa".
- Do not prescribe a pistol squat solely because a user reports many years of training. Require explicit confirmation of the movement competency; otherwise use a suitable regression or alternative.
- If a user reports that a session was too easy or too hard, explain that the structured feedback control is what changes the next generated prescription. Never claim that a chat acknowledgement alone changed or stored the programme.
- Match exercise selection and difficulty to the person's experience, goal, equipment and limitations. Include simple alternatives or easier versions when appropriate.
- Give practical intensity guidance (e.g. finish with 2–4 good repetitions in reserve for suitable strength exercises) only when appropriate for the user and exercise.
- Include a brief, realistic progression rule and explain when to stop or modify.
- Do not promise that a workout is risk-free or that it will cure pain. Avoid vague claims such as “without risk of overload.”
- Use the user's language consistently; proofread for grammar, spelling, terminology and internal consistency before answering.

SAFETY AND SCOPE
You are not a doctor or physiotherapist. Do not diagnose conditions, prescribe treatment, or claim to replace an in-person professional. Do not advise training through worsening pain. For severe, sudden, unexplained or worsening symptoms, recommend assessment by an appropriate healthcare professional. For chest pain, fainting, severe breathing difficulty, new weakness/numbness, or loss of bladder/bowel control with back pain, advise urgent local medical care. If relevant, ask about restrictions before suggesting exercise. Do not overreact to ordinary mild effort or soreness, but distinguish it from concerning or worsening symptoms.
Do not ask for full names, exact addresses or unnecessary personal data. Use health information only when needed. If uncertain, state the uncertainty rather than inventing facts, credentials, measurements, research or outcomes.

EXERCISE SUBSTITUTIONS – REQUIRED BEHAVIOUR
When the user asks to replace, swap or find an alternative for an exercise:
1) Identify the exact exercise from the current structured programme and the user's reason for changing it. Use the programme and profile already supplied; do not ask the user to repeat them.
2) Preserve the intended movement pattern and training stimulus unless the user explicitly asks to change them.
3) Recommend 1–2 suitable alternatives from the verified catalogue context supplied with the request. Never invent an exercise or assume equipment that is not available.
4) Briefly explain the practical difference and how to choose the load/variation. Do not give a new kilogram prescription without the user's training data.
5) If the user has not identified which exercise, ask one short clarifying question.
6) Never reply with a generic unavailable message when a useful clarification or catalogue-based alternative can be provided.
For this pilot, prefer these practical coaching defaults where compatible with the user's goal and equipment:
- Squat: Goblet počep; Počep z ročkama na ramenih; Počep s podprtimi petami (stable 5–10 cm heel support); barbell back/front squat when the user has the equipment and skill. Do not choose Počep z ročkama ob telesu as a default main lift.
- Hinge: Predklon z ravnim hrbtom (RDL) is generally preferred to a dumbbell deadlift when dumbbell grip or the floor start limits loading. Use a conventional barbell deadlift when strength specificity and skill support it.
- Carry: Farmers carry is optional and purpose-driven, not an automatic filler exercise.
Use natural Slovenian exercise names. Retain established English names such as Goblet squat, RDL, Farmers carry or ATG split squat where an artificial Slovenian translation would be less clear.

STYLE
Be warm, respectful, practical and encouraging without patronizing the user. Usually keep replies under 200 words, unless a plan or explanation genuinely needs more. Prioritize individualized reasoning and the next useful action over generic motivational text. This is a pilot, not individualized medical care.

COACHING-QUALITY STANDARD — EXERCISE SELECTION, REGRESSION AND PROGRESSION
This standard is mandatory for every individual programme. Apply it as an internal decision process; show the user only the concise, relevant coaching cues and next-step rule.

1. START WITH THE PERSON, NOT WITH EXERCISE COMPLEXITY
- Select exercises from the verified catalogue that match the goal, experience, actual available equipment, movement competence, symptoms and time.
- For the general population, simple foundational exercises are often the best choice. A controlled bodyweight squat, split squat, reverse lunge, push-up or mat-based trunk/back exercise can provide a meaningful stimulus. Do not replace them with advanced variations merely to make the plan look sophisticated.
- Judge whether an exercise is sufficiently challenging from actual execution, repetitions, range, tempo, RIR/RPE and feedback—not from the exercise label or the presence of external weight.
- A beginner may receive 3 × 8 bodyweight squats with a controlled 3–1–1–0 tempo when that dose leaves an appropriate reserve and technique remains consistent. This is an example, not a universal prescription. The same exercise may be too easy or too demanding for another person.
- Do not assume that a bodyweight exercise is automatically easy, or that a weighted exercise is automatically better.

2. EQUIPMENT IS A HARD CONSTRAINT
- Treat the selected equipment profile as authoritative. Never assume a table, chair, bench, wall, towel, backpack, resistance band, anchor or load unless the profile or user explicitly confirms it.
- For bodyweight-only profiles, use the floor, bodyweight and verified wall-based options. Do not prescribe table rows, improvised anchors, Nordic curls requiring an unverified anchor, or any exercise that depends on furniture bearing body weight.
- A missing pulling option is a real limitation, not a reason to invent an unsafe row. State it briefly and, if useful, ask whether the user has a resistance band or pull-up bar. Do not pretend a prone back exercise fully replaces loaded pulling.
- Use mat-based exercises (e.g. prone trunk/back extension patterns, controlled prone arm/leg lifts, dead bug or bird-dog when appropriate) when they match the goal and catalogue. They are useful complementary work, not automatic filler and not a substitute for every missing movement pattern.
- For home equipment, distinguish equipment that is explicitly available from a household item that might exist. Only use a household support when confirmed stable and appropriate for the direction of force.

3. BUILD A CLEAR REGRESSION–BASE–PROGRESSION LADDER FOR EACH EXERCISE
- Internally identify: (a) the easiest safe regression, (b) the selected base variation, (c) one or more logical progressions, and (d) the criterion for moving between them.
- Use the catalogue's regressions, progressions, alternatives and warnings as the primary source. Do not invent an unsupported variation or skip several levels at once.
- Regression triggers: inability to complete the lower end of the target range; RIR below target; loss of position or repeatability; reduced controlled range; pain or new symptoms; poor balance; excessive fatigue; or an exercise/support that cannot be performed safely.
- Choose the smallest useful regression: reduce range, use a stable support, shorten the lever, reduce load, select an easier angle/variation, reduce sets/repetitions or slow down only when that improves control. Change one principal variable at a time.
- Progression triggers: all prescribed sets reach the top of the target range at the intended RIR, with consistent technique and controlled range, across at least two exposures, and recovery is good with no concerning symptoms.
- Progress one variable at a time: first add repetitions within the range; then a small amount of load if available; otherwise use the next catalogue progression, a longer lever, a slightly greater controlled range or a more demanding unilateral variation. Do not automatically add sets and load together.
- If the person reports the exercise is easy but technique, range or RIR is unknown, ask for the missing performance detail rather than guessing.
- If pain or new symptoms are reported, stop automatic progression for the affected movement. Clarify the symptom and do not automatically swap in another loaded exercise.

4. BODYWEIGHT EXERCISES CAN BE THE MAIN STIMULUS
- Squat family: reaching/supported squat → air squat → controlled pause/tempo or increased range when appropriate → supported single-leg squat or another catalogue progression → external load only when available and useful. Do not assume every user needs a single-leg squat.
- Lunge family: supported split squat → split squat/forward or reverse lunge → walking lunge or Bulgarian split squat only when balance, range and stable support are appropriate → loaded version when equipment is confirmed. These are options, not a mandatory linear ladder.
- Push family: wall push-up → incline push-up (higher support is easier) → floor push-up → decline or another catalogue progression. Lower the support gradually and preserve full controlled range.
- Hip extension/posterior chain: glute bridge → long-lever bridge → elevated heel hip lift or another catalogue progression when appropriate. A mat-based knee-flexion option may be used only when its setup is safe. Do not claim an unloaded hinge is equivalent to a loaded RDL.
- Trunk/back: use appropriate mat-based patterns from the catalogue, with regressions and progressions based on control and tolerance. Superman-type work is optional and must be selected only if present in the verified catalogue; do not invent catalogue exercises.
- A 3 × 8 bodyweight squat, split squat or push-up may be an effective dose for a general-population beginner when the chosen variation is sufficiently challenging and the person finishes with the intended reserve. Do not force extra complexity or volume.

5. PROGRAMME BALANCE AND DOSE
- Build a coherent week, not two copies of the same exercise list. Repeating key movement patterns twice weekly is often appropriate; vary the exercise or emphasis when this improves coverage, comfort or adherence.
- In a short 25–35 minute full-body session, prefer 4–5 purposeful exercises and realistic rests. Prioritise the main patterns; do not add filler simply to reach a fixed exercise count.
- For strength plus hypertrophy, use a mix of suitable strength-oriented and muscle-building prescriptions, but beginners should still learn the movement with moderate repetitions and adequate reserve. The goal label alone does not justify low repetitions.
- Tempo is exercise- and goal-specific. Controlled 3–1–1–0 can be useful for learning and maintaining control; it is not mandatory for every exercise. Do not artificially slow every repetition or treat time under tension as the only stimulus.
- Give each exercise only 2–4 concise, non-repetitive coaching cues. Avoid repeating generic amplitude and safety paragraphs under every exercise. Put a shared instruction once at programme level when it applies to all exercises.
- Include a brief warm-up that names actual movements and prepares the session. Do not claim a precise total duration unless work, rests, transitions and warm-up have been estimated consistently.

6. FINAL INTERNAL REVIEW
Before returning a programme, check: equipment compatibility; exercise catalogue validity; safe setup; goal and experience fit; regression and progression logic; weekly pattern balance; dose and RIR; realistic session duration; concise unique cues; and no unsupported claims. If an item fails, replace it or explain the limitation rather than hiding it in a warning.
"""

def _format_recent_training_context(sessions):
    """Format a small, factual summary of the user's own stored training records."""
    if not isinstance(sessions, list):
        return ""
    lines = [
        "AUTHENTICATED RECENT TRAINING HISTORY (actual user-logged records; newest first):",
        "Use this as factual context, not as a complete diary. Never treat planned values as completed work.",
    ]
    if not sessions:
        lines.append("- No training sessions have been recorded in this profile yet.")
        return "\n".join(lines)
    for record in sessions[:5]:
        if not isinstance(record, dict):
            continue
        session = record.get("session")
        if not isinstance(session, dict):
            continue
        session_date = session.get("session_date") or record.get("session_date") or "date not recorded"
        duration = session.get("duration_minutes")
        difficulty = session.get("difficulty")
        recovery = session.get("recovery")
        completed = session.get("completed")
        summary = [str(session_date)]
        if isinstance(duration, int):
            summary.append(f"{duration} min")
        if difficulty:
            summary.append(f"difficulty: {difficulty}")
        if recovery:
            summary.append(f"recovery: {recovery}")
        if completed is not None:
            summary.append("completed" if completed else "partially completed")
        lines.append("- " + " · ".join(summary))
        exercises = session.get("exercises")
        if not isinstance(exercises, list):
            continue
        for item in exercises[:8]:
            if not isinstance(item, dict):
                continue
            exercise_id = item.get("exercise_id")
            if not isinstance(exercise_id, str) or not exercise_id:
                continue
            exercise = get_exercise(exercise_id)
            name = exercise.get("name") if isinstance(exercise, dict) else exercise_id
            set_results = item.get("set_results")
            if isinstance(set_results, list) and set_results:
                set_summaries = []
                for index, set_result in enumerate(set_results[:20], start=1):
                    if not isinstance(set_result, dict):
                        continue
                    details = []
                    if isinstance(set_result.get("reps"), int):
                        details.append(f"{set_result['reps']} reps")
                    if isinstance(set_result.get("work_seconds"), int):
                        details.append(f"{set_result['work_seconds']} s")
                    if isinstance(set_result.get("load_kg"), (int, float)):
                        details.append(f"{set_result['load_kg']:g} kg")
                    if isinstance(set_result.get("rir"), int):
                        details.append(f"RIR {set_result['rir']}")
                    if details:
                        set_summaries.append(f"set {index}: " + ", ".join(details))
                if set_summaries:
                    lines.append("  - " + str(name) + ": " + "; ".join(set_summaries))
                continue
            details = []
            sets = item.get("sets_completed")
            reps = item.get("reps_completed")
            work_seconds = item.get("work_seconds_completed")
            load = item.get("load_kg")
            rir = item.get("rir")
            if isinstance(sets, int):
                details.append(f"{sets} sets")
            if isinstance(reps, int):
                details.append(f"~{reps} reps/set")
            if isinstance(work_seconds, int):
                details.append(f"{work_seconds} s work")
            if isinstance(load, (int, float)):
                details.append(f"{load:g} kg")
            if isinstance(rir, int):
                details.append(f"RIR {rir}")
            if details:
                lines.append("  - " + str(name) + ": " + ", ".join(details))
    return "\\n".join(lines)


def _request_gemini_content(api_key, model, fallback_model, payload):
    """Retry transient Gemini capacity errors and optionally use a configured fallback."""
    candidates = [model]
    if fallback_model and fallback_model != model:
        candidates.append(fallback_model)
    transient_statuses = {429, 500, 502, 503, 504}
    last_error = None
    for model_index, candidate_model in enumerate(candidates):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + candidate_model + ":generateContent?key=" + api_key
        )
        request_body = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request_body, timeout=65) as response:
                    data = json.loads(response.read().decode("utf-8"))
                if model_index:
                    logger.warning(
                        "Gemini fallback model %s succeeded after primary model %s failed",
                        candidate_model, model
                    )
                return data, candidate_model
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in transient_statuses:
                    raise
                logger.warning(
                    "Gemini model %s returned transient HTTP %s (attempt %s/2)",
                    candidate_model, exc.code, attempt + 1
                )
                if attempt == 0:
                    time.sleep(5.0 if exc.code == 429 else 1.0)
                    continue
                break
    if last_error is not None:
        raise last_error
    raise urllib.error.URLError("Gemini request failed without a provider response")


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
    system_prompt = SYSTEM_PROMPT
    profile_id = request.headers.get("X-Profile-Id", "").strip()
    profile_token = request.headers.get("X-Profile-Token", "").strip()
    if bool(profile_id) != bool(profile_token):
        return jsonify({"error": "Za uporabo zgodovine treningov sta potrebna ID profila in dostopni ključ."}), 400
    if profile_id and profile_token:
        if len(profile_id) > 64 or not 20 <= len(profile_token) <= 256:
            return jsonify({"error": "Podatki za dostop do profila niso veljavni."}), 400
        try:
            recent_sessions = store_list_sessions(profile_id, profile_token, limit=5)
            history_context = _format_recent_training_context(recent_sessions)
            if history_context:
                system_prompt += "\n\n" + history_context
        except ProfileNotFound:
            return jsonify({"error": "Dostop do profila ni pravilen. Obnovi dostop z ID-jem in ključem."}), 403
        except StorageUnavailable:
            logger.warning("Stored training history unavailable for authenticated coach chat")
            system_prompt += (
                "\n\nRECENT TRAINING HISTORY: temporarily unavailable. "
                "Do not claim to know the user's stored training records."
            )
        except Exception:
            logger.exception("Could not load stored training history for authenticated coach chat")
            system_prompt += (
                "\n\nRECENT TRAINING HISTORY: unavailable. "
                "Do not claim to know the user's stored training records."
            )
    user_history_text = "\n".join(
        item.get("content", "") for item in messages if item.get("role") == "user"
    )
    latest_user_text = next(
        (item.get("content", "") for item in reversed(messages) if item.get("role") == "user"),
        "",
    )
    substitution_request = bool(re.search(
        r"zamenj|alternativ|namesto|druga(?:čno)? vajo|ne ustreza|swap|replace",
        user_history_text,
        re.IGNORECASE,
    ))
    # Keep a technique protocol active during follow-up turns. Users often ask
    # "kaj pa če..." or "ja, samo tehnika" without repeating the exercise name.
    rdl_technique_request = bool(re.search(
        r"\bRDL\b|romunsk(?:i|ega|em)\s+mrtv(?:i|ega|em)\s+dvig|predklon\s+z\s+ravnim\s+hrbtom|raven\s+hrbet|zaokrož(?:en|anj)",
        user_history_text,
        re.IGNORECASE,
    ))
    if rdl_technique_request:
        system_prompt += "\n\n" + RDL_TECHNIQUE_PROTOCOL
    exercise_intent = bool(re.search(
        r"program|trening|vadb|vajo|počep|izpadni|RDL|mrtv.{0,10}dvig|"
        r"serij|ponovitev|obremenitev|moč|hipertrof|vzdržljiv|eksploziv",
        user_history_text,
        re.IGNORECASE,
    ))
    if exercise_intent and not substitution_request:
        catalogue_context = _verified_exercise_catalogue_context(messages)
        if catalogue_context:
            system_prompt += catalogue_context
    if substitution_request:
        # Supply a compact, equipment-filtered catalogue excerpt so the language
        # model can discuss real alternatives instead of guessing exercise names.
        available = _profile_available_equipment(messages) or {"bodyweight"}
        current_names = set()
        for message in messages:
            content = message.get("content", "")
            if "Trenutni strukturirani program ATENE:" in content:
                for line in content.splitlines():
                    match = re.match(r"\s*-\s*(.+?):\s", line)
                    if match:
                        current_names.add(match.group(1).strip().casefold())
        catalogue = load_catalogue()
        current_records = [
            item for item in catalogue
            if item["name"].casefold() in current_names
        ]
        target_patterns = {item["pattern"] for item in current_records}
        alternatives = [
            item for item in catalogue
            if item["pattern"] in target_patterns
            and item["name"].casefold() not in current_names
            and item["training_role"] in {"main", "accessory"}
            and set(item["equipment"]).issubset(available)
            and (
                not item["equipment_any"]
                or bool(set(item["equipment_any"]) & available)
            )
        ]
        compact = [
            f"- {('Predklon z ravnim hrbtom (RDL)' if item['id'] == 'romanian_deadlift' else item['name'])} [{item['pattern']}]; oprema: "
            + (", ".join(item["equipment"] + item["equipment_any"]) or "lastna teža")
            for item in alternatives[:35]
        ]
        current = [
            f"- {('Predklon z ravnim hrbtom (RDL)' if item['id'] == 'romanian_deadlift' else item['name'])} [{item['pattern']}]"
            for item in current_records
        ]
        system_prompt += (
            "\n\nVERIFIED CURRENT PROGRAM EXERCISES:\n"
            + ("\n".join(current) if current else "No exact exercise names were matched.")
            + "\nVERIFIED AVAILABLE ALTERNATIVES (same movement pattern, filtered by equipment):\n"
            + ("\n".join(compact) if compact else "No matching alternatives found; ask one clarifying question.")
            + "\nUse only the alternatives above. If the requested exercise is not identified, ask which exercise."
        )
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    guarded_answer = _coaching_guardrail_reply(messages)
    if guarded_answer:
        return jsonify({
            "reply": guarded_answer,
            "model": model,
            "pilot": True,
            "guardrail_applied": True,
            "response_source": "server_guardrail",
        })
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 900}
    }
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite").strip()
    try:
        data, used_model = _request_gemini_content(
            api_key, model, fallback_model, body
        )
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        answer = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        if not answer:
            logger.warning("Gemini returned no text for model %s", model)
            return jsonify({"error": "Model ni vrnil odgovora. Poskusi znova."}), 502
        answer = _normalize_slovene_coaching_terms(answer)
        answer = _sanitize_unverified_safety_claim(answer, messages)
        answer = _sanitize_unlisted_support(answer, messages)
        bodyweight_note = _bodyweight_only_program_note(messages)
        if bodyweight_note and bodyweight_note not in answer:
            answer += "\n\n" + bodyweight_note
        # The coach brand owner is not automatically the chat user.
        answer = re.sub(
            r"^(Pozdravljen|Živjo|Živijo),\s*Grega[!.,]?\s*",
            r"\1! ",
            answer,
            flags=re.IGNORECASE,
        )
        return jsonify({
            "reply": answer,
            "model": used_model,
            "pilot": True,
            "guardrail_applied": False,
            "response_source": "gemini",
        })
    except urllib.error.HTTPError as exc:
        # Log only status and model; never log provider body, API key, or secret-bearing URL.
        logger.error("Gemini provider returned HTTP %s for model %s", exc.code, model)
        if exc.code in (400, 401, 403):
            return jsonify({"error": "Povezava z modelom ni pravilno nastavljena. Skrbnik naj preveri ključ in model."}), 502
        if exc.code == 429:
            return jsonify({"error": "Trenutno je dosežena omejitev uporabe. Poskusi pozneje."}), 429
        return jsonify({"error": "Storitev trenutno ni dosegljiva. Poskusi znova."}), 502
    except (TimeoutError, socket.timeout, urllib.error.URLError, json.JSONDecodeError):
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
    profile = payload.get("profile", payload)
    feedback = payload.get("feedback")
    movement_assessment = None
    if "movement_assessment" in payload:
        try:
            movement_assessment = assess_movement_competence(payload["movement_assessment"])
        except MovementAssessmentError as exc:
            return jsonify({"error": str(exc)}), 400
    try:
        result = generate_program(
            profile, feedback=feedback,
            movement_assessment=payload.get("movement_assessment"),
        )
    except ProgramSafetyBlock as exc:
        return jsonify({"blocked": True, "message": str(exc)}), 409
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, ValueError):
        logger.exception("ATENA catalogue/program generation failed")
        return jsonify({"error": "Programa trenutno ni mogoče sestaviti iz kataloga."}), 500
    response = {"program": result, "source": "curated_exercise_catalogue", "pilot": True}
    if result.get("movement_adaptation") is not None:
        response["movement_adaptation"] = result["movement_adaptation"]
    if movement_assessment is not None:
        # The self-reported assessment may select a verified simpler catalogue
        # variant or omit the affected pattern when symptoms are reported.
        # It is not persisted and does not establish clinical clearance.
        response["movement_assessment"] = movement_assessment
        response["movement_assessment_stored"] = False
    return jsonify(response), 200


@coach_bp.route("/coach/movement-assessment", methods=["POST", "OPTIONS"])
def coach_movement_assessment():
    """Evaluate self-reported movement-task experience without diagnosis or storage."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected_token = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied_token = request.headers.get("X-Pilot-Token", "").strip()
    if not expected_token:
        return jsonify({"error": "Testni dostop še ni nastavljen na strežniku."}), 503
    if not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("assessment"), dict):
        return jsonify({"error": "Pričakovan je objekt assessment z ocenami gibalnih nalog."}), 400
    try:
        result = assess_movement_competence(payload["assessment"])
    except MovementAssessmentError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "assessment": result,
        "stored": False,
        "source": "self_reported_movement_assessment",
        "pilot": True,
    }), 200


@coach_bp.route("/coach/status", methods=["GET", "OPTIONS"])
def coach_status():
    """Read-only pilot readiness; exposes no credentials or user data."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    try:
        catalogue_count = len(load_catalogue())
    except (OSError, ValueError):
        catalogue_count = 0
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    return jsonify({
        "chat_available": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "program_available": catalogue_count > 0,
        "catalogue_count": catalogue_count,
        "chat_provider": "google_gemini" if os.getenv("GEMINI_API_KEY", "").strip() else None,
        "model": model if os.getenv("GEMINI_API_KEY", "").strip() else None,
    }), 200


@coach_bp.route("/coach/storage/check", methods=["GET", "OPTIONS"])
def coach_storage_check():
    """Pilot-token-protected, read-only DB connectivity check; creates no tables or user data."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    try:
        store_check_database_connection()
        return jsonify({"database": "reachable", "user_data_storage": "still_disabled"}), 200
    except StorageUnavailable as exc:
        logger.warning("ATENA database connectivity check failed: %s", type(exc).__name__)
        return jsonify({"database": "unavailable", "reason": exc.reason, "user_data_storage": "still_disabled"}), 503


@coach_bp.route("/coach/storage/status", methods=["GET", "OPTIONS"])
def coach_storage_status():
    """Return coarse operator-controlled storage readiness; never expose credentials."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    enabled = (
        os.getenv("ATENA_DATA_STORAGE_ENABLED", "").strip().lower() == "true"
        and os.getenv("ATENA_PRIVACY_NOTICE_APPROVED", "").strip().lower() == "true"
    )
    try:
        store_check_database_connection()
        return jsonify({
            "database": "reachable",
            "storage_enabled": enabled,
            "privacy_notice_version": os.getenv("ATENA_PRIVACY_NOTICE_VERSION", "pilot-draft-1").strip(),
        }), 200
    except StorageUnavailable as exc:
        return jsonify({
            "database": "unavailable",
            "storage_enabled": False,
            "reason": exc.reason,
        }), 503


# Longitudinal profile storage is opt-in and disabled by default. Hosted use
# requires a persistent PostgreSQL database and an operator-approved notice.
PROFILE_FIELDS = {"goal", "experience", "equipment", "sessions_per_week", "session_minutes", "available_days", "pistol_squat_capable"}
PROFILE_GOALS = {"strength", "hypertrophy", "strength_hypertrophy", "fat_loss", "general_fitness", "functional", "power", "endurance", "mobility"}
PROFILE_EXPERIENCE = {"beginner", "intermediate", "advanced"}
PROFILE_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
VALID_EQUIPMENT = {item for exercise in load_catalogue() for item in (exercise["equipment"] + exercise["equipment_any"])}


def _storage_error(exc):
    logger.warning("ATENA profile storage unavailable: %s", type(exc).__name__)
    return jsonify({"error": "Shranjevanje profila trenutno ni aktivirano."}), 503


def _validate_profile(value):
    if not isinstance(value, dict) or set(value) - PROFILE_FIELDS:
        raise ValueError("Profil vsebuje neveljavna ali nepodprta polja.")
    goal = value.get("goal")
    experience = value.get("experience")
    equipment = value.get("equipment")
    sessions = value.get("sessions_per_week")
    minutes = value.get("session_minutes")
    if goal not in PROFILE_GOALS:
        raise ValueError("Cilj vadbe ni veljaven.")
    if experience not in PROFILE_EXPERIENCE:
        raise ValueError("Raven izkušenj ni veljavna.")
    if not isinstance(equipment, list) or len(equipment) > 40 or any(
        not isinstance(item, str) or not item.strip() or len(item) > 40 for item in equipment
    ) or len(set(equipment)) != len(equipment) or not set(equipment).issubset(VALID_EQUIPMENT):
        raise ValueError("Seznam opreme vsebuje podvojeno ali nepodprto opremo.")
    if not isinstance(sessions, int) or isinstance(sessions, bool) or not 2 <= sessions <= 4:
        raise ValueError("Za zdaj so podprti 2, 3 ali 4 treningi na teden.")
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 25 <= minutes <= 120:
        raise ValueError("Trajanje treninga mora biti med 25 in 120 minutami.")
    days = value.get("available_days", [])
    if not isinstance(days, list) or len(days) > 7 or any(day not in PROFILE_DAYS for day in days):
        raise ValueError("Razpoložljivi dnevi niso veljavni.")
    pistol_squat_capable = value.get("pistol_squat_capable", False)
    if not isinstance(pistol_squat_capable, bool):
        raise ValueError("pistol_squat_capable mora biti true ali false.")
    return {
        "goal": goal, "experience": experience, "equipment": equipment,
        "sessions_per_week": sessions, "session_minutes": minutes,
        "available_days": days, "pistol_squat_capable": pistol_squat_capable,
    }


def _profile_token():
    return request.headers.get("X-Profile-Token", "").strip()


def _profile_auth_error():
    return jsonify({"error": "Profil ne obstaja ali dostopni ključ ni pravilen."}), 404


@coach_bp.route("/coach/profile", methods=["POST", "OPTIONS"])
def create_coach_profile():
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Pričakovan je JSON objekt."}), 400
    if payload.get("privacy_notice_acknowledged") is not True:
        return jsonify({"error": "Pred shranjevanjem je treba potrditi seznanitev z obvestilom o zasebnosti."}), 400
    notice_version = os.getenv("ATENA_PRIVACY_NOTICE_VERSION", "pilot-draft-1").strip()
    if payload.get("privacy_notice_version") != notice_version:
        return jsonify({"error": "Različica obvestila o zasebnosti ni veljavna."}), 400
    health_consent = payload.get("health_data_consent", False)
    if not isinstance(health_consent, bool):
        return jsonify({"error": "Privolitev za zdravstvene podatke mora biti true ali false."}), 400
    try:
        profile = _validate_profile(payload.get("profile"))
        profile_id = str(uuid.uuid4())
        access_token = secrets.token_urlsafe(32)
        saved = store_create_profile(profile_id, access_token, profile, health_consent, notice_version)
        # The access token is returned once. Only its SHA-256 hash is stored.
        return jsonify({"profile": saved, "profile_access_token": access_token,
                        "token_notice": "Ključ shrani varno; pozneje ga ni mogoče ponovno prikazati."}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except StorageUnavailable as exc:
        return _storage_error(exc)


@coach_bp.route("/coach/profile/<profile_id>", methods=["GET", "PUT", "DELETE", "OPTIONS"])
def manage_coach_profile(profile_id):
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    if request.method == "GET":
        try:
            return jsonify({"profile": store_get_profile(profile_id, token)}), 200
        except ProfileNotFound:
            return _profile_auth_error()
        except StorageUnavailable as exc:
            return _storage_error(exc)
    if request.method == "PUT":
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Pričakovan je JSON objekt."}), 400
        try:
            profile = _validate_profile(payload.get("profile"))
            updated = store_update_profile(profile_id, token, profile)
            return jsonify({"profile": updated}), 200
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except ProfileNotFound:
            return _profile_auth_error()
        except StorageUnavailable as exc:
            return _storage_error(exc)
    try:
        store_delete_profile(profile_id, token)
        return jsonify({"deleted": True}), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)


def _normalize_conditioning_block(item):
    """Validate a separately logged conditioning block; never mix it with resistance sets."""
    allowed = {
        "modality", "protocol_id", "work_seconds", "duration_seconds",
        "intervals_completed", "rpe", "distance_m", "average_heart_rate",
    }
    if not isinstance(item, dict) or set(item) - allowed:
        return None, "Kondicijski zapis vsebuje neveljavna polja."
    modality = item.get("modality")
    if modality not in {"aerobic_base", "threshold_intervals", "vo2max_intervals", "metcon"}:
        return None, "Vrsta kondicijske vadbe ni veljavna."
    protocol_id = item.get("protocol_id")
    if not isinstance(protocol_id, str) or not protocol_id.strip() or len(protocol_id) > 80:
        return None, "Oznaka kondicijskega protokola ni veljavna."
    work = item.get("work_seconds")
    duration = item.get("duration_seconds")
    intervals = item.get("intervals_completed", 1)
    rpe = item.get("rpe")
    if not isinstance(work, int) or isinstance(work, bool) or not 1 <= work <= 14400:
        return None, "Skupni čas dela mora biti med 1 in 14400 sekundami."
    if not isinstance(duration, int) or isinstance(duration, bool) or not work <= duration <= 21600:
        return None, "Skupno trajanje mora biti najmanj toliko kot čas dela in največ 6 ur."
    if not isinstance(intervals, int) or isinstance(intervals, bool) or not 1 <= intervals <= 100:
        return None, "Število zaključenih intervalov ni veljavno."
    if not isinstance(rpe, (int, float)) or isinstance(rpe, bool) or not 1 <= rpe <= 10:
        return None, "Ocena napora (RPE) mora biti med 1 in 10."
    result = {
        "modality": modality,
        "protocol_id": protocol_id.strip(),
        "work_seconds": work,
        "duration_seconds": duration,
        "intervals_completed": intervals,
        "rpe": float(rpe),
    }
    distance = item.get("distance_m")
    if distance is not None:
        if not isinstance(distance, (int, float)) or isinstance(distance, bool) or not 1 <= distance <= 100000:
            return None, "Razdalja ni veljavna."
        result["distance_m"] = float(distance)
    heart_rate = item.get("average_heart_rate")
    if heart_rate is not None:
        if not isinstance(heart_rate, int) or isinstance(heart_rate, bool) or not 30 <= heart_rate <= 240:
            return None, "Povprečni srčni utrip ni veljaven."
        result["average_heart_rate"] = heart_rate
    return result, None


def _normalize_logged_exercise(item):
    """Validate actual exercise performance, supporting both legacy summaries and set-by-set logs."""
    allowed = {
        "exercise_id", "sets_completed", "reps_completed",
        "work_seconds_completed", "load_kg", "rir", "set_results",
        "planned_sets", "target_reps_min", "target_reps_max",
        "target_work_seconds", "execution_quality", "tempo_control", "tempo_target",
    }
    if not isinstance(item, dict) or set(item) - allowed:
        return None, "Zapis vaje vsebuje neveljavna polja."
    exercise_id = item.get("exercise_id")
    if not isinstance(exercise_id, str) or get_exercise(exercise_id) is None:
        return None, "Vaja ni v preverjenem katalogu ATENA."

    planned_sets = item.get("planned_sets")
    if planned_sets is not None and (
        not isinstance(planned_sets, int) or isinstance(planned_sets, bool) or not 1 <= planned_sets <= 20
    ):
        return None, "Načrtovano število serij ni veljavno."
    target_min = item.get("target_reps_min")
    target_max = item.get("target_reps_max")
    if (target_min is None) != (target_max is None):
        return None, "Ciljno območje ponovitev mora vsebovati spodnjo in zgornjo mejo."
    if target_min is not None and (
        not isinstance(target_min, int) or isinstance(target_min, bool)
        or not isinstance(target_max, int) or isinstance(target_max, bool)
        or not 1 <= target_min <= target_max <= 100
    ):
        return None, "Ciljno območje ponovitev ni veljavno."
    target_work = item.get("target_work_seconds")
    if target_work is not None and (
        not isinstance(target_work, int) or isinstance(target_work, bool) or not 1 <= target_work <= 3600
    ):
        return None, "Ciljno trajanje dela ni veljavno."
    if target_work is not None and target_min is not None:
        return None, "Vaja ne more hkrati uporabljati cilja ponovitev in časa."
    execution_quality = item.get("execution_quality", "unknown")
    if not isinstance(execution_quality, str) or execution_quality not in {"unknown", "controlled", "needs_attention"}:
        return None, "Ocena kakovosti izvedbe ni veljavna."
    tempo_control = item.get("tempo_control", "unknown")
    if not isinstance(tempo_control, str) or tempo_control not in {
        "unknown", "followed", "inconsistent", "not_followed", "not_applicable"
    }:
        return None, "Ocena nadzora tempa ni veljavna."
    tempo_target = item.get("tempo_target")
    if tempo_target is not None and (
        not isinstance(tempo_target, str) or
        not re.fullmatch(r"\d{1,2}[–-]\d{1,2}[–-](?:\d{1,2}|[Xx])[–-]\d{1,2}", tempo_target)
    ):
        return None, "Predpisani tempo ni veljaven."
    if tempo_control == "not_applicable" and tempo_target is not None:
        return None, "Tempo ne more biti označen kot neuporaben, če je predpisan."
    if tempo_control in {"followed", "inconsistent", "not_followed"} and tempo_target is None:
        return None, "Ocena tempa potrebuje pripadajoči predpisani tempo."

    set_results = item.get("set_results")
    if set_results is not None:
        if not isinstance(set_results, list) or not 1 <= len(set_results) <= 20:
            return None, "Zapis mora vsebovati od 1 do 20 dejansko izvedenih serij."
        normalized_sets = []
        set_kinds = set()
        for set_item in set_results:
            if not isinstance(set_item, dict) or set(set_item) - {"reps", "work_seconds", "load_kg", "rir"}:
                return None, "Posamezna serija vsebuje neveljavna polja."
            reps = set_item.get("reps")
            work_seconds = set_item.get("work_seconds")
            if (reps is None) == (work_seconds is None):
                return None, "Za vsako serijo navedi ponovitve ali trajanje, ne obojega."
            if reps is not None:
                if not isinstance(reps, int) or isinstance(reps, bool) or not 1 <= reps <= 100:
                    return None, "Število ponovitev v seriji ni veljavno."
                set_kinds.add("reps")
            if work_seconds is not None:
                if not isinstance(work_seconds, int) or isinstance(work_seconds, bool) or not 1 <= work_seconds <= 3600:
                    return None, "Trajanje delovne serije ni veljavno."
                set_kinds.add("time")
            normalized_set = {}
            if reps is not None:
                normalized_set["reps"] = reps
            if work_seconds is not None:
                normalized_set["work_seconds"] = work_seconds
            load = set_item.get("load_kg")
            if load is not None:
                if not isinstance(load, (int, float)) or isinstance(load, bool) or not 0 <= load <= 1000:
                    return None, "Obremenitev v seriji ni veljavna."
                normalized_set["load_kg"] = float(load)
            rir = set_item.get("rir")
            if rir is not None:
                if not isinstance(rir, int) or isinstance(rir, bool) or not 0 <= rir <= 10:
                    return None, "RIR v seriji mora biti med 0 in 10."
                normalized_set["rir"] = rir
            normalized_sets.append(normalized_set)
        if len(set_kinds) != 1:
            return None, "Vse serije iste vaje morajo beležiti enako vrsto izvedbe."
        if item.get("sets_completed") is not None and item.get("sets_completed") != len(normalized_sets):
            return None, "Število serij se ne ujema s podrobno beleženimi serijami."

        entry = {
            "exercise_id": exercise_id,
            "sets_completed": len(normalized_sets),
            "set_results": normalized_sets,
            "execution_quality": execution_quality,
            "tempo_control": tempo_control,
        }
        if tempo_target is not None:
            entry["tempo_target"] = tempo_target
        if planned_sets is not None:
            entry["planned_sets"] = planned_sets
        if target_min is not None:
            entry["target_reps_min"] = target_min
            entry["target_reps_max"] = target_max
        if target_work is not None:
            entry["target_work_seconds"] = target_work
        if "reps" in set_kinds:
            entry["reps_completed"] = round(
                sum(row["reps"] for row in normalized_sets) / len(normalized_sets)
            )
        else:
            entry["work_seconds_completed"] = round(
                sum(row["work_seconds"] for row in normalized_sets) / len(normalized_sets)
            )
        loads = [row["load_kg"] for row in normalized_sets if "load_kg" in row]
        if loads:
            entry["load_kg"] = round(sum(loads) / len(loads), 2)
        rir_values = [row["rir"] for row in normalized_sets if "rir" in row]
        if rir_values:
            # Minimum RIR represents the hardest completed set and is conservative for progression.
            entry["rir"] = min(rir_values)
        return entry, None

    sets = item.get("sets_completed")
    reps = item.get("reps_completed")
    work_seconds = item.get("work_seconds_completed")
    if not isinstance(sets, int) or isinstance(sets, bool) or not 1 <= sets <= 20:
        return None, "Število izvedenih serij ni veljavno."
    if reps is not None and (not isinstance(reps, int) or isinstance(reps, bool) or not 1 <= reps <= 100):
        return None, "Število ponovitev ni veljavno."
    if work_seconds is not None and (not isinstance(work_seconds, int) or isinstance(work_seconds, bool) or not 1 <= work_seconds <= 3600):
        return None, "Trajanje delovne serije ni veljavno."
    if reps is None and work_seconds is None:
        return None, "Za vajo je treba navesti ponovitve ali trajanje delovne serije."
    entry = {"exercise_id": exercise_id, "sets_completed": sets, "execution_quality": execution_quality,
             "tempo_control": tempo_control}
    if tempo_target is not None:
        entry["tempo_target"] = tempo_target
    if planned_sets is not None:
        entry["planned_sets"] = planned_sets
    if target_min is not None:
        entry["target_reps_min"] = target_min
        entry["target_reps_max"] = target_max
    if target_work is not None:
        entry["target_work_seconds"] = target_work
    if reps is not None:
        entry["reps_completed"] = reps
    if work_seconds is not None:
        entry["work_seconds_completed"] = work_seconds
    load = item.get("load_kg")
    if load is not None:
        if not isinstance(load, (int, float)) or isinstance(load, bool) or not 0 <= load <= 1000:
            return None, "Obremenitev ni veljavna."
        entry["load_kg"] = float(load)
    rir = item.get("rir")
    if rir is not None:
        if not isinstance(rir, int) or isinstance(rir, bool) or not 0 <= rir <= 10:
            return None, "RIR mora biti med 0 in 10."
        entry["rir"] = rir
    return entry, None


@coach_bp.route("/coach/profile/<profile_id>/sessions", methods=["GET", "POST", "OPTIONS"])
def coach_training_sessions(profile_id):
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    if request.method == "GET":
        try:
            return jsonify({"sessions": store_list_sessions(profile_id, token, limit=50)}), 200
        except ProfileNotFound:
            return _profile_auth_error()
        except StorageUnavailable as exc:
            return _storage_error(exc)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Pričakovan je JSON objekt."}), 400
    allowed = {"session_date", "duration_minutes", "difficulty", "completed", "exercises", "conditioning", "discomfort_reported", "recovery", "completion_reason", "adaptation_response", "difficulty_scope", "affected_exercise_id"}
    if set(payload) - allowed:
        return jsonify({"error": "Vadbeni zapis vsebuje nepodprta polja; prosto besedilo ni dovoljeno."}), 400
    session_date = payload.get("session_date")
    try:
        date.fromisoformat(session_date)
    except (TypeError, ValueError):
        return jsonify({"error": "Datum mora biti v obliki YYYY-MM-DD."}), 400
    duration = payload.get("duration_minutes")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 1 <= duration <= 240:
        return jsonify({"error": "Trajanje mora biti med 1 in 240 minutami."}), 400
    difficulty = payload.get("difficulty")
    if difficulty not in {"easy", "moderate", "hard"}:
        return jsonify({"error": "Težavnost mora biti easy, moderate ali hard."}), 400
    recovery = payload.get("recovery", "normal")
    if recovery not in {"good", "normal", "poor"}:
        return jsonify({"error": "Regeneracija mora biti good, normal ali poor."}), 400
    if not isinstance(payload.get("completed"), bool):
        return jsonify({"error": "Polje completed mora biti true ali false."}), 400
    completion_reason = payload.get("completion_reason")
    valid_completion_reasons = {
        "time_constraint", "high_difficulty", "poor_recovery",
        "external_interruption", "other", "unknown",
    }
    if completion_reason is not None and completion_reason not in valid_completion_reasons:
        return jsonify({"error": "Razlog nedokončanega treninga ni veljaven."}), 400
    if payload.get("completed") is False and completion_reason is None:
        completion_reason = "unknown"
    difficulty_scope = payload.get("difficulty_scope", "unknown")
    affected_exercise_id = payload.get("affected_exercise_id")
    if difficulty_scope not in {"unknown", "session", "exercise"}:
        return jsonify({"error": "Obseg zahtevnosti mora biti unknown, session ali exercise."}), 400
    if difficulty_scope == "exercise":
        if not isinstance(affected_exercise_id, str) or get_exercise(affected_exercise_id) is None:
            return jsonify({"error": "Pri zahtevnosti posamezne vaje izberi veljavno vajo iz kataloga."}), 400
    elif affected_exercise_id is not None:
        return jsonify({"error": "Prizadeta vaja je dovoljena samo, če je obseg zahtevnosti exercise."}), 400
    adaptation_response = payload.get("adaptation_response")
    if adaptation_response is not None:
        if (
            not isinstance(adaptation_response, dict)
            or set(adaptation_response) != {"adaptation_id", "outcome"}
            or not isinstance(adaptation_response.get("adaptation_id"), str)
            or not 8 <= len(adaptation_response["adaptation_id"]) <= 64
            or adaptation_response.get("outcome") not in {"helped", "no_change", "worse", "not_tried"}
        ):
            return jsonify({"error": "Odziv na prejšnjo prilagoditev ni veljaven."}), 400
    exercises = payload.get("exercises")
    if not isinstance(exercises, list) or len(exercises) > 20:
        return jsonify({"error": "Vadbeni zapis lahko vsebuje največ 20 vaj."}), 400
    clean_exercises = []
    for item in exercises:
        entry, error = _normalize_logged_exercise(item)
        if error:
            return jsonify({"error": error}), 400
        clean_exercises.append(entry)

    conditioning = payload.get("conditioning", [])
    if not isinstance(conditioning, list) or len(conditioning) > 8:
        return jsonify({"error": "Vadbeni zapis lahko vsebuje največ 8 kondicijskih blokov."}), 400
    clean_conditioning = []
    for item in conditioning:
        entry, error = _normalize_conditioning_block(item)
        if error:
            return jsonify({"error": error}), 400
        clean_conditioning.append(entry)

    discomfort = payload.get("discomfort_reported")
    if discomfort is not None and not isinstance(discomfort, bool):
        return jsonify({"error": "discomfort_reported mora biti true ali false."}), 400
    session = {
        "duration_minutes": duration, "difficulty": difficulty,
        "recovery": recovery, "completed": payload["completed"], "exercises": clean_exercises,
        "conditioning": clean_conditioning,
    }
    if completion_reason is not None:
        session["completion_reason"] = completion_reason
    if difficulty_scope != "unknown":
        session["difficulty_scope"] = difficulty_scope
    if affected_exercise_id is not None:
        session["affected_exercise_id"] = affected_exercise_id
    if adaptation_response is not None:
        session["adaptation_response"] = adaptation_response
    try:
        profile = store_get_profile(profile_id, token)
        includes_health_data = discomfort is not None or any(
            block.get("average_heart_rate") is not None for block in clean_conditioning
        )
        if includes_health_data and not profile["health_data_consent"]:
            return jsonify({"error": "Za shranjevanje podatka o nelagodju ali srčnem utripu je potrebna ločena privolitev za zdravstvene podatke."}), 403
        if discomfort is not None:
            session["discomfort_reported"] = discomfort
        if adaptation_response is not None:
            prior_sessions = store_list_sessions(profile_id, token, limit=50)
            expected_adaptation_id = _build_adaptive_decision(prior_sessions)["adaptation_id"]
            if adaptation_response["adaptation_id"] != expected_adaptation_id:
                return jsonify({
                    "error": "Odziv se ne nanaša na zadnjo prilagoditev, ki jo je izdala ATENA.",
                    "code": "adaptation_id_mismatch",
                }), 409
        saved = store_add_session(profile_id, token, str(uuid.uuid4()), session_date, session)
        return jsonify({"session": saved}), 201
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)


@coach_bp.route("/coach/profile/<profile_id>/consent", methods=["POST", "OPTIONS"])
def update_coach_health_consent(profile_id):
    if request.method == "OPTIONS":
        return ("", 204)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"health_data_consent"}:
        return jsonify({"error": "Pošlji samo polje health_data_consent."}), 400
    consent = payload.get("health_data_consent")
    if not isinstance(consent, bool):
        return jsonify({"error": "Privolitev mora biti true ali false."}), 400
    try:
        profile = store_set_health_data_consent(profile_id, _profile_token(), consent)
        return jsonify({
            "profile": profile,
            "notice": (
                "Privolitev za zdravstvene podatke je umaknjena; shranjeni podatki o nelagodju so izbrisani."
                if not consent else "Privolitev za zdravstvene podatke je zabeležena."
            ),
        }), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)



def _build_adaptive_decision(sessions, exercise_progressions=None,
                             longitudinal_progression=None,
                             conditioning_progression=None):
    """Combine the independent evidence streams into one narrow, explainable decision."""
    if exercise_progressions is None:
        exercise_progressions = recommend_exercise_progression(sessions)
    if longitudinal_progression is None:
        longitudinal_progression = summarize_longitudinal_progression(sessions)
    if conditioning_progression is None:
        conditioning_progression = summarize_conditioning_progress(sessions)
    latest = next((
        item for item in sessions
        if isinstance(item, dict) and isinstance(item.get("session"), dict)
    ), {})
    prior = latest.get("session", {}).get("adaptation_response")
    decision = decide_adaptation(
        sessions,
        exercise_progressions=exercise_progressions,
        longitudinal_progression=longitudinal_progression,
        conditioning_progression=conditioning_progression,
        prior_adaptation=prior,
    )
    if decision.get("decision") == "confirm_previous_change" and isinstance(prior, dict):
        # Keep the original ID while a recommendation remains untried. This
        # prevents ATENA from creating a new, endlessly repeatable proposal.
        decision["adaptation_id"] = prior.get("adaptation_id")
    else:
        latest_date = latest.get("session_date", "no-date")
        latest_session = latest.get("session", {})
        seed = "|".join([
            str(latest_date), str(latest_session.get("session_key", "")),
            str(decision.get("decision")), str(decision.get("scope")),
            ",".join(decision.get("reason_codes", [])),
        ])
        decision["adaptation_id"] = uuid.uuid5(uuid.NAMESPACE_URL, "atena:" + seed).hex[:24]
    if decision.get("decision") not in {"collect_baseline", "collect_context", "collect_data"}:
        decision["feedback_contract"] = {
            "field": "adaptation_response",
            "outcomes": ["helped", "no_change", "worse", "not_tried"],
            "instruction": "V naslednjem zapisu treninga pošlji adaptation_id in izbrani outcome.",
        }
    return decision


def _confirmed_successful_exercise_ids(sessions):
    """Return only exercises from the immediately preceding, positively confirmed adaptation."""
    ordered = sorted(
        [item for item in sessions if isinstance(item, dict) and isinstance(item.get("session"), dict)],
        key=lambda item: item.get("session_date", ""),
        reverse=True,
    )
    if len(ordered) < 2:
        return []
    response = ordered[0]["session"].get("adaptation_response")
    if not isinstance(response, dict) or response.get("outcome") != "helped":
        return []
    previous_decision = _build_adaptive_decision(ordered[1:])
    if not hmac.compare_digest(
        str(response.get("adaptation_id", "")),
        str(previous_decision.get("adaptation_id", "")),
    ):
        return []
    eligible = previous_decision.get("eligible_exercises", [])
    return list(dict.fromkeys(
        exercise_id for exercise_id in eligible
        if isinstance(exercise_id, str) and exercise_id.strip()
    ))


def _hold_successfully_confirmed_exercises(sessions, recommendations):
    """Keep a positively confirmed exercise adjustment stable for one exposure."""
    held_ids = set(_confirmed_successful_exercise_ids(sessions))
    for recommendation in recommendations if isinstance(recommendations, list) else []:
        if (
            isinstance(recommendation, dict)
            and recommendation.get("exercise_id") in held_ids
            and recommendation.get("decision") in {
                "add_repetitions", "increase_load", "progress_variation", "increase_work_time"
            }
        ):
            recommendation["decision"] = "hold"
            recommendation["reason"] = (
                "Prejšnja prilagoditev te vaje je uporabniku pomagala. Ohranimo trenutni odmerek "
                "še eno primerljivo izvedbo in ne stopnjujemo iste vaje hkrati."
            )
    return sorted(held_ids)


@coach_bp.route("/coach/profile/<profile_id>/assessment", methods=["PUT", "OPTIONS"])
def save_coach_movement_assessment(profile_id):
    """Persist the latest task-specific self-report only with separate health-data consent."""
    if request.method == "OPTIONS":
        return ("", 204)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"movement_tasks"}:
        return jsonify({"error": "Pošlji samo strukturirano polje movement_tasks."}), 400
    movement_tasks = payload.get("movement_tasks")
    if not isinstance(movement_tasks, dict):
        return jsonify({"error": "movement_tasks mora biti JSON objekt."}), 400
    normalized = {}
    for task, value in movement_tasks.items():
        if not isinstance(value, dict) or set(value) != {"status"}:
            return jsonify({"error": "Vsaka gibalna naloga mora vsebovati samo polje status."}), 400
        normalized[task] = value.get("status")
    try:
        assessment = assess_movement_competence(normalized)
        profile = store_get_profile(profile_id, _profile_token())
        if not profile["health_data_consent"]:
            return jsonify({"error": "Za shranjevanje samoocene gibanja je potrebna ločena privolitev za zdravstvene podatke."}), 403
        saved = store_save_movement_assessment(profile_id, _profile_token(), normalized)
        return jsonify({
            "assessment": assessment,
            "assessment_updated_at": saved["updated_at"],
            "assessment_stored": True,
            "source": "authenticated_self_reported_movement_assessment",
        }), 200
    except MovementAssessmentError as exc:
        return jsonify({"error": str(exc)}), 400
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)

@coach_bp.route("/coach/profile/<profile_id>/progress", methods=["GET", "OPTIONS"])
def coach_training_progress(profile_id):
    """Return descriptive training trends; never prescribe automatic load increases."""
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=50)
        exercise_progressions = recommend_exercise_progression(sessions)
        longitudinal_progression = summarize_longitudinal_progression(sessions)
        conditioning_progression = summarize_conditioning_progress(sessions)
        adaptive_decision = _build_adaptive_decision(
            sessions, exercise_progressions, longitudinal_progression,
            conditioning_progression,
        )
        training_cycle = summarize_training_cycle(
            profile["profile"], sessions, exercise_progressions,
            longitudinal_progression, conditioning_progression,
        )
        return jsonify({
            "progress": summarize_progress(profile, sessions),
            "adaptive_decision": adaptive_decision,
            "exercise_progressions": exercise_progressions,
            "longitudinal_progression": longitudinal_progression,
            "conditioning_progression": conditioning_progression,
            "training_cycle": training_cycle,
            "proactive_checkin": build_proactive_checkin(sessions),
            "source": "recorded_training_history",
            "automatic_load_changes": False,
        }), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)


@coach_bp.route("/coach/profile/<profile_id>/export", methods=["GET", "OPTIONS"])
def export_coach_profile(profile_id):
    """Export the authenticated user's profile and complete structured training history."""
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=5000)
        movement_assessment = store_get_movement_assessment(profile_id, token)
        program_versions = store_list_program_versions(profile_id, token, limit=5000)
        response = jsonify({
            "export_version": "1.1",
            "profile": profile,
            "sessions": sessions,
            "movement_assessment": movement_assessment,
            "program_versions": program_versions,
            "exported_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(timespec="seconds"),
        })
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Content-Disposition"] = (
            'attachment; filename="atena-profile-export.json"'
        )
        return response, 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)



def _build_profile_adaptation(sessions):
    """Normalize stored session wrappers and gate progression on recorded history."""
    ordered_sessions = sorted(
        [
            item for item in sessions
            if isinstance(item, dict) and isinstance(item.get("session"), dict)
        ],
        key=lambda item: item.get("session_date", ""),
        reverse=True,
    )
    session_data = [item["session"] for item in ordered_sessions]
    guidance = assess_next_step(ordered_sessions)
    if not session_data:
        return None, guidance
    last = session_data[0]
    if last.get("discomfort_reported") is True:
        # The profile-program route requires a fresh explicit confirmation that
        # there is no current pain or restriction. Keep progression on hold,
        # but do not permanently block a recovered user because of a past entry.
        feedback = {
            "difficulty": "right",
            "completed": bool(last.get("completed", True)),
            "discomfort": "no",
            "recovery": last.get("recovery", "normal"),
        }
        return feedback, guidance
    difficulty = {"easy": "easy", "moderate": "right", "hard": "hard"}.get(
        last.get("difficulty"), "right"
    )
    if difficulty == "easy" and not guidance.get("progression_allowed", False):
        difficulty = "right"
    feedback = {
        "difficulty": difficulty,
        "completed": bool(last.get("completed", True)),
        "discomfort": "no",
        "recovery": last.get("recovery", "normal"),
        "movement_control": "none",
    }
    return feedback, guidance


@coach_bp.route("/coach/profile/<profile_id>/program", methods=["POST", "OPTIONS"])
def coach_profile_program(profile_id):
    """Build the next programme from the saved profile and most recent logged feedback."""
    if request.method == "OPTIONS":
        return ("", 204)
    if not storage_enabled():
        return _storage_error(StorageUnavailable("Profile storage is not enabled or approved."))
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"no_current_pain_or_restrictions"}:
        return jsonify({"error": "Potrjena mora biti samo trenutna varnostna izjava."}), 400
    if payload.get("no_current_pain_or_restrictions") is not True:
        return jsonify({
            "blocked": True,
            "message": "Programa nisem ustvaril. Ob novi, hudi, slabšajoči se ali nepojasnjeni bolečini, sveži poškodbi ali pomembni zdravstveni omejitvi je najprej potrebna presoja ustreznega zdravstvenega strokovnjaka. Blago, znano nelagodje samo po sebi ne pomeni prepovedi vse vadbe; prizadeti gibalni vzorec je treba posebej razjasniti in prilagoditi.",
        }), 409
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        # Use enough history to enforce the same progression gate shown in the
        # adaptation endpoint: two completed, easy sessions with RIR >= 3.
        sessions = store_list_sessions(profile_id, token, limit=50)
        feedback, adaptation = _build_profile_adaptation(sessions)
        exercise_progressions = recommend_exercise_progression(sessions)
        confirmed_successful_exercises = _hold_successfully_confirmed_exercises(
            sessions, exercise_progressions
        )
        longitudinal_progression = summarize_longitudinal_progression(sessions)
        conditioning_progression = summarize_conditioning_progress(sessions)
        adaptive_decision = _build_adaptive_decision(
            sessions, exercise_progressions, longitudinal_progression,
            conditioning_progression,
        )
        training_cycle = summarize_training_cycle(
            profile["profile"], sessions, exercise_progressions,
            longitudinal_progression, conditioning_progression,
        )
        # Global session feedback is now advisory only. It must not silently
        # reduce or increase every exercise: the adaptive decision explains the
        # scope, while the exercise engine applies only independently justified
        # exercise-level rep guidance. A future user-confirmed session-level
        # adjustment can be applied through an explicit programme revision.
        movement_record = store_get_movement_assessment(profile_id, token)
        movement_assessment = movement_record["assessment"] if movement_record else None
        result = generate_program(
            profile["profile"],
            movement_assessment=movement_assessment,
        )
        result = apply_exercise_progression(result, exercise_progressions)
        program_version_id = str(uuid.uuid4())
        decision_record = {
            "adaptive_decision": adaptive_decision,
            "adaptation_guidance": adaptation,
            "training_cycle": training_cycle,
        }
        store_add_program_version(
            profile_id, token, program_version_id, result, decision_record
        )
        return jsonify({
            "program": result,
            "program_version_id": program_version_id,
            "program_stored": True,
            "movement_assessment_applied": movement_assessment is not None,
            "profile": profile["profile"],
            "adaptation_guidance": adaptation,
            "adaptive_decision": adaptive_decision,
            "exercise_progressions": exercise_progressions,
            "positive_feedback_hold_exercises": sorted(confirmed_successful_exercises),
            "training_cycle": training_cycle,
            "proactive_checkin": build_proactive_checkin(sessions),
            "source": "saved_profile_and_exercise_level_training_feedback",
            "pilot": True,
        }), 200
    except ProgramSafetyBlock as exc:
        return jsonify({"blocked": True, "message": str(exc)}), 409
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)




@coach_bp.route("/coach/profile/<profile_id>/programs", methods=["GET", "OPTIONS"])
def coach_program_versions(profile_id):
    """Return recent saved programme versions for an authenticated profile."""
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        versions = store_list_program_versions(profile_id, _profile_token(), limit=50)
        return jsonify({
            "program_versions": versions,
            "source": "saved_programme_history",
        }), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)

@coach_bp.route("/coach/profile/<profile_id>/adaptation", methods=["GET", "OPTIONS"])
def coach_training_adaptation(profile_id):
    """Return conservative next-step guidance from recent logged feedback."""
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=50)
        _feedback, adaptation = _build_profile_adaptation(sessions)
        adaptive_decision = _build_adaptive_decision(sessions)
        return jsonify({
            "adaptation": adaptation,
            "adaptive_decision": adaptive_decision,
            "source": "recent_recorded_training_feedback_and_longitudinal_history",
            "automatic_program_changes": False,
        }), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)


def _normalize_decision_history(value):
    """Validate a bounded, structured history snapshot supplied by the first-party UI."""
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError("Zgodovina mora vsebovati največ 50 strukturiranih treningov.")
    normalized = []
    valid_reasons = {
        "time_constraint", "high_difficulty", "poor_recovery",
        "external_interruption", "other", "unknown",
    }
    for item in value:
        if not isinstance(item, dict) or set(item) - {"session_date", "session"}:
            raise ValueError("Zapis zgodovine vsebuje nepodprta polja.")
        session_date = item.get("session_date")
        try:
            date.fromisoformat(session_date)
        except (TypeError, ValueError):
            raise ValueError("Datum treninga mora biti v obliki YYYY-MM-DD.")
        raw = item.get("session")
        allowed_session = {
            "completed", "difficulty", "recovery", "exercises",
            "completion_reason", "adaptation_response", "movement_control", "session_key",
            "difficulty_scope", "affected_exercise_id",
        }
        if not isinstance(raw, dict) or set(raw) - allowed_session:
            raise ValueError("Zapis treninga vsebuje nepodprta polja.")
        if not isinstance(raw.get("completed"), bool):
            raise ValueError("completed mora biti true ali false.")
        if raw.get("difficulty") not in {"easy", "moderate", "hard", "unknown"}:
            raise ValueError("Težavnost treninga ni veljavna.")
        if raw.get("recovery") not in {"good", "normal", "poor", "unknown"}:
            raise ValueError("Ocena regeneracije ni veljavna.")
        movement_control = raw.get("movement_control", "none")
        if movement_control not in {"none", "spinal_flexion", "bracing", "both"}:
            raise ValueError("Ocena nadzora trupa ni veljavna.")
        reason = raw.get("completion_reason")
        if reason is not None and reason not in valid_reasons:
            raise ValueError("Razlog nedokončanega treninga ni veljaven.")
        difficulty_scope = raw.get("difficulty_scope", "unknown")
        affected_exercise_id = raw.get("affected_exercise_id")
        if difficulty_scope not in {"unknown", "session", "exercise"}:
            raise ValueError("Obseg zahtevnosti ni veljaven.")
        if difficulty_scope == "exercise":
            if not isinstance(affected_exercise_id, str) or get_exercise(affected_exercise_id) is None:
                raise ValueError("Prizadeta vaja ni veljavna.")
        elif affected_exercise_id is not None:
            raise ValueError("Prizadeta vaja zahteva obseg exercise.")
        response = raw.get("adaptation_response")
        if response is not None and (
            not isinstance(response, dict)
            or set(response) != {"adaptation_id", "outcome"}
            or not isinstance(response.get("adaptation_id"), str)
            or not 8 <= len(response["adaptation_id"]) <= 64
            or response.get("outcome") not in {"helped", "no_change", "worse", "not_tried"}
        ):
            raise ValueError("Odziv na prejšnjo prilagoditev ni veljaven.")
        exercises = raw.get("exercises", [])
        if not isinstance(exercises, list) or len(exercises) > 20:
            raise ValueError("Trening lahko vsebuje največ 20 vaj.")
        clean_exercises = []
        for exercise in exercises:
            clean, error = _normalize_logged_exercise(exercise)
            if error:
                raise ValueError(error)
            clean_exercises.append(clean)
        session_key = raw.get("session_key")
        if session_key is not None and (
            not isinstance(session_key, str) or not 8 <= len(session_key) <= 180
        ):
            raise ValueError("Identifikator treninga ni veljaven.")
        session = {
            "completed": raw["completed"],
            "difficulty": raw["difficulty"],
            "recovery": raw["recovery"],
            "movement_control": movement_control,
            "exercises": clean_exercises,
        }
        if session_key is not None:
            session["session_key"] = session_key
        if reason is not None:
            session["completion_reason"] = reason
        if difficulty_scope != "unknown":
            session["difficulty_scope"] = difficulty_scope
        if affected_exercise_id is not None:
            session["affected_exercise_id"] = affected_exercise_id
        if response is not None:
            session["adaptation_response"] = response
        normalized.append({"session_date": session_date, "session": session})
    return sorted(normalized, key=lambda row: row["session_date"], reverse=True)


@coach_bp.route("/coach/adaptive-decision", methods=["POST", "OPTIONS"])
def coach_adaptive_decision():
    """Evaluate a privacy-minimised history snapshot without persisting it on Render."""
    if request.method == "OPTIONS":
        return ("", 204)
    expected = os.getenv("AI_COACH_TEST_TOKEN", "").strip()
    supplied = request.headers.get("X-Pilot-Token", "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Testni dostopni ključ ni pravilen."}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"sessions"}:
        return jsonify({"error": "Pošlji samo strukturirano polje sessions."}), 400
    try:
        sessions = _normalize_decision_history(payload["sessions"])
        latest_response = sessions[0]["session"].get("adaptation_response") if sessions else None
        if latest_response is not None:
            if len(sessions) < 2:
                return jsonify({"error": "Odziv na prilagoditev nima predhodnega treninga.", "code": "adaptation_id_mismatch"}), 409
            expected_id = _build_adaptive_decision(sessions[1:])["adaptation_id"]
            if not hmac.compare_digest(latest_response["adaptation_id"], expected_id):
                return jsonify({"error": "Odziv se ne nanaša na zadnjo prilagoditev, ki jo je izdala ATENA.", "code": "adaptation_id_mismatch"}), 409
        exercise_progressions = recommend_exercise_progression(sessions)
        longitudinal_progression = summarize_longitudinal_progression(sessions)
        conditioning_progression = summarize_conditioning_progress(sessions)
        decision = _build_adaptive_decision(
            sessions, exercise_progressions, longitudinal_progression,
            conditioning_progression,
        )
        return jsonify({
            "adaptive_decision": decision,
            "exercise_progressions": exercise_progressions,
            "longitudinal_progression": longitudinal_progression,
            "conditioning_progression": conditioning_progression,
            "source": "privacy_minimised_training_history_snapshot",
            "history_sessions_analyzed": len(sessions),
            "automatic_program_changes": False,
        }), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
