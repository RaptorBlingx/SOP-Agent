"""Intervene route — POST /api/v1/intervene (Section 6.3).

Operator sends approval/override/skip/abort/replan actions.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.routes.execute import _enqueue_run
from app.api.schemas import InterventionRequest, InterventionResponse
from app.core import database as db
from app.core.logging import get_logger

logger = get_logger("api.intervene")

router = APIRouter(prefix="/api/v1")

VALID_ACTIONS = {"approve", "override", "skip", "abort", "request_replan"}


async def _get_pending_step(session_id: str) -> dict[str, Any] | None:
    steps = await db.get_steps(session_id)
    for step in reversed(steps):
        if step.get("status") == "needs_approval" and step.get("operator_action") is None:
            return step
    return None


async def _get_pending_reason(session_id: str, step_id: str) -> str:
    events = await db.get_run_events(session_id)
    for event in reversed(events):
        if event.get("event_type") != "awaiting_operator":
            continue
        payload = event.get("payload", {})
        if payload.get("step_id") == step_id:
            return payload.get("reason") or "Operator intervention"
    return "Operator intervention"


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

    pending_step = await _get_pending_step(request.session_id)
    if not pending_step:
        raise HTTPException(status_code=409, detail="No pending approval for this session")

    step_id = pending_step["id"]
    reason = await _get_pending_reason(request.session_id, step_id)

    await db.record_approval(
        session_id=request.session_id,
        step_id=step_id,
        action=request.action,
        reason=reason,
        override_text=request.override_text,
    )

    # Resume the graph by updating the step and session state
    try:
        # Update the step with operator action
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

    if request.action in {"approve", "override", "skip", "request_replan"}:
        _enqueue_run(request.session_id, session.get("task_description", "Pending task description"))

    return InterventionResponse(
        session_id=request.session_id,
        status="resumed",
        message=f"Action '{request.action}' applied",
    )
