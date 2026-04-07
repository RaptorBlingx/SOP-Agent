"""Routing functions for LangGraph conditional edges (Section 5.4-5.5).

Three routing functions control flow between nodes:
- route_from_intake: plan vs resume
- route_from_verifier: continue / approval / replan / complete / fail
- route_from_approval_gate: continue / replan / abort
"""

from __future__ import annotations

from app.agents.state import AgentState
from app.core.logging import get_logger

logger = get_logger("agents.routing")


def route_from_intake(state: AgentState) -> str:
    """After intake, decide whether to plan or resume evidence gathering."""
    if state.status == "replanning":
        logger.info("Intake routing → replanner (resume with replan)")
        return "replanner"

    if state.steps:
        # Resuming a session — go straight to evidence for the current step
        logger.info("Intake routing → evidence_router (resuming step %d)", state.current_step_index)
        return "evidence_router"

    logger.info("Intake routing → planner (new session)")
    return "planner"


def route_from_verifier(state: AgentState) -> str:
    """After verification, decide the next transition.

    Possible outcomes:
    - "evidence_router" — continue to next step
    - "approval_gate" — human review needed
    - "replanner" — plan needs revision
    - "reporter" — all steps completed
    - "reporter" — fatal failure, generate report
    """
    # Check for failure
    if state.status == "failed":
        logger.info("Verifier routing → reporter (failed)")
        return "reporter"

    # Check for replanning needed
    if state.status == "replanning":
        logger.info("Verifier routing → replanner")
        return "replanner"

    # Check for approval needed
    if state.pending_approval is not None:
        logger.info("Verifier routing → approval_gate")
        return "approval_gate"

    # Check if all steps completed
    if state.current_step_index >= len(state.steps):
        logger.info("Verifier routing → reporter (all steps done)")
        return "reporter"

    # Continue to next step
    logger.info("Verifier routing → evidence_router (step %d)", state.current_step_index)
    return "evidence_router"


def route_from_approval_gate(state: AgentState) -> str:
    """After operator action in approval gate."""
    # Abort → report
    if state.status == "failed":
        logger.info("Approval routing → reporter (aborted)")
        return "reporter"

    # Replan requested
    if state.status == "replanning":
        logger.info("Approval routing → replanner")
        return "replanner"

    # All steps completed after approval
    if state.current_step_index >= len(state.steps):
        logger.info("Approval routing → reporter (all done)")
        return "reporter"

    # Continue to next step
    logger.info("Approval routing → evidence_router (step %d)", state.current_step_index)
    return "evidence_router"


def route_from_replanner(state: AgentState) -> str:
    """After replanning, go to evidence_router for the current step."""
    if state.status == "failed":
        logger.info("Replanner routing → reporter (replan failed)")
        return "reporter"

    logger.info("Replanner routing → evidence_router (step %d)", state.current_step_index)
    return "evidence_router"
