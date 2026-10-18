# ATENA: discovery, integration and value validation

## What ATENA is

ATENA is a specialist decision-support layer for AI fitness and human-performance agents. It is designed for the decision **"What should I do next, given the goal, current state, constraints, response and history?"** It is not a general-purpose chatbot or a medical diagnostic tool.

**Core proposition:** ATENA helps an agent make a structured next-action decision when there is meaningful uncertainty or a trade-off. Its response includes a decision, rationale, detected signals, uncertainty, monitoring targets and a boundary for reassessment.

## When an agent should call ATENA

Call ATENA before a consequential next-action decision when one or more of these apply:
- performance, effort/RPE and recovery signals conflict;
- symptoms affect the exercise or training choice;
- primary and secondary goals compete;
- time, energy or recovery are constrained;
- the decision depends on the response to prior training or a previous modification;
- the agent is uncertain whether to maintain, progress, reduce, modify, collect data or refer.

Do not call ATENA for simple factual questions, diagnosis, emergencies, or routine choices where no meaningful decision trade-off exists. The calling agent remains responsible for the final response and must preserve uncertainty.

## Connect

### Remote MCP (recommended for agent tool integrations)

- Endpoint: `https://atena-mcp.onrender.com/mcp`
- Tool: `atena_decide`
- Discovery tool: `atena_capabilities`
- Transport: Streamable HTTP
- Official registry identity: `io.github.shrek9999/atena`

Add the endpoint as a remote MCP server in the agent platform's MCP/tool settings. The exact UI differs by platform. Once connected, inspect the tool descriptions and make the agent's system instructions explicitly say when to call ATENA.

### Direct HTTP

- Base URL: `https://atena-mvp.onrender.com`
- Capabilities: `GET /capabilities`
- Decision: `POST /decision`

Example request:

```json
{
  "goal": { "primary": "strength", "secondary": "aerobic_fitness" },
  "person": {},
  "constraints": { "available_time": "limited" },
  "state": {
    "performance": "declining",
    "rpe": "increased",
    "recovery": "worse",
    "symptoms": "none"
  },
  "response": {},
  "question": "What should the agent change next?",
  "history": {}
}
```

Inspect the returned `decision`, `action`, `reason_codes`, `uncertainty`, and `decision_support`. The `decision_support` metadata explains which signals were detected, why the recommendation may add value, and what should trigger reassessment.

## How to evaluate whether ATENA adds value

A working endpoint or successful tool call proves integration, not decision superiority. Use two separate gates.

### Gate 1 — technical reliability
1. Verify `GET /health` and `GET /capabilities`.
2. Submit the same case through HTTP and MCP.
3. Confirm both routes return the same decision for the same input.
4. Run the 20-case unseen regression suite and record all mismatches.

The manual GitHub Actions workflow `ATENA Live Verification` performs these checks without calling a paid LLM API.

### Gate 2 — incremental decision value
Compare the same agent and model in two arms on identical cases:
- **A: agent alone**, with no ATENA tool available;
- **B: the same agent + ATENA**, with the tool available and trigger instructions.

Blind the evaluator to the arm. Score the decision using the same rubric in both arms:
- decision appropriateness and alignment with the primary goal;
- handling of uncertainty and missing information;
- risk/symptom handling;
- proportionality (avoiding unnecessary changes);
- clarity of monitoring and reassessment conditions.

Use unseen cases and report the number of wins, ties and losses, per-dimension scores, tool-call rate, latency and cost. Do not claim superiority from deterministic unit tests, a single example, or fluent explanations alone. A live LLM comparison requires an available model/API budget; the technical workflow deliberately does not make those paid calls.

## Discovery and distribution

- GitHub source and integration examples: https://github.com/shrek9999/atena-mvp
- Official MCP Registry identity: `io.github.shrek9999/atena`
- Remote MCP endpoint: `https://atena-mcp.onrender.com/mcp`

The registry helps developers discover the server; it does not automatically connect ATENA to their agents. Each developer still needs to add the endpoint or select it from a compatible directory and configure the agent's tool-use instructions.

