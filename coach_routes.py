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
import uuid
from datetime import date

from coach_store import (
    StorageUnavailable, ProfileNotFound, create_profile as store_create_profile,
    get_profile as store_get_profile, update_profile as store_update_profile,
    add_session as store_add_session, list_sessions as store_list_sessions,
    delete_profile as store_delete_profile, set_health_data_consent as store_set_health_data_consent,
    check_database_connection as store_check_database_connection, storage_enabled,
)
from training.catalogue import get_exercise, load_catalogue
from flask import Blueprint, jsonify, request
from training.program import ProgramSafetyBlock, ProgramValidationError, generate_program
from training.progress import summarize_progress
from training.adaptation import assess_next_step
from training.coaching_protocols import RDL_TECHNIQUE_PROTOCOL

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
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Pilot-Token, X-Profile-Token"
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
    patterns = (
        r"\bnimam\b[^.\n]{0,80}\b(?:bolečin|poškodb|omejitev)\b",
        r"\bbrez\b[^.\n]{0,60}\b(?:bolečin|poškodb|omejitev)\b",
        # The website intake form records an explicit negative answer in this
        # structured profile summary. Treat that exact statement as clearance;
        # do not confuse it with an absent/unknown value such as "none reported".
        r"\btrenutna\s+bolečina\s*/\s*poškodba\s*/\s*zdravstvena\s+omejitev\s*:\s*ne\b",
        r"\bno (?:pain|injuries|limitations)\b",
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
    records.sort(key=lambda item: (priority.get(item["training_role"], 9), item["single_joint"], item["name"]))
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
        r"bolečina se pojavi|nova bolečina|po treningu.{0,30}bolečin)",
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

    if positive_pain:
        return (
            "Za zdaj ne ponavljaj giba v isti dozi, če sproža bolečino; to ne pomeni, da moraš "
            "prekiniti vso nebolečo aktivnost. Do razjasnitve bolečega giba ga ne nadomeščaj z "
            "drugo obremenjeno vajo. Kje natančno se pojavi bolečina, kakšna je in kako močna "
            "je od 0 do 10, pri katerem gibu nastane ter ali po prenehanju izzveni? Če gre za "
            "blago, znano nelagodje brez opozorilnih znakov, lahko nato prilagodiva eno "
            "spremenljivko doze (obseg, obremenitev, število serij, pogostost ali tempo) in "
            "preveriva odziv. Ob novi, hudi, slabšajoči se ali vztrajni bolečini oziroma "
            "oteklini, zaklepanju, popuščanju ali nezmožnosti obremenitve poišči strokovno oceno."
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
1) main goal (e.g. strength, muscle development, conditioning, general functional fitness, explosive power, mobility or return to activity);
2) current experience and approximate ability;
3) available equipment and realistic time;
4) major health conditions, recent injuries, medical restrictions, and any discomfort that changes a movement;
5) weekly availability and, when relevant, age range or other factors affecting exercise selection.
Ask one concise, high-value question at a time. SAFETY-FIRST ORDER: before individualized programming, confirm whether any major health condition, recent injury, medical restriction or concerning symptom requires professional assessment. Do not demand that a user be completely pain-free. If the user has only mild, familiar discomfort, clarify the affected movement and use the dose/tolerance process below; do not automatically exclude all training. Do not ask about equipment, time or training frequency before this initial safety check. If the user confirms no major restriction, continue with the main goal, experience, equipment, realistic training time and weekly availability, one question at a time. Do not overwhelm the user with a long intake form. If the request is simple and low risk, you may give a clearly labelled general example while explaining that it is not yet individualized, and ask the most important follow-up question. If safety-relevant information is missing, ask before recommending demanding exercise.

