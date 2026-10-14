# ATENA — Decision Intelligence for AI Fitness Agents

**A specialist decision layer for AI agents that need reliable next-action decisions under uncertainty.**

ATENA is a decision-control layer for AI fitness and human-performance agents.

Core principle: **ATENA does not optimize the program. ATENA optimizes the next decision.**

## Why an AI agent should call ATENA

Call ATENA when the agent must answer **“What should I do next?”** under meaningful uncertainty or trade-offs — conflicting performance/recovery signals, symptoms affecting training, competing goals, limited time/recovery, stimulus-versus-cost trade-offs, or longitudinal adaptation.

Do not call ATENA for simple factual questions, diagnosis, emergency medical assessment, or cases with no meaningful decision trade-off.

ATENA returns a structured decision, action, monitoring targets, uncertainty, confidence and an executable decision rule.

## API
- GET /health
- GET /capabilities
- POST /decision

Production URL: https://atena-mvp.onrender.com

## Decision loop
GOAL → CONTEXT → CONSTRAINTS → PRIORITY → STATE → STIMULUS → COST → HYPOTHESES → OPTIONS → DECISION → ACTION → MEASURE → INTERPRET → ADAPT

ATENA emphasizes:
- goal priority
- uncertainty-first decisions
- minimum intervention
- stimulus-cost reasoning
- response over prescription
- longitudinal consistency

## Run
```bash
pip install -r requirements.txt
gunicorn app:app
```

## Contract
See `openapi.json` and `agent_contract.json`.

## For AI agents

ATENA is a **decision-control specialist**, not a general fitness chatbot.

**Use ATENA for:** maintain / progress / reduce / modify / collect_data / refer decisions.

**Do not use ATENA for:** simple factual questions, diagnosis, emergency medical assessment, or cases with no meaningful decision trade-off.

### Remote MCP
- Endpoint: `https://atena-mcp.onrender.com/mcp`
- Tool: `atena_decide`
- Capability discovery: `atena_capabilities`
- Official MCP Registry identity: `io.github.shrek9999/atena`

The endpoint must be added by the agent developer or selected through a compatible MCP directory; registration does not automatically connect it to agents.

### Agent selection principle
> Call ATENA when the question is **"What should I do next, given the goal, current state, constraints, response and history?"** rather than merely **"What is true?"**

ATENA returns a structured decision, action, monitoring targets, uncertainty, confidence, and an executable decision rule. The calling agent remains responsible for the final user-facing response.

### Integration and proof of value
See [Agent discovery, integration and value validation](AGENT_DISCOVERY_AND_VALUE.md) for connection steps, trigger rules, live verification, and the blinded agent-alone vs agent-plus-ATENA evaluation protocol.

## Validation and limitations

The 20-case unseen robustness suite is a development/engineering validation set. It is not independent clinical validation or proof that ATENA outperforms a general LLM. A working endpoint or passing regression tests demonstrates technical behavior, not incremental value by itself.

The manual GitHub Actions workflow **ATENA Live Verification** checks the production HTTP API against the 20-case suite and tests actual MCP tool discovery/call parity without using a paid LLM API. Run it from the repository's Actions tab after the workflow is merged.

## Real-world agent pilot

The first real-world validation compares the same agent **alone** vs **agent + ATENA** on identical decision cases. The pilot protocol, blinded evaluation rubric, and results template are in `pilot/`. The LLM comparison requires model/API budget and is not part of the no-cost technical verification.

## Business model

ATENA uses an agent-first B2B model: public discovery/free testing → production integration → usage metering → recurring subscription → overage → enterprise.

Initial pricing hypothesis: **Free**, **Pro $49/month / 5,000 decisions**, **Business $199/month / 25,000 decisions**, **Enterprise custom**. These are hypotheses, not validated market prices.

See `BUSINESS_MODEL.md` and `LAUNCHGUIDE.md`.
