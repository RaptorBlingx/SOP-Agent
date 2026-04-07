"""Node 1: intake_node — session validation and resume logic (Section 5.2).

Pure control logic. No LLM call. Validates session, collection, provider
config, and resume state. Decides plan-from-scratch vs checkpoint resume.
"""

from __future__ import annotations

from app.agents.state import AgentState
from app.core import database as db
from app.core.logging import get_logger

logger = get_logger("agents.nodes.intake")


async def intake_node(state: AgentState) -> dict:
    """Validate session state and decide routing: plan or resume."""
    logger.info("Intake: session=%s, status=%s", state.session_id, state.status)

    # Check if session exists in DB
    session = await db.get_session(state.session_id)

    if session and session.get("status") not in ("planning", None):
        # Resume from checkpoint
        existing_steps = await db.get_steps(state.session_id)

        if existing_steps:
            # Find the first non-completed step to resume from
            resume_index = 0
            for i, step_row in enumerate(existing_steps):
                if step_row["status"] in ("completed", "skipped"):
                    resume_index = i + 1
                else:
                    resume_index = i
                    break

            logger.info("Resuming session %s from step %d", state.session_id, resume_index)

            await db.add_run_event(
                state.session_id, "resumed",
                {"resume_from_step": resume_index}
            )

            return {
                "current_step_index": resume_index,
                "status": "executing",
                "run_events": state.run_events + [
                    {"event_type": "resumed", "detail": f"Resumed from step {resume_index}"}
                ],
            }

    # New session — need to plan
    if not session:
        from app.core.config import get_settings
        settings = get_settings()
        await db.create_session(
            session_id=state.session_id,
            task_description=state.task_description,
            collection_id=state.collection_id,
            reasoning_profile=state.reasoning_profile,
            model_provider=settings.model_provider,
            model_name=settings.active_model_name,
        )

    await db.add_run_event(state.session_id, "intake_complete", {"action": "plan"})

    return {
        "status": "planning",
        "run_events": state.run_events + [
            {"event_type": "intake_complete", "detail": "Ready to plan"}
        ],
    }
