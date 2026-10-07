# ATENA Remote MCP

ATENA is exposed as a remote MCP server for AI agents.

## Endpoint

After the Render service is deployed:

`https://atena-mcp.onrender.com/mcp`

## Tools

- `atena_decide(payload)` — send a decision case to ATENA
- `atena_capabilities()` — inspect supported capabilities

## Agent pattern

1. Agent receives a fitness/human-performance decision problem.
2. Agent gathers available context.
3. Agent calls `atena_decide` when decision support is useful.
4. Agent treats ATENA as decision intelligence, not as an unquestionable authority.
5. Agent preserves uncertainty and required-information signals.

Connecting the MCP server proves integration, not superiority. Validation remains Agent-alone vs Agent+ATENA on identical cases.
