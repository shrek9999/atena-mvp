"""HERMES v0.1: read-only public-source evidence collector.

This is not an autonomous investment analyst. It retrieves a bounded set of
user-selected public documents from an explicit allowlist and returns a
structured evidence pack. It never trades, forecasts, or invents conclusions.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Protocol

from zeus.coordinator import SpecialistUnavailable, TaskRequest


ALLOWED_HOSTS = {
    "fred.stlouisfed.org",
    "www.federalreserve.gov",
    "www.ecb.europa.eu",
    "data.ecb.europa.eu",
    "ec.europa.eu",
    "www.bls.gov",
    "www.bea.gov",
    "www.sec.gov",
    "www.imf.org",
    "www.coingecko.com",
    "api.coingecko.com",
}
MAX_URLS = 5
MAX_DOCUMENT_BYTES = 250_000
MAX_EXCERPT_CHARS = 6_000
DEFAULT_TIMEOUT_SECONDS = 12.0


class FetchResponse(Protocol):
    status: int
    headers: Any
    body: bytes


class SourceFetcher(Protocol):
    def fetch(self, url: str, timeout: float, max_bytes: int) -> tuple[int, str, bytes]: ...


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_source_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibSourceFetcher:
    """Bounded HTTPS GET with allowlisted hosts and redirect validation."""

    def fetch(self, url: str, timeout: float, max_bytes: int) -> tuple[int, str, bytes]:
        _validate_source_url(url)
        opener = urllib.request.build_opener(_SafeRedirect())
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "HERMES-public-research/0.1 (+read-only; contact: none)",
                "Accept": "text/html,application/json,text/csv,text/plain,application/xml",
            },
            method="GET",
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError("source document exceeds the size limit")
                return response.status, content_type, body
        except urllib.error.HTTPError as exc:
            raise SpecialistUnavailable("public source returned HTTP error") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise SpecialistUnavailable("public source could not be reached") from None


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth:
            cleaned = " ".join(data.split())
            if cleaned:
                self.parts.append(cleaned)


def _validate_source_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2000:
        raise ValueError("source URL must be text up to 2000 characters")
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or host not in ALLOWED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not parsed.path.startswith("/")
    ):
        raise ValueError("source URL is not on the HTTPS public-source allowlist")
    return urllib.parse.urlunsplit(("https", host, parsed.path, parsed.query, ""))


def _extract_document(content_type: str, body: bytes) -> tuple[str, str]:
    text = body.decode("utf-8", errors="replace")
    normalized_type = content_type.lower()
    if "html" in normalized_type or re.search(r"<(html|body|article)\b", text, re.I):
        parser = _VisibleText()
        parser.feed(text)
        text = " ".join(parser.parts)
        kind = "html"
    elif "json" in normalized_type:
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, ensure_ascii=False, indent=2)
        except ValueError:
            kind = "text"
        else:
            kind = "json"
    elif "csv" in normalized_type or text.lstrip().startswith(("DATE,", "observation_date,")):
        kind = "csv_or_tabular"
    else:
        kind = "text"
    return " ".join(text.split()), kind


class HermesResearchAdapter:
    """Collect evidence from at most five explicitly supplied public URLs."""

    def __init__(
        self,
        fetcher: SourceFetcher | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        if timeout <= 0 or timeout > 30:
            raise ValueError("timeout must be between 0 and 30 seconds")
        self._fetcher = fetcher or UrllibSourceFetcher()
        self._timeout = timeout
        self._clock = clock

    def __call__(self, request: TaskRequest) -> dict[str, Any]:
        if request.domain not in {"markets", "investment_research"}:
            raise ValueError("HERMES accepts markets and investment_research tasks only")
        spec = request.payload
        research_type = spec.get("research_type", "asset")
        if research_type not in {"asset", "macro", "capital_flows", "opportunity", "risk_review"}:
            raise ValueError("unsupported HERMES research_type")
        subject = spec.get("subject", request.objective)
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 500:
            raise ValueError("subject must be non-empty text up to 500 characters")
        urls = spec.get("source_urls", [])
        if not isinstance(urls, list) or len(urls) > MAX_URLS:
            raise ValueError("source_urls must be a list of at most five URLs")
        if len(set(urls)) != len(urls):
            raise ValueError("source_urls must not contain duplicates")
        safe_urls = [_validate_source_url(url) for url in urls]
        horizon = spec.get("time_horizon", "unspecified")
        if horizon not in {"short", "medium", "long", "unspecified"}:
            raise ValueError("invalid time_horizon")

        documents = []
        failures = []
        for url in safe_urls:
            try:
                status, content_type, body = self._fetcher.fetch(
                    url, self._timeout, MAX_DOCUMENT_BYTES
                )
                if status < 200 or status >= 300:
                    failures.append({"url": url, "reason": "http_error"})
                    continue
                text, kind = _extract_document(content_type, body)
                if not text:
                    failures.append({"url": url, "reason": "empty_document"})
                    continue
                documents.append({
                    "url": url,
                    "retrieved_at": self._clock().astimezone(timezone.utc).isoformat(),
                    "content_type": content_type[:120],
                    "document_type": kind,
                    "excerpt": text[:MAX_EXCERPT_CHARS],
                    "truncated": len(text) > MAX_EXCERPT_CHARS,
                })
            except Exception:
                failures.append({"url": url, "reason": "source_rejected_or_unavailable"})

        status = "completed" if documents else ("blocked" if not urls else "failed")
        return {
            "schema_version": "0.1",
            "agent": "HERMES",
            "status": status,
            "subject": subject.strip(),
            "research_type": research_type,
            "as_of": self._clock().astimezone(timezone.utc).isoformat(),
            "time_horizon": horizon,
            "executive_view": "insufficient_evidence",
            "thesis": "No investment conclusion is generated by HERMES v0.1; this output is a source evidence pack only.",
            "layers": {
                "fundamentals": {
                    "assessment": "Requires analyst interpretation of the retrieved source material.",
                    "evidence": [],
                    "unknowns": ["No autonomous fundamental analysis is performed in v0.1."],
                },
                "capital_flows": {
                    "assessment": "Requires verified flow datasets and analyst interpretation.",
                    "evidence": [],
                    "proxies": [],
                    "unknowns": ["No capital-flow metric is calculated or inferred in v0.1."],
                },
                "price_confirmation": {
                    "assessment": "No price confirmation is calculated in v0.1.",
                    "evidence": [],
                    "invalidation_conditions": [],
                },
            },
            "source_documents": documents,
            "source_failures": failures,
            "catalysts": [],
            "risks": ["Retrieved excerpts may be incomplete; consult the original source."],
            "scenarios": {"upside": "Not assessed", "base": "Not assessed", "downside": "Not assessed"},
            "confidence": {
                "level": "low",
                "reason": "Evidence collection only; no independent validation, calculations, or forecasting.",
            },
            "sources": [
                {
                    "title": "Public source document",
                    "url": item["url"],
                    "publisher": urllib.parse.urlsplit(item["url"]).hostname,
                    "published_at": None,
                    "retrieved_at": item["retrieved_at"],
                    "supports": "Retrieved document excerpt only; no derived investment claim.",
                }
                for item in documents
            ],
            "limitations": [
                "HERMES v0.1 is a read-only evidence collector, not a financial analyst.",
                "Only explicitly supplied HTTPS URLs on the public-source allowlist are fetched.",
                "No live price, capital flow, valuation, probability, or buy/sell recommendation is produced.",
                "No credentials, paid APIs, account access, trading, or portfolio mutation are used.",
            ],
            "requires_human_approval": False,
        }
