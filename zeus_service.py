"""Authenticated HTTP entry point for the isolated ZEUS coordinator.

No request payloads or specialist results are written to the durable ledger.
All lifecycle writes are fail-closed when the ledger is configured.
"""
from __future__ import annotations

import hmac
import logging
import os
import threading
from functools import wraps
from typing import Any

from flask import Flask, jsonify, request

from zeus.coordinator import (
    Coordinator,
    LedgerPersistenceUnavailable,
    TaskRequest,
    TaskStatus,
)
from zeus.factory import build_coordinator
from zeus.ledger_worker_client import LedgerWorkerClient


MAX_BODY_BYTES = 64_000
SAFE_TASK_FIELDS = (
    "task_id", "domain", "specialist", "status", "created_at", "updated_at",
    "started_at", "completed_at", "expires_at", "attempt_count", "error_code",
    "recovery_code",
)
SAFE_EVENT_FIELDS = (
    "event_id", "task_id", "event_type", "from_status", "to_status", "occurred_at",
)


def _public_record(record) -> dict[str, Any]:
    data = Coordinator.as_dict(record)
    return {key: data.get(key) for key in SAFE_TASK_FIELDS}


def _public_metadata(data: dict[str, Any]) -> dict[str, Any]:
    # Explicit allowlist protects the API if the ledger schema gains fields.
    return {key: data.get(key) for key in SAFE_TASK_FIELDS}


def run_startup_smoke(ledger: LedgerWorkerClient, api_token: str) -> dict[str, Any]:
    """Run one deterministic synthetic API lifecycle against the live D1 ledger.

    This is opt-in via ZEUS_STARTUP_SMOKE=1. It uses a fixed, non-sensitive
    task ID and a stub ATENA adapter; it never contacts a real specialist.
    """
    task_id = "zeus-internal-smoke-v1"
    existing = ledger.get_task(task_id)
    if isinstance(existing.get("task"), dict):
        task = existing["task"]
        if task.get("status") == "completed":
            events = ledger.get_events(task_id).get("events", [])
            expected = ["queued", "assigned", "running", "completed"]
            if [event.get("to_status") for event in events] == expected:
                return {"status": "already_completed", "task_id": task_id}
        raise RuntimeError("ZEUS startup smoke task exists in an incomplete state")

    coordinator = Coordinator(
        adapters={"ATENA": lambda _task: {"smoke_test": "passed", "version": "v1"}},
        ledger=ledger,
    )
    client = create_app(coordinator=coordinator, api_token=api_token).test_client()
    auth = {"Authorization": "Bearer " + api_token}

    unauthorized = client.get("/v1/tasks")
    if unauthorized.status_code != 401:
        raise RuntimeError("ZEUS startup smoke authentication check failed")

    created = client.post("/v1/tasks", headers=auth, json={
        "task_id": task_id,
        "objective": "Synthetic ZEUS internal lifecycle validation",
        "domain": "fitness",
        "requires_approval": False,
    })
    if created.status_code != 201:
        raise RuntimeError("ZEUS startup smoke task creation failed")

    executed = client.post(f"/v1/tasks/{task_id}/run", headers=auth)
    execution_task = (executed.get_json() or {}).get("task", {})
    if executed.status_code != 200 or execution_task.get("status") != "completed":
        raise RuntimeError(
            "ZEUS startup smoke execution failed "
            f"(HTTP {executed.status_code}, status={execution_task.get('status')}, "
            f"error_code={execution_task.get('error_code')})"
        )

    retrieved = client.get(f"/v1/tasks/{task_id}", headers=auth)
    if retrieved.status_code != 200:
        raise RuntimeError("ZEUS startup smoke durable read failed")
    task = retrieved.get_json().get("task", {})
    if task.get("status") != "completed" or "objective" in task or "payload" in task:
        raise RuntimeError("ZEUS startup smoke metadata safety check failed")

    event_response = client.get(f"/v1/tasks/{task_id}/events", headers=auth)
    if event_response.status_code != 200:
        raise RuntimeError("ZEUS startup smoke event read failed")
    events = event_response.get_json().get("events", [])
    if [event.get("to_status") for event in events] != [
        "queued", "assigned", "running", "completed"
    ]:
        raise RuntimeError("ZEUS startup smoke event sequence was incomplete")

    return {
        "status": "passed",
        "task_id": task_id,
        "events": len(events),
        "checks": ["authentication", "create", "run", "durable_read", "event_history"],
    }



