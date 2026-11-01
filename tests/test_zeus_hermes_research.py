import json
from datetime import datetime, timezone

import pytest

from zeus.coordinator import TaskRequest
from zeus.hermes_research import HermesResearchAdapter, _validate_source_url


class FakeFetcher:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def fetch(self, url, timeout, max_bytes):
        self.calls.append((url, timeout, max_bytes))
        if url not in self.responses:
            raise RuntimeError("unexpected URL")
        return self.responses[url]


def make_request(payload=None, domain="markets"):
    return TaskRequest(
        objective="Review public macro evidence",
        domain=domain,
        payload=payload or {
            "research_type": "macro",
            "subject": "US inflation",
            "source_urls": ["https://www.bls.gov/news.release/cpi.nr0.htm"],
        },
    )


def test_hermes_collects_allowlisted_public_source_and_returns_structured_evidence():
    url = "https://www.bls.gov/news.release/cpi.nr0.htm"
    fetcher = FakeFetcher({
        url: (200, "text/html; charset=utf-8",
              b"<html><head><script>secret()</script></head><body><h1>CPI release</h1><p>Prices rose 2 percent.</p></body></html>")
    })
    adapter = HermesResearchAdapter(
        fetcher=fetcher,
        clock=lambda: datetime(2026, 11, 1, tzinfo=timezone.utc),
    )
    result = adapter(make_request())

    assert result["agent"] == "HERMES"
    assert result["status"] == "completed"
    assert result["executive_view"] == "insufficient_evidence"
    assert result["source_documents"][0]["document_type"] == "html"
    assert "CPI release" in result["source_documents"][0]["excerpt"]
    assert "secret" not in result["source_documents"][0]["excerpt"]
    assert result["sources"][0]["url"] == url
    assert result["requires_human_approval"] is False
    assert fetcher.calls[0][2] == 250_000


def test_hermes_rejects_non_allowlisted_urls_before_fetch():
    fetcher = FakeFetcher()
    adapter = HermesResearchAdapter(fetcher=fetcher)
    with pytest.raises(ValueError, match="allowlist"):
        adapter(make_request({"source_urls": ["https://example.com/anything"]}))
    assert fetcher.calls == []


@pytest.mark.parametrize("url", [
    "http://www.bls.gov/data",
    "https://user:pass@www.bls.gov/data",
    "https://www.bls.gov:8443/data",
    "https://www.bls.gov.evil.example/data",
    "https://127.0.0.1/private",
])
def test_url_validation_rejects_unsafe_url_shapes(url):
    with pytest.raises(ValueError):
        _validate_source_url(url)


def test_hermes_limits_source_count_and_rejects_duplicates():
    adapter = HermesResearchAdapter(fetcher=FakeFetcher())
    with pytest.raises(ValueError, match="at most five"):
        adapter(make_request({"source_urls": ["https://www.bls.gov/a"] * 6}))
    with pytest.raises(ValueError, match="duplicates"):
        adapter(make_request({"source_urls": ["https://www.bls.gov/a"] * 2}))


def test_hermes_marks_missing_sources_as_blocked_not_as_research():
    result = HermesResearchAdapter(fetcher=FakeFetcher())(
        make_request({"research_type": "macro", "subject": "Liquidity"})
    )
    assert result["status"] == "blocked"
    assert result["source_documents"] == []
    assert result["executive_view"] == "insufficient_evidence"


def test_hermes_sanitizes_source_fetch_failures():
    class FailingFetcher:
        def fetch(self, url, timeout, max_bytes):
            raise OSError("secret token in exception")

    result = HermesResearchAdapter(fetcher=FailingFetcher())(make_request())
    assert result["status"] == "failed"
    assert result["source_failures"][0]["reason"] == "source_rejected_or_unavailable"
    assert "secret" not in json.dumps(result)


def test_hermes_rejects_wrong_domain_and_invalid_research_type():
    adapter = HermesResearchAdapter(fetcher=FakeFetcher())
    with pytest.raises(ValueError):
        adapter(make_request(domain="fitness"))
    with pytest.raises(ValueError):
        adapter(make_request({"research_type": "trade_now"}))


def test_hermes_caps_document_excerpt():
    url = "https://www.bls.gov/news.release/cpi.nr0.htm"
    adapter = HermesResearchAdapter(fetcher=FakeFetcher({
        url: (200, "text/plain", ("A" * 8000).encode())
    }))
    result = adapter(make_request())
    assert len(result["source_documents"][0]["excerpt"]) == 6000
    assert result["source_documents"][0]["truncated"] is True
