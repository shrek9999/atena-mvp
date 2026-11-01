import io
import json
import urllib.error

from zeus.coordinator import Coordinator
from zeus.ledger_worker_client import LedgerWorkerClient, UrllibLedgerTransport
from zeus_service import create_app


TOKEN = "z" * 48
AUTH = {"Authorization": "Bearer " + TOKEN}


class ReadLedger:
    def __init__(self):
        self.task = {
            "task_id": "durable-read-1",
            "domain": "fitness",
            "specialist": "ATENA",
            "status": "queued",
            "created_at": "2026-11-01T10:00:00+00:00",
            "updated_at": "2026-11-01T10:00:00+00:00",
            "attempt_count": 0,
            "private_payload": "must never be exposed",
        }

    def get_task(self, task_id):
        if task_id != self.task["task_id"]:
            return {"error": "not_found"}
        return {"task": dict(self.task)}

    def list_tasks(self, limit=50):
        return {"tasks": [dict(self.task)]}


def test_task_get_reads_durable_ledger_even_when_process_memory_is_empty():
    ledger = ReadLedger()
    app = create_app(coordinator=Coordinator(ledger=ledger), api_token=TOKEN)
    response = app.test_client().get("/v1/tasks/durable-read-1", headers=AUTH)

    assert response.status_code == 200
    task = response.get_json()["task"]
    assert task["task_id"] == "durable-read-1"
    assert task["status"] == "queued"
    assert "private_payload" not in task
    assert "objective" not in task
    assert "result" not in task


def test_task_list_reads_durable_ledger_even_when_process_memory_is_empty():
    ledger = ReadLedger()
    app = create_app(coordinator=Coordinator(ledger=ledger), api_token=TOKEN)
    response = app.test_client().get("/v1/tasks", headers=AUTH)

    assert response.status_code == 200
    tasks = response.get_json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "durable-read-1"
    assert "private_payload" not in tasks[0]


def test_durable_task_get_returns_404_only_for_confirmed_missing_task():
    app = create_app(coordinator=Coordinator(ledger=ReadLedger()), api_token=TOKEN)
    response = app.test_client().get("/v1/tasks/absent-task", headers=AUTH)

    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"


def test_ledger_client_preserves_worker_404_as_not_found():
    class Transport:
        def request(self, method, url, token, body, timeout):
            return 404, json.dumps({"error": "not_found"})

    client = LedgerWorkerClient(
        "https://ledger.example.workers.dev", "x" * 48, transport=Transport()
    )
    assert client.get_task("absent-task") == {"error": "not_found"}


def test_urllib_transport_returns_http_error_status_without_losing_it(monkeypatch):
    def raise_404(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://ledger.example.workers.dev/v1/tasks/absent-task",
            404,
            "Not Found",
            {},
            io.BytesIO(b""),
        )

    monkeypatch.setattr("urllib.request.urlopen", raise_404)
    status, body = UrllibLedgerTransport().request(
        "GET",
        "https://ledger.example.workers.dev/v1/tasks/absent-task",
        "x" * 48,
        None,
        2.0,
    )
    assert status == 404
    assert body == ""



def test_runtime_startup_reconciles_orphaned_tasks_before_serving_api(monkeypatch):
    from zeus.coordinator import Coordinator

    class StartupLedger:
        def __init__(self):
            self.tasks = [{"task_id": "restart-queued", "status": "queued"}]
            self.transitions = []

        def list_tasks(self, limit=50):
            return {"tasks": [dict(task) for task in self.tasks]}

        def transition_task(self, task_id, from_status, to_status, error_code=None, recovery_code=None):
            task = self.tasks[0]
            assert task["task_id"] == task_id
            assert task["status"] == from_status
            task["status"] = to_status
            task["recovery_code"] = recovery_code
            self.transitions.append((task_id, from_status, to_status, recovery_code))
            return {"task": dict(task)}

    ledger = StartupLedger()
    monkeypatch.setattr("zeus_service.LedgerWorkerClient.from_environment", lambda: ledger)
    monkeypatch.setattr("zeus_service.build_coordinator", lambda ledger: Coordinator(ledger=ledger))

    app = create_app(api_token=TOKEN)

    assert ledger.tasks[0]["status"] == "blocked"
    assert ledger.tasks[0]["recovery_code"] == "runtime_restarted"
    response = app.test_client().get("/v1/tasks/restart-queued", headers=AUTH)
    assert response.status_code == 200
    assert response.get_json()["task"]["status"] == "blocked"
