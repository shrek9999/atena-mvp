"""Composition root for the isolated ZEUS prototype."""
from __future__ import annotations

from zeus.atena_mcp import ATENA_MCP_URL, AtenaMCPAdapter, MCPTransport
from zeus.coordinator import Coordinator
from zeus.hermes_research import HermesResearchAdapter


def build_coordinator(
    atena_transport: MCPTransport | None = None,
    atena_url: str = ATENA_MCP_URL,
) -> Coordinator:
    """Create ZEUS with ATENA and the read-only HERMES evidence collector."""
    return Coordinator(adapters={
        "ATENA": AtenaMCPAdapter(transport=atena_transport, url=atena_url),
        "HERMES": HermesResearchAdapter(),
    })
