import json

import pytest

from zeus.coordinator import TaskStatus
from zeus.ledger_worker_client import LedgerWorkerClient


class FakeTransport:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload or {"ok": True}
        self.calls = []

    def request(self, method, url, token, body, timeout):
        self.calls.append((method, url, token, body, timeout))
        return self.status, json.dumps(self.payload)


def make_client(transport=None):
    return LedgerWorkerClient(
        "https://ledger.example.workers.dev",
        "s" * 48,
        transport=transport or FakeTransport(),
    )


def test_create_task_sends_only_minimal_metadata():
    transport = FakeTransport(status=201, payload={"task_id": "task-1", "status": "queued"})
    result = make_client(transport).create_task("task-1", "markets")
    method, url, token, body, timeout = transport.calls[0]

    assert result["status"] == "queued"
    assert method == "POST"
    assert url.endswith("/v1/tasks")
    assert body == {"task_id": "task-1", "domain": "markets", "specialist": "HERMES"}
    assert "objective" not in body
    assert "payload" not in body
    assert token == "s" * 48


def test_transition_uses_compare_and_set_status_contract():
    transport = FakeTransport(payload={"task": {"status": "running"}})
    result = make_client(transport).transition_task(
        "task-2", TaskStatus.ASSIGNED, TaskStatus.RUNNING
    )
    call = transport.calls[0]
    assert result["task"]["status"] == "running"
    assert call[3] == {"from_status": "assigned", "to_status": "running"}
    assert call[1].endswith("/v1/tasks/task-2/status")


def test_client_rejects_non_https_and_short_secret():
    with pytest.raises(ValueError, match="HTTPS"):
        LedgerWorkerClient("http://ledger.example", "s" * 48)
    with pytest.raises(ValueError, match="32 characters"):
        LedgerWorkerClient("https://ledger.example", "short")


def test_client_rejects_bad_task_ids_and_limits():
    client = make_client()
    with pytest.raises(ValueError):
        client.get_task("../secrets")
    with pytest.raises(ValueError):
        client.list_tasks(101)


def test_worker_errors_are_sanitized():
    from zeus.coordinator import SpecialistUnavailable

    client = make_client(FakeTransport(status=409, payload={"error": "secret detail"}))
    with pytest.raises(SpecialistUnavailable) as error:
        client.get_task("task-3")
    assert "secret detail" not in str(error.value)


def test_environment_configuration_is_opt_in(monkeypatch):
    monkeypatch.delenv("ZEUS_LEDGER_URL", raising=False)
    monkeypatch.delenv("ZEUS_LEDGER_TOKEN", raising=False)
    with pytest.raises(ValueError, match="not configured"):
        LedgerWorkerClient.from_environment()
