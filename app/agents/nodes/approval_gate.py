"""Node 6: approval_gate_node — human-on-the-loop interrupt (Section 5.2).

Interrupts the graph when policy or uncertainty justifies intervention.
Supports: approve, override, skip, abort, request_replan.
"""

from __future__ import annotations

from app.agents.state import AgentState
from app.core import database as db
from app.core.logging import get_logger

logger = get_logger("agents.nodes.approval_gate")


async def approval_gate_node(state: AgentState) -> dict:
    """Process the operator's intervention decision.

    This node is reached after the graph is interrupted (interrupt_before)
    and the operator has submitted an action via the API.
    The operator's action is expected to be in state.pending_approval or
    set on the current step's operator_action field.
    """
    if not state.pending_approval:
        logger.warning("Approval gate reached without pending approval")
        return {"status": "executing"}

    step_id = state.pending_approval.step_id
    step_idx = None
    for i, s in enumerate(state.steps):
        if s.step_id == step_id:
            step_idx = i
            break

    if step_idx is None:
        logger.error("Could not find step %s for approval", step_id)
        return {"status": "executing", "pending_approval": None}

    step = state.steps[step_idx]
    action = step.operator_action or "approve"
    updated_steps = list(state.steps)

    logger.info("Approval gate: step=%s, action=%s", step_id, action)

    if action == "approve":
        updated_steps[step_idx] = step.model_copy(update={
            "status": "completed",
            "verification_summary": "Approved by operator",
        })
        await db.update_step(step_id, status="completed", operator_action="approve", completed_at=db._now())
        await db.record_approval(state.session_id, step_id, "approve")
        await db.update_session(state.session_id, awaiting_operator=0, status="executing")

        return {
            "steps": updated_steps,
            "current_step_index": step_idx + 1,
            "pending_approval": None,
            "status": "executing",
            "run_events": state.run_events + [
                {"event_type": "operator_approved", "detail": f"Step {step.order} approved"}
            ],
        }

    elif action == "override":
        override_text = step.recommended_action or "Operator override"
        updated_steps[step_idx] = step.model_copy(update={
            "status": "completed",
            "verification_summary": f"Overridden by operator: {override_text}",
            "operator_action": "override",
        })
        await db.update_step(step_id, status="completed", operator_action="override", completed_at=db._now())
        await db.record_approval(state.session_id, step_id, "override", override_text=override_text)
        await db.update_session(state.session_id, awaiting_operator=0, status="executing")

        return {
            "steps": updated_steps,
            "current_step_index": step_idx + 1,
            "pending_approval": None,
            "status": "executing",
            "run_events": state.run_events + [
                {"event_type": "operator_override", "detail": f"Step {step.order} overridden"}
            ],
        }

    elif action == "skip":
        updated_steps[step_idx] = step.model_copy(update={
            "status": "skipped",
            "operator_action": "skip",
        })
        await db.update_step(step_id, status="skipped", operator_action="skip")
        await db.record_approval(state.session_id, step_id, "skip")
        await db.update_session(state.session_id, awaiting_operator=0, status="executing")

        return {
            "steps": updated_steps,
            "current_step_index": step_idx + 1,
            "pending_approval": None,
            "status": "executing",
            "run_events": state.run_events + [
                {"event_type": "operator_skip", "detail": f"Step {step.order} skipped"}
            ],
        }

    elif action == "abort":
        await db.update_session(state.session_id, status="failed", awaiting_operator=0)
        await db.record_approval(state.session_id, step_id, "abort")

        return {
            "pending_approval": None,
            "status": "failed",
            "last_error": "Aborted by operator",
            "run_events": state.run_events + [
                {"event_type": "operator_abort", "detail": "Run aborted by operator"}
            ],
        }

    elif action == "request_replan":
        updated_steps[step_idx] = step.model_copy(update={
            "status": "replanned",
            "operator_action": "request_replan",
        })
        await db.update_step(step_id, status="replanned", operator_action="request_replan")
        await db.record_approval(state.session_id, step_id, "request_replan")
        await db.update_session(state.session_id, awaiting_operator=0, status="replanning")

        return {
            "steps": updated_steps,
            "pending_approval": None,
            "status": "replanning",
            "run_events": state.run_events + [
                {"event_type": "operator_replan", "detail": f"Replan requested at step {step.order}"}
            ],
        }

    else:
        logger.warning("Unknown operator action: %s", action)
        return {"pending_approval": None, "status": "executing"}
