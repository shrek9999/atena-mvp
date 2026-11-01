from zeus.factory import build_coordinator
from zeus.coordinator import TaskRequest, TaskStatus

from tests.test_zeus_atena_mcp import FakeTransport


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


def test_factory_leaves_hermes_blocked_without_adapter():
    coordinator = build_coordinator(atena_transport=FakeTransport())
    record = coordinator.submit(TaskRequest(
        objective="Synthetic market research",
        domain="markets",
    ))
    assert record.status is TaskStatus.BLOCKED
    assert record.specialist == "HERMES"
    assert record.error_code == "specialist_unavailable"
