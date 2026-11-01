import json

import pytest

from zeus.atena_mcp import AtenaMCPAdapter
from zeus.coordinator import TaskRequest


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, url, body, headers, timeout):
        self.calls.append((url, body, headers, timeout))
        method = body.get("method")
        if method == "initialize":
            return 200, {"Mcp-Session-Id": "synthetic-session"}, json.dumps({
                "jsonrpc": "2.0", "id": body["id"],
                "result": {"protocolVersion": "2025-03-26", "capabilities": {}},
            })
        if method == "notifications/initialized":
            return 202, {}, ""
        if method == "tools/call":
            return 200, {}, json.dumps({
                "jsonrpc": "2.0", "id": body["id"],
                "result": {"structuredContent": {
                    "decision": "maintain", "confidence": 0.8,
                    "monitoring": ["synthetic metric"],
                }},
            })
        raise AssertionError(f"Unexpected MCP method: {method}")


def request(payload=None, domain="fitness"):
    return TaskRequest(
        objective="Synthetic training decision",
        domain=domain,
        payload=payload or {"goal": {"primary": "strength"}},
    )


def test_adapter_initializes_and_calls_atena_tool():
    transport = FakeTransport()
    result = AtenaMCPAdapter(transport=transport)(request())

    assert result["decision"] == "maintain"
    assert [call[1].get("method") for call in transport.calls] == [
        "initialize", "notifications/initialized", "tools/call"
    ]
    call = transport.calls[-1]
    assert call[1]["params"]["name"] == "atena_decide"
    assert call[1]["params"]["arguments"]["payload"]["goal"]["primary"] == "strength"
    assert call[2]["Mcp-Session-Id"] == "synthetic-session"


def test_adapter_rejects_non_fitness_domain():
    with pytest.raises(ValueError):
        AtenaMCPAdapter(transport=FakeTransport())(request(domain="markets"))


def test_adapter_requires_goal_and_rejects_unknown_fields():
    adapter = AtenaMCPAdapter(transport=FakeTransport())
    with pytest.raises(ValueError):
        adapter(request(payload={"question": "decide"}))
    with pytest.raises(ValueError):
        adapter(request(payload={"goal": {"primary": "strength"}, "secret": "no"}))


def test_adapter_rejects_oversized_payload():
    adapter = AtenaMCPAdapter(transport=FakeTransport())
    huge = {"goal": {"primary": "strength"}, "history": {"notes": "x" * 17000}}
    with pytest.raises(ValueError):
        adapter(request(payload=huge))


def test_adapter_parses_sse_response():
    raw = "event: message\ndata: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"ok\":true}}\n\n"
    assert AtenaMCPAdapter._parse_response(raw)["result"]["ok"] is True


def test_adapter_extracts_text_json_tool_result():
    result = {"content": [{"type": "text", "text": '{"decision":"progress"}'}]}
    assert AtenaMCPAdapter._extract_tool_result(result)["decision"] == "progress"
