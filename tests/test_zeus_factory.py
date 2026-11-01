import json

from zeus.factory import build_coordinator
from zeus.coordinator import TaskRequest, TaskStatus


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
                "result": {"structuredContent": {"decision": "maintain"}},
            })
        raise AssertionError(f"Unexpected MCP method: {method}")


def test_factory_routes_fitness_task_to_atena_adapter():
    transport = FakeTransport()
    coordinator = build_coordinator(atena_transport=transport)
    record = coordinator.submit(TaskRequest(
        objective="Synthetic strength decision",
        domain="fitness",
        payload={"goal": {"primary": "strength"}},
    ))

    assert record.status is TaskStatus.COMPLETED
    assert record.specialist == "ATENA"
    assert record.result["decision"] == "maintain"
    assert [call[1].get("method") for call in transport.calls] == [
        "initialize", "notifications/initialized", "tools/call"
    ]


def test_factory_registers_hermes_and_returns_blocked_evidence_pack_without_sources():
    coordinator = build_coordinator(atena_transport=FakeTransport())
    record = coordinator.submit(TaskRequest(
        objective="Synthetic market research",
        domain="markets",
        payload={"research_type": "macro", "subject": "Synthetic macro topic"},
    ))
    assert record.status is TaskStatus.COMPLETED
    assert record.specialist == "HERMES"
    assert record.result["agent"] == "HERMES"
    assert record.result["status"] == "blocked"
    assert record.result["executive_view"] == "insufficient_evidence"
    assert record.error_code is None
