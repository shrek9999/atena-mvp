"""One-off, read-only live MCP compatibility check for ATENA.

Calls only atena_capabilities. It sends no user data and never calls the
decision endpoint. Uses Python's standard library only.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

ENDPOINT = "https://atena-mcp.onrender.com/mcp"
PROTOCOL_VERSION = "2025-03-26"


def parse_rpc(raw: str) -> dict:
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                value = json.loads(line[5:].strip())
            except ValueError:
                continue
            if isinstance(value, dict):
                return value
    raise RuntimeError("MCP response did not contain a JSON-RPC message")


def post(message: dict, session_id: str | None = None,
         protocol_version: str = PROTOCOL_VERSION) -> tuple[int, dict, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "zeus-live-smoke/0.1",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
        headers["MCP-Protocol-Version"] = protocol_version
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(message).encode("utf-8"),
        headers=headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.status, dict(response.headers.items()), response.read().decode("utf-8")


def post_with_retry(message: dict, session_id: str | None = None,
                    protocol_version: str = PROTOCOL_VERSION) -> tuple[int, dict, str]:
    last_error = None
    for attempt in range(3):
        try:
            return post(message, session_id, protocol_version)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(8)
    raise RuntimeError("ATENA MCP was unreachable after bounded retries") from last_error


def main() -> None:
    status, headers, raw = post_with_retry({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "zeus-live-smoke", "version": "0.1.0"},
        },
    })
    if status != 200:
        raise RuntimeError(f"MCP initialize returned HTTP {status}")
    initialized = parse_rpc(raw)
    if "error" in initialized or not isinstance(initialized.get("result"), dict):
        raise RuntimeError("MCP initialize did not return a valid result")
    negotiated = initialized["result"].get("protocolVersion", PROTOCOL_VERSION)
    session_id = next(
        (value for key, value in headers.items() if key.lower() == "mcp-session-id"),
        None,
    )

    status, _, _ = post_with_retry(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        session_id, negotiated,
    )
    if status not in (200, 202):
        raise RuntimeError(f"MCP initialized notification returned HTTP {status}")

    status, _, raw = post_with_retry({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "atena_capabilities", "arguments": {}},
    }, session_id, negotiated)
    if status != 200:
        raise RuntimeError(f"atena_capabilities returned HTTP {status}")
    response = parse_rpc(raw)
    if "error" in response or not isinstance(response.get("result"), dict):
        raise RuntimeError("MCP capabilities call failed")
    result = response["result"]
    if result.get("isError"):
        raise RuntimeError("ATENA MCP reported a tool error")

    capabilities = result.get("structuredContent")
    if not isinstance(capabilities, dict):
        for item in result.get("content", []):
            if item.get("type") == "text":
                try:
                    candidate = json.loads(item.get("text", ""))
                except ValueError:
                    continue
                if isinstance(candidate, dict):
                    capabilities = candidate
                    break
    if not isinstance(capabilities, dict):
        raise RuntimeError("ATENA MCP returned no structured capabilities")

    expected = {"maintain", "progress", "reduce", "modify", "collect_data", "refer"}
    actual = set(capabilities.get("decision_types", []))
    if capabilities.get("service") != "ATENA" or not expected.issubset(actual):
        raise RuntimeError("ATENA MCP capabilities did not match the expected contract")

    # One synthetic, non-personal decision call proves the complete MCP tool
    # contract end to end. This uses the free /decision route, never /paid/decision.
    synthetic_payload = {
        "goal": {"primary": "strength", "secondary": "aerobic_fitness"},
        "person": {},
        "constraints": {"available_time": "two sessions per week"},
        "state": {
            "performance": "stable",
            "strength": "stable",
            "rpe": 7,
            "recovery": "stable",
            "symptoms": "none",
            "sleep": "normal",
            "wellness": "normal",
        },
        "response": {"performance_response": "stable", "recovery_response": "stable"},
        "question": "Should the current training stimulus be maintained?",
        "history": {},
    }
    status, _, raw = post_with_retry({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "atena_decide", "arguments": {"payload": synthetic_payload}},
    }, session_id, negotiated)
    if status != 200:
        raise RuntimeError(f"atena_decide returned HTTP {status}")
    decision_response = parse_rpc(raw)
    if "error" in decision_response or not isinstance(decision_response.get("result"), dict):
        raise RuntimeError("MCP decision call failed")
    decision_result = decision_response["result"]
    if decision_result.get("isError"):
        raise RuntimeError("ATENA decision tool reported an error")

    decision = decision_result.get("structuredContent")
    if not isinstance(decision, dict):
        for item in decision_result.get("content", []):
            if item.get("type") == "text":
                try:
                    candidate = json.loads(item.get("text", ""))
                except ValueError:
                    continue
                if isinstance(candidate, dict):
                    decision = candidate
                    break
    if not isinstance(decision, dict) or decision.get("decision") not in expected:
        raise RuntimeError("ATENA returned an invalid synthetic decision")
    if not isinstance(decision.get("action"), str) or not decision["action"]:
        raise RuntimeError("ATENA decision response is missing an action")

    print("LIVE MCP CHECK: PASS")
    print(f"Service: {capabilities.get('service')} {capabilities.get('version')}")
    print("Tools: atena_capabilities, atena_decide")
    print("Decision types: " + ", ".join(sorted(actual)))
    print(f"Synthetic decision: {decision.get('decision')}")
    print("No user data sent; no paid endpoint called.")


if __name__ == "__main__":
    main()
