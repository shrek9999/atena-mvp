"""Structured movement-quality observation framework for ATENA.

This is a coach-facing observation aid, not a diagnostic screen or pass/fail test.
It operationalises the coaching loop: test -> manipulate -> observe -> progress.
Only recorded observations are interpreted; missing evidence stays unknown.
"""
from __future__ import annotations

ASSESSMENT_VERSION = "1.0"

# Each criterion is observable during a coached task. "look_for" describes
# movement quality, not pathology. Follow-ups are simple manipulations that
# help a coach test a hypothesis rather than assume a cause.
MOVEMENT_RUBRICS = {
    "squat": {
        "task": "Počep",
        "criteria": {
            "foot_tripod": "Ohranja stik in porazdelitev pritiska prek pete ter glavice 1. in 5. stopalnice.",
            "ankle_knee_hip_coordination": "Gibanje poteka usklajeno v gležnju, kolenu in kolku.",
            "ankle_dorsiflexion": "Doseže potrebno dorzalno fleksijo brez izgube opore stopala.",
            "knee_control": "Koleno sledi smeri stopala brez nenadzorovanega medialnega pomika.",
            "trunk_control": "Ohranja nadzorovan položaj trupa skozi celotno amplitudo.",
            "pelvic_control": "Ohranja nadzor medenice; morebitno podvijanje ocenimo glede na obseg, obremenitev in simptome.",
            "range_control": "Uporabi največjo razpoložljivo amplitudo, ki jo lahko nadzoruje.",
            "tempo_control": "Ohranja predpisani tempo, npr. 3 s spust, 1 s zadržek, 1 s dvig.",
        },
        "manipulations": [
            "Ponovi počep do višje tarče oziroma na klop.",
            "Primerjaj običajno izvedbo z rahlo privzdignjeno peto.",
            "Zmanjšaj globino in preveri, ali se nadzor izboljša.",
            "Ponovi z oporo rok, nato oporo postopno zmanjšaj.",
        ],
        "coaching_options": ["prilagodi globino", "uporabi oporo", "upočasni tempo", "izberi goblet ali reaching različico", "postopno povečaj amplitudo"],
    },
    "hinge": {
        "task": "Predklon z ravnim hrbtom",
        "criteria": {
            "hip_strategy": "Gibanje se začne s pomikom kolkov nazaj; kolena se prilagodijo nalogi.",
            "spine_pelvis_control": "Ohranja nadzorovan odnos trupa in medenice skozi amplitudo.",
            "dowel_neutral_spine": "Pri učenju s palico ohranja tri stične točke (trtica oziroma križnično-sakralni predel, torakalni del hrbtenice, zadnji del glave) in nespremenjen položaj roke v ledveni krivini kot četrto kontrolno točko.",
            "foot_pressure": "Ohranja stabilno oporo stopal brez nenadzorovanega prenosa teže.",
            "load_path": "Breme, kadar je prisotno, ostaja blizu telesa in pod nadzorom.",
            "range_control": "Ustavi amplitudo, preden izgubi nadzor položaja.",
            "tempo_control": "Ohranja predpisani tempo brez sunkov ali pospeševanja skozi kritični del.",
        },
        "manipulations": [
            "Vadi predklon s palico: tri stične točke ostanejo v stiku, roka v ledveni krivini pa ohranja nespremenjen položaj kot četrta kontrolna točka.",
            "Vadi odmik bokov proti steni.",
            "Zmanjšaj amplitudo in uporabi lahek predmet kot tarčo.",
            "Primerjaj izvedbo brez bremena in z lahkim kettlebellom.",
            "Uporabi podporo ene roke in preveri nadzor.",
        ],
        "coaching_options": ["stenska vaja za vzorec", "zmanjšaj amplitudo", "zmanjšaj breme", "uporabi dvig s povišane podlage", "napreduj v RDL ali deadlift različico"],
    },
    "lunge": {
        "task": "Izpadni korak / enonožni počep",
        "criteria": {
            "stance_and_foot": "Ohranja stabilno postavitev stopal in oporo sprednje noge.",
            "knee_tracking": "Koleno sprednje noge sledi smeri stopala.",
            "pelvis_and_trunk": "Ohranja nadzor medenice in trupa brez nenadzorovanega nagiba ali rotacije.",
            "balance_control": "Ohranja ravnotežje skozi celotno ponovitev.",
            "range_control": "Uporabi amplitudo, ki jo lahko ponovi brez izgube nadzora.",
            "tempo_control": "Ohranja dogovorjeni tempo v ekscentrični in koncentrični fazi.",
        },
        "manipulations": [
            "Začni s statičnim razkorakom in manjšo amplitudo.",
            "Dodaj oporo roke in preveri kakovost izvedbe.",
            "Primerjaj split squat z vzvratnim izpadnim korakom.",
            "Zmanjšaj globino ali obseg ponovitev, če se nadzor poslabša.",
        ],
        "coaching_options": ["statični split squat", "opora roke", "krajša amplituda", "vzvratni izpadni korak", "postopno večji obseg"],
    },
    "horizontal_push": {
        "task": "Horizontalni potisk / skleca",
        "criteria": {
            "trunk_alignment": "Ohranja nadzorovan položaj trupa in medenice.",
            "scapular_control": "Lopatici se gibljeta nadzorovano glede na fazo potiska.",
            "elbow_path": "Pot komolcev je nadzorovana in ustreza izbrani različici.",
            "range_control": "Doseže ponovljivo amplitudo brez izgube položaja.",
            "tempo_control": "Ohranja predpisani tempo tudi v zadnjih ponovitvah.",
        },
        "manipulations": [
            "Dvigni oporo rok (stena, višja klop) in ponovno opazuj.",
            "Zmanjšaj amplitudo, nato jo postopno povečuj.",
            "Zmanjšaj število ponovitev in preveri kakovost zadnje ponovitve.",
        ],
        "coaching_options": ["skleca ob steni", "skleca na višji opori", "skleca na nižji opori", "polna skleca"],
    },
    "horizontal_pull": {
        "task": "Horizontalni poteg / veslanje",
        "criteria": {
            "anchor_safety": "Opora oziroma sidrišče je stabilno in primerno za obremenitev.",
            "trunk_control": "Ohranja nadzor trupa brez sunkovitega iztega ali rotacije.",
            "scapular_control": "Lopatici se gibljeta nadzorovano brez prisilnega položaja.",
            "elbow_path": "Pot komolcev je nadzorovana in skladna z različico.",
            "range_control": "Ohranja ponovljivo amplitudo brez izgube položaja.",
            "tempo_control": "Ohranja nadzorovano vračanje bremena.",
        },
        "manipulations": [
            "Zmanjšaj naklon telesa pri TRX/ring veslanju.",
            "Zmanjšaj breme pri veslanju z utežjo ali elastiko.",
            "Preveri sidrišče pred vsako serijo; ne uporabljaj nestabilnega pohištva.",
        ],
        "coaching_options": ["veslanje z elastiko", "pokončnejše TRX/ring veslanje", "veslanje z ročko", "postopno večji naklon ali breme"],
    },
    "vertical_push": {
        "task": "Vertikalni potisk",
        "criteria": {
            "overhead_range": "Doseže razpoložljivo amplitudo nad glavo brez siljenja v končni položaj.",
            "scapular_motion": "Lopatica se med dvigom nadzorovano obrača navzgor.",
            "trunk_compensation": "Ne nadomešča giba z nenadzorovanim iztegom ledvenega dela.",
            "load_control": "Breme ostaja nadzorovano v celotni poti.",
            "tempo_control": "Ohranja dogovorjeni tempo brez sunkov.",
        },
        "manipulations": [
            "Primerjaj izvedbo brez bremena in z lažjim bremenom.",
            "Uporabi enoročno ali nevtralno različico, če izboljša nadzor.",
            "Zmanjšaj amplitudo na območje, ki ga lahko nadzoruje.",
        ],
        "coaching_options": ["potisk brez bremena", "potisk z elastiko", "enoročni potisk", "potisk z ročkami"],
    },
    "vertical_pull": {
        "task": "Vertikalni poteg",
        "criteria": {
            "grip_and_hang_tolerance": "Ohranja varen oprijem in toleranco položaja, če vaja vključuje visenje.",
            "scapular_control": "Začne in nadzoruje gibanje lopatic brez sunkov.",
            "trunk_control": "Ohranja nadzor trupa brez nihanja.",
            "range_control": "Uporabi ponovljivo amplitudo, ki jo lahko nadzoruje.",
            "tempo_control": "Nadzoruje tudi ekscentrično vračanje.",
        },
        "manipulations": [
            "Začni z elastiko ali pomočjo stopal.",
            "Uporabi lat pulldown, če visenje še ni primerno.",
            "Zmanjšaj amplitudo in preveri nadzor lopatic.",
        ],
        "coaching_options": ["pulldown z elastiko", "lat pulldown", "stopalno podprt zgib", "asistiran zgib", "zgib"],
    },
    "locomotion": {
        "task": "Hoja / tek",
        "criteria": {
            "rhythm_and_continuity": "Ohranja enakomeren ritem in kontinuiteto gibanja.",
            "postural_control": "Ohranja funkcionalen nadzor trupa med gibanjem.",
            "step_control": "Korak je ponovljiv in brez očitne izgube nadzora.",
            "effort_tolerance": "Obremenitev je primerna trenutni pripravljenosti in odzivu vadečega.",
            "symptom_response": "Spremlja odziv med aktivnostjo in po njej.",
        },
        "manipulations": [
            "Začni s krajšo hojo in postopno podaljšuj trajanje.",
            "Zmanjšaj hitrost ali naklon in ponovno opazuj.",
            "Tek obravnavaj ločeno od hoje; napreduj postopno glede na odziv.",
        ],
        "coaching_options": ["hoja", "živahna hoja", "izmenjava hoje in teka", "lahek tek"],
    },
    "jump_landing": {
        "task": "Skok in doskok (ločena presoja pripravljenosti)",
        "criteria": {
            "takeoff_control": "Odriv je ponovljiv in pod nadzorom.",
            "landing_foot_control": "Doskok je tih, stabilen in nadzorovan.",
            "knee_hip_trunk_control": "Kolki, kolena in trup sodelujejo pri zaviranju brez očitne izgube nadzora.",
            "balance_after_landing": "Po doskoku lahko zadrži stabilen položaj.",
            "repeatability": "Kakovost ostane podobna pri več ponovitvah.",
        },
        "manipulations": [
            "Najprej preveri nadzorovan počep in dvig na prste.",
            "Nadaljuj z nizkim poskokom na mestu samo, če je to primerno.",
            "Preveri posamezen doskok z zelo majhne višine; višine ne povečuj avtomatično.",
        ],
        "coaching_options": ["brez skokov", "dvigi na prste", "nizek poskok na mestu", "nizek skok z nadzorovanim doskokom"],
        "requires_explicit_readiness_review": True,
    },
}

