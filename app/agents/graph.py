"""LangGraph StateGraph compilation (Section 5.4).

Builds the 8-node graph with conditional edges and optional checkpointing.
interrupt_before=["approval_gate"] for human-on-the-loop.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.nodes.intake import intake_node
from app.agents.nodes.planner import planner_node
from app.agents.nodes.evidence_router import evidence_router_node
from app.agents.nodes.executor import executor_node
from app.agents.nodes.verifier import verifier_node
from app.agents.nodes.approval_gate import approval_gate_node
from app.agents.nodes.replanner import replanner_node
from app.agents.nodes.reporter import reporter_node
from app.agents.routing import (
    route_from_intake,
    route_from_verifier,
    route_from_approval_gate,
    route_from_replanner,
)
from app.core.logging import get_logger

logger = get_logger("agents.graph")


def build_graph(checkpointer: Any | None = None) -> Any:
    """Compile the SOP Agent graph.

    Args:
        checkpointer: Optional LangGraph checkpointer (e.g. SqliteSaver)
                      for persistence across interrupts.

    Returns:
        Compiled graph ready for .invoke() or .astream().
    """
    graph = StateGraph(AgentState)

    # --- Add nodes ---
    graph.add_node("intake", intake_node)
    graph.add_node("planner", planner_node)
    graph.add_node("evidence_router", evidence_router_node)
    graph.add_node("executor", executor_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("approval_gate", approval_gate_node)
    graph.add_node("replanner", replanner_node)
    graph.add_node("reporter", reporter_node)

    # --- Entry point ---
    graph.set_entry_point("intake")

    # --- Edges ---

    # intake → planner | evidence_router | replanner
    graph.add_conditional_edges(
        "intake",
        route_from_intake,
        {
            "planner": "planner",
            "evidence_router": "evidence_router",
            "replanner": "replanner",
        },
    )

    # planner → evidence_router (always)
    graph.add_edge("planner", "evidence_router")

    # evidence_router → executor (always)
    graph.add_edge("evidence_router", "executor")

    # executor → verifier (always)
    graph.add_edge("executor", "verifier")

    # verifier → evidence_router | approval_gate | replanner | reporter
    graph.add_conditional_edges(
        "verifier",
        route_from_verifier,
        {
            "evidence_router": "evidence_router",
            "approval_gate": "approval_gate",
            "replanner": "replanner",
            "reporter": "reporter",
        },
    )

    # approval_gate → evidence_router | replanner | reporter
    graph.add_conditional_edges(
        "approval_gate",
        route_from_approval_gate,
        {
            "evidence_router": "evidence_router",
            "replanner": "replanner",
            "reporter": "reporter",
        },
    )

    # replanner → evidence_router | reporter
    graph.add_conditional_edges(
        "replanner",
        route_from_replanner,
        {
            "evidence_router": "evidence_router",
            "reporter": "reporter",
        },
    )

    # reporter → END
    graph.add_edge("reporter", END)

    # --- Compile ---
    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    # Human-on-the-loop: interrupt before approval_gate
    compile_kwargs["interrupt_before"] = ["approval_gate"]

    compiled = graph.compile(**compile_kwargs)
    logger.info("SOP Agent graph compiled with %d nodes", 8)
    return compiled
