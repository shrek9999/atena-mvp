from zeus.coordinator import Coordinator, TaskRequest, TaskStatus
from zeus.factory import build_coordinator


class EmptyFetcher:
    def fetch(self, url, timeout, max_bytes):
        raise AssertionError("No URL should be fetched in this test")


def test_factory_registers_hermes_and_routes_market_tasks_to_it():
    coordinator = Coordinator(adapters={"HERMES": lambda task: {"agent": "HERMES"}})
    task = coordinator.submit(TaskRequest(
        objective="Research a market topic",
        domain="markets",
        task_id="hermes-route",
    ))
    assert task.status is TaskStatus.COMPLETED
    assert task.specialist == "HERMES"
    assert task.result == {"agent": "HERMES"}


def test_production_composition_root_registers_read_only_hermes_collector(monkeypatch):
    from zeus import factory
    from zeus.hermes_research import HermesResearchAdapter

    monkeypatch.setattr(factory, "HermesResearchAdapter", lambda: HermesResearchAdapter(fetcher=EmptyFetcher()))
    coordinator = build_coordinator(atena_transport=None)
    task = coordinator.submit(TaskRequest(
        objective="Assess macro conditions",
        domain="markets",
        payload={"research_type": "macro", "subject": "Macro conditions"},
        task_id="hermes-empty-evidence",
    ))
    assert task.specialist == "HERMES"
    assert task.status is TaskStatus.COMPLETED
    assert task.result["agent"] == "HERMES"
    assert task.result["status"] == "blocked"
    assert task.result["executive_view"] == "insufficient_evidence"
