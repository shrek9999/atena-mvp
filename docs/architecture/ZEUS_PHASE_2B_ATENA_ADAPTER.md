# ZEUS Phase 2B – ATENA MCP adapter

## Status
A first ATENA adapter has been added as an isolated, offline-testable component.
It targets the existing Streamable HTTP MCP endpoint and the existing
`atena_decide` tool. It does not alter the ATENA service, deploy anything,
or add dependencies.

## Safety and scope
- Network transport is injectable; CI tests use a synthetic in-memory transport.
- Only `fitness` and `human_performance` tasks can route to this adapter.
- Input is allowlisted to ATENA's documented decision fields and capped at 16 KB.
- No user-specific data is included in tests.
- The adapter does not store session identifiers beyond its own instance.
- HERMES remains unavailable until its actual service/repository is located.
- This is not yet a production integration; remote MCP compatibility must be
  confirmed with a synthetic read-only/capabilities check before deployment.

## MCP exchange
The adapter performs MCP `initialize`, sends
`notifications/initialized`, then invokes `tools/call` for `atena_decide`.
It supports JSON and Server-Sent Events JSON-RPC responses and carries the
MCP session/protocol headers when supplied.

## Next gate
Run the complete offline regression suite. If green, perform a single
synthetic ATENA MCP compatibility check (no personal or medical details).
Do not deploy ZEUS or change production routing as part of this phase.
