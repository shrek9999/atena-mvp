# HERMES v0.1 — ZEUS integration notes

## What is implemented

HERMES v0.1 is a read-only public-source evidence collector registered by the
ZEUS composition root. It accepts a market or investment-research task with:
- research type: asset, macro, capital_flows, opportunity, or risk_review;
- subject and optional time horizon;
- up to five explicitly supplied public source URLs.

The fetcher accepts HTTPS only and enforces an exact hostname allowlist:
Federal Reserve, FRED, ECB, European Commission, BLS, BEA, SEC, IMF and
CoinGecko public hosts. Redirect destinations are validated against the same
allowlist. Each document is limited to 250 KB and each request has a bounded
timeout. Retrieved excerpts are capped at 6,000 characters and labeled with
retrieval timestamps.

The output preserves source URLs and retrieval timestamps. It does not claim
that a source was published at retrieval time; publication dates are unknown
unless separately established.

## Deliberate limits

This version does not:
- search the web for sources automatically;
- infer or calculate capital flows, valuations, returns or price signals;
- synthesize an investment thesis or forecast;
- make buy/sell recommendations;
- access exchanges, wallets, brokerage accounts or private portfolio data;
- call a language model, paid API, or paid data source.

Its executive view is always `insufficient_evidence`. The result is an evidence
pack for a later analyst/research stage, not an investment decision.

## Safety and cost

- No credentials, cookies, API keys or account access.
- GET requests only; no write methods.
- Exact host allowlist and redirect validation reduce SSRF risk.
- Bounded source count, body size, excerpt length and network timeout.
- No added third-party Python dependencies.
- No database, deployment, background polling or paid service.

## Validation required before promotion

The automated tests use mocked fetchers. They validate URL restrictions,
redirect/host policy, document extraction, size limits, failure sanitization,
structured output and ZEUS routing. A live retrieval smoke test may be run
against one selected official source after CI passes; it must remain read-only.
