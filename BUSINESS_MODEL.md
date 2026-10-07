# ATENA — Business Model v1

## Product

ATENA is a decision-intelligence service for AI fitness and human-performance agents.

Core proposition:

> ATENA does not optimize the program. ATENA optimizes the next decision.

The paying customer is **the company or developer operating an AI agent**. The human is not the primary user of ATENA; the agent calls ATENA as a specialist decision layer.

## Why this can be a business

Generic LLMs are good at generating answers, but production agents need reliable specialist behavior when decisions involve:
- uncertainty
- conflicting signals
- competing goals
- recovery/stimulus trade-offs
- symptoms affecting training
- longitudinal adaptation
- minimum-intervention decisions

ATENA packages this decision logic behind a stable API/MCP contract.

The commercial value is therefore not "fitness content". It is **decision quality, consistency and reduced unnecessary intervention inside another agent**.

## Recommended revenue model

### 1. Free discovery tier

Purpose: maximize adoption and agent experimentation.

- public MCP availability
- limited monthly decision calls
- full basic decision schema
- no SLA
- attribution/link to ATENA documentation

This tier should remain frictionless. Discovery is strategically more important than early revenue.

### 2. Production tier — usage based

Recommended initial positioning:

**ATENA Pro — $49/month**
- 5,000 decision calls included
- API/MCP production access
- usage analytics
- API key / tenant identity
- higher rate limits
- version stability

Overage can be priced by additional decision credits.

### 3. Business tier

**ATENA Business — $199/month**
- 25,000 decision calls included
- higher rate limits
- production monitoring
- decision/version analytics
- priority support
- commercial integration rights

### 4. Enterprise

Custom annual contracts.

Sell:
- SLA
- dedicated capacity
- private deployment / VPC where justified
- custom governance
- auditability
- custom schemas or domain extensions
- security/procurement support

Do not optimize for enterprise first. First prove repeated agent usage and measurable decision value.

## Why not pure per-call pricing?

MCP/tool ecosystems are moving toward usage-based and per-call monetization, but extremely small per-call prices can produce little revenue unless call volume is very high. Current 2026 MCP monetization sources show freemium, subscriptions and usage-based models all emerging, while hosted B2B services remain the strongest path to meaningful recurring revenue. DigitalOcean's Action Gateway, for example, prices standard MCP/tool invocations at $0.10 per 1,000 calls, illustrating how low infrastructure-level tool-call prices can be. citeturn0search2turn0search1

For ATENA, the better commercial unit is therefore a **decision credit inside a recurring production plan**, not a tiny standalone micro-payment for every call.

## Long-term pricing evolution

Once real usage data exists, pricing should move toward:

**Base subscription + included decision credits + usage overage + enterprise SLA**

Potential future differentiators:
- longitudinal memory / decision history
- evaluation and benchmarking
- decision observability
- domain-specific specialist modules
- governance and audit trails
- outcome-based pricing where measurable

Do not implement these prematurely.

## Distribution strategy

ATENA should be discoverable wherever agents discover tools:

1. Official MCP Registry — canonical identity
2. GitHub — source of truth and technical trust
3. Glama — ecosystem discovery
4. Smithery — ecosystem discovery
5. MCP marketplaces with payment rails — commercial distribution
6. Direct integrations with AI-agent platforms

The important distinction is:

**directories create discovery; hosted API/MCP creates recurring revenue.**

Current MCP monetization research supports this distinction: many directories are primarily discovery channels, while dedicated marketplaces provide subscription or per-call payment infrastructure. citeturn0search1turn0search4

## Go-to-market wedge

Do not sell "AI fitness".

Sell a much narrower technical problem:

> **A specialist decision layer for AI agents that need reliable next-action decisions in human performance.**

First target:
- AI fitness agents
- AI personal-training products
- digital coaching platforms
- human-performance software
- sports-performance agents
- wellness agents that make training decisions

The first commercial proof should be one external agent integrating ATENA in production.

## The critical economic metric

The key metric is not downloads or GitHub stars.

It is:

**ATENA decisions that change or improve the calling agent's next action.**

Track:
- active agent integrations
- decision calls / month
- repeat decision calls per agent
- percentage of calls resulting in an actionable decision
- retention of integrated agents
- production error rate / uptime
- average revenue per integrated agent
- measurable decision-quality lift

The strongest future sales claim would be:

> "Agents using ATENA make fewer unnecessary interventions and handle uncertainty more consistently."

That claim must come from a real controlled evaluation, not from the current authored benchmark.

## Current business status

ATENA is technically ready for early external integration.

What is proven:
- production API
- remote MCP
- structured agent input
- structured decision output
- official MCP Registry publication workflow and successful registry verification
- 20/20 unseen production decision benchmark
- 5/5 production smoke suite

What is **not yet proven**:
- that a real external LLM agent performs materially better with ATENA than without ATENA
- willingness of external customers to pay
- retention / repeat usage
- optimal pricing

Therefore the next commercial milestone is **not more feature development**.

It is:

**1 external agent → repeated usage → controlled Agent vs Agent+ATENA evaluation → first paid production customer.**
