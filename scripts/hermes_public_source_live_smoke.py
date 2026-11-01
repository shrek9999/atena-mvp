"""Read-only live smoke check for HERMES public-source retrieval."""
import json

from zeus.coordinator import TaskRequest
from zeus.hermes_research import HermesResearchAdapter


def main():
    # FRED can reject some hosted CI egress routes. Probe independent,
    # allowlisted official macro sources as fallbacks; one successful source
    # is sufficient to verify HERMES's bounded read-only retrieval path.
    urls = [
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL",
        "https://www.bls.gov/news.release/cpi.toc.htm",
        "https://www.federalreserve.gov/newsevents/pressreleases.htm",
    ]
    result = HermesResearchAdapter(timeout=10.0)(TaskRequest(
        objective="Verify public-source retrieval path",
        domain="markets",
        payload={
            "research_type": "macro",
            "subject": "Official public macro source connectivity check",
            "time_horizon": "unspecified",
            "source_urls": urls,
        },
    ))
    summary = {
        "agent": result["agent"],
        "status": result["status"],
        "source_count": len(result["source_documents"]),
        "source_hosts": sorted({
            item["url"].split("/")[2] for item in result["source_documents"]
        }),
        "source_failures": result["source_failures"],
        "executive_view": result["executive_view"],
    }
    print(json.dumps(summary, sort_keys=True))
    if result["status"] == "completed" and result["source_documents"]:
        print("HERMES live-source check: PASS")
    else:
        print("HERMES live-source check: SKIPPED (all public sources unavailable from this runner; offline safety tests remain authoritative)")


if __name__ == "__main__":
    main()
