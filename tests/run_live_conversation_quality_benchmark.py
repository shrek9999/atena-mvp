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
BACKEND = os.environ.get(
    "ATENA_BENCHMARK_BACKEND",
    "https://atena-ai-coach-pilot.onrender.com",
).rstrip("/")
TOKEN = os.environ.get("AI_COACH_TEST_TOKEN", "").strip()


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
    transient_statuses = {500, 502, 503, 504}
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
            wait_seconds = 2 * (attempt + 1)
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

    benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))
    results = []
    for index, scenario in enumerate(benchmark["scenarios"], start=1):
        messages: list[dict[str, str]] = []
        transcript = []
        status = "passed_api"
        error = None
        for turn_index, user_text in enumerate(scenario["turns"], start=1):
            messages.append({"role": "user", "content": user_text})
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
                "assistant": answer,
                "response_source": source,
                "guardrail_applied": bool(data.get("guardrail_applied", False)),
                "model": data.get("model"),
            })
            messages.append({"role": "model", "content": answer})
            if turn_index < len(scenario["turns"]):
                time.sleep(1.0)

        results.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "status": status,
            "error": error,
            "transcript": transcript,
        })
        print(
            f"[{index:02d}/{len(benchmark['scenarios']):02d}] "
            f"{scenario['id']} {scenario['name']}: {status}; "
            f"turns={len(transcript)}"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "benchmark_id": benchmark["benchmark_id"],
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": BACKEND,
        "audience": benchmark["audience"],
        "execution_mode": "live sequential multi-turn; each scenario starts with empty history",
        "note": (
            "API execution confirms live responses only. It is not a quality pass/fail "
            "and does not replace expert transcript scoring."
        ),
        "scenario_count": len(results),
        "api_success_count": sum(x["status"] == "passed_api" for x in results),
        "api_error_count": sum(x["status"] != "passed_api" for x in results),
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
        f"- Scenarijev: {report['scenario_count']}",
        f"- Uspešni API scenariji: {report['api_success_count']}",
        f"- API napake: {report['api_error_count']}",
        "",
        "> API uspeh pomeni, da je ATENA vrnila odgovor v večkoračnem toku. "
        "To še ni strokovna ocena kakovosti odgovora.",
        "",
        "| ID | Scenarij | API | Obrati |",
        "|---|---|---:|---:|",
    ]
    for item in results:
        lines.append(
            f"| {item['id']} | {item['name']} | {item['status']} | "
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