def run_live_agent_smoke(
    coordinator: Coordinator,
    ledger: LedgerWorkerClient,
    api_token: str,
) -> dict[str, Any]:
    """Exercise both real specialist adapters through ZEUS with synthetic inputs.

    Results remain in coordinator memory only. The D1 ledger receives only
    task metadata and lifecycle events. This check is opt-in and non-blocking
    for service availability.
    """
    client = create_app(coordinator=coordinator, api_token=api_token).test_client()
    auth = {"Authorization": "Bearer " + api_token}
    expected_events = ["queued", "assigned", "running", "completed"]
    atena_payload = {
        "goal": {"primary": "strength", "secondary": "aerobic_fitness"},
        "person": {},
        "constraints": {"available_time": "two sessions per week"},
        "state": {
            "performance": "stable",
            "strength": "stable",
            "rpe": 7,
            "recovery": "stable",
            "symptoms": "none",
            "sleep": "normal",
            "wellness": "normal",
        },
        "response": {
            "performance_response": "stable",
            "recovery_response": "stable",
        },
        "question": "Should the current training stimulus be maintained?",
        "history": {},
    }
    tasks = [
        {
            "task_id": "zeus-live-atena-v1",
            "specialist": "ATENA",
            "domain": "fitness",
            "objective": "Synthetic ATENA connectivity check; no personal data.",
            "payload": atena_payload,
        },
        {
            "task_id": "zeus-live-hermes-v1",
            "specialist": "HERMES",
            "domain": "markets",
            "objective": "Synthetic HERMES public-source connectivity check; no investment recommendation.",
            "payload": {
                "research_type": "macro",
                "subject": "Official public macro source connectivity check",
                "time_horizon": "unspecified",
                "source_urls": [
                    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL",
                    "https://www.bls.gov/news.release/cpi.toc.htm",
                    "https://www.federalreserve.gov/newsevents/pressreleases.htm",
                ],
            },
        },
    ]
    agent_results: dict[str, dict[str, Any]] = {}

    for item in tasks:
        task_id = item["task_id"]
        existing = ledger.get_task(task_id)
        if isinstance(existing.get("task"), dict):
            task = existing["task"]
            if task.get("status") == "completed":
                events = ledger.get_events(task_id).get("events", [])
                if [event.get("to_status") for event in events] == expected_events:
                    agent_results[item["specialist"]] = {
                        "status": "already_completed",
                        "events": len(events),
                    }
                    continue
            raise RuntimeError("ZEUS live-agent smoke task exists in an incomplete state")

        created = client.post("/v1/tasks", headers=auth, json={
            "task_id": task_id,
            "objective": item["objective"],
            "domain": item["domain"],
            "payload": item["payload"],
            "requires_approval": False,
        })
        if created.status_code != 201:
            raise RuntimeError(
                f"ZEUS live-agent smoke could not create {item['specialist']} task"
            )

        executed = client.post(f"/v1/tasks/{task_id}/run", headers=auth)
        execution_task = (executed.get_json() or {}).get("task", {})
        if executed.status_code != 200 or execution_task.get("status") != "completed":
            raise RuntimeError(
                f"ZEUS live-agent smoke execution failed for {item['specialist']}"
            )

        record = coordinator.get(task_id)
        result = record.result if record is not None else None
        if not isinstance(result, dict):
            raise RuntimeError(
                f"ZEUS live-agent smoke returned no structured {item['specialist']} result"
            )
        if item["specialist"] == "ATENA":
            valid_decisions = {
                "maintain", "progress", "reduce", "modify", "collect_data", "refer"
            }
            if (
                result.get("decision") not in valid_decisions
                or not isinstance(result.get("action"), str)
                or not result["action"].strip()
            ):
                raise RuntimeError("ATENA synthetic decision contract was invalid")
            evidence_count = 0
        else:
            documents = result.get("source_documents")
            if result.get("status") != "completed" or not isinstance(documents, list) or not documents:
                raise RuntimeError("HERMES did not retrieve an allowlisted public source")
            evidence_count = len(documents)

        retrieved = client.get(f"/v1/tasks/{task_id}", headers=auth)
        if retrieved.status_code != 200 or retrieved.get_json().get("task", {}).get("status") != "completed":
            raise RuntimeError(
                f"ZEUS live-agent smoke durable read failed for {item['specialist']}"
            )
        event_response = client.get(f"/v1/tasks/{task_id}/events", headers=auth)
        events = (event_response.get_json() or {}).get("events", [])
        if (
            event_response.status_code != 200
            or [event.get("to_status") for event in events] != expected_events
        ):
            raise RuntimeError(
                f"ZEUS live-agent smoke event history failed for {item['specialist']}"
            )
        agent_results[item["specialist"]] = {
            "status": "passed",
            "events": len(events),
            "evidence_count": evidence_count,
        }

    return {
        "status": "passed",
        "agents": agent_results,
        "checks": ["ZEUS routing", "specialist execution", "durable lifecycle", "event history"],
        "results_persisted": False,
    }

