"""Intervene route — POST /api/v1/intervene (Section 6.3).

Operator sends approval/override/skip/abort/replan actions.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import InterventionRequest, InterventionResponse
from app.core import database as db
from app.core.logging import get_logger

logger = get_logger("api.intervene")

router = APIRouter(prefix="/api/v1")

VALID_ACTIONS = {"approve", "override", "skip", "abort", "request_replan"}


@router.post("/intervene", response_model=InterventionResponse)
async def intervene(request: InterventionRequest) -> InterventionResponse:
    """Submit an operator intervention for a pending approval."""
    if request.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Must be one of: {', '.join(sorted(VALID_ACTIONS))}",
        )

    if request.action == "override" and not request.override_text:
        raise HTTPException(status_code=400, detail="override_text required for override action")

    session = await db.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Record the approval action
    # Get pending approvals for this session
    approvals = await db.get_approvals(request.session_id)
    pending = [a for a in approvals if a.get("operator_action") is None]

    if not pending:
        raise HTTPException(status_code=409, detail="No pending approval for this session")

    latest = pending[-1]

    await db.record_approval(
        session_id=request.session_id,
        step_id=latest.get("step_id", "unknown"),
        action=request.action,
        reason=latest.get("reason", "Operator intervention"),
        override_text=request.override_text,
    )

    # Resume the graph by updating the step and session state
    try:
        # Update the step with operator action
        step_id = latest.get("step_id", "unknown")
        await db.update_step(step_id, operator_action=request.action)

        if request.action == "abort":
            await db.update_session(request.session_id, status="failed", awaiting_operator=0)
        elif request.action == "request_replan":
            await db.update_session(request.session_id, status="replanning", awaiting_operator=0)
        elif request.action in ("approve", "override", "skip"):
            new_status = "completed" if request.action in ("approve", "override") else "skipped"
            await db.update_step(step_id, status=new_status, completed_at=db._now())
            await db.update_session(request.session_id, status="executing", awaiting_operator=0)
    except Exception as exc:
        logger.exception("Failed to apply intervention for session %s", request.session_id)
        raise HTTPException(status_code=500, detail=f"Intervention failed: {exc}")

    return InterventionResponse(
        session_id=request.session_id,
        status="resumed",
        message=f"Action '{request.action}' applied",
    )
