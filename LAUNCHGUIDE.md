# ATENA — MCP Launch Guide

## Name
ATENA Decision Intelligence

## One-line description
Decision-control specialist for AI fitness and human-performance agents.

## What it does
ATENA helps an AI agent choose the next training or human-performance action when uncertainty, conflicting signals, symptoms, recovery cost, competing goals, limited time or longitudinal adaptation make a generic answer unreliable.

## Best use cases
- maintain / progress / reduce / modify decisions
- uncertainty and high-value data collection
- stimulus-versus-recovery trade-offs
- competing primary and secondary goals
- symptom-aware training modification
- longitudinal adaptation

## Do not use for
- simple factual questions
- diagnosis
- emergency medical assessment
- decisions with no meaningful uncertainty or trade-off

## Remote MCP
https://atena-mcp.onrender.com/mcp

## Official MCP Registry identity
io.github.shrek9999/atena

## Decision types
maintain, progress, reduce, modify, collect_data, refer

## Product principle
ATENA does not optimize the program. ATENA optimizes the next decision.


## Production readiness gate (2026-10-18)

- [x] HTTP API 20-case production verification passed.
- [x] MCP initialize, tool discovery, real decision call, and HTTP/MCP parity passed.
- [x] Gemini pilot client now uses a 60-second ATENA timeout and bounded retries; MCP upstream timeout is 60 seconds.
- [ ] Re-confirm Gemini project is still Free Tier with no linked billing account, then manually run the gated 1-case pilot.
- [ ] Review pilot artifact and compare baseline vs ATENA-assisted output; technical API/MCP tests do not substitute for this experiment.
- [ ] Set Render API health check to `/health`; confirm and implement a real health endpoint for MCP before setting its health check.
- [ ] Review public access and implement/test request-size bounds, rate limits and abuse controls before public end-user traffic.
- [ ] Review MCP Origin/Host validation, authentication, data minimization, retention and deletion behavior.
- [ ] Human-review the safety cases for pain, red flags, post-operative rehabilitation and unknown medical constraints before any public AI-trainer pilot.

Current Render configuration was inspected read-only: both services are on Free, allow `0.0.0.0/0`, and have no health-check path configured. No hosting configuration was changed because the available connection exposes read-only service inspection, not configuration updates.
