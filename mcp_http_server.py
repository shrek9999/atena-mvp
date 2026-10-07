import os
from mcp.server.fastmcp import FastMCP
import requests

mcp = FastMCP("ATENA", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
ATENA_URL = os.environ.get("ATENA_URL", "https://atena-mvp.onrender.com")

@mcp.tool()
def atena_decide(payload: dict) -> dict:
    """Send fitness/human-performance context to ATENA and return a structured next decision."""
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
    mcp.run(transport="streamable-http")
