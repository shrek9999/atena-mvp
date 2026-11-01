import os
from flask import Flask
import coach_routes
from coach_routes import coach_bp


def test_storage_status_requires_pilot_token_and_never_enables_storage_by_default(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-secret")
    monkeypatch.delenv("ATENA_DATA_STORAGE_ENABLED", raising=False)
    monkeypatch.delenv("ATENA_PRIVACY_NOTICE_APPROVED", raising=False)
    monkeypatch.setattr(coach_routes, "store_check_database_connection", lambda: True)
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    client = app.test_client()

    denied = client.get("/coach/storage/status")
    assert denied.status_code == 403
    response = client.get("/coach/storage/status", headers={"X-Pilot-Token": "pilot-secret"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["database"] == "reachable"
    assert payload["storage_enabled"] is False
    assert "password" not in payload
    assert "connection" not in payload


def test_storage_status_reports_disabled_when_database_unavailable(monkeypatch):
    from coach_store import StorageUnavailable
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-secret")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    monkeypatch.setattr(
        coach_routes, "store_check_database_connection",
        lambda: (_ for _ in ()).throw(StorageUnavailable("hidden", "database_network_connection_failed")),
    )
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    response = app.test_client().get(
        "/coach/storage/status", headers={"X-Pilot-Token": "pilot-secret"}
    )
    assert response.status_code == 503
    assert response.get_json()["storage_enabled"] is False
