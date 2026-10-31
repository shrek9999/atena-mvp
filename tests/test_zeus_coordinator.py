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
