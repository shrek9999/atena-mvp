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

The same run passed the complete offline regression suite: **120 tests passed**. The coordinator ledger now returns isolated snapshots, rejects non-JSON results and caps stored specialist results at 64 KB.
Run: https://github.com/shrek9999/atena-mvp/actions/runs/41279949566

## Safety and scope
- Network transport is injectable; unit tests use a synthetic in-memory transport.
- The live smoke check calls only `atena_capabilities` and `atena_decide`.
- The live decision payload is synthetic and contains no user-specific or medical data.
- The check uses the free `/decision` route through MCP, never `/paid/decision`.
- Only `fitness` and `human_performance` tasks can route to ATENA.
- Coordinator task input must be JSON-compatible and is capped at 64 KB; ATENA input is allowlisted to documented decision fields and capped at 16 KB.
- Specialist outputs must be JSON-compatible and are capped at 64 KB; returned task records are isolated snapshots.
- No new Python dependencies were added.
- No Render service, Cloudflare Worker, production deployment or user flow was changed.
- The adapter does not persist session identifiers or task data.

## MCP exchange
The adapter performs MCP `initialize`, sends
`notifications/initialized`, then invokes `tools/call` for `atena_decide`.
It supports JSON and Server-Sent Events JSON-RPC responses and carries the
MCP session/protocol headers when supplied. It opens a fresh session per
ATENA decision because the hosted MCP service expires idle sessions, and
serializes adapter calls to prevent session cross-talk. The factory registers
this adapter under the existing `ATENA` specialist route.

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
   implementation exists. No HERMES source was found in the two connected GitHub
   repositories, three Render services, or the connected Cloudflare Worker.
2. Define persistent task storage separately from ATENA's coaching D1 database.
3. Add explicit lifecycle controls, cancellation and task expiry before any API.
4. Keep ZEUS isolated from production until those controls and HERMES routing
   are complete.