## Safety and limitations

ATENA provides decision support for training/human-performance workflows. It does not diagnose, replace clinical judgment, or handle emergencies. Confidence is a score associated with the selected decision, not a calibrated probability that a medical or causal hypothesis is true.


## Operational limits and integration requirements

- **No automatic agent connection:** publishing or registering ATENA does not grant an agent access. The agent owner must explicitly configure the remote MCP endpoint or call the HTTP API.
- **MCP protocol:** use Streamable HTTP at `https://atena-mcp.onrender.com/mcp` with a compatible MCP client. A plain browser `GET /mcp` is not a valid end-to-end test; verify with MCP initialization and tool discovery/call instead.
- **Cold starts and transient failures:** the current Render services use the Free plan. Allow for cold-start latency and implement bounded retries with backoff for transient 5xx/network errors. Do not blindly retry invalid requests (4xx), and do not repeat a consequential decision indefinitely.
- **Check service readiness:** verify `GET https://atena-mvp.onrender.com/health` and `GET https://atena-mvp.onrender.com/capabilities` before a pilot. A successful health check proves availability, not decision quality.
- **Fallback behavior:** if ATENA is unavailable, the calling agent should state that decision support could not be reached, use its own safety rules, avoid pretending ATENA was consulted, and request human review when uncertainty or symptoms make that appropriate.
- **Sensitive data minimization:** send only context necessary for the decision. Avoid names, contact details, identifiers, and unrelated health or personal data.
- **Validation boundary:** technical checks and the 20-case regression suite are engineering tests, not independent clinical validation or proof of superiority over an agent without ATENA. Measure incremental value with blinded A/B cases before making performance claims.
- **Production readiness checks still required:** confirm request-volume limits, abuse protection, authentication/authorization requirements, uptime monitoring, and the service's configured HTTP health-check path before opening a paid or high-volume integration. These settings must be verified in the hosting dashboard; do not assume they are enabled.


## Minimal copy-paste integration recipe

### Agent system-instruction snippet

Use this as a starting point in the calling agent's system instructions:

> For consequential fitness or human-performance decisions, call ATENA before deciding when performance, RPE, recovery or symptoms conflict; when goals compete; when time or recovery is constrained; or when the next step depends on prior response. Do not call ATENA for simple factual questions, diagnosis, emergencies, or routine choices without a meaningful trade-off. Send only the context needed for the decision. Treat ATENA output as decision support, not as medical truth. Preserve uncertainty, explain the final recommendation in plain language, and follow the agent's own safety policies. If ATENA is unavailable, do not claim it was consulted; apply the agent's fallback safety rules and seek human review when warranted.

### First integration smoke test

1. Configure a compatible MCP client with the remote endpoint `https://atena-mcp.onrender.com/mcp` using Streamable HTTP.
2. Discover tools and confirm that both `atena_capabilities` and `atena_decide` are listed.
3. Call `atena_capabilities` first.
4. Call `atena_decide` with a synthetic case, not a real person's identifiable or sensitive information.
5. Confirm that the result includes a decision and useful action/monitoring/uncertainty fields.
6. Repeat the same case through `POST https://atena-mvp.onrender.com/decision` and compare the decision. The no-cost GitHub Actions workflow automates this parity check.

### Safe failure handling

- Use a bounded retry policy with backoff for network errors and transient HTTP 5xx only.
- Do not automatically retry 4xx validation/authentication errors or repeat a consequential decision indefinitely.
- Set an overall deadline. If the deadline expires, use a transparent fallback and record that ATENA was unavailable.
- Never send names, emails, account IDs, or unrelated health details unless a documented use case and appropriate consent require them.

### What a successful smoke test means

A successful tool discovery and call confirms technical interoperability for that test client. It does not prove that the agent will call ATENA at the right times, that the recommendation is correct, or that ATENA improves decisions. Those require a blinded agent-alone versus agent-plus-ATENA evaluation on the same unseen cases.
