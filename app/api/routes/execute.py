"""Execute route — POST /api/v1/execute + GET /api/v1/execute/{session_id}/stream (Section 6.2).

Starts or resumes SOP execution. SSE endpoint streams execution events.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import ExecuteRequest, ExecuteResponse
from app.agents.graph import build_graph
from app.agents.state import AgentState, ExecutionStep
from app.core import database as db
from app.core.logging import get_logger

logger = get_logger("api.execute")

router = APIRouter(prefix="/api/v1")

# In-memory event queues per session for SSE streaming
_event_queues: dict[str, asyncio.Queue] = {}


def _get_queue(session_id: str) -> asyncio.Queue:
    if session_id not in _event_queues:
        _event_queues[session_id] = asyncio.Queue()
    return _event_queues[session_id]


@router.post("/execute", response_model=ExecuteResponse)
async def start_execution(request: ExecuteRequest) -> ExecuteResponse:
    """Start or resume SOP execution for a session."""
    session = await db.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] in ("executing", "completed"):
        return ExecuteResponse(
            session_id=request.session_id,
            status=session["status"],
            message=f"Session already {session['status']}",
        )

    queue = _get_queue(request.session_id)

    # Run graph in background task
    asyncio.create_task(
        _run_graph(request.session_id, request.task_description, queue)
    )

    return ExecuteResponse(
        session_id=request.session_id,
        status="executing",
        message="Execution started",
    )


async def _run_graph(session_id: str, task_description: str, queue: asyncio.Queue) -> None:
    """Execute the agent graph and push events to the SSE queue."""
    try:
        graph = build_graph()

        # Load session to get collection_id and current state
        session = await db.get_session(session_id)
        collection_id = session.get("collection_id", f"sop_{session_id}") if session else f"sop_{session_id}"
        existing_steps = await db.get_steps(session_id) if session else []

        resume_index = 0
        for i, s in enumerate(existing_steps):
            if s["status"] not in ("completed", "skipped"):
                resume_index = i
                break
        else:
            resume_index = len(existing_steps)

        # Build initial state
        initial_state: dict = {
            "session_id": session_id,
            "task_description": task_description,
            "status": "executing",
            "messages": [],
            "steps": [],
            "current_step_index": resume_index,
            "active_evidence_pack": [],
            "pending_approval": None,
            "final_report": None,
            "collection_id": collection_id,
            "replan_count": session.get("replan_count", 0) if session else 0,
            "run_events": [],
        }

        config = {"configurable": {"thread_id": session_id}}

        async for event in graph.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                evt = {
                    "node": node_name,
                    "status": node_output.get("status", ""),
                    "current_step_index": node_output.get("current_step_index"),
                }
                await queue.put({"event": "node_update", "data": json.dumps(evt)})

                # Check if waiting for approval
                if node_output.get("pending_approval") is not None:
                    await queue.put({
                        "event": "approval_needed",
                        "data": json.dumps(node_output["pending_approval"]),
                    })

        # Signal completion
        await queue.put({"event": "done", "data": "{}"})

    except Exception as exc:
        logger.exception("Graph execution failed for session %s", session_id)
        await queue.put({
            "event": "error",
            "data": json.dumps({"detail": str(exc)}),
        })
    finally:
        # Clean up after a delay so SSE client can read final events
        await asyncio.sleep(5)
        _event_queues.pop(session_id, None)


@router.get("/execute/{session_id}/stream")
async def stream_execution(session_id: str) -> EventSourceResponse:
    """SSE endpoint streaming execution events."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    queue = _get_queue(session_id)

    async def event_generator() -> AsyncGenerator[dict, None]:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
                yield event
                if event.get("event") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "keepalive", "data": "{}"}

    return EventSourceResponse(event_generator())
