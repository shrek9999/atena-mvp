#!/usr/bin/env python3
"""Run the live ATENA multi-turn conversation benchmark against the Render pilot.

Uses only the Python standard library. The pilot token is supplied by GitHub
Actions Secrets and is never printed or written to the report.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "conversation_quality_benchmark_v1.json"
OUT_DIR = ROOT / "benchmark-results"
OUT_JSON = OUT_DIR / "live-conversation-benchmark.json"
OUT_MD = OUT_DIR / "live-conversation-benchmark.md"
REPEATS = int(os.environ.get("ATENA_BENCHMARK_REPEATS", "2"))
BACKEND = os.environ.get(
    "ATENA_BENCHMARK_BACKEND",
    "https://atena-ai-coach-pilot.onrender.com",
).rstrip("/")
TOKEN = os.environ.get("AI_COACH_TEST_TOKEN", "").strip()


def select_scenarios(scenarios: list[dict], selection: str) -> list[dict]:
    """Select an ordered subset; empty, ALL, or FULL means the complete suite."""
    normalized = selection.strip()
    if not normalized or normalized.upper() in {"ALL", "FULL"}:
        return list(scenarios)
    requested = [item.strip() for item in normalized.split(",") if item.strip()]
    duplicates = sorted({item for item in requested if requested.count(item) > 1})
    if duplicates:
        raise ValueError("Duplicate scenario ID(s) would cause repeated model calls: " + ", ".join(duplicates))
    by_id = {item.get("id"): item for item in scenarios}
    unknown = [item for item in requested if item not in by_id]
    if unknown:
        raise ValueError("Unknown benchmark scenario ID(s): " + ", ".join(unknown))
    return [by_id[item] for item in requested]


def request_chat(messages: list[dict[str, str]]) -> dict:
    payload = json.dumps({"messages": messages}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BACKEND + "/coach/chat",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Pilot-Token": TOKEN,
            "User-Agent": "ATENA-live-conversation-benchmark/1.0",
        },
        method="POST",
    )
    transient_statuses = {429, 500, 502, 503, 504}
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=100) as response:
                data = json.loads(response.read().decode("utf-8"))
                if response.status != 200 or not isinstance(data.get("reply"), str):
                    raise RuntimeError(f"Unexpected HTTP {response.status} response shape")
                return data
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                message = parsed.get("error", "Unknown API error")
            except json.JSONDecodeError:
                message = detail[:300]
            last_error = RuntimeError(f"HTTP {exc.code}: {message}")
            if exc.code not in transient_statuses or attempt == 2:
                raise last_error from exc
            wait_seconds = (5 if exc.code == 429 else 2) * (attempt + 1)
            print(f"Transient HTTP {exc.code}; retrying this turn in {wait_seconds}s.")
            time.sleep(wait_seconds)
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = RuntimeError(f"Network/timeout error: {exc}")
            if attempt == 2:
                raise last_error from exc
            wait_seconds = 2 * (attempt + 1)
            print(f"Transient network error; retrying this turn in {wait_seconds}s.")
            time.sleep(wait_seconds)
    raise last_error or RuntimeError("Chat request failed after retries.")


def main() -> int:
    if len(TOKEN) < 16:
        print("Required GitHub Actions secret AI_COACH_TEST_TOKEN is missing or too short.")
        return 2

    if not 1 <= REPEATS <= 3:
        print("ATENA_BENCHMARK_REPEATS must be between 1 and 3.")
        return 2

    benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))
    try:
        scenarios = select_scenarios(
            benchmark["scenarios"],
            os.environ.get("ATENA_BENCHMARK_SCENARIOS", ""),
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    results = []
    for repeat_index in range(1, REPEATS + 1):
        print(f"Starting independent benchmark repetition {repeat_index}/{REPEATS}.")
        for index, scenario in enumerate(scenarios, start=1):
            # Every scenario in every repetition starts with an empty conversation.
            messages: list[dict[str, str]] = []
            transcript = []
            status = "passed_api"
            error = None
            for turn_index, user_text in enumerate(scenario["turns"], start=1):
                user_profile = scenario.get("user_profile", "").strip()
                message_content = user_text
                if turn_index == 1 and user_profile:
                    message_content = (
                        "KONTEKST TESTNEGA UPORABNIKA (podatki profila; upoštevaj kot podane, "
                        "ne sklepaj več, kot piše): " + user_profile
                        + "\n\nUPORABNIKOVO SPOROČILO: " + user_text
                    )
                messages.append({"role": "user", "content": message_content})
                try:
                    data = request_chat(messages)
                except RuntimeError as exc:
                    status = "api_error"
                    error = str(exc)
                    transcript.append({
                        "turn": turn_index,
                        "user": user_text,
                        "error": error,
                    })
                    break
                answer = data["reply"].strip()
                source = data.get("response_source", "model_or_unreported")
                transcript.append({
                    "turn": turn_index,
                    "user": user_text,
                    "user_profile": user_profile if turn_index == 1 else None,
                    "user_profile_context_included": bool(turn_index == 1 and user_profile),
                    "assistant": answer,
                    "response_source": source,
                    "guardrail_applied": bool(data.get("guardrail_applied", False)),
                    "model": data.get("model"),
                })
                messages.append({"role": "model", "content": answer})
                if turn_index < len(scenario["turns"]):
                    time.sleep(5.0)

            results.append({
                "repeat": repeat_index,
                "id": scenario["id"],
                "name": scenario["name"],
                "status": status,
                "error": error,
                "transcript": transcript,
            })
            print(
                f"[run {repeat_index}/{REPEATS}] "
                f"[{index:02d}/{len(scenarios):02d}] "
                f"{scenario['id']} {scenario['name']}: {status}; "
                f"turns={len(transcript)}"
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    response_source_counts = {}
    for item in results:
        for turn in item["transcript"]:
            source = turn.get("response_source", "unknown")
            response_source_counts[source] = response_source_counts.get(source, 0) + 1

    report = {
        "benchmark_id": benchmark["benchmark_id"],
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": BACKEND,
        "audience": benchmark["audience"],
        "execution_mode": "live sequential multi-turn; each scenario starts with empty history; user_profile is injected into the first user turn",
        "note": (
            "API execution confirms live responses only. It is not a quality pass/fail "
            "and does not replace expert transcript scoring."
        ),
        "backend_commit": os.environ.get("GITHUB_SHA"),
        "scenario_count": len(scenarios),
        "scenario_ids": [item["id"] for item in scenarios],
        "repeat_count": REPEATS,
        "execution_count": len(results),
        "total_turns": sum(len(x["transcript"]) for x in results),
        "api_success_count": sum(x["status"] == "passed_api" for x in results),
        "api_error_count": sum(x["status"] != "passed_api" for x in results),
        "response_source_counts": response_source_counts,
        "results": results,
    }
    OUT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# ATENA – live conversation benchmark",
        "",
        f"- Izvedeno: {report['executed_at_utc']}",
        f"- Backend: {BACKEND}",
        f"- Backend commit: {report['backend_commit'] or 'unknown'}",
        f"- Scenarijev: {report['scenario_count']}",
        f"- Neodvisnih ponovitev: {report['repeat_count']}",
        f"- Izvedb scenarijev: {report['execution_count']}",
        f"- Uporabniških obratov: {report['total_turns']}",
        f"- Uspešne API izvedbe: {report['api_success_count']}",
        f"- API napake: {report['api_error_count']}",
        f"- Viri odgovorov: {', '.join(f'{key}={value}' for key, value in sorted(response_source_counts.items()))}",
        "",
        "> API uspeh pomeni, da je ATENA vrnila odgovor v večkoračnem toku. "
        "To še ni strokovna ocena kakovosti odgovora.",
        "",
        "| Ponovitev | ID | Scenarij | API | Obrati |",
        "|---:|---|---|---:|---:|",
    ]
    for item in results:
        lines.append(
            f"| {item['repeat']} | {item['id']} | {item['name']} | {item['status']} | "
            f"{len(item['transcript'])} |"
        )
    lines += [
        "",
        "Celotni prepisi in metapodatki odgovorov so v "
        "live-conversation-benchmark.json.",
        "",
        "## Ročna strokovna ocena",
        "",
        "Za vsak scenarij je treba oceniti osem dimenzij (0–2) in preveriti "
        "kritične napake po docs/conversation-quality-benchmark.md. "
        "Ne ocenjuj samo zadnjega odgovora; preberi celoten prepis.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        f"Benchmark complete: {report['api_success_count']}/{report['scenario_count']} "
        "scenarios returned live responses; transcripts saved."
    )
    return 0 if report["api_error_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