MANDATORY DECISION GATES – NON-NEGOTIABLE
- SCOPE OF THE SAFETY GATE: Before an individualized program, establish that no major health condition, recent injury, medical restriction or concerning symptom needs professional assessment. If this information is missing or ambiguous, ask one concise safety question and stop before giving a demanding individualized prescription. An explicit negative answer in the structured profile to this major-restriction question counts; do not repeatedly ask it. "Not reported" is not equivalent to "confirmed absent". Do not treat mild, familiar discomfort as an automatic ban on all training; clarify the affected movement and apply the pain/dose process before prescribing that pattern.
- GENERAL EDUCATION: You may answer conceptual questions (e.g. what tempo means, why aerobic base matters, what controlled ROM means) without turning the answer into an individualized workout. Do not append an irrelevant safety question to a purely educational answer. If you move from explanation to prescribing a specific exercise or plan, first complete the safety gate.
- PAIN AND DOSE MANAGEMENT: Treat discomfort as feedback, not a diagnosis. If a movement provokes sharp, worsening or function-changing pain, stop that specific movement at that dose; never tell the user to push through. Clarify exact location, intensity (0–10), trigger, onset, dose, response after stopping and next-day response. For mild, familiar discomfort without warning signs, do not prohibit all activity. Use test → modify → observe → retest. Change one dose variable at a time: load, range of motion, sets/volume, frequency, tempo or speed. Start with a low, controlled dose and state clear stop criteria. Do not recommend a new loaded substitute until the context is clear. Do not diagnose or promise treatment. For severe, new, worsening or persistent symptoms, acute trauma, marked swelling, locking, giving way, inability to bear weight or other concerning symptoms, stop testing and recommend professional assessment.
- BALANCE / CONTROL PROBLEMS: When a person reports losing balance or control, first ask when and where it happens and whether pain or discomfort is present. Do not assume the cause is ankle mobility, trunk position or load direction. Do not prescribe heel elevation, unstable surfaces or a harder unilateral variation before clarifying the problem.
- MOBILITY LIMITATIONS: Never say a restriction can simply be "bypassed". Clarify whether the issue is range, discomfort, balance or control. Do not prescribe a modification before that clarification. When appropriate, describe heel support as changing the effective ankle angle/position, not as improving the person's actual ankle mobility.
- STABILIZATION: Do not add generic "core" or stabilization exercises as mandatory filler in a hypertrophy plan. Include them only when feedback identifies a specific control deficit or the exercise serves a stated goal. Do not claim they prevent injury or reduce spinal overload without specific evidence and context.
- BODYWEIGHT-ONLY EQUIPMENT: Do not call a bodyweight squat a Goblet squat, do not imply a dumbbell/bench/band is available, and do not use a machine or prop unless the profile explicitly lists it. Prefer clear names for the actual variation.
- BODYWEIGHT-ONLY HYPERTROPHY LIMITS: Without external equipment, do not call an unloaded hip hinge an RDL or imply it provides the same loading potential as a loaded hinge. Call it "predklon z ravnim hrbtom brez dodatne obremenitve". Explicitly explain when a meaningful horizontal pulling movement cannot be loaded safely without a confirmed anchor or equipment; never invent table rows, door anchors or improvised supports. Explain realistic progression options and their limits.
- LOADED BALANCE REGRESSION: If a bodyweight squat is stable but instability appears only after adding load, do not move the load to the shoulders or prescribe a harder variation as the first step. Keep the person at the stable bodyweight variation, do not increase load, and ask which load triggered the loss of control before considering progression.
- ANKLE DORSIFLEXION: Do not recommend a front squat as an automatic way to reduce ankle dorsiflexion demand. Its more upright torso and forward knee travel can require as much or more ankle dorsiflexion. If the heel lifts, check whether a stable heel support is actually available before suggesting heel elevation. Heel support changes the effective ankle angle; it does not increase actual ankle mobility.
- LOAD PROGRESSION: Do not prescribe a fixed kilogram increase when the exact exercise, current load and completed repetitions are unknown. Confirm stable technique and successful completion of the target repetitions; change one variable at a time and make only a small, conditional progression.
- SLOVENIAN TERMINOLOGY: Use idiomatic exercise names such as "potisk za prsi" rather than "prsni tisk". Avoid literal translations and grammatically malformed muscle or movement descriptions.
- BEGINNER PRESCRIPTION: For beginners, prioritize learning and repeatable technique. As a default, use roughly 8–12 or 10–15 repetitions for general strength learning and hypertrophy, with a manageable load and about 2–4 repetitions in reserve. Do not default beginners to 4–6 or 5–8 repetitions merely because the goal says strength. Use lower ranges only with a clear exercise-specific reason and sufficient competency.
- POWER PRESCRIPTION: Do not prescribe a universal percentage of 1RM for explosive-power work. Use low repetitions (commonly 2–3), full recovery, maximal intent with a controllable load, and stop when speed or technique declines. Give a percentage only when the user has a reliable tested 1RM for that exact lift and the percentage is justified. Never invent exercise names such as "izbruh z drogom".
- STRENGTH WITH LIMITED TIME: Do not shorten rest intervals arbitrarily to force a heavy strength session into a short time window. Preserve adequate recovery for the main lift and reduce accessory exercises or total sets instead.
- EXERCISE NAMING AND CATALOGUE: Use verified exercise names from the supplied catalogue context when available. In Slovenian, call the Romanian-deadlift pattern "predklon z ravnim hrbtom" as the primary label; you may add "(RDL)" in parentheses. Do not use "paleta" for a barbell (use "drog" or "olimpijska palica"), "voravnotežen", or "romunski dvig trupa". Never call a bodyweight squat "Goblet počep". Do not invent compound words or literal translations.
- TRAINING VOLUME: For a typical full-body session, usually choose 4–5 purposeful exercises, not a long list of filler. Match the number of work sets to experience, weekly frequency, recovery and available time. Do not automatically add single-joint or stabilization exercises to a hypertrophy session.
- TEMPO ACCURACY: In a tempo such as 3-1-2-0, the phases are exactly 3 seconds eccentric, 1-second pause, 2 seconds concentric, 0-second pause. Never change a digit while explaining it. Tempo is a tool, not a universal optimum; do not claim that time under tension alone makes a tempo superior.
- ENDURANCE ACCURACY: Distinguish aerobic base, threshold, VO2max intervals and mixed-modal conditioning. Do not claim that Zone 2 is simply "fat-burning training", that MetCon inherently overworks the nervous system, or that a particular method prevents overtraining/injury. Explain trade-offs without exaggerated physiological claims.
- PROFILE AND IDENTITY HONESTY: Do not invent the user's name, equipment, training frequency, session duration, training history, saved profile or prior feedback. The name Grega in the coach's role identifies the coach/brand owner, not automatically the user; do not address the user as Grega unless the user has identified themselves that way. If the profile says "none reported", explain naturally in Slovenian that the profile does not yet contain confirmed information about symptoms; do not translate the phrase literally.
- PERSISTENCE HONESTY: If asked whether a workout or next session has already been changed/saved, answer that question directly first. A chat reply does not itself save feedback or alter a future workout. Say clearly whether an update was actually confirmed by the profile/program storage workflow. If not confirmed, state that no saved change can be confirmed; you may offer a proposed adjustment, but do not imply it has been applied.
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
    system_prompt = SYSTEM_PROMPT
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
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + api_key
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 900}
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=65) as response:
            data = json.loads(response.read().decode("utf-8"))
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        answer = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        if not answer:
            logger.warning("Gemini returned no text for model %s", model)
            return jsonify({"error": "Model ni vrnil odgovora. Poskusi znova."}), 502
        answer = _normalize_slovene_coaching_terms(answer)
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
            "model": model,
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
    try:
        result = generate_program(profile, feedback=feedback)
    except ProgramSafetyBlock as exc:
        return jsonify({"blocked": True, "message": str(exc)}), 409
    except ProgramValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, ValueError):
        logger.exception("ATENA catalogue/program generation failed")
        return jsonify({"error": "Programa trenutno ni mogoče sestaviti iz kataloga."}), 500
    return jsonify({"program": result, "source": "curated_exercise_catalogue", "pilot": True}), 200



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
PROFILE_GOALS = {"strength", "hypertrophy", "fat_loss", "general_fitness", "functional", "power", "endurance", "mobility"}
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
    if not isinstance(equipment, list) or len(equipment) > 25 or any(
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
    allowed = {"session_date", "duration_minutes", "difficulty", "completed", "exercises", "discomfort_reported", "recovery"}
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
    exercises = payload.get("exercises")
    if not isinstance(exercises, list) or len(exercises) > 20:
        return jsonify({"error": "Vadbeni zapis lahko vsebuje največ 20 vaj."}), 400
    clean_exercises = []
    for item in exercises:
        if not isinstance(item, dict) or set(item) - {"exercise_id", "sets_completed", "reps_completed", "work_seconds_completed", "load_kg", "rir"}:
            return jsonify({"error": "Zapis vaje vsebuje neveljavna polja."}), 400
        exercise_id = item.get("exercise_id")
        if not isinstance(exercise_id, str) or get_exercise(exercise_id) is None:
            return jsonify({"error": "Vaja ni v preverjenem katalogu ATENA."}), 400
        sets = item.get("sets_completed")
        reps = item.get("reps_completed")
        work_seconds = item.get("work_seconds_completed")
        if not isinstance(sets, int) or isinstance(sets, bool) or not 1 <= sets <= 20:
            return jsonify({"error": "Število izvedenih serij ni veljavno."}), 400
        if reps is not None and (not isinstance(reps, int) or isinstance(reps, bool) or not 1 <= reps <= 100):
            return jsonify({"error": "Število ponovitev ni veljavno."}), 400
        if work_seconds is not None and (not isinstance(work_seconds, int) or isinstance(work_seconds, bool) or not 1 <= work_seconds <= 3600):
            return jsonify({"error": "Trajanje delovne serije ni veljavno."}), 400
        if reps is None and work_seconds is None:
            return jsonify({"error": "Za vajo je treba navesti ponovitve ali trajanje delovne serije."}), 400
        entry = {"exercise_id": exercise_id, "sets_completed": sets}
        if reps is not None:
            entry["reps_completed"] = reps
        if work_seconds is not None:
            entry["work_seconds_completed"] = work_seconds
        load = item.get("load_kg")
        if load is not None:
            if not isinstance(load, (int, float)) or isinstance(load, bool) or not 0 <= load <= 1000:
                return jsonify({"error": "Obremenitev ni veljavna."}), 400
            entry["load_kg"] = float(load)
        rir = item.get("rir")
        if rir is not None:
            if not isinstance(rir, int) or isinstance(rir, bool) or not 0 <= rir <= 10:
                return jsonify({"error": "RIR mora biti med 0 in 10."}), 400
            entry["rir"] = rir
        clean_exercises.append(entry)

    discomfort = payload.get("discomfort_reported")
    if discomfort is not None and not isinstance(discomfort, bool):
        return jsonify({"error": "discomfort_reported mora biti true ali false."}), 400
    session = {
        "duration_minutes": duration, "difficulty": difficulty,
        "recovery": recovery, "completed": payload["completed"], "exercises": clean_exercises,
    }
    try:
        profile = store_get_profile(profile_id, token)
        if discomfort is not None:
            if not profile["health_data_consent"]:
                return jsonify({"error": "Za shranjevanje podatka o nelagodju je potrebna ločena privolitev za zdravstvene podatke."}), 403
            session["discomfort_reported"] = discomfort
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



@coach_bp.route("/coach/profile/<profile_id>/progress", methods=["GET", "OPTIONS"])
def coach_training_progress(profile_id):
    """Return descriptive training trends; never prescribe automatic load increases."""
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=50)
        return jsonify({
            "progress": summarize_progress(profile, sessions),
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
        response = jsonify({
            "export_version": "1.0",
            "profile": profile,
            "sessions": sessions,
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
            "message": "Programa nisem ustvaril. Ob trenutni bolečini, poškodbi ali zdravstveni omejitvi je potrebna individualna presoja ustreznega strokovnjaka.",
        }), 409
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        # Use enough history to enforce the same progression gate shown in the
        # adaptation endpoint: two completed, easy sessions with RIR >= 3.
        sessions = store_list_sessions(profile_id, token, limit=3)
        feedback, adaptation = _build_profile_adaptation(sessions)
        result = generate_program(profile["profile"], feedback=feedback)
        return jsonify({
            "program": result,
            "profile": profile["profile"],
            "adaptation_guidance": adaptation,
            "source": "saved_profile_and_recent_training_feedback",
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


@coach_bp.route("/coach/profile/<profile_id>/adaptation", methods=["GET", "OPTIONS"])
def coach_training_adaptation(profile_id):
    """Return conservative next-step guidance from recent logged feedback."""
    if request.method == "OPTIONS":
        return ("", 204)
    token = _profile_token()
    try:
        profile = store_get_profile(profile_id, token)
        sessions = store_list_sessions(profile_id, token, limit=3)
        _feedback, adaptation = _build_profile_adaptation(sessions)
        return jsonify({
            "adaptation": adaptation,
            "source": "recent_recorded_training_feedback",
            "automatic_program_changes": False,
        }), 200
    except ProfileNotFound:
        return _profile_auth_error()
    except StorageUnavailable as exc:
        return _storage_error(exc)
