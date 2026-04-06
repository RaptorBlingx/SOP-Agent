"""Agent state schema — the full Pydantic state contract (Section 5.1).

This is the authoritative state definition for the LangGraph agent.
All node functions receive and return mutations of AgentState.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


# ---------------------------------------------------------------------------
# Evidence Reference
# ---------------------------------------------------------------------------

class EvidenceRef(BaseModel):
    """A reference to a retrieved chunk used as evidence."""
    chunk_id: str
    source_file: str
    section_path: str | None = None
    page_number: int | None = None
    quote: str
    score: float


# ---------------------------------------------------------------------------
# Execution Step
# ---------------------------------------------------------------------------

class ExecutionStep(BaseModel):
    """A single step in the execution plan."""
    step_id: str
    order: int
    title: str
    objective: str
    branch_condition: str | None = None
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_approval: bool = False
    status: Literal[
        "pending",
        "ready",
        "executing",
        "completed",
        "needs_approval",
        "replanned",
        "skipped",
        "failed",
    ] = "pending"
    recommended_action: str | None = None
    verification_summary: str | None = None
    confidence: float | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    operator_action: str | None = None


# ---------------------------------------------------------------------------
# Approval Request
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    """A request for operator intervention."""
    request_id: str
    step_id: str
    severity: Literal["medium", "high", "critical"]
    reason: str
    allowed_actions: list[str] = Field(
        default_factory=lambda: ["approve", "override", "skip", "abort", "request_replan"]
    )


# ---------------------------------------------------------------------------
# Structured Output Schemas (Section 5.3)
# ---------------------------------------------------------------------------

class PlanSchema(BaseModel):
    """Structured output for the planner node."""
    steps: list[ExecutionStep]


class ExecutionDecision(BaseModel):
    """Structured output for the executor node."""
    recommended_action: str
    prerequisites: list[str] = Field(default_factory=list)
    completion_signal: str = ""
    confidence: float


class VerificationDecision(BaseModel):
    """Structured output for the verifier node."""
    outcome: Literal["continue", "needs_approval", "replan", "fail"]
    rationale: str
    confidence: float
    policy_reason: str | None = None


class ReportOutput(BaseModel):
    """Structured output for the reporter node."""
    summary: str
    markdown_report: str


# ---------------------------------------------------------------------------
# Agent State (Section 5.1)
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """Full graph state — checkpointed after every node execution."""
    session_id: str
    task_description: str
    collection_id: str
    reasoning_profile: Literal["low_cost", "balanced", "high_reasoning", "local"] = "balanced"
    steps: list[ExecutionStep] = Field(default_factory=list)
    current_step_index: int = 0
    active_evidence_pack: list[EvidenceRef] = Field(default_factory=list)
    pending_approval: ApprovalRequest | None = None
    replan_count: int = 0
    messages: Annotated[list, add_messages] = Field(default_factory=list)
    run_events: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal[
        "planning",
        "executing",
        "awaiting_operator",
        "replanning",
        "completed",
        "failed",
    ] = "planning"
    final_report: str | None = None
    last_error: str | None = None
