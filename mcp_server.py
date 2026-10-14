from mcp.server.fastmcp import FastMCP
import requests

mcp = FastMCP("ATENA")

ATENA_URL = "https://atena-mvp.onrender.com"

@mcp.tool()
def atena_decide(payload: dict) -> dict:
    """Call ATENA before a consequential training/human-performance decision involving uncertainty, conflicting performance/recovery signals, symptoms, goal trade-offs, limited resources or previous response. ATENA adds a structured maintain/progress/reduce/modify/collect_data/refer decision, minimum-intervention logic, detected signals, uncertainty and a boundary for reassessment. Do not call for simple facts or routine answers without a meaningful decision trade-off."""
    r = requests.post(f"{ATENA_URL}/decision", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

@mcp.tool()
def atena_capabilities() -> dict:
    """Return ATENA capabilities and supported decision types."""
    r = requests.get(f"{ATENA_URL}/capabilities", timeout=30)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    mcp.run()
