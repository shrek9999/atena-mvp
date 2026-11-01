"""Minimal Streamable HTTP MCP client for the existing ATENA service.

Uses only the Python standard library. Network access is injected so the
adapter can be tested offline. No credentials or user-specific data are stored.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from zeus.coordinator import SpecialistUnavailable, TaskRequest


ATENA_MCP_URL = "https://atena-mcp.onrender.com/mcp"
_ALLOWED_PAYLOAD_KEYS = {
    "goal", "person", "constraints", "state", "response", "question", "history"
}
_MAX_PAYLOAD_BYTES = 16_000


class MCPTransport(Protocol):
    def post(self, url: str, body: dict[str, Any], headers: dict[str, str],
             timeout: float) -> tuple[int, dict[str, str], str]: ...


class UrllibMCPTransport:
    """Small synchronous HTTP transport; no third-party dependency required."""

    def post(self, url: str, body: dict[str, Any], headers: dict[str, str],
             timeout: float) -> tuple[int, dict[str, str], str]:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, dict(response.headers.items()), response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SpecialistUnavailable(f"ATENA MCP HTTP {exc.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise SpecialistUnavailable("ATENA MCP is unreachable") from None


class AtenaMCPAdapter:
    """Coordinator adapter calling ATENA's atena_decide MCP tool."""

    def __init__(self, transport: MCPTransport | None = None,
                 url: str = ATENA_MCP_URL, timeout: float = 65.0) -> None:
        self._transport = transport or UrllibMCPTransport()
        self._url = url
        self._timeout = timeout
        self._request_id = 0
        self._session_id: str | None = None
        self._protocol_version = "2025-03-26"

    def __call__(self, request: TaskRequest) -> dict[str, Any]:
        if request.domain not in {"fitness", "human_performance"}:
            raise ValueError("ATENA accepts fitness and human_performance tasks only")
        payload = self._decision_payload(request)
        self._initialize()
        result = self._rpc("tools/call", {
            "name": "atena_decide",
            "arguments": {"payload": payload},
        })
        if result.get("isError"):
            raise SpecialistUnavailable("ATENA decision tool returned an error")
        return self._extract_tool_result(result)

    @staticmethod
    def _decision_payload(request: TaskRequest) -> dict[str, Any]:
        supplied = request.payload.get("atena_payload", request.payload)
        if not isinstance(supplied, dict):
            raise ValueError("ATENA payload must be an object")
        unknown = set(supplied) - _ALLOWED_PAYLOAD_KEYS
        if unknown:
            raise ValueError("ATENA payload contains unsupported fields")
        payload = dict(supplied)
        if not isinstance(payload.get("goal"), dict) or not payload["goal"]:
            raise ValueError("ATENA payload requires a non-empty goal object")
        for key in ("person", "constraints", "state", "response", "history"):
            if key not in payload:
                payload[key] = {}
            if not isinstance(payload[key], dict):
                raise ValueError(f"ATENA {key} must be an object")
        if "question" not in payload:
            payload["question"] = request.objective
        if not isinstance(payload["question"], str) or len(payload["question"]) > 2000:
            raise ValueError("ATENA question must be text up to 2000 characters")
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > _MAX_PAYLOAD_BYTES:
            raise ValueError("ATENA payload exceeds the 16 KB safety limit")
        return payload

    def _initialize(self) -> None:
        if self._session_id is not None:
            return
        result, response_headers = self._send({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": self._protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "zeus-coordinator", "version": "0.1.0"},
            },
        }, initializing=True)
        negotiated = result.get("protocolVersion")
        if negotiated:
            self._protocol_version = negotiated
        self._session_id = self._header(response_headers, "mcp-session-id")
        self._notify("notifications/initialized", {})

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        result, _ = self._send({
            "jsonrpc": "2.0", "id": self._next_id(),
            "method": method, "params": params,
        })
        return result

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send(self, body: dict[str, Any], initializing: bool = False
              ) -> tuple[dict[str, Any], dict[str, str]]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
            headers["MCP-Protocol-Version"] = self._protocol_version
        status, response_headers, raw = self._transport.post(
            self._url, body, headers, self._timeout
        )
        if status not in (200, 202):
            raise SpecialistUnavailable(f"ATENA MCP returned HTTP {status}")
        if not body.get("id"):
            return {}, response_headers
        parsed = self._parse_response(raw)
        if "error" in parsed:
            raise SpecialistUnavailable("ATENA MCP JSON-RPC request failed")
        result = parsed.get("result")
        if not isinstance(result, dict):
            raise SpecialistUnavailable("ATENA MCP response was malformed")
        return result, response_headers

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        candidates = []
        try:
            candidates.append(json.loads(raw))
        except (ValueError, TypeError):
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        candidates.append(json.loads(line[5:].strip()))
                    except ValueError:
                        continue
        for candidate in candidates:
            if isinstance(candidate, dict) and (
                "result" in candidate or "error" in candidate
            ):
                return candidate
        raise SpecialistUnavailable("ATENA MCP response contained no JSON-RPC result")

    @staticmethod
    def _extract_tool_result(result: dict[str, Any]) -> dict[str, Any]:
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        content = result.get("content", [])
        for item in content:
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                try:
                    decoded = json.loads(item["text"])
                except ValueError:
                    continue
                if isinstance(decoded, dict):
                    return decoded
        raise SpecialistUnavailable("ATENA returned no structured decision")

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    @staticmethod
    def _header(headers: dict[str, str], name: str) -> str | None:
        return next((v for k, v in headers.items() if k.lower() == name.lower()), None)
