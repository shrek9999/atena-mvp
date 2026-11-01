import pytest

from zeus.coordinator import Coordinator, LedgerPersistenceUnavailable, SpecialistUnavailable
from zeus_service import create_app


TOKEN = "z" * 48
AUTH = {"Authorization": "Bearer " + TOKEN}


def make_app(ledger=None):
    adapters = {"ATENA": lambda task: {"decision": "maintain"}}
    coordinator = Coordinator(adapters=adapters, ledger=ledger)
    return create_app(coordinator=coordinator, api_token=TOKEN)


def test_health_is_public_but_task_api_requires_authentication():
    client = make_app().test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/v1/tasks").status_code == 401


def test_task_api_returns_only_metadata_and_requires_bearer_token():
    client = make_app().test_client()
    response = client.post("/v1/tasks", headers=AUTH, json={
        "task_id": "api-task-1",
        "objective": "Sensitive objective should not be echoed",
        "domain": "fitness",
        "payload": {"goal": {"primary": "strength"}},
    })
    assert response.status_code == 201
    task = response.get_json()["task"]
    assert task["task_id"] == "api-task-1"
    assert "objective" not in task
    assert "payload" not in task
    assert "result" not in task


def test_approval_is_a_separate_explicit_action():
    client = make_app().test_client()
    created = client.post("/v1/tasks", headers=AUTH, json={
        "task_id": "approval-api",
        "objective": "Do an approval-gated action",
        "domain": "fitness",
        "requires_approval": True,
    })
    assert created.status_code == 201
    approved = client.post("/v1/tasks/approval-api/approve", headers=AUTH)
    assert approved.status_code == 200
    run_after = client.post("/v1/tasks/approval-api/run", headers=AUTH)
    assert run_after.status_code == 200
    assert run_after.get_json()["task"]["status"] == "completed"


def test_create_rejects_client_supplied_approval_flag():
    client = make_app().test_client()
    response = client.post("/v1/tasks", headers=AUTH, json={
        "objective": "No self approval",
        "domain": "fitness",
        "approved": True,
    })
    assert response.status_code == 400


def test_task_execution_and_cancel_endpoints():
    client = make_app().test_client()
    created = client.post("/v1/tasks", headers=AUTH, json={
        "task_id": "run-api",
        "objective": "Run a safe test",
        "domain": "fitness",
    })
    assert created.status_code == 201
    ran = client.post("/v1/tasks/run-api/run", headers=AUTH)
    assert ran.status_code == 200
    assert ran.get_json()["task"]["status"] == "completed"
    assert client.post("/v1/tasks/run-api/cancel", headers=AUTH).status_code == 409


class UnavailableLedger:
    def create_task(self, task_id, domain):
        raise SpecialistUnavailable("offline")

    def transition_task(self, *args, **kwargs):
        raise SpecialistUnavailable("offline")


def test_api_returns_503_if_durable_task_creation_cannot_be_confirmed():
    client = create_app(
        coordinator=Coordinator(ledger=UnavailableLedger()),
        api_token=TOKEN,
    ).test_client()
    response = client.post("/v1/tasks", headers=AUTH, json={
        "task_id": "ledger-down",
        "objective": "Fail closed",
        "domain": "markets",
    })
    assert response.status_code == 503
    assert response.get_json()["error"] == "ledger_unavailable"


def test_lazy_wsgi_root_is_liveness_but_health_requires_runtime_configuration():
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from zeus_service import _LazyWSGIApp

    client = Client(_LazyWSGIApp(), Response)
    root_probe = client.head("/")
    assert root_probe.status_code == 200
    health = client.get("/health")
    assert health.status_code == 503
    assert health.get_json()["error"] == "service_not_configured"


def test_lazy_wsgi_health_initializes_configured_runtime(monkeypatch):
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    import zeus_service

    monkeypatch.setattr(zeus_service, "create_app", lambda: make_app())
    client = Client(zeus_service._LazyWSGIApp(), Response)
    health = client.get("/health")

    assert health.status_code == 200
    assert health.get_json()["service"] == "ZEUS"


def test_lazy_wsgi_fails_closed_when_runtime_secrets_are_missing(monkeypatch):
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from zeus_service import _LazyWSGIApp

    monkeypatch.delenv("ZEUS_API_TOKEN", raising=False)
    monkeypatch.delenv("ZEUS_LEDGER_URL", raising=False)
    monkeypatch.delenv("ZEUS_LEDGER_TOKEN", raising=False)
    client = Client(_LazyWSGIApp(), Response)
    response = client.get("/v1/tasks")
    assert response.status_code == 503
    assert response.get_json()["error"] == "service_not_configured"



class SmokeLedger:
    def __init__(self):
        self.tasks = {}
        self.events = []

    def create_task(self, task_id, domain):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "task_id": task_id, "domain": domain,
            "specialist": "ATENA", "status": "queued",
            "created_at": now, "updated_at": now,
            "attempt_count": 0, "error_code": None, "recovery_code": None,
        }
        self.tasks[task_id] = row
        self.events.append({"event_id": 1, "task_id": task_id,
                            "event_type": "created", "from_status": None,
                            "to_status": "queued", "occurred_at": now})

    def transition_task(self, task_id, from_status, to_status,
                        error_code=None, recovery_code=None):
        from datetime import datetime, timezone
        row = self.tasks[task_id]
        source = from_status.value if hasattr(from_status, "value") else from_status
        target = to_status.value if hasattr(to_status, "value") else to_status
        assert row["status"] == source
        now = datetime.now(timezone.utc).isoformat()
        row.update(status=target, updated_at=now, error_code=error_code,
                   recovery_code=recovery_code)
        if target == "running":
            row["attempt_count"] += 1
        self.events.append({
            "event_id": len(self.events) + 1, "task_id": task_id,
            "event_type": "status_changed", "from_status": source,
            "to_status": target, "occurred_at": now,
        })
        return {"task": row}

    def get_task(self, task_id):
        row = self.tasks.get(task_id)
        return {"task": dict(row)} if row else {"error": "not_found"}

    def list_tasks(self, limit=50, offset=0):
        rows = list(self.tasks.values())[offset:offset + limit]
        return {"tasks": [dict(row) for row in rows]}

    def get_events(self, task_id):
        return {"events": [dict(event) for event in self.events
                           if event["task_id"] == task_id]}


def test_opt_in_startup_smoke_exercises_authenticated_durable_api_lifecycle():
    from zeus_service import run_startup_smoke

    ledger = SmokeLedger()
    first = run_startup_smoke(ledger, TOKEN)
    assert first["status"] == "passed"
    assert first["events"] == 4
    second = run_startup_smoke(ledger, TOKEN)
    assert second["status"] == "already_completed"
    assert len(ledger.tasks) == 1
