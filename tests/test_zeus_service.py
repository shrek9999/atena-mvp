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
