"""Deterministic, bounded task coordination for the ZEUS prototype.

The first prototype intentionally uses injected specialist adapters and an
in-memory ledger. It does not call external services or make model decisions.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
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


TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.BLOCKED,
    TaskStatus.CANCELLED,
}

SPECIALIST_BY_DOMAIN = {
    "fitness": "ATENA",
    "human_performance": "ATENA",
    "markets": "HERMES",
    "investment_research": "HERMES",
}


class SpecialistUnavailable(RuntimeError):
    """Raised when a specialist adapter is not registered."""


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
            encoded_payload = json.dumps(
                self.payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("payload must contain JSON-compatible values") from None
        if len(encoded_payload) > MAX_REQUEST_BYTES:
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
    result: dict[str, Any] | None = None
    error_code: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Coordinator:
    """A synchronous coordinator with an in-memory, bounded task ledger.

    Adapters are callables receiving the validated TaskRequest and returning a
    JSON-compatible dictionary. They must not recursively delegate tasks.
    """

    def __init__(
        self,
        adapters: dict[str, Callable[[TaskRequest], dict[str, Any]]] | None = None,
        max_tasks: int = 1000,
    ) -> None:
        if max_tasks < 1:
            raise ValueError("max_tasks must be at least 1")
        self._adapters = dict(adapters or {})
        self._max_tasks = max_tasks
        self._tasks: dict[str, TaskRecord] = {}

    def submit(self, request: TaskRequest) -> TaskRecord:
        request.validate()
        request = replace(
            request,
            payload=json.loads(json.dumps(request.payload, ensure_ascii=False, allow_nan=False)),
            acceptance_criteria=tuple(request.acceptance_criteria),
        )
        if request.task_id in self._tasks:
            raise ValueError("task_id already exists")
        if len(self._tasks) >= self._max_tasks:
            raise RuntimeError("task ledger capacity reached")

        now = _now()
        record = TaskRecord(
            task_id=request.task_id,
            objective=request.objective.strip(),
            domain=request.domain,
            specialist=None,
            status=TaskStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        self._tasks[record.task_id] = record

        specialist = SPECIALIST_BY_DOMAIN[request.domain]
        record.specialist = specialist
        self._transition(record, TaskStatus.ASSIGNED)

        # Approval is a hard gate: no specialist adapter is called.
        if request.requires_approval and not request.approved:
            record.error_code = "approval_required"
            self._transition(record, TaskStatus.BLOCKED)
            return self._snapshot(record)

        adapter = self._adapters.get(specialist)
        if adapter is None:
            record.error_code = "specialist_unavailable"
            self._transition(record, TaskStatus.BLOCKED)
            return self._snapshot(record)

        self._transition(record, TaskStatus.RUNNING)
        try:
            result = adapter(request)
            if not isinstance(result, dict):
                raise TypeError("specialist adapter must return a dictionary")
            serialized = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            if len(serialized.encode("utf-8")) > MAX_RESULT_BYTES:
                raise ValueError("specialist result exceeds the 64 KB limit")
            record.result = json.loads(serialized)
            self._transition(record, TaskStatus.COMPLETED)
        except SpecialistUnavailable:
            record.error_code = "specialist_unavailable"
            self._transition(record, TaskStatus.BLOCKED)
        except Exception:
            # Do not expose exception text or payloads in the task ledger.
            record.error_code = "specialist_execution_failed"
            self._transition(record, TaskStatus.FAILED)
        return self._snapshot(record)

    def get(self, task_id: str) -> TaskRecord | None:
        record = self._tasks.get(task_id)
        return self._snapshot(record) if record is not None else None

    def list_tasks(self) -> list[TaskRecord]:
        return [self._snapshot(record) for record in self._tasks.values()]

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
        record.updated_at = _now()

    @staticmethod
    def as_dict(record: TaskRecord) -> dict[str, Any]:
        data = asdict(record)
        data["status"] = record.status.value
        return data
