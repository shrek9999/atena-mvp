# ZEUS Phase 2B – ATENA MCP adapter

## Status
The isolated ZEUS prototype now includes an ATENA MCP adapter and a composition
factory that wires fitness/human-performance tasks to the existing ATENA MCP
service. HERMES remains deliberately unregistered until its actual
implementation is located.

The complete GitHub Actions regression suite passed: **115 tests passed** on
2026-11-01. This includes synthetic end-to-end coordinator-to-adapter tests
using an in-memory MCP transport.

## Safety and scope
- Network transport is injectable; CI tests use a synthetic in-memory transport.
- Only `fitness` and `human_performance` tasks can route to ATENA.
- Input is allowlisted to ATENA's documented decision fields and capped at 16 KB.
- No user-specific or medical data is included in tests.
- No new Python dependencies were added.
- No Render service, Cloudflare Worker, production API or live user flow was changed.
- The adapter does not persist session identifiers or task data.
- Remote MCP compatibility has not yet been verified; CI proves protocol handling
  against a synthetic transport, not the live remote endpoint.

## MCP exchange
The adapter performs MCP `initialize`, sends
`notifications/initialized`, then invokes `tools/call` for `atena_decide`.
It supports JSON and Server-Sent Events JSON-RPC responses and carries the
MCP session/protocol headers when supplied. The factory registers this adapter
under the existing `ATENA` specialist route.

## HERMES discovery
The connected account inventory currently shows:
- two GitHub repositories owned by the account: `atena-mvp` and
  `tiny-figolla-016703`;
- three Render services: `atena-mvp`, `atena-mcp` and
  `atena-ai-coach-pilot`;
- one Cloudflare Worker: `tiny-figolla-016703`.

No HERMES/Pozejdon implementation was identified in these connected resources.
This is an inventory result, not proof that no implementation exists elsewhere.

## Next gate
1. Run a synthetic, read-only live MCP compatibility check against ATENA
   (capabilities/tool discovery only; no personal data).
2. Locate or define HERMES source and interface before enabling market routing.
3. Keep ZEUS isolated from production until the live adapter check, payload
   contract review, persistent task storage and operational controls are complete.
