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



def test_enqueue_can_be_cancelled_before_dispatch():
    calls = []
    coordinator = Coordinator(adapters={"ATENA": lambda task: calls.append(task.task_id) or {"ok": True}})
    queued = coordinator.enqueue(TaskRequest(
        objective="Cancel before dispatch", domain="fitness", task_id="cancel-queued"
    ))

    assert queued.status is TaskStatus.QUEUED
    assert coordinator.cancel("cancel-queued") is True
    cancelled = coordinator.get("cancel-queued")
    assert cancelled.status is TaskStatus.CANCELLED
    assert cancelled.error_code == "cancelled_by_request"
    assert coordinator.cancel("cancel-queued") is False
    assert calls == []


def test_running_task_cannot_be_cancelled_or_misreported_as_stopped():
    coordinator = None
    cancel_results = []

    def adapter(task):
        cancel_results.append(coordinator.cancel(task.task_id))
        return {"decision": "maintain"}

    coordinator = Coordinator(adapters={"ATENA": adapter})
    task = coordinator.submit(TaskRequest(
        objective="Cancellation boundary", domain="fitness", task_id="running-cancel"
    ))

    assert cancel_results == [False]
    assert task.status is TaskStatus.COMPLETED
    assert task.attempt_count == 1
    assert task.started_at is not None
    assert task.completed_at is not None


def test_expired_terminal_tasks_are_purged_and_capacity_reclaimed():
    from datetime import datetime, timedelta, timezone

    now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    coordinator = Coordinator(
        max_tasks=1,
        retention_seconds=60,
        clock=lambda: now[0],
        adapters={"ATENA": lambda task: {"ok": True}},
    )
    coordinator.submit(TaskRequest(
        objective="First task", domain="fitness", task_id="expires"
    ))
    assert coordinator.get("expires") is not None

    now[0] += timedelta(seconds=61)
    assert coordinator.get("expires") is None
    second = coordinator.enqueue(TaskRequest(
        objective="Second task", domain="fitness", task_id="capacity-reclaimed"
    ))
    assert second.status is TaskStatus.QUEUED


def test_queued_task_dispatch_is_single_attempt_only():
    calls = []
    coordinator = Coordinator(
        adapters={"ATENA": lambda task: calls.append(task.task_id) or {"ok": True}}
    )
    queued = coordinator.enqueue(TaskRequest(
        objective="Single dispatch", domain="fitness", task_id="single-dispatch"
    ))
    result = coordinator.run(queued.task_id)

    assert result.status is TaskStatus.COMPLETED
    assert result.attempt_count == 1
    assert calls == ["single-dispatch"]
    with pytest.raises(ValueError, match="only queued"):
        coordinator.run(queued.task_id)
