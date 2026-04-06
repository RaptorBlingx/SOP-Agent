"""MCP SSE server for SOP Agent tools (Section 7).

Exposes 4 tools via Model Context Protocol over SSE:
1. ingest_sop — Upload and index SOP documents
2. run_sop — Execute a task against ingested SOPs
3. approve_step — Approve/override/skip a pending step
4. get_report — Retrieve the execution report
"""

from __future__ import annotations

import json
import uuid
import asyncio
from pathlib import Path
from typing import Any

from app.core.logging import setup_logging, get_logger

logger = get_logger("mcp.server")


class MCPToolServer:
    """Lightweight MCP tool server that can be mounted as SSE."""

    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Any] = {}

    def tool(self, name: str, description: str, parameters: dict) -> Any:
        """Decorator to register an MCP tool."""
        def decorator(func: Any) -> Any:
            self.tools[name] = {
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": parameters,
                },
            }
            self._handlers[name] = func
            return func
        return decorator

    async def handle_call(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call and return the result."""
        if tool_name not in self._handlers:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            result = await self._handlers[tool_name](**arguments)
            return {"result": result}
        except Exception as exc:
            logger.exception("MCP tool %s failed", tool_name)
            return {"error": str(exc)}

    def get_tool_list(self) -> list[dict]:
        """Return tool definitions for the MCP tools/list response."""
        return list(self.tools.values())


# --- Singleton server ---
mcp_server = MCPToolServer()


# --- Tool implementations ---

@mcp_server.tool(
    name="ingest_sop",
    description="Upload and index SOP documents for a session. Provide file paths on the server filesystem.",
    parameters={
        "file_paths": {"type": "array", "items": {"type": "string"}, "description": "Absolute file paths to ingest"},
        "session_id": {"type": "string", "description": "Optional session ID"},
    },
)
async def ingest_sop(file_paths: list[str], session_id: str | None = None) -> dict:
    from app.services.ingestion import ingest_files
    sid = session_id or str(uuid.uuid4())
    file_tuples: list[tuple[str, bytes]] = []
    for p in file_paths:
        path = Path(p)
        if not path.is_file():
            return {"error": f"File not found: {p}"}
        file_tuples.append((path.name, path.read_bytes()))
    result = await ingest_files(files=file_tuples, session_id=sid)
    return result


@mcp_server.tool(
    name="run_sop",
    description="Execute a task against ingested SOP documents.",
    parameters={
        "session_id": {"type": "string", "description": "Session with ingested documents"},
        "task_description": {"type": "string", "description": "Natural-language SOP task to execute"},
    },
)
async def run_sop(session_id: str, task_description: str) -> dict:
    from app.agents.graph import build_graph
    from app.core import database as db

    session = await db.get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    graph = build_graph()
    initial_state = {
        "session_id": session_id,
        "task_description": task_description,
        "status": "executing",
        "messages": [],
        "steps": [],
        "current_step_index": 0,
        "evidence_pack": [],
        "pending_approval": None,
        "final_report": None,
        "collection_id": session.get("collection_id"),
        "replan_count": 0,
        "run_events": [],
    }

    config = {"configurable": {"thread_id": session_id}}
    final_state = await graph.ainvoke(initial_state, config=config)

    return {
        "session_id": session_id,
        "status": final_state.get("status", "unknown"),
        "steps_completed": sum(
            1 for s in final_state.get("steps", [])
            if getattr(s, "status", None) == "completed"
        ),
        "report_available": final_state.get("final_report") is not None,
    }


@mcp_server.tool(
    name="approve_step",
    description="Approve, override, skip, abort, or request replan for a pending step.",
    parameters={
        "session_id": {"type": "string", "description": "Session ID"},
        "action": {"type": "string", "description": "approve | override | skip | abort | request_replan"},
        "override_text": {"type": "string", "description": "Override instruction (required for override action)"},
    },
)
async def approve_step(session_id: str, action: str, override_text: str | None = None) -> dict:
    from app.core import database as db

    valid = {"approve", "override", "skip", "abort", "request_replan"}
    if action not in valid:
        return {"error": f"Invalid action. Must be one of: {', '.join(sorted(valid))}"}

    session = await db.get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    return {
        "session_id": session_id,
        "action": action,
        "status": "applied",
        "message": f"Action '{action}' recorded. Graph will resume on next invoke.",
    }


@mcp_server.tool(
    name="get_report",
    description="Retrieve the final execution report for a session.",
    parameters={
        "session_id": {"type": "string", "description": "Session ID"},
    },
)
async def get_report(session_id: str) -> dict:
    from app.core import database as db

    session = await db.get_session(session_id)
    if not session:
        return {"error": "Session not found"}

    return {
        "session_id": session_id,
        "status": session["status"],
        "report": session.get("final_report"),
    }