def create_app(
    coordinator: Coordinator | None = None,
    api_token: str | None = None,
) -> Flask:
    token = api_token or os.environ.get("ZEUS_API_TOKEN", "")
    if not isinstance(token, str) or len(token) < 32:
        raise RuntimeError("ZEUS_API_TOKEN must contain at least 32 characters")
    if coordinator is None:
        ledger = LedgerWorkerClient.from_environment()
        coordinator = build_coordinator(ledger=ledger)
        coordinator.recover_orphaned_tasks()
        if os.environ.get("ZEUS_STARTUP_SMOKE") == "1":
            try:
                result = run_startup_smoke(ledger, token)
                logging.getLogger("zeus").info(
                    "ZEUS startup smoke %s (task_id=%s, events=%s)",
                    result["status"], result["task_id"], result.get("events", 0),
                )
            except Exception as exc:
                logging.getLogger("zeus").error(
                    "ZEUS startup smoke failed (%s): %s", type(exc).__name__, exc
                )
                raise RuntimeError("ZEUS startup smoke failed") from None
        if os.environ.get("ZEUS_LIVE_AGENT_SMOKE") == "1":
            try:
                result = run_live_agent_smoke(coordinator, ledger, token)
                logging.getLogger("zeus").info(
                    "ZEUS live-agent smoke %s (agents=%s, results_persisted=%s)",
                    result["status"],
                    ",".join(sorted(result["agents"])),
                    result["results_persisted"],
                )
            except Exception as exc:
                # This opt-in integration probe must never make the public
                # coordinator unavailable when a specialist is temporarily down.
                logging.getLogger("zeus").error(
                    "ZEUS live-agent smoke failed (%s)", type(exc).__name__
                )

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES

    @app.get("/")
    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "ZEUS"})

    @app.before_request
    def require_authentication():
        if request.path in {"/", "/health"}:
            return None
        supplied = request.headers.get("Authorization", "")
        expected = "Bearer " + token
        if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            return jsonify({"error": "unauthorized"}), 401
        return None

    @app.errorhandler(413)
    def body_too_large(_error):
        return jsonify({"error": "body_too_large"}), 413

    @app.post("/v1/tasks")
    def create_task():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "invalid_json_object"}), 400
        allowed = {
            "task_id", "objective", "domain", "acceptance_criteria",
            "payload", "requires_approval",
        }
        if set(body) - allowed:
            return jsonify({"error": "unknown_field"}), 400
        if not isinstance(body.get("objective"), str) or not body["objective"].strip():
            return jsonify({"error": "objective_required"}), 400
        if not isinstance(body.get("domain"), str):
            return jsonify({"error": "domain_required"}), 400
        criteria = body.get("acceptance_criteria", [])
        if not isinstance(criteria, list):
            return jsonify({"error": "acceptance_criteria_must_be_a_list"}), 400
        payload = body.get("payload", {})
        if not isinstance(payload, dict):
            return jsonify({"error": "payload_must_be_an_object"}), 400
        requires_approval = body.get("requires_approval", False)
        if not isinstance(requires_approval, bool):
            return jsonify({"error": "requires_approval_must_be_boolean"}), 400
        try:
            task = TaskRequest(
                objective=body["objective"],
                domain=body["domain"],
                acceptance_criteria=tuple(criteria),
                payload=payload,
                requires_approval=requires_approval,
                approved=False,
                task_id=body.get("task_id") or __import__("uuid").uuid4().hex,
            )
            record = coordinator.enqueue(task)
        except ValueError as exc:
            return jsonify({"error": "invalid_task", "detail": str(exc)}), 400
        except LedgerPersistenceUnavailable:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        except RuntimeError:
            return jsonify({"error": "coordinator_capacity_reached"}), 503
        return jsonify({"task": _public_record(record)}), 201

    @app.get("/v1/tasks")
    def list_tasks():
        try:
            tasks = [_public_metadata(item) for item in coordinator.list_task_metadata()]
        except Exception:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        return jsonify({"tasks": tasks})

    @app.get("/v1/tasks/<task_id>")
    def get_task(task_id: str):
        try:
            record = coordinator.get_task_metadata(task_id)
        except Exception:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        if record is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"task": _public_metadata(record)})

    @app.get("/v1/tasks/<task_id>/events")
    def get_task_events(task_id: str):
        try:
            events = coordinator.get_task_events(task_id)
        except Exception:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        if events is None:
            return jsonify({"error": "not_found"}), 404
        safe_events = [
            {key: item.get(key) for key in SAFE_EVENT_FIELDS}
            for item in events
        ]
        return jsonify({"events": safe_events})

    @app.post("/v1/tasks/<task_id>/approve")
    def approve_task(task_id: str):
        try:
            record = coordinator.approve(task_id)
        except KeyError:
            return jsonify({"error": "not_found"}), 404
        except ValueError:
            return jsonify({"error": "approval_not_allowed"}), 409
        return jsonify({"task": _public_record(record), "approved": True})

    @app.post("/v1/tasks/<task_id>/run")
    def run_task(task_id: str):
        try:
            record = coordinator.run(task_id)
        except KeyError:
            return jsonify({"error": "not_found"}), 404
        except ValueError:
            return jsonify({"error": "task_not_queued"}), 409
        except LedgerPersistenceUnavailable:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        return jsonify({"task": _public_record(record)})

    @app.post("/v1/tasks/<task_id>/cancel")
    def cancel_task(task_id: str):
        try:
            cancelled = coordinator.cancel(task_id)
        except LedgerPersistenceUnavailable:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        if not cancelled:
            return jsonify({"error": "task_not_cancellable"}), 409
        return jsonify({"task_id": task_id, "status": TaskStatus.CANCELLED.value})

    return app


class _LazyWSGIApp:
    """Defer secret-dependent runtime construction until the WSGI app is used."""

    def __init__(self):
        self._app = None
        self._initialization_lock = threading.Lock()

    def __call__(self, environ, start_response):
        if self._app is None and environ.get("PATH_INFO") == "/":
            body = b'{"status":"ok","service":"ZEUS"}'
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ])
            return [body]
        if self._app is None:
            # Multiple Gunicorn threads can receive the first readiness probe
            # concurrently. Serialize initialization so recovery and any
            # opt-in startup smoke can never race each other.
            with self._initialization_lock:
                if self._app is None:
                    try:
                        self._app = create_app()
                    except (RuntimeError, ValueError) as exc:
                        # Log only the safe exception type/message; never log tokens
                        # or environment values.
                        logging.getLogger("zeus").error(
                            "ZEUS startup configuration error (%s): %s",
                            type(exc).__name__,
                            exc,
                        )
                        body = b'{"error":"service_not_configured"}'
                        start_response("503 Service Unavailable", [
                            ("Content-Type", "application/json"),
                            ("Content-Length", str(len(body))),
                            ("Cache-Control", "no-store"),
                        ])
                        return [body]
        return self._app(environ, start_response)


app = _LazyWSGIApp()
