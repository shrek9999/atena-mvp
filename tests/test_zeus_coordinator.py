import pytest

from zeus.coordinator import Coordinator, TaskRequest, TaskStatus


def test_routes_fitness_task_to_atena_and_records_result():
    calls = []
    coordinator = Coordinator(
        adapters={"ATENA": lambda task: calls.append(task.task_id) or {"decision": "maintain"}}
    )
    task = coordinator.submit(
        TaskRequest(objective="Assess a training trade-off", domain="fitness", task_id="fitness-1")
    )

    assert calls == ["fitness-1"]
    assert task.specialist == "ATENA"
    assert task.status is TaskStatus.COMPLETED
    assert task.result == {"decision": "maintain"}


def test_routes_market_task_to_hermes_but_blocks_if_not_connected():
    coordinator = Coordinator()
    task = coordinator.submit(
        TaskRequest(objective="Review market conditions", domain="markets", task_id="markets-1")
    )

    assert task.specialist == "HERMES"
    assert task.status is TaskStatus.BLOCKED
    assert task.error_code == "specialist_unavailable"


def test_approval_gate_prevents_adapter_execution():
    calls = []
    coordinator = Coordinator(
        adapters={"ATENA": lambda task: calls.append(task.task_id) or {"ok": True}}
    )
    task = coordinator.submit(
        TaskRequest(
            objective="Publish a training plan",
            domain="fitness",
            requires_approval=True,
            task_id="approval-1",
        )
    )

    assert calls == []
    assert task.status is TaskStatus.BLOCKED
    assert task.error_code == "approval_required"


def test_approved_task_can_run():
    coordinator = Coordinator(adapters={"ATENA": lambda task: {"ok": True}})
    task = coordinator.submit(
        TaskRequest(
            objective="Run an approved action",
            domain="fitness",
            requires_approval=True,
            approved=True,
            task_id="approved-1",
        )
    )
    assert task.status is TaskStatus.COMPLETED


def test_rejects_unknown_domains_and_duplicate_ids():
    coordinator = Coordinator()
    with pytest.raises(ValueError):
        coordinator.submit(TaskRequest(objective="Do work", domain="general"))

    request = TaskRequest(objective="Do work", domain="fitness", task_id="duplicate")
    coordinator.submit(request)
    with pytest.raises(ValueError, match="already exists"):
        coordinator.submit(request)


def test_adapter_failure_is_sanitized():
    coordinator = Coordinator(adapters={"ATENA": lambda task: (_ for _ in ()).throw(RuntimeError("secret"))})
    task = coordinator.submit(
        TaskRequest(objective="Test safe failure", domain="fitness", task_id="failure-1")
    )
    assert task.status is TaskStatus.FAILED
    assert task.error_code == "specialist_execution_failed"
    assert task.result is None
    assert "secret" not in str(coordinator.as_dict(task))


def test_ledger_capacity_is_bounded():
    coordinator = Coordinator(max_tasks=1)
    coordinator.submit(TaskRequest(objective="First", domain="fitness", task_id="first"))
    with pytest.raises(RuntimeError, match="capacity"):
        coordinator.submit(TaskRequest(objective="Second", domain="fitness", task_id="second"))



def test_returned_records_cannot_mutate_internal_ledger():
    coordinator = Coordinator(adapters={"ATENA": lambda task: {"decision": {"value": "maintain"}}})
    returned = coordinator.submit(
        TaskRequest(objective="Snapshot isolation", domain="fitness", task_id="snapshot-1")
    )
    returned.status = TaskStatus.FAILED
    returned.result["decision"]["value"] = "corrupted"

    stored = coordinator.get("snapshot-1")
    assert stored.status is TaskStatus.COMPLETED
    assert stored.result == {"decision": {"value": "maintain"}}

    listed = coordinator.list_tasks()
    listed[0].result["decision"]["value"] = "also corrupted"
    assert coordinator.get("snapshot-1").result == {"decision": {"value": "maintain"}}


def test_rejects_non_json_and_oversized_specialist_results():
    non_json = Coordinator(adapters={"ATENA": lambda task: {"bad": object()}})
    task = non_json.submit(
        TaskRequest(objective="Reject non JSON", domain="fitness", task_id="bad-json")
    )
    assert task.status is TaskStatus.FAILED
    assert task.error_code == "specialist_execution_failed"

    oversized = Coordinator(adapters={"ATENA": lambda task: {"large": "x" * 65_000}})
    task = oversized.submit(
        TaskRequest(objective="Reject oversized", domain="fitness", task_id="large-result")
    )
    assert task.status is TaskStatus.FAILED
    assert task.error_code == "specialist_execution_failed"



def test_rejects_non_json_and_oversized_task_payloads():
    coordinator = Coordinator()
    with pytest.raises(ValueError, match="JSON-compatible"):
        coordinator.submit(TaskRequest(
            objective="Reject non JSON", domain="fitness", payload={"bad": object()}
        ))
    with pytest.raises(ValueError, match="64 KB"):
        coordinator.submit(TaskRequest(
            objective="Reject oversized", domain="fitness", payload={"notes": "x" * 65_000}
        ))


def test_adapter_receives_a_copy_of_the_task_payload():
    original_payload = {"goal": {"primary": "strength"}}

    def mutating_adapter(task):
        task.payload["goal"]["primary"] = "mutated"
        return {"ok": True}

    coordinator = Coordinator(adapters={"ATENA": mutating_adapter})
    coordinator.submit(TaskRequest(
        objective="Payload isolation", domain="fitness", payload=original_payload
    ))
    assert original_payload == {"goal": {"primary": "strength"}}
