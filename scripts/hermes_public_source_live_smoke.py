"""Read-only live smoke check for HERMES public-source retrieval."""
import json

from zeus.coordinator import TaskRequest
from zeus.hermes_research import HermesResearchAdapter


def main():
    result = HermesResearchAdapter(timeout=15.0)(TaskRequest(
        objective="Verify public-source retrieval path",
        domain="markets",
        payload={
            "research_type": "macro",
            "subject": "Public CPI source connectivity check",
            "time_horizon": "unspecified",
            "source_urls": ["https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"],
        },
    ))
    summary = {
        "agent": result["agent"],
        "status": result["status"],
        "source_count": len(result["source_documents"]),
        "source_host": "fred.stlouisfed.org" if result["source_documents"] else None,
        "source_failures": result["source_failures"],
        "executive_view": result["executive_view"],
    }
    print(json.dumps(summary, sort_keys=True))
    if result["status"] != "completed" or len(result["source_documents"]) != 1:
        raise SystemExit("HERMES live public-source smoke check failed")


if __name__ == "__main__":
    main()
