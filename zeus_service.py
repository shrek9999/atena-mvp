"""Authenticated HTTP entry point for the isolated ZEUS coordinator.

No request payloads or specialist results are written to the durable ledger.
All lifecycle writes are fail-closed when the ledger is configured.
"""
from __future__ import annotations

import hmac
import os
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
)


def _public_record(record) -> dict[str, Any]:
    data = Coordinator.as_dict(record)
    return {key: data.get(key) for key in SAFE_TASK_FIELDS}


def _public_metadata(data: dict[str, Any]) -> dict[str, Any]:
    # Explicit allowlist protects the API if the ledger schema gains fields.
    return {key: data.get(key) for key in SAFE_TASK_FIELDS}


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

    def __call__(self, environ, start_response):
        if self._app is None and environ.get("PATH_INFO") in {"/", "/health"}:
            body = b'{"status":"ok","service":"ZEUS"}'
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ])
            return [body]
        if self._app is None:
            try:
                self._app = create_app()
            except (RuntimeError, ValueError):
                body = b'{"error":"service_not_configured"}'
                start_response("503 Service Unavailable", [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ])
                return [body]
        return self._app(environ, start_response)


app = _LazyWSGIApp()
