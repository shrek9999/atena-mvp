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


class FakeDurableLedger:
    def __init__(self, fail_on=None):
        self.statuses = {}
        self.transitions = []
        self.fail_on = fail_on

    def create_task(self, task_id, domain):
        if self.fail_on == "create":
            from zeus.coordinator import SpecialistUnavailable
            raise SpecialistUnavailable("offline")
        self.statuses[task_id] = "queued"
        return {"status": "queued"}

    def transition_task(self, task_id, from_status, to_status, error_code=None):
        from zeus.coordinator import SpecialistUnavailable
        source = from_status.value if isinstance(from_status, TaskStatus) else from_status
        target = to_status.value if isinstance(to_status, TaskStatus) else to_status
        if self.fail_on == target:
            raise SpecialistUnavailable("offline")
        assert self.statuses[task_id] == source
        self.statuses[task_id] = target
        self.transitions.append((task_id, source, target, error_code))
        return {"task": {"status": target}}


def test_durable_ledger_mirrors_confirmed_lifecycle_transitions():
    ledger = FakeDurableLedger()
    calls = []
    coordinator = Coordinator(
        adapters={"ATENA": lambda task: calls.append(task.task_id) or {"ok": True}},
        ledger=ledger,
    )
    task = coordinator.submit(TaskRequest(
        objective="Durable lifecycle", domain="fitness", task_id="durable-1"
    ))

    assert task.status is TaskStatus.COMPLETED
    assert ledger.statuses["durable-1"] == "completed"
    assert [entry[2] for entry in ledger.transitions] == [
        "assigned", "running", "completed"
    ]
    assert calls == ["durable-1"]


def test_durable_create_failure_does_not_create_local_task():
    from zeus.coordinator import LedgerPersistenceUnavailable

    coordinator = Coordinator(ledger=FakeDurableLedger(fail_on="create"))
    with pytest.raises(LedgerPersistenceUnavailable):
        coordinator.enqueue(TaskRequest(
            objective="Do not accept without durable record",
            domain="fitness",
            task_id="durable-create-fail",
        ))
    assert coordinator.get("durable-create-fail") is None


def test_durable_transition_failure_keeps_last_confirmed_local_status():
    from zeus.coordinator import LedgerPersistenceUnavailable

    ledger = FakeDurableLedger(fail_on="assigned")
    calls = []
    coordinator = Coordinator(
        adapters={"ATENA": lambda task: calls.append(task.task_id) or {"ok": True}},
        ledger=ledger,
    )
    queued = coordinator.enqueue(TaskRequest(
        objective="Fail closed on assignment",
        domain="fitness",
        task_id="durable-assigned-fail",
    ))

    with pytest.raises(LedgerPersistenceUnavailable):
        coordinator.run(queued.task_id)

    assert coordinator.get(queued.task_id).status is TaskStatus.QUEUED
    assert ledger.statuses[queued.task_id] == "queued"
    assert calls == []


def test_completion_write_failure_does_not_claim_task_completed():
    from zeus.coordinator import LedgerPersistenceUnavailable

    ledger = FakeDurableLedger(fail_on="completed")
    coordinator = Coordinator(
        adapters={"ATENA": lambda task: {"decision": "maintain"}},
        ledger=ledger,
    )
    queued = coordinator.enqueue(TaskRequest(
        objective="Completion persistence outage",
        domain="fitness",
        task_id="durable-complete-fail",
    ))

    with pytest.raises(LedgerPersistenceUnavailable):
        coordinator.run(queued.task_id)

    local = coordinator.get(queued.task_id)
    assert local.status is TaskStatus.RUNNING
    assert local.result == {"decision": "maintain"}
    assert ledger.statuses[queued.task_id] == "running"


def test_durable_cancel_write_failure_does_not_claim_cancellation():
    from zeus.coordinator import LedgerPersistenceUnavailable

    ledger = FakeDurableLedger()
    coordinator = Coordinator(ledger=ledger)
    queued = coordinator.enqueue(TaskRequest(
        objective="Cancel safely", domain="fitness", task_id="durable-cancel"
    ))
    ledger.fail_on = "cancelled"

    with pytest.raises(LedgerPersistenceUnavailable):
        coordinator.cancel(queued.task_id)

    assert coordinator.get(queued.task_id).status is TaskStatus.QUEUED
    assert ledger.statuses[queued.task_id] == "queued"



class RestartRecoveryLedger:
    def __init__(self):
        self.tasks = [
            {"task_id": "orphan-queued", "status": "queued"},
            {"task_id": "orphan-assigned", "status": "assigned"},
            {"task_id": "orphan-running", "status": "running"},
            {"task_id": "already-done", "status": "completed"},
        ]
        self.transitions = []

    def list_tasks(self, limit=50):
        return {"tasks": self.tasks[:limit]}

    def transition_task(self, task_id, from_status, to_status, error_code=None, recovery_code=None):
        task = next(item for item in self.tasks if item["task_id"] == task_id)
        assert task["status"] == from_status
        task["status"] = to_status
        task["recovery_code"] = recovery_code
        self.transitions.append((task_id, from_status, to_status, recovery_code))
        return {"task": dict(task)}


def test_restart_recovery_blocks_active_tasks_without_replaying_them():
    ledger = RestartRecoveryLedger()
    coordinator = Coordinator(ledger=ledger)

    recovered = coordinator.recover_orphaned_tasks()

    assert recovered == ["orphan-queued", "orphan-assigned", "orphan-running"]
    assert [task["status"] for task in ledger.tasks] == [
        "blocked", "blocked", "blocked", "completed"
    ]
    assert all(item[3] == "runtime_restarted" for item in ledger.transitions)
