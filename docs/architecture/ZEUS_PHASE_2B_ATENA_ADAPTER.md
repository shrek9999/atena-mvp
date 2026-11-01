# ZEUS Phase 2B – ATENA MCP adapter

## Status
The isolated ZEUS prototype now includes an ATENA MCP adapter and a composition
factory that wires fitness/human-performance tasks to the existing ATENA MCP
service. HERMES remains deliberately unregistered until its actual
implementation is located.

**Live integration verified on 2026-11-01.** GitHub Actions executed the actual
`AtenaMCPAdapter` against `https://atena-mcp.onrender.com/mcp`, discovered
`atena_capabilities`, and called `atena_decide` with a fully synthetic
fitness scenario. ATENA returned a valid `maintain` decision and action.

The same run passed the complete offline regression suite: **115 tests passed**.
Run: https://github.com/shrek9999/atena-mvp/actions/runs/41279734851

## Safety and scope
- Network transport is injectable; unit tests use a synthetic in-memory transport.
- The live smoke check calls only `atena_capabilities` and `atena_decide`.
- The live decision payload is synthetic and contains no user-specific or medical data.
- The check uses the free `/decision` route through MCP, never `/paid/decision`.
- Only `fitness` and `human_performance` tasks can route to ATENA.
- Input is allowlisted to ATENA's documented decision fields and capped at 16 KB.
- No new Python dependencies were added.
- No Render service, Cloudflare Worker, production deployment or user flow was changed.
- The adapter does not persist session identifiers or task data.

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
1. Locate the actual HERMES source and interface, or design its contract if no
   implementation exists.
2. Harden task-ledger isolation, result validation and lifecycle controls.
3. Define persistent task storage separately from ATENA's coaching D1 database.
4. Keep ZEUS isolated from production until those controls and end-to-end
   specialist routing are complete.
