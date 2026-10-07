import os
from mcp.server.fastmcp import FastMCP
import requests
from pydantic import BaseModel, Field

mcp = FastMCP("ATENA", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
ATENA_URL = os.environ.get("ATENA_URL", "https://atena-mvp.onrender.com")

class AtenaDecisionInput(BaseModel):
    goal: dict = Field(description="Primary and secondary goals, priorities, and maintenance goals. Goal priority is essential for trade-offs.")
    person: dict = Field(default_factory=dict, description="Relevant person context only; do not include unnecessary sensitive data.")
    constraints: dict = Field(default_factory=dict, description="Time, recovery, energy, stress, equipment, schedule, or other constraints affecting the decision.")
    state: dict = Field(default_factory=dict, description="Current performance, RPE, recovery, sleep, symptoms, fatigue, wellness, and other observed state.")
    response: dict = Field(default_factory=dict, description="Observed response to recent training or a previous modification.")
    question: str = Field(default="", description="The concrete decision the calling agent needs to make next.")
    history: dict = Field(default_factory=dict, description="Relevant longitudinal history and previous decisions/responses.")


@mcp.tool()
def atena_decide(payload: AtenaDecisionInput) -> dict:
    """Use ATENA when an AI agent needs a defensible next training/human-performance decision rather than a generic answer. Call it for conflicting signals, uncertainty, symptoms affecting training, recovery/stimulus-cost trade-offs, competing goals or limited time, or longitudinal adaptation. ATENA returns maintain/progress/reduce/modify/collect_data/refer plus rationale, monitoring and a decision rule. It is not a diagnostic or emergency-medicine tool; for simple factual questions with no decision trade-off, do not call it."""
    r = requests.post(f"{ATENA_URL}/decision", json=payload.model_dump(), timeout=30)
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
