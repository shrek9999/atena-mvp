"""Authenticated client for the isolated ZEUS ledger Worker.

The client stores task lifecycle metadata only. It never sends objectives,
payloads, specialist results, health data, or portfolio information.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from zeus.coordinator import SpecialistUnavailable, TaskStatus, SPECIALIST_BY_DOMAIN


class LedgerTransport(Protocol):
    def request(
        self, method: str, url: str, token: str, body: dict[str, Any] | None, timeout: float
    ) -> tuple[int, str]: ...


class UrllibLedgerTransport:
    def request(self, method, url, token, body, timeout):
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "User-Agent": "ZEUS-Ledger-Client/0.1",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read(65_536).decode("utf-8")
        except urllib.error.HTTPError as exc:
            # Preserve HTTP status so callers can distinguish a missing task
            # from an unavailable ledger without exposing response details.
            return exc.code, exc.read(65_536).decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError):
            raise SpecialistUnavailable("ZEUS ledger Worker is unreachable") from None


class LedgerWorkerClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        transport: LedgerTransport | None = None,
        timeout: float = 8.0,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.startswith("https://"):
            raise ValueError("ledger Worker URL must use HTTPS")
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("ledger token must contain at least 32 characters")
        if timeout <= 0 or timeout > 20:
            raise ValueError("timeout must be between 0 and 20 seconds")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._transport = transport or UrllibLedgerTransport()
        self._timeout = timeout

    @classmethod
    def from_environment(cls, transport: LedgerTransport | None = None):
        url = os.environ.get("ZEUS_LEDGER_URL", "")
        token = os.environ.get("ZEUS_LEDGER_TOKEN", "")
        if not url or not token:
            raise ValueError("ZEUS ledger persistence is not configured")
        return cls(url, token, transport=transport)

    def create_task(self, task_id: str, domain: str) -> dict[str, Any]:
        specialist = SPECIALIST_BY_DOMAIN.get(domain)
        if specialist is None:
            raise ValueError("unsupported ZEUS task domain")
        return self._request("POST", "/v1/tasks", {
            "task_id": task_id,
            "domain": domain,
            "specialist": specialist,
        }, expected=(201,))

    def transition_task(
        self,
        task_id: str,
        from_status: TaskStatus | str,
        to_status: TaskStatus | str,
        error_code: str | None = None,
        recovery_code: str | None = None,
    ) -> dict[str, Any]:
        source = from_status.value if isinstance(from_status, TaskStatus) else from_status
        target = to_status.value if isinstance(to_status, TaskStatus) else to_status
        body = {"from_status": source, "to_status": target}
        if error_code is not None:
            body["error_code"] = error_code
        if recovery_code is not None:
            body["recovery_code"] = recovery_code
        return self._request("POST", "/v1/tasks/" + self._path_id(task_id) + "/status",
                             body, expected=(200,))

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request(
            "GET", "/v1/tasks/" + self._path_id(task_id), expected=(200, 404)
        )

    def list_tasks(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if not isinstance(offset, int) or offset < 0 or offset > 1_000_000:
            raise ValueError("offset must be between 0 and 1000000")
        return self._request(
            "GET", "/v1/tasks?limit=" + str(limit) + "&offset=" + str(offset),
            expected=(200,),
        )

    def get_events(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", "/v1/tasks/" + self._path_id(task_id) + "/events",
                             expected=(200,))

    @staticmethod
    def _path_id(task_id: str) -> str:
        if not isinstance(task_id, str) or not task_id or len(task_id) > 100:
            raise ValueError("invalid task id")
        if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in task_id):
            raise ValueError("invalid task id")
        return task_id

    def _request(self, method, path, body=None, expected=(200,)):
        status, raw = self._transport.request(
            method, self._base_url + path, self._token, body, self._timeout
        )
        if status not in expected:
            # A short bounded hint is useful for edge-level 403/5xx diagnosis.
            # The API never returns this exception detail to callers.
            hint = " ".join(raw.split())[:120] if status in {403, 429, 500, 502, 503} else ""
            detail = f"; response={hint}" if hint else ""
            raise SpecialistUnavailable(
                f"ZEUS ledger Worker rejected the request (HTTP {status}{detail})"
            )
        try:
            decoded = json.loads(raw)
        except (ValueError, TypeError):
            raise SpecialistUnavailable("ZEUS ledger Worker returned malformed JSON") from None
        if not isinstance(decoded, dict):
            raise SpecialistUnavailable("ZEUS ledger Worker returned malformed data")
        return decoded
