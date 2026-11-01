"""Deterministic, bounded task coordination for the ZEUS prototype.

The prototype uses injected specialist adapters and an in-memory ledger.
It supports explicit enqueue/run/cancel semantics but is not a durable queue.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class TaskStatus(str, Enum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


MAX_REQUEST_BYTES = 64_000
MAX_RESULT_BYTES = 64_000
DEFAULT_RETENTION_SECONDS = 30 * 24 * 60 * 60

TERMINAL_STATUSES = {
    TaskStatus.COMPLETED, TaskStatus.FAILED,
    TaskStatus.BLOCKED, TaskStatus.CANCELLED,
}

SPECIALIST_BY_DOMAIN = {
    "fitness": "ATENA",
    "human_performance": "ATENA",
    "markets": "HERMES",
    "investment_research": "HERMES",
}


class SpecialistUnavailable(RuntimeError):
    """Raised when a specialist adapter is not registered or reachable."""


@dataclass(frozen=True)
class TaskRequest:
    objective: str
    domain: str
    acceptance_criteria: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    approved: bool = False
    task_id: str = field(default_factory=lambda: str(uuid4()))

    def validate(self) -> None:
        if not isinstance(self.objective, str) or not self.objective.strip():
            raise ValueError("objective must be a non-empty string")
        if len(self.objective) > 1000:
            raise ValueError("objective must be at most 1000 characters")
        if not isinstance(self.domain, str) or self.domain not in SPECIALIST_BY_DOMAIN:
            raise ValueError("domain must be one of: fitness, human_performance, markets, investment_research")
        if not isinstance(self.acceptance_criteria, (tuple, list)):
            raise ValueError("acceptance_criteria must be a list or tuple")
        if len(self.acceptance_criteria) > 20:
            raise ValueError("at most 20 acceptance criteria are allowed")
        if any(not isinstance(item, str) or not item.strip() or len(item) > 300
               for item in self.acceptance_criteria):
            raise ValueError("each acceptance criterion must be a non-empty string up to 300 characters")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")
        try:
            encoded = json.dumps(self.payload, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("payload must contain JSON-compatible values") from None
        if len(encoded) > MAX_REQUEST_BYTES:
            raise ValueError("payload exceeds the 64 KB safety limit")
        if not isinstance(self.requires_approval, bool) or not isinstance(self.approved, bool):
            raise ValueError("approval flags must be boolean")
        if not isinstance(self.task_id, str) or not self.task_id.strip() or len(self.task_id) > 100:
            raise ValueError("task_id must be a non-empty string up to 100 characters")
        if self.approved and not self.requires_approval:
            raise ValueError("approved cannot be true when approval is not required")


@dataclass
class TaskRecord:
    task_id: str
    objective: str
    domain: str
    specialist: str | None
    status: TaskStatus
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    expires_at: str | None = None
    attempt_count: int = 0
    result: dict[str, Any] | None = None
    error_code: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class Coordinator:
    """Synchronous coordinator with a bounded, process-local task ledger.

    enqueue() creates a cancellable queued task. run() performs one dispatch.
    submit() is the convenience enqueue+run operation. Running adapter calls
    cannot be interrupted; cancellation is accepted only before execution.
    """

    def __init__(
        self,
        adapters: dict[str, Callable[[TaskRequest], dict[str, Any]]] | None = None,
        max_tasks: int = 1000,
        retention_seconds: int = DEFAULT_RETENTION_SECONDS,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        if max_tasks < 1:
            raise ValueError("max_tasks must be at least 1")
        if retention_seconds < 1:
            raise ValueError("retention_seconds must be at least 1")
        self._adapters = dict(adapters or {})
        self._max_tasks = max_tasks
        self._retention_seconds = retention_seconds
        self._clock = clock
        self._tasks: dict[str, TaskRecord] = {}
        self._requests: dict[str, TaskRequest] = {}
        self._lock = threading.RLock()

    def enqueue(self, request: TaskRequest) -> TaskRecord:
        request.validate()
        request = replace(
            request,
            payload=json.loads(json.dumps(request.payload, ensure_ascii=False, allow_nan=False)),
            acceptance_criteria=tuple(request.acceptance_criteria),
        )
        with self._lock:
            self._purge_expired_locked()
            if request.task_id in self._tasks:
                raise ValueError("task_id already exists")
            if len(self._tasks) >= self._max_tasks:
                raise RuntimeError("task ledger capacity reached")
            now = _iso(self._clock())
            record = TaskRecord(
                task_id=request.task_id, objective=request.objective.strip(),
                domain=request.domain, specialist=None, status=TaskStatus.QUEUED,
                created_at=now, updated_at=now,
            )
            self._tasks[record.task_id] = record
            self._requests[record.task_id] = request
            return self._snapshot(record)

    def run(self, task_id: str) -> TaskRecord:
        with self._lock:
            self._purge_expired_locked()
            record = self._tasks.get(task_id)
            request = self._requests.get(task_id)
            if record is None or request is None:
                raise KeyError("task not found or expired")
            if record.status is not TaskStatus.QUEUED:
                raise ValueError("only queued tasks can be run")
            specialist = SPECIALIST_BY_DOMAIN[request.domain]
            record.specialist = specialist
            self._transition(record, TaskStatus.ASSIGNED)
            if request.requires_approval and not request.approved:
                record.error_code = "approval_required"
                self._finish(record, TaskStatus.BLOCKED)
                return self._snapshot(record)
            adapter = self._adapters.get(specialist)
            if adapter is None:
                record.error_code = "specialist_unavailable"
                self._finish(record, TaskStatus.BLOCKED)
                return self._snapshot(record)
            self._transition(record, TaskStatus.RUNNING)
            record.started_at = _iso(self._clock())
            record.attempt_count += 1

        # Do not hold the ledger lock while calling a specialist.
        try:
            result = adapter(request)
            if not isinstance(result, dict):
                raise TypeError("specialist adapter must return a dictionary")
            serialized = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            if len(serialized.encode("utf-8")) > MAX_RESULT_BYTES:
                raise ValueError("specialist result exceeds the 64 KB limit")
            safe_result = json.loads(serialized)
            with self._lock:
                current = self._tasks.get(task_id)
                if current is None or current.status is not TaskStatus.RUNNING:
                    raise RuntimeError("task state changed during specialist execution")
                current.result = safe_result
                self._finish(current, TaskStatus.COMPLETED)
                return self._snapshot(current)
        except SpecialistUnavailable:
            with self._lock:
                current = self._tasks[task_id]
                if current.status is TaskStatus.RUNNING:
                    current.error_code = "specialist_unavailable"
                    self._finish(current, TaskStatus.BLOCKED)
                return self._snapshot(current)
        except Exception:
            with self._lock:
                current = self._tasks[task_id]
                if current.status is TaskStatus.RUNNING:
                    current.error_code = "specialist_execution_failed"
                    self._finish(current, TaskStatus.FAILED)
                return self._snapshot(current)

    def submit(self, request: TaskRequest) -> TaskRecord:
        queued = self.enqueue(request)
        return self.run(queued.task_id)

    def cancel(self, task_id: str) -> bool:
        """Cancel only queued/assigned tasks; never pretend to stop running work."""
        with self._lock:
            self._purge_expired_locked()
            record = self._tasks.get(task_id)
            if record is None or record.status not in {TaskStatus.QUEUED, TaskStatus.ASSIGNED}:
                return False
            record.error_code = "cancelled_by_request"
            self._finish(record, TaskStatus.CANCELLED)
            self._requests.pop(task_id, None)
            return True

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            self._purge_expired_locked()
            record = self._tasks.get(task_id)
            return self._snapshot(record) if record is not None else None

    def list_tasks(self) -> list[TaskRecord]:
        with self._lock:
            self._purge_expired_locked()
            return [self._snapshot(record) for record in self._tasks.values()]

    def _finish(self, record: TaskRecord, status: TaskStatus) -> None:
        self._transition(record, status)
        now = self._clock()
        record.completed_at = _iso(now)
        record.expires_at = _iso(now + timedelta(seconds=self._retention_seconds))
        self._requests.pop(record.task_id, None)

    def _purge_expired_locked(self) -> None:
        now = self._clock()
        expired = [
            task_id for task_id, record in self._tasks.items()
            if record.expires_at is not None
            and datetime.fromisoformat(record.expires_at) <= now
        ]
        for task_id in expired:
            self._tasks.pop(task_id, None)
            self._requests.pop(task_id, None)

    @staticmethod
    def _snapshot(record: TaskRecord) -> TaskRecord:
        copied_result = json.loads(json.dumps(record.result)) if record.result is not None else None
        return replace(record, result=copied_result)

    @staticmethod
    def _transition(record: TaskRecord, status: TaskStatus) -> None:
        if record.status in TERMINAL_STATUSES:
            raise ValueError("terminal task status cannot be changed")
        allowed = {
            TaskStatus.QUEUED: {TaskStatus.ASSIGNED, TaskStatus.CANCELLED},
            TaskStatus.ASSIGNED: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
            TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED},
        }
        if status not in allowed.get(record.status, set()):
            raise ValueError(f"invalid task transition: {record.status.value} -> {status.value}")
        record.status = status
        record.updated_at = _iso(_now())

    @staticmethod
    def as_dict(record: TaskRecord) -> dict[str, Any]:
        data = asdict(record)
        data["status"] = record.status.value
        return data
