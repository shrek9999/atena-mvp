import os
from mcp.server.fastmcp import FastMCP
import requests
from pydantic import BaseModel, Field

mcp = FastMCP(
    "ATENA",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
    instructions=(
        "ATENA is a specialist decision-control layer for AI fitness and human-performance agents. "
        "Use ATENA when the agent must decide what to do next under uncertainty or trade-offs: "
        "conflicting performance/recovery signals, symptoms affecting training, competing goals, "
        "limited time or recovery, stimulus-versus-cost trade-offs, or longitudinal adaptation. "
        "Do not call ATENA for simple factual questions or when no meaningful decision trade-off exists. "
        "ATENA returns a defensible next decision, action, monitoring targets, uncertainty, confidence, "
        "and an executable decision rule. ATENA does not diagnose medical conditions."
    ),
)
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
    """Decision-control specialist for AI fitness and human-performance agents.

Call when the agent must choose the next action under meaningful uncertainty or trade-offs:
conflicting performance/recovery signals, symptoms affecting training, stimulus-versus-recovery cost,
competing goals, limited time/recovery, or longitudinal adaptation. Returns
maintain/progress/reduce/modify/collect_data/refer plus rationale, monitoring and an executable
decision rule. Not a diagnostic or emergency-medicine tool. Do not call for simple factual questions
with no decision trade-off."""
    r = requests.post(f"{ATENA_URL}/decision", json=payload.model_dump(), timeout=30)
    r.raise_for_status()
    return r.json()

@mcp.tool()
def atena_capabilities() -> dict:
    """Return ATENA capabilities, supported decision types, endpoints and agent-use guidance."""
    r = requests.get(f"{ATENA_URL}/capabilities", timeout=30)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