VALID_OBSERVATIONS = {"controlled", "needs_attention", "not_observed", "not_applicable"}


class MovementQualityError(ValueError):
    """Raised when structured movement observations are malformed."""


def get_movement_rubric(pattern: str) -> dict:
    """Return a defensive copy of the rubric for one movement task."""
    if pattern not in MOVEMENT_RUBRICS:
        raise MovementQualityError(f"Nepodprt gibalni vzorec: {pattern}.")
    rubric = MOVEMENT_RUBRICS[pattern]
    return {
        **rubric,
        "criteria": dict(rubric["criteria"]),
        "manipulations": list(rubric["manipulations"]),
        "coaching_options": list(rubric["coaching_options"]),
    }


def summarize_movement_observation(pattern: str, observations: object, tempo: str | None = None) -> dict:
    """Summarise recorded observations without diagnosis or automatic clearance.

    A needs_attention observation creates a coaching prompt, not a diagnosis.
    Unobserved criteria remain unknown and never count as successful.
    """
    rubric = get_movement_rubric(pattern)
    if not isinstance(observations, dict) or not observations:
        raise MovementQualityError("Vnesi vsaj eno opažanje.")
    unknown = sorted(set(observations) - set(rubric["criteria"]))
    if unknown:
        raise MovementQualityError("Neznana merila: " + ", ".join(unknown))
    invalid = {key: value for key, value in observations.items() if value not in VALID_OBSERVATIONS}
    if invalid:
        raise MovementQualityError("Neveljavna oznaka opažanja.")
    attention = [key for key, value in observations.items() if value == "needs_attention"]
    missing = [key for key in rubric["criteria"] if observations.get(key, "not_observed") == "not_observed"]
    if tempo is not None and (not isinstance(tempo, str) or not tempo.strip()):
        raise MovementQualityError("Tempo mora biti neprazen niz.")
    return {
        "version": ASSESSMENT_VERSION,
        "pattern": pattern,
        "scope": "coaching_observation_not_clinical_assessment",
        "observations": dict(observations),
        "needs_attention": attention,
        "not_observed": missing,
        "tempo_observed": tempo,
        "recommended_process": "test_manipulate_observe_progress",
        "suggested_manipulations": list(rubric["manipulations"]) if attention else [],
        "coaching_options": list(rubric["coaching_options"]) if attention else [],
        "automatic_exercise_change": "none",
        "automatic_readiness_clearance": False,
        "requires_explicit_readiness_review": bool(rubric.get("requires_explicit_readiness_review", False)),
    }
