"""Language selection and deterministic response localization for ATENA."""
from __future__ import annotations

import re

SUPPORTED_LANGUAGES = {"en", "sl"}


def normalize_language(value: object) -> str | None:
    """Normalize supported language tags; return None for unsupported values."""
    if not isinstance(value, str):
        return None
    value = value.strip().replace("_", "-").casefold()
    if not value:
        return None
    primary = value.split("-", 1)[0]
    return primary if primary in SUPPORTED_LANGUAGES else None


def resolve_response_language(messages: list[dict], requested_language: object = None) -> str:
    """Use an explicit client locale first, then the latest user turn; default to English."""
    explicit = normalize_language(requested_language)
    if explicit:
        return explicit
    latest = next(
        (item.get("content", "") for item in reversed(messages)
         if isinstance(item, dict) and item.get("role") == "user"
         and isinstance(item.get("content"), str)),
        "",
    )
    lowered = latest.casefold()
    if re.search(r"[čćžšđ]", lowered) or re.search(
        r"\b(?:živjo|živijo|prosim|želim|rad bi|rada bi|imam|nimam|trening|vadba|počep|boli|koleno|mišice|moč|vzdržljivost|oprema|roke|hrbet)\b",
        lowered,
    ):
        return "sl"
    return "en"


def language_instruction(language: str) -> str:
    """Return a concise, explicit output-language contract for the model."""
    if language == "sl":
        return (
            "RESPONSE LANGUAGE: Slovenian (sl-SI). Reply entirely in natural, "
            "grammatically correct Slovenian. Keep standard exercise names or "
            "technical abbreviations in English only when they are commonly used; "
            "explain them briefly in Slovenian. Do not switch languages mid-answer."
        )
    return (
        "RESPONSE LANGUAGE: English (en). Reply entirely in natural, clear, "
        "grammatically correct international English. Use standard strength-and-"
        "conditioning terminology, explain specialist terms briefly when useful, "
        "and do not switch languages mid-answer."
    )


def localize_guardrail_reply(reply: str, language: str) -> str:
    """Localize high-priority deterministic safety/persistence replies without model calls."""
    if language != "en" or not isinstance(reply, str):
        return reply
    lowered = reply.casefold()
    if "noge ne moreš normalno obremeniti" in lowered:
        return (
            "Because you cannot bear weight normally on your leg, you need an urgent "
            "medical assessment today. Do not perform squats, lunges, or other loaded "
            "exercises, and do not test the knee with additional movements. Contact an "
            "urgent medical service; call 112 if the situation is severe, rapidly "
            "worsening, or you cannot get help safely. I cannot diagnose the cause."
        )
    if "oteklina ali zaklepanje kolena" in lowered:
        return (
            "Knee swelling or locking can be warning signs. For now, avoid squats, "
            "lunges, and other loaded movements involving that knee. Arrange a prompt "
            "medical assessment before loading it again. If you cannot bear weight "
            "normally, seek urgent medical care today. Can you currently put weight "
            "through that leg and walk normally?"
        )
    if "ne nadaljuj avtomatično" in lowered:
        return (
            "Do not automatically continue with the original plan while poor sleep and "
            "muscle fatigue are still present. Postpone demanding training until you "
            "feel better. If you want to stay active, choose only easy activity that "
            "does not increase fatigue or cause pain. Do not make up missed training "
            "by doubling the workload. Is the fatigue mainly in the muscles you trained, "
            "or do you also feel generally exhausted?"
        )
    if "ne morem potrditi" in lowered and "shranjen" in lowered:
        return (
            "I cannot confirm that your next workout has been changed or saved. A chat "
            "message alone does not update your programme. I can recommend an adjustment "
            "based on your feedback, but I must not describe it as saved until the "
            "dedicated programme or profile process confirms it."
        )
    if "preden pripravim individualni trening" in lowered or "varnostnega vprašanja" in lowered:
        return (
            "I can use the information you have shared, but I still need to clarify one "
            "safety point before prescribing an individualized programme or training "
            "loads. Do you currently have any pain, injury, movement limitation, or "
            "medical restriction I should take into account?"
        )
    return (
        "I need to clarify one safety or movement detail before I can recommend an "
        "individualized exercise or training load. Please tell me what you are "
        "experiencing and where in the movement it occurs. I will not guess or "
        "progress the exercise until that is clear."
    )
