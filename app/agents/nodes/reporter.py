"""Node 8: reporter_node — final Markdown report generation (Section 5.2).

Produces the final report with completed steps, operator interventions,
replans, and unresolved exceptions. Temperature 0.3.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.core.llm_factory import get_llm, call_llm_with_retry
from app.core import database as db
from app.core.logging import get_logger

logger = get_logger("agents.nodes.reporter")

REPORTER_SYSTEM_PROMPT = """You are a professional report writer. Generate a clear, well-structured
Markdown report summarizing an SOP execution run.

Include:
- Executive summary
- Task description
- Step-by-step execution details with outcomes
- Operator interventions and their reasons
- Any replanning events
- Unresolved issues or exceptions
- Conclusion and recommendations

Write in a professional, concise style suitable for operational records.
"""


async def reporter_node(state: AgentState) -> dict:
    """Generate the final execution report."""
    logger.info("Generating report for session %s", state.session_id)

    # Collect step summaries
    step_lines: list[str] = []
    completed = 0
    skipped = 0
    failed = 0
    interventions = 0

    for step in state.steps:
        status_icon = {
            "completed": "✅",
            "skipped": "⏭️",
            "failed": "❌",
            "needs_approval": "🟡",
            "pending": "⬜",
        }.get(step.status, "❓")

        step_lines.append(
            f"- {status_icon} Step {step.order}: **{step.title}** [{step.status}]\n"
            f"  - Objective: {step.objective}\n"
            f"  - Action: {step.recommended_action or 'N/A'}\n"
            f"  - Verification: {step.verification_summary or 'N/A'}\n"
            f"  - Confidence: {step.confidence or 0.0:.2f}"
        )
        if step.operator_action:
            step_lines.append(f"  - Operator Action: {step.operator_action}")
            interventions += 1

        if step.status == "completed":
            completed += 1
        elif step.status == "skipped":
            skipped += 1
        elif step.status == "failed":
            failed += 1

    steps_detail = "\n".join(step_lines)

    # Try LLM-enhanced report
    messages = [
        SystemMessage(content=REPORTER_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"## Task\n{state.task_description}\n\n"
            f"## Execution Summary\n"
            f"- Total steps: {len(state.steps)}\n"
            f"- Completed: {completed}\n"
            f"- Skipped: {skipped}\n"
            f"- Failed: {failed}\n"
            f"- Human interventions: {interventions}\n"
            f"- Replans: {state.replan_count}\n"
            f"- Final status: {state.status}\n\n"
            f"## Step Details\n{steps_detail}\n\n"
            f"Generate a professional Markdown report."
        )),
    ]

    llm = get_llm(temperature=0.3)

    try:
        response = await asyncio.wait_for(
            call_llm_with_retry(llm, messages),
            timeout=35,
        )
        report_content = response.content if hasattr(response, 'content') else str(response)
    except Exception as exc:
        logger.warning("LLM report generation failed: %s — using template", exc)
        report_content = _template_report(state, completed, skipped, failed, interventions, steps_detail)

    # Update state and persist
    await db.update_session(
        state.session_id,
        status="completed",
        final_report=report_content,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    await db.add_run_event(state.session_id, "run_completed", {"status": "completed"})

    logger.info("Report generated for session %s", state.session_id)

    return {
        "final_report": report_content,
        "status": "completed",
        "run_events": state.run_events + [
            {"event_type": "run_completed", "detail": "Report generated"}
        ],
    }


def _template_report(
    state: AgentState,
    completed: int,
    skipped: int,
    failed: int,
    interventions: int,
    steps_detail: str,
) -> str:
    """Fallback template-based report when LLM is unavailable."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""# SOP Execution Report

**Generated:** {now}
**Session:** {state.session_id}
**Status:** {state.status}

---

## Executive Summary

Task: {state.task_description}

| Metric | Value |
|---|---|
| Total Steps | {len(state.steps)} |
| Completed | {completed} |
| Skipped | {skipped} |
| Failed | {failed} |
| Human Interventions | {interventions} |
| Replans | {state.replan_count} |

---

## Step-by-Step Execution

{steps_detail}

---

## Conclusion

Execution {"completed successfully" if failed == 0 else "completed with issues"}.
{f"{interventions} operator intervention(s) were recorded." if interventions else ""}
{f"{state.replan_count} replan(s) were performed." if state.replan_count else ""}
"""
